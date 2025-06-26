# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['sablon.py'],
    pathex=[],
    binaries=[('\\multimedia', 'PyQt5\\Qt\\plugins\\multimedia'), ('\\imageformats', 'PyQt5\\Qt\\plugins\\imageformats'), ('\\mediaservice', 'PyQt5\\Qt\\plugins\\mediaservice')],
    datas=[('egyes.py', '.'), ('kettes.py', '.'), ('harmas.py', '.'), ('negyes.py', '.')],
    hiddenimports=['docx', 'openpyxl', 'PyPDF2', 'PyQt5.QtMultimedia', 'PyQt5.QtMultimediaWidgets'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='Szita suite',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['C:\\Users\\ap\\Downloads\\favicon.ico'],
)
