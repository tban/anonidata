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
    ('config', 'config'),
]

# Agregar modelo spaCy si existe
if spacy_model_path and spacy_model_path.exists():
    model_name = spacy_model_path.name
    datas_list.append((str(spacy_model_path), f'spacy/data/{model_name}'))
    print(f"✓ Incluyendo modelo spaCy: {model_name} desde {spacy_model_path}")
else:
    print("⚠ Modelo spaCy no encontrado - NER no estará disponible")

a = Analysis(
    ['main.py'],
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
    optimize=0,  # 0 para compatibilidad con NumPy en Python 3.13
)

pyz = PYZ(a.pure)

# MODO ONEFILE: Un solo ejecutable con todo incluido
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='anonidata-backend',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,   # strip no funciona en Windows
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,   # True para poder leer stdout/stderr
    disable_windowed_traceback=False,
    argv_emulation=False,
    # Sin target_arch: usa la arquitectura nativa del sistema
    codesign_identity=None,
    entitlements_file=None,
)
