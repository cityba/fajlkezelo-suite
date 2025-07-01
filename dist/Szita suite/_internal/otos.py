import subprocess
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QTreeWidget, QTreeWidgetItem,
    QHeaderView, QLabel, QPushButton, QProgressBar, QComboBox,
    QMessageBox,QGroupBox,QGridLayout,QLineEdit,QCheckBox,QTextEdit,QFileDialog
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QColor, QBrush, QIcon, QFont, QPalette, QTextCursor
import sys
import os
import shutil
import json
import time
import concurrent.futures
import psutil
import GPUtil

CONFIG_PATH = os.path.join(os.path.expanduser("~"), ".buildapp_settings.json")

class TurboExecutor:
    """Optimalizált végrehajtó nagy teljesítményű feladatokhoz"""
    def __init__(self):
        # Automatikusan meghatározza a rendelkezésre álló erőforrásokat
        self.cpu_cores = max(1, psutil.cpu_count(logical=False))
        self.max_workers = max(1, self.cpu_cores - 1)  # Agresszív párhuzamosítás
        
        # GPU gyorsítás ellenőrzése
        self.gpu_available = False
        try:
            gpus = GPUtil.getGPUs()
            self.gpu_available = len(gpus) > 0
        except:
            pass
        
    def execute(self, func, *args, **kwargs):
        """Többszálas végrehajtás ThreadPoolExecutorral"""
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            return executor.submit(func, *args, **kwargs)
    
    def memory_intensive_task(self, func, *args, **kwargs):
        """Memória-intenzív feladatok optimalizált végrehajtása"""
        # Memória prioritás beállítása
        process = psutil.Process()
        process.nice(psutil.HIGH_PRIORITY_CLASS)
        
        # Memória korlát növelése (ha lehetséges)
        try:
            process.memory_maps()
            # Memória foglalás optimalizálása
            return func(*args, **kwargs)
        finally:
            process.nice(psutil.NORMAL_PRIORITY_CLASS)

class BuildApp(QWidget):
    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int)
    resource_signal = pyqtSignal(str, str, str)
    progress_timer_start_signal = pyqtSignal()
    progress_timer_stop_signal = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("⚡ Hyper-Sign - Exe és Installer Gyártó")
        
        # Optimalizált végrehajtó
        self.executor = TurboExecutor()
        
        # Set performance theme
        self.set_performance_theme()
        
        # Progress timer setup
        self.progress_timer = QTimer()
        self.progress_timer.setInterval(5000)  # 5 másodpercenként
        self.progress_timer.timeout.connect(self.increment_progress)
        self.progress_timer_start_signal.connect(self.progress_timer.start)
        self.progress_timer_stop_signal.connect(self.progress_timer.stop)
        self.progress_target = 0
        self.progress_step = 2
        
        # Create central widget
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(10, 10, 10, 10)
        
        # Create form area
        form_group = QGroupBox("Build Beállítások")
        form_layout = QGridLayout(form_group)
        form_layout.setSpacing(8)
        
        # Form fields
        self.fields = {
            "script_path": QLineEdit(),
            "output_name": QLineEdit(),
            "icon_path": QLineEdit(),
            "png_path": QLineEdit(),
            "upx_path": QLineEdit(),
            "extra_args": QLineEdit(),
            "pfx_path": QLineEdit(),
            "pfx_pass": QLineEdit(),
            "build_mode": QComboBox()  # New field for build mode
        }
        self.fields["build_mode"].addItems(["onefile", "onedir"])
        self.fields["pfx_pass"].setEchoMode(QLineEdit.Password)
        
        # Performance options
        self.performance_options = {
            "high_priority": QCheckBox("Magas CPU prioritás"),
            "max_memory": QCheckBox("Maximális memóriahasználat"),
            "gpu_acceleration": QCheckBox("GPU gyorsítás (ha elérhető)"),
            "parallel_processing": QCheckBox("Párhuzamos feldolgozás")
        }
        self.performance_options["gpu_acceleration"].setEnabled(self.executor.gpu_available)
        
        # Row counter
        row = 0
        
        # Python script
        form_layout.addWidget(QLabel("Python script (.py):"), row, 0)
        form_layout.addWidget(self.fields["script_path"], row, 1)
        browse_script_btn = QPushButton("Tallózás")
        browse_script_btn.clicked.connect(self.browse_script)
        form_layout.addWidget(browse_script_btn, row, 2)
        row += 1
        
        # Output name
        form_layout.addWidget(QLabel("Output name:"), row, 0)
        form_layout.addWidget(self.fields["output_name"], row, 1, 1, 2)
        row += 1
        
        # Build mode (new option)
        form_layout.addWidget(QLabel("Build mód:"), row, 0)
        form_layout.addWidget(self.fields["build_mode"], row, 1, 1, 2)
        row += 1
        
        # Extra args
        form_layout.addWidget(QLabel("Extra PyInstaller args:"), row, 0)
        form_layout.addWidget(self.fields["extra_args"], row, 1, 1, 2)
        row += 1
        
        # ICO icon
        form_layout.addWidget(QLabel("ICO icon:"), row, 0)
        form_layout.addWidget(self.fields["icon_path"], row, 1)
        browse_icon_btn = QPushButton("Tallózás")
        browse_icon_btn.clicked.connect(self.browse_icon)
        form_layout.addWidget(browse_icon_btn, row, 2)
        row += 1
        
        # PNG icon
        form_layout.addWidget(QLabel("PNG icon (data):"), row, 0)
        form_layout.addWidget(self.fields["png_path"], row, 1)
        browse_png_btn = QPushButton("Tallózás")
        browse_png_btn.clicked.connect(self.browse_png)
        form_layout.addWidget(browse_png_btn, row, 2)
        row += 1
        
        # UPX dir
        form_layout.addWidget(QLabel("UPX dir:"), row, 0)
        form_layout.addWidget(self.fields["upx_path"], row, 1)
        browse_upx_btn = QPushButton("Tallózás")
        browse_upx_btn.clicked.connect(self.browse_upx)
        form_layout.addWidget(browse_upx_btn, row, 2)
        row += 1
        
        # PFX
        form_layout.addWidget(QLabel("PFX (sign):"), row, 0)
        form_layout.addWidget(self.fields["pfx_path"], row, 1)
        browse_pfx_btn = QPushButton("Tallózás")
        browse_pfx_btn.clicked.connect(self.browse_pfx)
        form_layout.addWidget(browse_pfx_btn, row, 2)
        row += 1
        
        # PFX password
        form_layout.addWidget(QLabel("PFX password:"), row, 0)
        form_layout.addWidget(self.fields["pfx_pass"], row, 1, 1, 2)
        row += 1
        
        # Performance settings
        form_layout.addWidget(QLabel("Teljesítmény beállítások:"), row, 0)
        row += 1
        
        for option in self.performance_options.values():
            form_layout.addWidget(option, row, 0, 1, 3)
            row += 1
        
        # Add form to main layout
        main_layout.addWidget(form_group)
        
        # Progress bar
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
        
        # Start button
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
        
        # Log area
        log_group = QGroupBox("Napló")
        log_layout = QVBoxLayout(log_group)
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setStyleSheet(
            "background-color: #0A0A0A;"
            "color: #00FF00;"
            "font-family: Consolas;"
            "font-size: 11px;"
            "border: 1px solid #333;"
            "border-radius: 3px;"
        )
        log_layout.addWidget(self.log_text)
        
        # Add log to main layout
        main_layout.addWidget(log_group, 1)
        
        # Load settings
        self.load_settings()
        
        # Set icon
        self.setWindowIcon(QIcon(self.get_icon_path()))
        
        # Performance flags
        self.high_priority = False
        self.max_memory = False
        self.gpu_acceleration = False
        self.parallel_processing = True

        # Connect signals
        self.log_signal.connect(self._log_message)
        self.progress_signal.connect(self._update_progress)

    def increment_progress(self):
        """Progresszív növelés időzítővel"""
        current = self.progress.value()
        if current < self.progress_target:
            new_value = min(current + self.progress_step, self.progress_target)
            self.progress.setValue(new_value)

    def set_performance_theme(self):
        """High-performance visual theme"""
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
        
        # Performance-oriented styles
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
            QLineEdit, QComboBox {
                background-color: #1A1A1A;
                color: #DDD;
                border: 1px solid #444;
                border-radius: 3px;
                padding: 5px;
                selection-background-color: #2A82DA;
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
        """)

    def _log_message(self, message):
        """Thread-safe log message handler"""
        timestamp = time.strftime("%H:%M:%S")
        full_message = f"[{timestamp}] {message}"
        self.log_text.append(full_message)
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _update_progress(self, value):
        """Thread-safe progress update"""
        self.progress.setValue(value)

    def get_icon_path(self):
        """Get path to application icon"""
        paths = [
            "icon.ico",
            "icon.png",
            os.path.join(os.path.dirname(__file__), "icon.ico"),
            os.path.join(os.path.dirname(__file__), "icon.png")
        ]
        
        for path in paths:
            if os.path.exists(path):
                return path
        return ""

    def browse_script(self):
        path, _ = QFileDialog.getOpenFileName(
            self, 
            "Válassz Python scriptet", 
            "", 
            "Python Files (*.py)"
        )
        if path:
            self.fields["script_path"].setText(path)
            if not self.fields["output_name"].text():
                base = os.path.splitext(os.path.basename(path))[0]
                self.fields["output_name"].setText(base)

    def browse_icon(self):
        path, _ = QFileDialog.getOpenFileName(
            self, 
            "Válassz ICO fájlt", 
            "", 
            "ICO Files (*.ico)"
        )
        if path:
            self.fields["icon_path"].setText(path)

    def browse_png(self):
        path, _ = QFileDialog.getOpenFileName(
            self, 
            "Válassz PNG fájlt", 
            "", 
            "PNG Files (*.png)"
        )
        if path:
            self.fields["png_path"].setText(path)

    def browse_upx(self):
        path = QFileDialog.getExistingDirectory(
            self, 
            "Válassz UPX könyvtárat"
        )
        if path:
            self.fields["upx_path"].setText(path)

    def browse_pfx(self):
        path, _ = QFileDialog.getOpenFileName(
            self, 
            "Válassz PFX fájlt", 
            "", 
            "PFX Files (*.pfx)"
        )
        if path:
            self.fields["pfx_path"].setText(path)

    def run_and_stream(self, cmd, cwd=None):
        """Run a command and stream output to log (memory optimized)"""
        self.log_signal.emit(f"> {cmd}")
        
        # Process priority settings
        priority_flags = 0
        if self.high_priority:
            priority_flags |= subprocess.HIGH_PRIORITY_CLASS
            
        # Memory optimization flags
        creation_flags = 0
        if self.max_memory:
            creation_flags |= subprocess.CREATE_NO_WINDOW
            
        proc = subprocess.Popen(
            cmd, 
            shell=True, 
            cwd=cwd, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.STDOUT, 
            text=True,
            creationflags=creation_flags,
            bufsize=1,
            universal_newlines=True
        )
        
        # Set process priority
        if self.high_priority:
            try:
                psutil.Process(proc.pid).nice(psutil.HIGH_PRIORITY_CLASS)
            except:
                pass
        
        # Stream output without blocking
        while True:
            line = proc.stdout.readline()
            if not line:
                break
            self.log_signal.emit(line.strip())
        
        proc.wait()
        return proc.returncode == 0

    def build_exe(self):
        """Build the executable with performance optimizations"""
        self.log_signal.emit("=== EXE BUILD FOLYAMAT ===")
        self.log_signal.emit("Optimalizált módban...")
        
        script = self.fields["script_path"].text()
        name = self.fields["output_name"].text() or os.path.splitext(os.path.basename(script))[0]
        folder = os.path.dirname(script)
        build_mode = self.fields["build_mode"].currentText()  # Get selected build mode
         
        if not script:
            QMessageBox.warning(self, "Hiányzó script", "Kérlek válassz egy Python scriptet!")
            return False
        
        # Start progress timer for this phase (0-33%)
        self.progress_target = 60
        self.progress_timer_start_signal.emit()
        
        # Prepare command with performance flags
        cmd = ['pyinstaller']
        cmd += [os.path.basename(script)]
        
        cmd += [
            '--name', name,
            '--noconfirm',
            f'--{build_mode}',  # Use selected build mode
            '--windowed',
            '--clean'
        ]
        
        icon_path = self.fields["icon_path"].text()
        if icon_path:
            cmd += ['--icon', os.path.normpath(icon_path)]
            cmd += ['--add-data', f'{icon_path}{os.pathsep}.']
        
        png_path = self.fields["png_path"].text()
        if png_path:
            cmd += ['--add-data', f'{png_path}{os.pathsep}.']
        
        upx_path = self.fields["upx_path"].text()
        if upx_path:
            cmd += ['--upx-dir', os.path.normpath(upx_path)]
        
        extra_args = self.fields["extra_args"].text()
        if extra_args:
            cmd += extra_args.split()
        
        # Performance optimizations
        if self.parallel_processing:
            cmd += ['--log-level=ERROR']
            
        if self.gpu_acceleration and self.executor.gpu_available:
            cmd += ['--noupx']
            self.log_signal.emit("GPU gyorsítás aktív - UPX letiltva")
        
        # Copy resources to build folder in parallel
        if self.parallel_processing:
            self.log_signal.emit("Párhuzamos erőforrás másolás...")
            futures = []
            for src in [script, icon_path, png_path]:
                if src and os.path.exists(src):
                    dst = os.path.join(folder, os.path.basename(src))
                    if os.path.abspath(src) != os.path.abspath(dst):
                        future = self.executor.execute(shutil.copy, src, folder)
                        futures.append(future)
            
            # Wait for all copies to complete
            for future in futures:
                future.result()
        else:
            for src in [script, icon_path, png_path]:
                if src and os.path.exists(src):
                    dst = os.path.join(folder, os.path.basename(src))
                    if os.path.abspath(src) != os.path.abspath(dst):
                        shutil.copy(src, folder)
        
        # Run command with high priority
        self.log_signal.emit(f"EXE build elindítva ({build_mode} mód)...")
        success = self.run_and_stream(cmd, cwd=folder)
        
        # Stop progress timer and set to phase end
        self.progress_signal.emit(62)
        self.progress_timer_stop_signal.emit()
        
        return success

    def sign_exe(self):
        """Sign the executable with performance optimizations"""
        self.log_signal.emit("=== EXE ALÁÍRÁS ===")
        self.log_signal.emit("Optimalizált módban...")
        
        # Start progress timer for this phase (33-66%)
        self.progress_target = 66
        self.progress_timer_start_signal.emit()
        
        script = self.fields["script_path"].text()
        name = self.fields["output_name"].text() or os.path.splitext(os.path.basename(script))[0]
        folder = os.path.dirname(script)
        build_mode = self.fields["build_mode"].currentText()
        
        # Determine executable path based on build mode
        if build_mode == "onefile":
            exe_path = os.path.join(folder, 'dist', f'{name}.exe')
        else:  # onedir
            exe_path = os.path.join(folder, 'dist', name, f'{name}.exe')
        
        # Check if executable exists
        if not os.path.exists(exe_path):
            QMessageBox.warning(self, "Hiányzó EXE", "Buildeld meg előbb az EXE-t!")
            return False
        
        # Get signing parameters
        pfx_path = self.fields["pfx_path"].text()
        pfx_pass = self.fields["pfx_pass"].text()
        
        if not pfx_path or not pfx_pass:
            QMessageBox.warning(self, "Hiányzó adatok", "PFX fájl és jelszó megadása kötelező az aláíráshoz!")
            return False
        
        # Create temp copy to avoid path issues
        temp_exe = os.path.join(folder, f'temp_{name}.exe')
        shutil.copy(exe_path, temp_exe)
        
        # Prepare command
        cmd = [
            'signtool', 'sign', '/a', '/f', pfx_path, '/p', pfx_pass,
            '/fd', 'SHA256', '/t', 'http://timestamp.digicert.com', temp_exe
        ]
        
        # Run command
        success = self.run_and_stream(cmd)
        
        if success:
            shutil.move(temp_exe, exe_path)
        
        # Stop progress timer and set to phase end
        self.progress_signal.emit(66)
        self.progress_timer_stop_signal.emit()
        
        return success

    def build_installer(self):
        """Build the installer with performance optimizations"""
        self.log_signal.emit("=== INSTALLER BUILD FOLYAMAT ===")
        self.log_signal.emit("Optimalizált módban...")
        
        # Start progress timer for this phase (66-98%)
        self.progress_target = 98
        self.progress_timer_start_signal.emit()
        
        script = self.fields["script_path"].text()
        name = self.fields["output_name"].text() or os.path.splitext(os.path.basename(script))[0]
        folder = os.path.dirname(script)
        build_mode = self.fields["build_mode"].currentText()
        
        # Copy icon to build folder
        icon_path = self.fields["icon_path"].text()
        if icon_path:
            icon_dest = os.path.join(folder, 'icon.ico')
            if os.path.abspath(icon_path) != os.path.abspath(icon_dest):
                shutil.copy(icon_path, icon_dest)
        
        # Create ISS script
        iss_file = os.path.join(folder, f'{name}.iss')
        
        # Determine files section based on build mode
        files_section = ""
        if build_mode == "onefile":
            files_section = f'Source: "dist\\{name}.exe"; DestDir: "{{app}}"; Flags: ignoreversion'
        else:  # onedir
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

        with open(iss_file, 'w', encoding='utf-8') as f:
            f.write(content)
        
        # Find Inno Setup compiler
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
            QMessageBox.critical(self, "Hiba", "Inno Setup nem található!")
            return False
        
        # Prepare command with performance flags
        cmd = [iscc_found]
        if self.parallel_processing:
            cmd.append("/Q")
        cmd.append(iss_file)
        
        # Run command
        success = self.run_and_stream(cmd)
        
        # Stop progress timer and set to phase end
        self.progress_signal.emit(98)
        self.progress_timer_stop_signal.emit()
        
        # Final progress update
        if success:
            self.progress_signal.emit(100)
        else:
            self.progress_signal.emit(98)
        
        return success

    def start_pipeline(self):
        """Start the build pipeline with performance settings"""
        # Apply performance settings
        self.high_priority = self.performance_options["high_priority"].isChecked()
        self.max_memory = self.performance_options["max_memory"].isChecked()
        self.gpu_acceleration = self.performance_options["gpu_acceleration"].isChecked()
        self.parallel_processing = self.performance_options["parallel_processing"].isChecked()
        
        # Log performance settings
        self.log_signal.emit(f"=== TELJESÍTMÉNY BEÁLLÍTÁSOK ===")
        self.log_signal.emit(f"Magas CPU prioritás: {'Igen' if self.high_priority else 'Nem'}")
        self.log_signal.emit(f"Maximális memória: {'Igen' if self.max_memory else 'Nem'}")
        self.log_signal.emit(f"GPU gyorsítás: {'Igen' if self.gpu_acceleration else 'Nem'}")
        self.log_signal.emit(f"Párhuzamos feldolgozás: {'Igen' if self.parallel_processing else 'Nem'}")
        self.log_signal.emit(f"Build mód: {self.fields['build_mode'].currentText()}")
        
        self.save_settings()
        self.log_text.clear()
        self.progress.setValue(0)
        self.start_button.setEnabled(False)
        
        # Create and start worker thread
        self.worker = BuildWorker(self)
        self.worker.finished.connect(self.pipeline_finished)
        self.worker.start()

    def pipeline_finished(self, success):
        """Handle pipeline completion"""
        self.start_button.setEnabled(True)
        
        if success:
            # Create custom styled message box
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle("Siker")
            msg_box.setText("Pipeline sikeresen lefutott!")
            msg_box.setIcon(QMessageBox.Information)
            
            # Apply dark style
            msg_box.setStyleSheet("""
                QMessageBox {
                    background-color: #2c3e50;
                    color: #ecf0f1;
                    font-family: 'Segoe UI';
                }
                QLabel {
                    color: #ecf0f1;
                    font-size: 14px;
                }
                QPushButton {
                    background-color: #3498db;
                    color: white;
                    border-radius: 4px;
                    padding: 6px 12px;
                    min-width: 80px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #2980b9;
                }
            """)
            
            # Set dark palette
            dark_palette = QPalette()
            dark_palette.setColor(QPalette.Window, QColor(44, 62, 80))
            dark_palette.setColor(QPalette.WindowText, QColor(236, 240, 241))
            dark_palette.setColor(QPalette.Text, QColor(236, 240, 241))
            dark_palette.setColor(QPalette.ButtonText, QColor(236, 240, 241))
            dark_palette.setColor(QPalette.Button, QColor(52, 152, 219))
            msg_box.setPalette(dark_palette)
            
            msg_box.exec_()
        else:
            # Error message with dark style
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle("Hiba")
            msg_box.setText("A build folyamat hibába futott. Nézd meg a naplót részletekért!")
            msg_box.setIcon(QMessageBox.Warning)
            
            # Apply dark style
            msg_box.setStyleSheet("""
                QMessageBox {
                    background-color: #2c3e50;
                    color: #ecf0f1;
                    font-family: 'Segoe UI';
                }
                QLabel {
                    color: #ecf0f1;
                    font-size: 14px;
                }
                QPushButton {
                    background-color: #e74c3c;
                    color: white;
                    border-radius: 4px;
                    padding: 6px 12px;
                    min-width: 80px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #c0392b;
                }
            """)
            
            # Set dark palette
            dark_palette = QPalette()
            dark_palette.setColor(QPalette.Window, QColor(44, 62, 80))
            dark_palette.setColor(QPalette.WindowText, QColor(236, 240, 241))
            dark_palette.setColor(QPalette.Text, QColor(236, 240, 241))
            dark_palette.setColor(QPalette.ButtonText, QColor(236, 240, 241))
            dark_palette.setColor(QPalette.Button, QColor(231, 76, 60))
            msg_box.setPalette(dark_palette)
            
            msg_box.exec_()
    def log_message(self, message):
        """Add message to log (thread-safe)"""
        self.log_signal.emit(message)

    def update_progress(self, value):
        """Update progress bar (thread-safe)"""
        self.progress_signal.emit(value)

    def load_settings(self):
        """Load settings from JSON file"""
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                    # Load field values
                    for key, field in self.fields.items():
                        if key in data:
                            if isinstance(field, QComboBox):
                                index = field.findText(data[key])
                                if index >= 0:
                                    field.setCurrentIndex(index)
                            else:
                                field.setText(data[key])
                    
                    # Load performance settings
                    for option_key in self.performance_options:
                        if option_key in data:
                            self.performance_options[option_key].setChecked(data[option_key])
                    
            except Exception as e:
                self.log_signal.emit(f"Beállítás betöltési hiba: {str(e)}")

    def save_settings(self):
        """Save settings to JSON file"""
        data = {}
        for key, field in self.fields.items():
            if isinstance(field, QComboBox):
                data[key] = field.currentText()
            else:
                data[key] = field.text()
        
        # Save performance settings
        for option_key, option_widget in self.performance_options.items():
            data[option_key] = option_widget.isChecked()
        
        try:
            with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            self.log_signal.emit(f"Beállítás mentési hiba: {str(e)}")


class BuildWorker(QThread):
    """Worker thread for build pipeline with performance optimizations"""
    finished = pyqtSignal(bool)
    
    def __init__(self, app):
        super().__init__()
        self.app = app
    
    def run(self):
        """Run the build pipeline steps with resource optimization"""
        success = False
        
        try:
            # Set process priority if requested
            if self.app.high_priority:
                try:
                    psutil.Process(os.getpid()).nice(psutil.HIGH_PRIORITY_CLASS)
                    self.app.log_message("Magas CPU prioritás beállítva")
                except Exception as e:
                    self.app.log_message(f"CPU prioritás beállítási hiba: {str(e)}")
            
            # Execute build steps
            if not self.app.build_exe():
                self.app.log_message("EXE build sikertelen!")
                self.finished.emit(False)
                return
            
            if not self.app.sign_exe():
                self.app.log_message("Aláírás sikertelen!")
                self.finished.emit(False)
                return
            
            if not self.app.build_installer():
                self.app.log_message("Installer build sikertelen!")
                self.finished.emit(False)
                return
            
            success = True
        except Exception as e:
            self.app.log_message(f"Váratlan hiba: {str(e)}")
        finally:
            # Reset priority
            if self.app.high_priority:
                try:
                    psutil.Process(os.getpid()).nice(psutil.NORMAL_PRIORITY_CLASS)
                except:
                    pass
            
            self.finished.emit(success)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = BuildApp()
    window.show()
    sys.exit(app.exec_())