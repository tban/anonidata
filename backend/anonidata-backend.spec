# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('config', 'config'), ('utils', 'utils'), ('core', 'core'), ('processors', 'processors'), ('detectors', 'detectors')],
    hiddenimports=[
        'spacy',
        'es_core_news_sm',
        'pikepdf',
        'fitz',  # PyMuPDF
        'PIL',
        'cv2',  # OpenCV
        'numpy',
        'loguru',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Excluir módulos de testing y desarrollo no necesarios
        'pytest',
        'pytest-cov',
        'coverage',
        'black',
        'mypy',
        'flake8',
        # Excluir librerías de ML/DL pesadas no usadas directamente
        'torch',
        'tensorflow',
        'keras',
        # Excluir Jupyter y IPython
        'IPython',
        'jupyter',
        'notebook',
        # Excluir matplotlib y plotting
        'matplotlib',
        'seaborn',
        'plotly',
        # Excluir pandas si no se usa
        'pandas',
    ],
    noarchive=False,
    optimize=2,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [('O', None, 'OPTION'), ('O', None, 'OPTION')],
    name='anonidata-backend',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
