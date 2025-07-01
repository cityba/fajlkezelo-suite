# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['sablon.py'],
    pathex=[],
    binaries=[('C:\\Users\\ap\\AppData\\Local\\Programs\\Python\\Python313\\Lib\\site-packages\\PyQt5\\Qt5\\plugins\\imageformats', 'PyQt5\\Qt5\\plugins\\multimedia'), ('C:\\Users\\ap\\AppData\\Local\\Programs\\Python\\Python313\\Lib\\site-packages\\PyQt5\\Qt5\\plugins\\imageformats', 'PyQt5\\Qt5\\plugins\\multimedia')],
    datas=[('C:/Users/ap/Documents/fajlkezelo-suite/system_control_panel_15843.ico', '.'), ('C:/Users/ap/Documents/fajlkezelo-suite/system_control_panel_15843.png', '.'), ('egyes.py', '.'), ('kettes.py', '.'), ('harmas.py', '.'), ('negyes.py', '.'), ('otos.py', '.')],
    hiddenimports=['docx', 'openpyxl', 'PyPDF2', 'PyQt5.QtMultimedia', 'PyQt5.QtMultimediaWidgets', 'psutil', 'GPUtil'],
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
    [],
    exclude_binaries=True,
    name='Szita suite',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['C:\\Users\\ap\\Documents\\fajlkezelo-suite\\system_control_panel_15843.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Szita suite',
)
