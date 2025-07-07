# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['sablon.py'],
    pathex=[],
    binaries=[('C:\\Users\\ap\\AppData\\Local\\Programs\\Python\\Python313\\Lib\\site-packages\\PyQt5\\Qt5\\plugins\\imageformats', 'PyQt5\\Qt5\\plugins\\multimedia'), ('C:\\Users\\ap\\AppData\\Local\\Programs\\Python\\Python313\\Lib\\site-packages\\PyQt5\\Qt5\\plugins\\imageformats', 'PyQt5\\Qt5\\plugins\\multimedia')],
    datas=[('egyes.py', '.'), ('harmas.py', '.'), ('hatos.py', '.'), ('hetes.py', '.'), ('icon.ico', '.'), ('kettes.py', '.'), ('negyes.py', '.'), ('otos.py', '.'), ('README.md', '.'), ('system_control_panel_15843.ico', '.'), ('system_control_panel_15843.png', '.'), ('C:/Users/ap/Documents/fajlkezelo-suite/icon.ico', '.'), ('C:/Users/ap/Documents/fajlkezelo-suite/system_control_panel_15843.png', '.'), ('egyes.py', '.'), ('kettes.py', '.'), ('harmas.py', '.'), ('negyes.py', '.'), ('otos.py', '.'), ('hatos.py', '.'), ('hetes.py', '.')],
    hiddenimports=['openpyxl', 'PyPDF2', 'time', 'winreg', 'csv', 're', 'os', 'pyodbc', 'pefile', 'threading', 'PyQt5', 'collections', 'mysql', 'tempfile', 'json', 'sys', 'subprocess', 'docx', 'queue', 'random', 'datetime', 'ctypes', 'traceback', 'shutil', 'math', 'platform', 'socket', 'importlib', 'matplotlib', 'pandas', 'psutil', 'numpy', 'concurrent', 'appdirs', 'textwrap', 'fnmatch', 'matplotlib.backends.backend_qt5agg', 'matplotlib.backends.qt_compat', 'pefile', 'numpy', 'pyodbc', 'mysql.connector', 'docx', 'openpyxl', 'PyPDF2', 'PyQt5.QtMultimedia', 'PyQt5.QtMultimediaWidgets', 'psutil', 'GPUtil'],
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
    icon=['C:\\Users\\ap\\Documents\\fajlkezelo-suite\\icon.ico'],
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
