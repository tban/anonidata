# -*- mode: python ; coding: utf-8 -*-

import sys
import platform
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

# Construir lista de datas usando rutas relativas
datas_list = [
    ('backend/config', 'config'),
]

# Agregar modelo spaCy si existe
if spacy_model_path and spacy_model_path.exists():
    model_name = spacy_model_path.name
    datas_list.append((str(spacy_model_path), f'spacy/data/{model_name}'))
    print(f"✓ Incluyendo modelo spaCy: {model_name} desde {spacy_model_path}")
else:
    print("⚠ Modelo spaCy no encontrado - NER no estará disponible")

# Agregar Tesseract OCR si se copio en la carpeta del backend
tesseract_local_path = Path('backend/tesseract')
if tesseract_local_path.exists():
    datas_list.append((str(tesseract_local_path), 'tesseract'))
    print("✓ Incluyendo Tesseract OCR en el paquete portable")

# Agregar DLLs de pyzbar (especialmente en Windows para libiconv y libzbar)
try:
    import pyzbar
    pyzbar_path = Path(pyzbar.__file__).parent
    for dll_path in pyzbar_path.glob("*.dll"):
        # Copiar a la subcarpeta 'pyzbar' (donde la librería busca libzbar-64.dll)
        datas_list.append((str(dll_path), 'pyzbar'))
        # Copiar al directorio raíz '.' (para que Windows encuentre libiconv.dll al cargar libzbar-64.dll)
        datas_list.append((str(dll_path), '.'))
        print(f"✓ Incluyendo DLL de pyzbar en raíz y subcarpeta: {dll_path.name}")
except Exception as e:
    print(f"⚠ No se pudieron incluir DLLs de pyzbar: {e}")

print("✓ Incluyendo configuración desde: backend/config")

a = Analysis(
    ['backend/main.py'],
    pathex=[],
    binaries=[],
    datas=datas_list,
    hiddenimports=[
        'loguru', 'pypdf', 'PyMuPDF', 'Pillow', 'numpy', 'cv2', 'pytesseract', 'pyzbar',
        # spaCy core modules
        'spacy', 'spacy.lang.es', 'spacy.parts_of_speech', 'spacy.symbols',
        'spacy.vocab', 'spacy.tokens', 'spacy.tokens.doc', 'spacy.tokens.span',
        'spacy.tokens.token', 'spacy.tokenizer', 'spacy.matcher', 'spacy.matcher.matcher',
        'spacy.attrs', 'spacy.lexeme', 'spacy.strings', 'spacy.morphology',
        'spacy.pipeline', 'spacy.pipeline.ner', 'spacy.pipeline.tagger',
        'spacy.pipeline.entityruler', 'spacy.pipeline.sentencizer',
        'spacy.kb', 'spacy.util', 'spacy.lookups',
        # thinc (spacy dependency)
        'thinc', 'thinc.api', 'thinc.config', 'thinc.model', 'thinc.layers',
        # Additional spacy internals
        'spacy.training', 'spacy.scorer', 'spacy.displacy', 'spacy.cli',
        'cymem', 'cymem.cymem', 'preshed', 'preshed.maps', 'murmurhash',
        'blis', 'blis.py', 'srsly', 'srsly.msgpack', 'srsly.json_wrapper',
        'wasabi', 'catalogue', 'confection',
    ],
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

import sys as _sys

# Configuración por plataforma
_is_windows = _sys.platform == 'win32'
_is_mac = _sys.platform == 'darwin'

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [('O', None, 'OPTION'), ('O', None, 'OPTION')] if not _is_windows else [],
    name='anonidata-backend',
    debug=False,
    bootloader_ignore_signals=False,
    strip=not _is_windows,  # strip no funciona en Windows
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=platform.machine() if _is_mac else None,
    codesign_identity=None,
    entitlements_file=None,
)
