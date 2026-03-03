#!/usr/bin/env python3
"""
Deploy artifacts to Google Drive.
Updates existing files by ID using a Google Service Account.

Required environment variables:
  GOOGLE_SERVICE_ACCOUNT_KEY  - JSON key content of the service account
  DRIVE_FILE_IDS              - JSON with file IDs mapping (exe, dmg, version_json)
  APP_VERSION                 - Application version (e.g. 1.0.0)
  BUILD_NUMBER                - Build number
  PRODUCT_NAME                - Product name

Required files (passed as arguments):
  --exe PATH       - Path to Windows portable .exe
  --dmg PATH       - Path to macOS .dmg
  --version PATH   - Path to write/upload version.json
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

try:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
except ImportError:
    print("Installing required packages...")
    import subprocess
    subprocess.check_call([
        sys.executable, '-m', 'pip', 'install', '--quiet',
        'google-auth', 'google-api-python-client'
    ])
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload


SCOPES = ['https://www.googleapis.com/auth/drive.file']

# Maximum retries for API calls
MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds


def get_drive_service():
    """Create authenticated Google Drive service."""
    key_json = os.environ.get('GOOGLE_SERVICE_ACCOUNT_KEY')
    if not key_json:
        print("ERROR: GOOGLE_SERVICE_ACCOUNT_KEY environment variable not set")
        sys.exit(1)

    try:
        key_info = json.loads(key_json)
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JSON in GOOGLE_SERVICE_ACCOUNT_KEY: {e}")
        sys.exit(1)

    credentials = service_account.Credentials.from_service_account_info(
        key_info, scopes=SCOPES
    )
    service = build('drive', 'v3', credentials=credentials)
    return service


def update_file(service, file_id: str, local_path: str, mime_type: str, description: str):
    """Update an existing file on Google Drive by its ID."""
    if not os.path.exists(local_path):
        print(f"  ⚠ Skipping {description}: file not found at {local_path}")
        return False

    file_size = os.path.getsize(local_path)
    size_mb = file_size / (1024 * 1024)
    print(f"  → Uploading {description} ({size_mb:.1f} MB)...")

    media = MediaFileUpload(
        local_path,
        mimetype=mime_type,
        resumable=True if file_size > 5 * 1024 * 1024 else False  # Resumable for files > 5MB
    )

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            result = service.files().update(
                fileId=file_id,
                media_body=media,
                fields='id,name,size,modifiedTime'
            ).execute()

            print(f"  ✓ {description} uploaded successfully")
            print(f"    ID: {result.get('id')}")
            print(f"    Size: {int(result.get('size', 0)) / (1024*1024):.1f} MB")
            print(f"    Modified: {result.get('modifiedTime')}")
            return True

        except Exception as e:
            if attempt < MAX_RETRIES:
                print(f"  ⚠ Attempt {attempt} failed: {e}")
                print(f"    Retrying in {RETRY_DELAY}s...")
                time.sleep(RETRY_DELAY)
            else:
                print(f"  ✗ Failed to upload {description} after {MAX_RETRIES} attempts: {e}")
                return False


def get_current_version(service, file_id: str) -> dict:
    """Download current version.json from Google Drive."""
    try:
        import io
        from googleapiclient.http import MediaIoBaseDownload

        request = service.files().get_media(fileId=file_id)
        buffer = io.BytesIO()
        downloader = MediaIoBaseDownload(buffer, request)

        done = False
        while not done:
            _, done = downloader.next_chunk()

        buffer.seek(0)
        content = buffer.read().decode('utf-8')
        return json.loads(content)

    except Exception as e:
        print(f"  ⚠ Could not read current version.json: {e}")
        return {}


def main():
    parser = argparse.ArgumentParser(description='Deploy artifacts to Google Drive')
    parser.add_argument('--exe', help='Path to Windows portable .exe')
    parser.add_argument('--dmg', help='Path to macOS .dmg')
    parser.add_argument('--version-file', help='Path to write version.json before uploading')
    args = parser.parse_args()

    # Parse Drive file IDs
    file_ids_json = os.environ.get('DRIVE_FILE_IDS', '{}')
    try:
        file_ids = json.loads(file_ids_json)
    except json.JSONDecodeError:
        print("ERROR: Invalid DRIVE_FILE_IDS JSON")
        sys.exit(1)

    app_version = os.environ.get('APP_VERSION', '0.0.0')
    product_name = os.environ.get('PRODUCT_NAME', 'AnoniData')

    print("=" * 50)
    print("🚀 DEPLOYING TO GOOGLE DRIVE")
    print("=" * 50)
    print(f"  Product: {product_name}")
    print(f"  Version: {app_version}")
    print()

    # Authenticate
    print("1. Authenticating with Google Drive...")
    service = get_drive_service()
    print("  ✓ Authenticated")
    print()

    # Get current build number from existing version.json
    print("2. Reading current version metadata...")
    current_build = 0
    version_file_id = file_ids.get('version_json')
    if version_file_id:
        current_meta = get_current_version(service, version_file_id)
        current_build = current_meta.get('build', 0)
        print(f"  Current build: #{current_build}")
    else:
        print("  ⚠ No version_json file ID configured")

    next_build = current_build + 1
    build_number = int(os.environ.get('BUILD_NUMBER', next_build))
    print(f"  Next build: #{build_number}")
    print()

    # Upload artifacts
    print("3. Uploading artifacts...")
    uploaded = []

    # Upload EXE
    if args.exe and file_ids.get('exe'):
        if update_file(service, file_ids['exe'], args.exe,
                       'application/octet-stream', 'AnoniData.exe'):
            uploaded.append('AnoniData.exe')

    # Upload DMG
    if args.dmg and file_ids.get('dmg'):
        if update_file(service, file_ids['dmg'], args.dmg,
                       'application/octet-stream', 'AnoniData.dmg'):
            uploaded.append('AnoniData.dmg')

    print()

    # Generate and upload version.json
    print("4. Updating version.json...")
    if version_file_id:
        # Google Drive download URLs (direct download format)
        drive_urls = {}
        if file_ids.get('exe'):
            drive_urls['AnoniData.exe'] = f"https://drive.google.com/uc?export=download&id={file_ids['exe']}"
        if file_ids.get('dmg'):
            drive_urls['AnoniData.dmg'] = f"https://drive.google.com/uc?export=download&id={file_ids['dmg']}"
        if version_file_id:
            drive_urls['version.json'] = f"https://drive.google.com/uc?export=download&id={version_file_id}"

        version_data = {
            'productName': product_name,
            'version': app_version,
            'build': build_number,
            'date': time.strftime('%Y-%m-%dT%H:%M:%S.000Z', time.gmtime()),
            'installers': uploaded,
            'mainInstallerFilename': uploaded[0] if uploaded else None,
            'downloadUrls': drive_urls,
        }

        # Write version.json locally
        version_path = args.version_file or '/tmp/version.json'
        with open(version_path, 'w') as f:
            json.dump(version_data, f, indent=2)

        print(f"  Generated version.json:")
        print(f"    {json.dumps(version_data, indent=4)}")

        if update_file(service, version_file_id, version_path,
                       'application/json', 'version.json'):
            print("  ✓ version.json updated")
        else:
            print("  ✗ Failed to update version.json")
    else:
        print("  ⚠ Skipped (no version_json file ID)")

    print()
    print("=" * 50)
    if uploaded:
        print(f"🎉 DEPLOYMENT COMPLETE: v{app_version} Build #{build_number}")
        print(f"   Uploaded: {', '.join(uploaded)}")
    else:
        print("⚠ DEPLOYMENT INCOMPLETE: No artifacts were uploaded")
    print("=" * 50)

    # Exit with error if nothing was uploaded
    if not uploaded:
        sys.exit(1)


if __name__ == '__main__':
    main()
