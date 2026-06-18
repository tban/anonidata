# -*- mode: python ; coding: utf-8 -*-

import sys
from pathlib import Path

# Detectar plataforma
_is_windows = sys.platform == 'win32'
_is_mac = sys.platform == 'darwin'

# Encontrar la ubicación del modelo spaCy
spacy_model_path = None
try:
    import spacy
    for model_name in ['es_core_news_lg', 'es_core_news_sm']:
        try:
            nlp = spacy.load(model_name)
            spacy_model_path = Path(nlp._path)
            print(f"✓ Modelo spaCy encontrado: {model_name}")
            break
        except:
            continue
    if not spacy_model_path:
        print("⚠ No se encontró ningún modelo spaCy")
except:
    print("⚠ spaCy no disponible")

# Construir lista de datas
datas_list = [
    ('config', 'config'),
]

# Agregar modelo spaCy si existe
if spacy_model_path and spacy_model_path.exists():
    model_name = spacy_model_path.name
    datas_list.append((str(spacy_model_path), f'spacy/data/{model_name}'))
    print(f"✓ Incluyendo modelo spaCy desde: {spacy_model_path}")

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=datas_list,
    hiddenimports=[
        'loguru', 'pypdf', 'PyMuPDF', 'Pillow', 'numpy', 'cv2', 'pytesseract', 'pyzbar',
        # spaCy
        'spacy', 'spacy.lang.es', 'spacy.parts_of_speech', 'spacy.symbols',
        'spacy.vocab', 'spacy.tokens', 'spacy.tokens.doc', 'spacy.tokens.span',
        'spacy.tokens.token', 'spacy.tokenizer', 'spacy.matcher', 'spacy.matcher.matcher',
        'spacy.attrs', 'spacy.lexeme', 'spacy.strings', 'spacy.morphology',
        'spacy.pipeline', 'spacy.pipeline.ner', 'spacy.pipeline.tagger',
        'spacy.pipeline.entityruler', 'spacy.pipeline.sentencizer',
        'spacy.kb', 'spacy.util', 'spacy.lookups',
        'spacy.training', 'spacy.scorer', 'spacy.displacy', 'spacy.cli',
        # thinc
        'thinc', 'thinc.api', 'thinc.config', 'thinc.model', 'thinc.layers',
        # spacy deps
        'cymem', 'cymem.cymem', 'preshed', 'preshed.maps', 'murmurhash',
        'blis', 'blis.py', 'srsly', 'srsly.msgpack', 'srsly.json_wrapper',
        'wasabi', 'catalogue', 'confection',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Testing / dev tools
        'pytest', 'mypy', 'black', 'flake8', 'mypy_extensions',
        'unittest', 'test', 'tests', '_pytest',
        'coverage', 'pytest_cov',
        # Deep learning (no se usa)
        'torch', 'torchvision', 'torchaudio', 'transformers',
        'tensorflow', 'keras', 'caffe2',
        'easyocr',
        'safetensors', 'tokenizers', 'huggingface_hub',
        # Ciencia / análisis (no se usa)
        'scipy', 'scikit-image', 'skimage',
        'pandas', 'matplotlib', 'IPython', 'jupyter',
        # PDF redundantes (no se usan, ya tenemos PyMuPDF)
        'pdfminer', 'pdfplumber', 'pdf2image', 'reportlab',
        'pypdfium2',
        # NLP redundante (no se usa)
        'presidio_analyzer', 'presidio_anonymizer',
        'phonenumbers',
        # Imágenes redundantes
        'imageio', 'tifffile', 'shapely', 'scikit_image',
        # Otros no necesarios
        'cryptography', 'sympy', 'networkx', 'mpmath',
        'pygments', 'Pygments',
    ],
    noarchive=False,
    optimize=0,  # 0 para compatibilidad con NumPy en Python 3.13
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [] if _is_windows else [('O', None, 'OPTION'), ('O', None, 'OPTION')],
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
    target_arch='arm64' if _is_mac else None,
    codesign_identity=None,
    entitlements_file=None,
)
