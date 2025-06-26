# szita.spec
import os
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

block_cipher = None

a = Analysis(
    ['sablon.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('egyes.py', '.'),
        ('kettes.py', '.'),
        ('harmas.py', '.'),
        ('negyes.py', '.')
    ],
    hiddenimports=[
        'docx', 
        'openpyxl', 
        'PyPDF2', 
        'PyQt5.QtMultimedia',
        'PyQt5.QtMultimediaWidgets'
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# HIBÁS: Eredeti, nem működő változat
# pyqt5_data = collect_data_files('PyQt5', include_py_files=True)
# a.datas += pyqt5_data

# JAVÍTOTT: Konvertáljuk 3 elemű tuple-ökké
pyqt5_data = collect_data_files('PyQt5', include_py_files=True)
a.datas += [(src, dest, 'DATA') for src, dest in pyqt5_data]  # <-- Típus hozzáadva

# HIBÁS: Eredeti, nem működő változat
# pyqt5_binaries = collect_dynamic_libs('PyQt5')
# a.binaries += pyqt5_binaries

# JAVÍTOTT: Konvertáljuk 3 elemű tuple-ökké
pyqt5_binaries = collect_dynamic_libs('PyQt5')
a.binaries += [(src, dest, 'BINARY') for src, dest in pyqt5_binaries]  # <-- Típus hozzáadva

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],  # Üres lista az EXE opcióknak
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
    icon=os.path.join('C:\\', 'Users', 'ap', 'Downloads', 'favicon.ico'),
)