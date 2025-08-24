import sys
import subprocess
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QProgressBar, QComboBox,
    QMessageBox, QGroupBox, QGridLayout, QLineEdit, QCheckBox, QTextEdit, QFileDialog,
    QApplication, QListWidget, QDialog, QDialogButtonBox,QListWidgetItem
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QColor, QPalette 
import os
import shutil
import json
import time
import re
import traceback
import importlib.util
import importlib

CONFIG_PATH = os.path.join(os.path.expanduser("~"), ".buildapp_settings.json")

class MissingImportsDialog(QDialog):
    def __init__(self, imports, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Hiányzó importok kezelése")
        layout = QVBoxLayout(self)
        
        label = QLabel(f"{len(imports)} hiányzó modult észleltünk. Kérjük válaszd ki melyeket szeretnéd hozzáadni:")
        layout.addWidget(label)
        
        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QListWidget.MultiSelection)
        for imp in imports:
            item = QListWidgetItem(imp)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked)
            self.list_widget.addItem(item)
        layout.addWidget(self.list_widget)
        
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
    
    def get_selected_imports(self):
        return [self.list_widget.item(i).text() 
                for i in range(self.list_widget.count()) 
                if self.list_widget.item(i).checkState() == Qt.Checked]

class BuildWorker(QThread):
    log_signal = pyqtSignal(str, str)
    progress_signal = pyqtSignal(int)
    finished = pyqtSignal(bool)
    ask_missing_imports = pyqtSignal(list)
    ask_additional_files = pyqtSignal(list, list)

    def __init__(self, app):
        super().__init__()
        self.app = app
        self.missing_imports_response = None
        self.missing_imports_list = []
        self.additional_files_response = None
        self.additional_files_list = []
        self.add_binary_files = []

    def run(self):
        try:
            self.log_signal.emit("BuildWorker szál elindult", "green")
            
            if not self.build_exe():
                self.log_signal.emit("EXE build sikertelen!", "red")
                self.finished.emit(False)
                return
            
            if not self.sign_exe():
                self.log_signal.emit("Aláírás sikertelen!", "red")
                self.finished.emit(False)
                return
            
            if not self.build_installer():
                self.log_signal.emit("Installer build sikertelen!", "red")
                self.finished.emit(False)
                return
            
            self.log_signal.emit("✅ Minden folyamat sikeresen befejeződött!", "green")
            self.finished.emit(True)
        except Exception as e:
            self.log_signal.emit(f"❌ Váratlan hiba: {str(e)}", "red")
            traceback.print_exc()
            self.finished.emit(False)

    def analyze_hidden_imports(self, script_path):
        self.log_signal.emit("🔍 Hidden import elemzés...", "yellow")
        
        found_imports = set()
        missing_imports = set()
        
        try:
            with open(script_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
                import_pattern = r'^\s*(?:import|from)\s+([a-zA-Z0-9_\.]+)'
                matches = re.finditer(import_pattern, content, re.MULTILINE)
                for match in matches:
                    module = match.group(1).strip()
                    if module:
                        top_level = module.split('.')[0]
                        if top_level not in found_imports:
                            found_imports.add(top_level)
                
                dynamic_pattern = r'__import__\([\'"]([^\'"]+)[\'"]\)'
                dynamic_matches = re.findall(dynamic_pattern, content)
                for module in dynamic_matches:
                    module = module.strip()
                    if module:
                        top_level = module.split('.')[0]
                        if top_level not in found_imports:
                            found_imports.add(top_level)
                
                valid_imports = set()
                for module in list(found_imports):
                    try:
                        if importlib.util.find_spec(module):
                            valid_imports.add(module)
                        else:
                            missing_imports.add(module)
                    except:
                        missing_imports.add(module)
                
                self.log_signal.emit(f"✅ {len(valid_imports)} fő csomag találva", "green")
                if missing_imports:
                    self.log_signal.emit(f"⚠️ {len(missing_imports)} fő csomag hiányzik", "yellow")
                
                return list(valid_imports), list(missing_imports)
                
        except Exception as e:
            self.log_signal.emit(f"❌ Hiba az elemzés során: {str(e)}", "red")
            traceback.print_exc()
            return [], []

    def find_other_py_files(self, folder):
        py_files = []
        script_name = os.path.basename(self.app.fields["script_path"].text())
        for file in os.listdir(folder):
            if file.endswith(".py") and file != script_name:
                py_files.append(os.path.join(folder, file))
        return py_files

    def analyze_other_imports(self, folder):
        other_files = self.find_other_py_files(folder)
        all_imports = set()
        all_missing = set()
        
        for file in other_files:
            imports, missing = self.analyze_hidden_imports(file)
            all_imports.update(imports)
            all_missing.update(missing)
        
        return list(all_imports), list(all_missing)

    def find_additional_files(self, folder):
        data_files = []
        binary_files = []
        binary_exts = ['.dll', '.pyd', '.so', '.exe', '.bin', '.dat']
        
        for root, dirs, files in os.walk(folder, topdown=True):
            # Kihagyjuk a nem kívánt mappákat
            for dir_to_remove in ['.git', 'dist', 'Output', 'build', '__pycache__']:
                if dir_to_remove in dirs:
                    dirs.remove(dir_to_remove)
             
            for file in files:
                if file.endswith(('.iss', '.spec')):
                    continue
                
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, folder)
                
                
                # Kihagyjuk a fő scriptet és az ikonfájlokat
                if file == os.path.basename(self.app.fields["script_path"].text()):
                    continue
                if self.app.fields["icon_path"].text() and full_path == self.app.fields["icon_path"].text():
                    continue
                if self.app.fields["png_path"].text() and full_path == self.app.fields["png_path"].text():
                    continue
                
                # Kihagyjuk a .gitignore fájlt
                if file == '.gitignore':
                    continue
                    
                # Bináris fájlok azonosítása
                if any(file.endswith(ext) for ext in binary_exts):
                    binary_files.append(rel_path)
                else:
                    data_files.append(rel_path)
        
        return data_files, binary_files
    def build_exe(self):
        self.log_signal.emit("=== EXE BUILD FOLYAMAT ===", "yellow")
        script = self.app.fields["script_path"].text()
        if not script:
            self.log_signal.emit("❌ Hiányzó Python script!", "red")
            return False
            
        name = self.app.fields["output_name"].text() or os.path.splitext(os.path.basename(script))[0]
        folder = os.path.dirname(script)
        build_mode = self.app.fields["build_mode"].currentText()
        
        # Python interpreter helyes meghatározása
        python_exe = sys.executable
        if getattr(sys, 'frozen', False):
            # Ha EXE-ből futunk, keressük a python.exe-t
            base_dir = os.path.dirname(sys.executable)
            python_exe = os.path.join(base_dir, 'python.exe')
            if not os.path.exists(python_exe):
                # Ha nincs a mappában, próbáljuk a PATH-ból
                python_exe = shutil.which('python') or shutil.which('python3')
                if not python_exe:
                    self.log_signal.emit("❌ Nem található Python interpreter!", "red")
                    return False
        
        cmd = [python_exe, '-m', 'PyInstaller', os.path.basename(script)]
        cmd += ['--name', name, '--noconfirm',  f'--{build_mode}',  '--clean']
        
        # Új: Konzol elrejtése (windowed) opció hozzáadása
        if self.app.windowed_mode:
            cmd += ['--windowed']
            self.log_signal.emit("  ➕ Konzol elrejtése (windowed)", "green")
        
        if self.app.auto_hidden_import:
            self.log_signal.emit("🔍 Automatikus hidden import keresés...", "yellow")
            found_imports, missing_imports = self.analyze_hidden_imports(script)
            hidden_imports = set()
            self.log_signal.emit("🔍 Egyéb Python fájlok elemzése...", "blue")
            other_imports, other_missing = self.analyze_other_imports(folder)
            found_imports.extend(other_imports)
            missing_imports.extend(other_missing)
            
            self.missing_imports_response = None
            self.missing_imports_list = []
            
            if missing_imports:
                self.log_signal.emit(f"⚠️ {len(missing_imports)} hiányzó modul észlelve", "yellow")
                self.ask_missing_imports.emit(missing_imports)
                
                while self.missing_imports_response is None:
                    time.sleep(0.1)
                
                if self.missing_imports_response:
                    hidden_imports.update(self.missing_imports_list)
                     
            
            hidden_imports.update(found_imports)

            for imp in sorted(hidden_imports):  # sorted -> szép rendezett lista a logban
                cmd += ['--hidden-import', imp]
                self.log_signal.emit(f"  ➕ {imp}", "green")  
                


        
        if self.app.auto_other_files:
            self.log_signal.emit("🔍 További fájlok keresése...", "yellow")
            data_files, binary_files = self.find_additional_files(folder)
            
            if data_files or binary_files:
                self.additional_files_response = None
                self.additional_files_list = []
                self.add_binary_files = []
                
                self.ask_additional_files.emit(data_files, binary_files)
                
                while self.additional_files_response is None:
                    time.sleep(0.1)
                
                if self.additional_files_response:
                    for file in self.additional_files_list:
                        if file in self.add_binary_files:
                            cmd += ['--add-binary', f"{file};."]
                            self.log_signal.emit(f"  ➕ BINÁRIS: {file}", "green")
                        else:
                            cmd += ['--add-data', f"{file};."]
                            self.log_signal.emit(f"  ➕ ADAT: {file}", "green")
        
        icon_path = self.app.fields["icon_path"].text()
        if icon_path:
            cmd += ['--icon', os.path.normpath(icon_path)]
            cmd += ['--add-data', f'{icon_path}{os.pathsep}.']
        
        png_path = self.app.fields["png_path"].text()
        if png_path:
            cmd += ['--add-data', f'{png_path}{os.pathsep}.']
        
        upx_path = self.app.fields["upx_path"].text()
        if upx_path:
            cmd += ['--upx-dir', os.path.normpath(upx_path)]
        
        extra_args = self.app.fields["extra_args"].text()
        if extra_args:
            cmd += extra_args.split()
        
        self.log_signal.emit("Erőforrás másolás...", "blue")
        for src in [script, icon_path, png_path]:
            if src and os.path.exists(src):
                dst = os.path.join(folder, os.path.basename(src))
                if os.path.abspath(src) != os.path.abspath(dst):
                    shutil.copy(src, folder)
        
        self.progress_signal.emit(20)
        
        self.log_signal.emit(f"EXE build elindítva ({build_mode} mód)...", "blue")
        self.log_signal.emit(f"Parancs: {' '.join(cmd)}", "default")
        
        try:
            # Windows alatt elrejtjük az ablakot
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = 0  # SW_HIDE
            else:
                startupinfo = None

            process = subprocess.Popen(
                cmd, 
                cwd=folder, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.STDOUT, 
                text=True,
                bufsize=1,
                universal_newlines=True,
                startupinfo=startupinfo  # Ez elrejti az ablakot
            )
            
            while True:
                line = process.stdout.readline()
                if not line:
                    break
                self.log_signal.emit(line.strip(), "default")
            
            process.wait()
            success = process.returncode == 0
        except Exception as e:
            self.log_signal.emit(f"❌ Hiba a build folyamatban: {str(e)}", "red")
            success = False
        
        self.progress_signal.emit(60)
        
        return success

    def sign_exe(self):
        self.log_signal.emit("=== EXE ALÁÍRÁS ===", "yellow")
        script = self.app.fields["script_path"].text()
        name = self.app.fields["output_name"].text() or os.path.splitext(os.path.basename(script))[0]
        folder = os.path.dirname(script)
        build_mode = self.app.fields["build_mode"].currentText()
        
        if build_mode == "onefile":
            exe_path = os.path.join(folder, 'dist', f'{name}.exe')
        else:
            exe_path = os.path.join(folder, 'dist', name, f'{name}.exe')
        
        if not os.path.exists(exe_path):
            self.log_signal.emit("❌ Hiányzó EXE!", "red")
            return False
        
        pfx_path = self.app.fields["pfx_path"].text()
        pfx_pass = self.app.fields["pfx_pass"].text()
        
        if not pfx_path or not pfx_pass:
            self.log_signal.emit("❌ Hiányzó PFX fájl vagy jelszó!", "red")
            return False
        
        temp_exe = os.path.join(folder, f'temp_{name}.exe')
        try:
            shutil.copy(exe_path, temp_exe)
        except Exception as e:
            self.log_signal.emit(f"❌ Hiba EXE másolásakor: {str(e)}", "red")
            return False
        
        cmd = [
            'signtool', 'sign', '/a', '/f', pfx_path, '/p', pfx_pass,
            '/fd', 'SHA256', '/t', 'http://timestamp.digicert.com', temp_exe
        ]
        
        self.log_signal.emit(f"Aláíró parancs: {' '.join(cmd)}", "blue")
        
        try:
            # Windows alatt elrejtjük az ablakot
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = 0
            else:
                startupinfo = None

            process = subprocess.Popen(
                cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.STDOUT, 
                text=True,
                bufsize=1,
                universal_newlines=True,
                startupinfo=startupinfo
            )
            
            while True:
                line = process.stdout.readline()
                if not line:
                    break
                self.log_signal.emit(line.strip(), "default")
            
            process.wait()
            success = process.returncode == 0
        except Exception as e:
            self.log_signal.emit(f"❌ Hiba az aláíráskor: {str(e)}", "red")
            success = False
        
        if success:
            try:
                shutil.move(temp_exe, exe_path)
                self.log_signal.emit("✅ EXE sikeresen aláírva", "green")
            except Exception as e:
                self.log_signal.emit(f"❌ Hiba az aláírt EXE mozgatásakor: {str(e)}", "red")
                success = False
        else:
            self.log_signal.emit("❌ EXE aláírás sikertelen", "red")
        
        if os.path.exists(temp_exe):
            try:
                os.remove(temp_exe)
            except:
                pass
        
        self.progress_signal.emit(80)
        return success

    def build_installer(self):
        self.log_signal.emit("=== INSTALLER BUILD FOLYAMAT ===", "yellow")
        script = self.app.fields["script_path"].text()
        name = self.app.fields["output_name"].text() or os.path.splitext(os.path.basename(script))[0]
        folder = os.path.dirname(script)
        
        icon_path = self.app.fields["icon_path"].text()
        if icon_path:
            icon_dest = os.path.join(folder, 'icon.ico')
            if os.path.abspath(icon_path) != os.path.abspath(icon_dest):
                shutil.copy(icon_path, icon_dest)

        png_path = self.app.fields["png_path"].text()
        if png_path:
            png_dest = os.path.join(folder, 'icon.png')
            if os.path.abspath(png_path) != os.path.abspath(png_dest):
                shutil.copy(png_path, png_dest)

        iss_file = os.path.join(folder, f'{name}.iss')
        
        build_mode = self.app.fields["build_mode"].currentText()
        if build_mode == "onefile":
            files_section = f'Source: "dist\\{name}.exe"; DestDir: "{{app}}"; Flags: ignoreversion'
        else:
            files_section = f'Source: "dist\\{name}\\*"; DestDir: "{{app}}"; Flags: ignoreversion recursesubdirs createallsubdirs\n'
            
        content = f'''[Setup]
AppName={name}
AppVersion=1.0.1
AppPublisher=Szita_Team
DefaultDirName={{commonpf}}\\{name}
OutputBaseFilename={name}_telepito
DefaultGroupName={name}
SetupIconFile=icon.ico
Compression=lzma
SolidCompression=yes
WizardStyle=modern
LanguageDetectionMethod=none
AppContact=https://bankkontir.hu
AppCopyright=Szita_Team
SignTool=mysign

[Languages]
Name: "hu"; MessagesFile: "compiler:Languages\\Hungarian.isl"

[Files]
{files_section}

[Icons]
Name: "{{group}}\\{name}"; Filename: "{{app}}\\{name}.exe"
Name: "{{commondesktop}}\\{name}"; Filename: "{{app}}\\{name}.exe"; Tasks: desktopikon

[Tasks]
Name: desktopikon; Description: "Asztali ikon létrehozása"; GroupDescription: "Kiegészítő lehetőségek"; Flags: unchecked
Name: deleteinstaller; Description: "Telepítő törlése telepítés után"; GroupDescription: "Kiegészítő lehetőségek"; Flags: unchecked

[Run]
Filename: "{{app}}\\{name}.exe"; Description: "Alkalmazás indítása"; Flags: nowait postinstall skipifsilent

Filename: "cmd.exe"; \
  Parameters: "/C timeout /T 5 /NOBREAK >nul & del ""{{srcexe}}"""; \
  Flags: runhidden shellexec; Tasks: deleteinstaller
'''

        try:
            with open(iss_file, 'w', encoding='utf-8') as f:
                f.write(content)
            self.log_signal.emit(f"ISS szkript létrehozva: {iss_file}", "green")
        except Exception as e:
            self.log_signal.emit(f"❌ Hiba ISS szkript létrehozásakor: {str(e)}", "red")
            return False
        
        iscc_paths = [
            r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
            r"C:\Program Files\Inno Setup 6\ISCC.exe",
            "ISCC.exe"
        ]
        
        iscc_found = None
        for path in iscc_paths:
            if os.path.exists(path):
                iscc_found = path
                break
        
        if not iscc_found:
            self.log_signal.emit("❌ Inno Setup nem található!", "red")
            return False
        
        cmd = [iscc_found, iss_file]
        self.log_signal.emit(f"Installer parancs: {' '.join(cmd)}", "blue")
        
        try:
            # Windows alatt elrejtjük az ablakot
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = 0
            else:
                startupinfo = None

            process = subprocess.Popen(
                cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.STDOUT, 
                text=True,
                bufsize=1,
                universal_newlines=True,
                startupinfo=startupinfo
            )
            
            while True:
                line = process.stdout.readline()
                if not line:
                    break
                self.log_signal.emit(line.strip(), "default")
            
            process.wait()
            success = process.returncode == 0
        except Exception as e:
            self.log_signal.emit(f"❌ Hiba az installer build közben: {str(e)}", "red")
            success = False
        
        if success:
            self.log_signal.emit("✅ Installer sikeresen elkészült", "green")
        else:
            self.log_signal.emit("❌ Installer build sikertelen", "red")
        
        self.progress_signal.emit(100)
        return success

class BuildApp(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("⚡ Hyper-Sign - Exe és Installer Gyártó")
        self.set_performance_theme()
        
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(10, 10, 10, 10)
        
        form_group = QGroupBox("Build Beállítások")
        form_layout = QGridLayout(form_group)
        form_layout.setSpacing(8)
        
        self.fields = {
            "script_path": QLineEdit(),
            "output_name": QLineEdit(),
            "icon_path": QLineEdit(),
            "png_path": QLineEdit(),
            "upx_path": QLineEdit(),
            "extra_args": QLineEdit(),
            "pfx_path": QLineEdit(),
            "pfx_pass": QLineEdit(),
            "build_mode": QComboBox()
        }
        self.fields["build_mode"].addItems(["onefile", "onedir"])
        self.fields["pfx_pass"].setEchoMode(QLineEdit.Password)
        
        self.performance_options = {
            "high_priority": QCheckBox("Magas CPU prioritás"),
            "max_memory": QCheckBox("Maximális memóriahasználat"),
            "gpu_acceleration": QCheckBox("GPU gyorsítás (ha elérhető)"),
            "parallel_processing": QCheckBox("Párhuzamos feldolgozás"),
            "auto_hidden_import": QCheckBox("Automatikus hidden import keresés"),
            "auto_other_files": QCheckBox("Automatikus más fájlok felismerése"),
            # Új: Konzol elrejtése (windowed) opció
            "windowed_mode": QCheckBox("Konzol elrejtése (windowed)")
        }
        # Alapértelmezett pipálások
        self.performance_options["auto_hidden_import"].setChecked(True)
        self.performance_options["auto_other_files"].setChecked(True)
        self.performance_options["windowed_mode"].setChecked(True)  # Alapértelmezetten pipálva
        
        row = 0
        
        form_layout.addWidget(QLabel("Python script (.py):"), row, 0)
        form_layout.addWidget(self.fields["script_path"], row, 1)
        browse_script_btn = QPushButton("Tallózás")
        browse_script_btn.clicked.connect(self.browse_script)
        form_layout.addWidget(browse_script_btn, row, 2)
        row += 1
        
        form_layout.addWidget(QLabel("Output name:"), row, 0)
        form_layout.addWidget(self.fields["output_name"], row, 1, 1, 2)
        row += 1
        
        form_layout.addWidget(QLabel("Build mód:"), row, 0)
        form_layout.addWidget(self.fields["build_mode"], row, 1, 1, 2)
        row += 1
        
        form_layout.addWidget(QLabel("Extra PyInstaller args:"), row, 0)
        form_layout.addWidget(self.fields["extra_args"], row, 1, 1, 2)
        row += 1
        
        form_layout.addWidget(QLabel("ICO icon:"), row, 0)
        form_layout.addWidget(self.fields["icon_path"], row, 1)
        browse_icon_btn = QPushButton("Tallózás")
        browse_icon_btn.clicked.connect(self.browse_icon)
        form_layout.addWidget(browse_icon_btn, row, 2)
        row += 1
        
        form_layout.addWidget(QLabel("PNG icon (data):"), row, 0)
        form_layout.addWidget(self.fields["png_path"], row, 1)
        browse_png_btn = QPushButton("Tallózás")
        browse_png_btn.clicked.connect(self.browse_png)
        form_layout.addWidget(browse_png_btn, row, 2)
        row += 1
        
        form_layout.addWidget(QLabel("UPX dir:"), row, 0)
        form_layout.addWidget(self.fields["upx_path"], row, 1)
        browse_upx_btn = QPushButton("Tallózás")
        browse_upx_btn.clicked.connect(self.browse_upx)
        form_layout.addWidget(browse_upx_btn, row, 2)
        row += 1
        
        form_layout.addWidget(QLabel("PFX (sign):"), row, 0)
        form_layout.addWidget(self.fields["pfx_path"], row, 1)
        browse_pfx_btn = QPushButton("Tallózás")
        browse_pfx_btn.clicked.connect(self.browse_pfx)
        form_layout.addWidget(browse_pfx_btn, row, 2)
        row += 1
        
        form_layout.addWidget(QLabel("PFX password:"), row, 0)
        form_layout.addWidget(self.fields["pfx_pass"], row, 1, 1, 2)
        row += 1
        
        form_layout.addWidget(QLabel("Teljesítmény beállítások:"), row, 0)
        row += 1
        
        for option in self.performance_options.values():
            form_layout.addWidget(option, row, 0, 1, 3)
            row += 1
        
        main_layout.addWidget(form_group)
        
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setTextVisible(True)
        self.progress.setFormat("Készültség: %p%")
        self.progress.setStyleSheet("""
            QProgressBar {
                border: 2px solid #444;
                border-radius: 5px;
                text-align: center;
                background: #222;
                height: 20px;
                color: white;
            }
            QProgressBar::chunk {
                background: #4CAF50;
                width: 10px;
            }
        """)
        main_layout.addWidget(self.progress)
        
        self.start_button = QPushButton("🚀 Start")
        self.start_button.setStyleSheet(
            "QPushButton {"
            "   background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4CAF50, stop:1 #2E7D32);"
            "   color: white;"
            "   font-weight: bold;"
            "   font-size: 14px;"
            "   padding: 12px;"
            "   border-radius: 6px;"
            "   border: 1px solid #2E7D32;"
            "}"
            "QPushButton:hover {"
            "   background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #66BB6A, stop:1 #388E3C);"
            "}"
            "QPushButton:disabled {"
            "   background: #81C784;"
            "}"
        )
        self.start_button.clicked.connect(self.start_pipeline)
        main_layout.addWidget(self.start_button)
        
        log_group = QGroupBox("Napló")
        log_layout = QVBoxLayout(log_group)
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setStyleSheet(
            "background-color: #0A0A0A;"
            "font-family: Consolas;"
            "font-size: 11px;"
            "border: 1px solid #333;"
            "border-radius: 3px;"
        )
        log_layout.addWidget(self.log_text)
        
        main_layout.addWidget(log_group, 1)
        
        self.load_settings()
        
        self.high_priority = False
        self.max_memory = False
        self.gpu_acceleration = False
        self.parallel_processing = True
        self.auto_hidden_import = True
        self.auto_other_files = True
        self.windowed_mode = True  # Új: Konzol elrejtése opció

    def set_performance_theme(self):
        palette = QPalette()
        palette.setColor(QPalette.Window, QColor(30, 30, 30))
        palette.setColor(QPalette.WindowText, QColor(220, 220, 220))
        palette.setColor(QPalette.Base, QColor(20, 20, 20))
        palette.setColor(QPalette.AlternateBase, QColor(40, 40, 40))
        palette.setColor(QPalette.ToolTipBase, QColor(0, 170, 255))
        palette.setColor(QPalette.ToolTipText, Qt.white)
        palette.setColor(QPalette.Text, QColor(220, 220, 220))
        palette.setColor(QPalette.Button, QColor(50, 50, 50))
        palette.setColor(QPalette.ButtonText, QColor(220, 220, 220))
        palette.setColor(QPalette.BrightText, Qt.red)
        palette.setColor(QPalette.Highlight, QColor(0, 120, 215))
        palette.setColor(QPalette.HighlightedText, Qt.white)
        
        self.setPalette(palette)
        
        self.setStyleSheet("""
            QWidget {
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            QGroupBox {
                border: 1px solid #444;
                border-radius: 5px;
                margin-top: 1ex;
                padding-top: 12px;
                background-color: #252525;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top center;
                padding: 0 8px;
                background-color: transparent;
                color: #4CAF50;
                font-weight: bold;
            }
            QLineEdit,QComboBox{
                background-color: #1A1A1A;
                color: #DDD;
                border: 1px solid #444;
                border-radius: 3px;
                padding: 5px;
                selection-background-color: #2A82DA;
            }
            
            QComboBox QAbstractItemView {
                background-color: #1A1A1A;     
                color: #DDD;                      
                selection-background-color: #000; 
                selection-color: #DDD;             
                border: 1px solid #444;
            }
            QPushButton {
                background-color: #444;
                color: white;
                border-radius: 4px;
                padding: 6px 12px;
                border: 1px solid #555;
            }
            QPushButton:hover {
                background-color: #555;
                border: 1px solid #666;
            }
            QCheckBox {
                color: #CCC;
                spacing: 5px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
            }
            QLabel {
                color: #AAA;
            }
            QMessageBox {
            background-color: #0A0A0A;
        }
        QMessageBox QLabel {
            color: #FFFFFF;
            font-family: 'Segoe UI', Arial, sans-serif;
            font-size: 12px;
        }
        QMessageBox QPushButton {
            background-color: #444;
            color: white;
            border-radius: 4px;
            padding: 6px 12px;
            border: 1px solid #555;
        }
        QMessageBox QPushButton:hover {
            background-color: #555;
            border: 1px solid #666;
        }
        """)

    def log_message(self, message, color="default"):
        timestamp = time.strftime("%H:%M:%S")
        full_message = f"[{timestamp}] {message}"
        
        if color == "green":
            html = f'<font color="#4CAF50">{full_message}</font>'
        elif color == "red":
            html = f'<font color="#F44336">{full_message}</font>'
        elif color == "yellow":
            html = f'<font color="#FFC107">{full_message}</font>'
        elif color == "blue":
            html = f'<font color="#2196F3">{full_message}</font>'
        else:
            html = f'<font color="#CCCCCC">{full_message}</font>'
            
        self.log_text.append(html)
        self.log_text.verticalScrollBar().setValue(self.log_text.verticalScrollBar().maximum())

    def update_progress(self, value):
        self.progress.setValue(value)

    def browse_script(self):
        path, _ = QFileDialog.getOpenFileName(self, "Válassz Python scriptet", "", "Python Files (*.py)")
        if path:
            self.fields["script_path"].setText(path)
            # mindig a script mappanevét állítja be output_name-nek
            folder_name = os.path.basename(os.path.dirname(path))
            self.fields["output_name"].setText(folder_name)


    def browse_icon(self):
        path, _ = QFileDialog.getOpenFileName(self, "Válassz ICO fájlt", "", "ICO Files (*.ico)")
        if path:
            self.fields["icon_path"].setText(path)

    def browse_png(self):
        path, _ = QFileDialog.getOpenFileName(self, "Válassz PNG fájlt", "", "PNG Files (*.png)")
        if path:
            self.fields["png_path"].setText(path)

    def browse_upx(self):
        path = QFileDialog.getExistingDirectory(self, "Válassz UPX könyvtárat")
        if path:
            self.fields["upx_path"].setText(path)

    def browse_pfx(self):
        path, _ = QFileDialog.getOpenFileName(self, "Válassz PFX fájlt", "", "PFX Files (*.pfx)")
        if path:
            self.fields["pfx_path"].setText(path)

    def start_pipeline(self):
        self.high_priority = self.performance_options["high_priority"].isChecked()
        self.max_memory = self.performance_options["max_memory"].isChecked()
        self.gpu_acceleration = self.performance_options["gpu_acceleration"].isChecked()
        self.parallel_processing = self.performance_options["parallel_processing"].isChecked()
        self.auto_hidden_import = self.performance_options["auto_hidden_import"].isChecked()
        self.auto_other_files = self.performance_options["auto_other_files"].isChecked()
        # Új: Konzol elrejtése opció
        self.windowed_mode = self.performance_options["windowed_mode"].isChecked()
        
        self.log_message(f"=== TELJESÍTMÉNY BEÁLLÍTÁSOK ===", "yellow")
        self.log_message(f"Magas CPU prioritás: {'Igen' if self.high_priority else 'Nem'}", "default")
        self.log_message(f"Maximális memória: {'Igen' if self.max_memory else 'Nem'}", "default")
        self.log_message(f"GPU gyorsítás: {'Igen' if self.gpu_acceleration else 'Nem'}", "default")
        self.log_message(f"Párhuzamos feldolgozás: {'Igen' if self.parallel_processing else 'Nem'}", "default")
        self.log_message(f"Automatikus hidden import: {'Igen' if self.auto_hidden_import else 'Nem'}", "default")
        self.log_message(f"Automatikus fájl felismerés: {'Igen' if self.auto_other_files else 'Nem'}", "default")
        self.log_message(f"Konzol elrejtése (windowed): {'Igen' if self.windowed_mode else 'Nem'}", "default")  # Új
        self.log_message(f"Build mód: {self.fields['build_mode'].currentText()}", "default")
        
        self.save_settings()
        self.log_text.clear()
        self.progress.setValue(0)
        self.start_button.setEnabled(False)
        
        self.worker = BuildWorker(self)
        self.worker.log_signal.connect(self.log_message)
        self.worker.progress_signal.connect(self.update_progress)
        self.worker.finished.connect(self.pipeline_finished)
        self.worker.ask_missing_imports.connect(self.ask_missing_imports)
        self.worker.ask_additional_files.connect(self.ask_additional_files)
        self.worker.start()

    def pipeline_finished(self, success):
        self.start_button.setEnabled(True)
        
        if success:
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle("Siker")
            msg_box.setText("Pipeline sikeresen lefutott!")
            msg_box.setIcon(QMessageBox.Information)
            msg_box.exec_()
        else:
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle("Hiba")
            msg_box.setText("A build folyamat hibába futott. Nézd meg a naplót részletekért!")
            msg_box.setIcon(QMessageBox.Warning)
            msg_box.exec_()

    def ask_missing_imports(self, missing_imports):
        dlg = MissingImportsDialog(missing_imports, self)
        if dlg.exec_() == QDialog.Accepted:
            self.worker.missing_imports_response = True
            self.worker.missing_imports_list = dlg.get_selected_imports()
        else:
            self.worker.missing_imports_response = False
            self.worker.missing_imports_list = []

    def ask_additional_files(self, data_files, binary_files):
        dlg = MissingImportsDialog(data_files + binary_files, self)
        dlg.setWindowTitle("További fájlok kezelése")
        dlg.list_widget.clear()
        
        for file in data_files:
            item = QListWidgetItem(f"[ADAT] {file}")
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked)
            dlg.list_widget.addItem(item)
            
        for file in binary_files:
            item = QListWidgetItem(f"[BINÁRIS] {file}")
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked)
            dlg.list_widget.addItem(item)
        
        if dlg.exec_() == QDialog.Accepted:
            self.worker.additional_files_response = True
            self.worker.additional_files_list = [dlg.list_widget.item(i).text().split("] ")[1] 
                                         for i in range(dlg.list_widget.count()) 
                                         if dlg.list_widget.item(i).checkState() == Qt.Checked]
            self.worker.add_binary_files = [dlg.list_widget.item(i).text().split("] ")[1] 
                                    for i in range(dlg.list_widget.count()) 
                                    if dlg.list_widget.item(i).text().startswith("[BINÁRIS]") 
                                    and dlg.list_widget.item(i).checkState() == Qt.Checked]
        else:
            self.worker.additional_files_response = False
            self.worker.additional_files_list = []
            self.worker.add_binary_files = []

    def load_settings(self):
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                    for key, field in self.fields.items():
                        if key in data:
                            if isinstance(field, QComboBox):
                                index = field.findText(data[key])
                                if index >= 0:
                                    field.setCurrentIndex(index)
                            else:
                                field.setText(data[key])
                    
                    for option_key in self.performance_options:
                        if option_key in data:
                            self.performance_options[option_key].setChecked(data[option_key])
                    
            except:
                pass

    def save_settings(self):
        data = {}
        for key, field in self.fields.items():
            if isinstance(field, QComboBox):
                data[key] = field.currentText()
            else:
                data[key] = field.text()
        
        for option_key, option_widget in self.performance_options.items():
            data[option_key] = option_widget.isChecked()
        
        try:
            with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
        except:
            pass

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = BuildApp()
    window.show()
    sys.exit(app.exec_())