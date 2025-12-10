# -*- mode: python ; coding: utf-8 -*-

import sys
from pathlib import Path

# Encontrar la ubicación del modelo spaCy
spacy_model_path = None
try:
    import spacy
    try:
        nlp = spacy.load("es_core_news_lg")
        spacy_model_path = Path(nlp._path)
    except:
        try:
            nlp = spacy.load("es_core_news_sm")
            spacy_model_path = Path(nlp._path)
        except:
            print("ADVERTENCIA: No se encontró modelo spaCy")
except:
    print("ADVERTENCIA: spaCy no disponible")

# Construir lista de datas
datas_list = [
    ('/Users/tban/Documents/Desarrollos/anonidata/config', 'config'),
]

# Agregar modelo spaCy si existe
if spacy_model_path and spacy_model_path.exists():
    model_name = spacy_model_path.name
    datas_list.append((str(spacy_model_path), f'spacy/data/{model_name}'))
    print(f"✓ Incluyendo modelo spaCy: {model_name} desde {spacy_model_path}")
else:
    print("⚠ Modelo spaCy no encontrado - NER no estará disponible")

print(f"✓ Incluyendo configuración desde: /Users/tban/Documents/Desarrollos/anonidata/config")

a = Analysis(
    ['/Users/tban/Documents/Desarrollos/anonidata/main.py'],
    pathex=[],
    binaries=[],
    datas=datas_list,
    hiddenimports=['loguru', 'pypdf', 'PyMuPDF', 'Pillow', 'numpy', 'cv2', 'pytesseract', 'spacy', 'pyzbar', 'spacy.lang.es'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'pytest', 'mypy', 'black', 'flake8', 'mypy_extensions',
        'unittest', 'test', 'tests', '_pytest',
        'coverage', 'pytest_cov',
        'torch', 'transformers', 'scipy', 'torchvision',
    ],
    noarchive=False,
    optimize=2,
)

pyz = PYZ(a.pure)

# MODO ONEFILE: Un solo ejecutable con todo incluido
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [('O', None, 'OPTION'), ('O', None, 'OPTION')],
    name='anonidata-backend',
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch='arm64',
    codesign_identity=None,
    entitlements_file=None,
)
