import sys
import os
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QAction, QStackedWidget, QWidget, 
    QVBoxLayout, QHBoxLayout, QLabel, QFileDialog, QMessageBox, QPushButton
)
from PyQt5.QtGui import QIcon, QFont
from PyQt5.QtCore import Qt
import platform

# --- PROFI EXE MODUL FIX (PYTHON 3.13+) ---
if getattr(sys, 'frozen', False):
    if hasattr(os, 'add_dll_directory'):
        os.add_dll_directory(sys._MEIPASS)
    os.environ['PATH'] = sys._MEIPASS + os.pathsep + os.environ.get('PATH', '')

# Modulok importálása
modules = {}
module_names = ["egyes", "kettes", "harmas", "negyes", "otos", "hatos", "hetes", "nyolc", "kilenc"]

for module_name in module_names:
    try:
        module = __import__(module_name)
        modules[module_name] = module
    except ImportError:
        class Dummy(QWidget):
            def __init__(self, parent=None):
                super().__init__(parent)
                l = QVBoxLayout(self)
                l.addWidget(QLabel(f"Modul {module_name} nem elérhető"))
        setattr(sys.modules[__name__], module_name.capitalize(), Dummy)

class MainApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Szita Fájlkezelő Suite 2025")
        self.setGeometry(100, 100, 1300, 900)
        self.setStyleSheet("QMainWindow { background-color: #2c3e50; }")
        
        self.init_ui()
        self.init_menu()

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        
        # 1. FŐCÍM
        title = QLabel("Fájlkezelő Suite 2025")
        title.setStyleSheet("color: #ecf0f1; font-size: 24px; font-weight: bold; margin: 10px;")
        title.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title)
        
        # 2. VÍZSZINTES GOMBSOR (Navigation Bar)
        nav_container = QWidget()
        nav_layout = QHBoxLayout(nav_container)
        nav_layout.setContentsMargins(5, 5, 5, 5)
        nav_layout.setSpacing(8)
        
        # 3. STACKED WIDGET (A tartalomnak, fülek nélkül)
        self.content_stack = QStackedWidget()
        
        tab_data = [
            ("Fájl kezelő", "egyes", "FileCopyApp"),
            ("Fájlba kereső", "kettes", "FileSearchApp"),
            ("Fájlkereső/Törlő", "nyolc", "FileFinderApp"),
            ("Mappa Összehasonlító", "kilenc", "ProFolderDiff"),
            ("Média", "harmas", "MediaFinder"),
            ("Hálózat", "negyes", "NetworkScanner"),
            ("EXE készítő", "otos", "BuildApp"),
            ("EXE elemző", "hatos", "ProcessMonitorApp"),
            ("SQL kezelő", "hetes", "DatabaseBrowser"),
        ]
        
        btn_style = """
            QPushButton {
                background-color: #34495e;
                color: #ecf0f1;
                border: 2px solid #2c3e50;
                padding: 8px 15px;
                font-weight: bold;
                border-radius: 5px;
            }
            QPushButton:hover { background-color: #1abc9c; border-color: #16a085; }
            QPushButton:pressed { background-color: #16a085; }
        """

        for i, (name, module_name, class_name) in enumerate(tab_data):
            # Navigációs gomb
            btn = QPushButton(name)
            btn.setStyleSheet(btn_style)
            btn.clicked.connect(lambda checked, idx=i: self.content_stack.setCurrentIndex(idx))
            nav_layout.addWidget(btn)
            
            # Widget példányosítás
            if module_name in modules:
                try:
                    widget = getattr(modules[module_name], class_name)()
                    self.content_stack.addWidget(widget)
                except Exception as e:
                    self.content_stack.addWidget(QLabel(f"Hiba a {name} betöltésekor: {e}"))
            else:
                lbl = QLabel(f"Hiányzó modul: {module_name}")
                lbl.setAlignment(Qt.AlignCenter)
                self.content_stack.addWidget(lbl)
        
        main_layout.addWidget(nav_container)
        main_layout.addWidget(self.content_stack)

    def init_menu(self):
        menubar = self.menuBar()
        menubar.setStyleSheet("QMenuBar { background-color: #34495e; color: #ecf0f1; }")
        file_menu = menubar.addMenu("Fájl")
        exit_act = QAction("Kilépés", self)
        exit_act.triggered.connect(self.close)
        file_menu.addAction(exit_act)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    if platform.system() == 'Windows':
        try:
            from ctypes import windll
            windll.shcore.SetProcessDpiAwareness(1)
        except: pass
    window = MainApp()
    window.show()
    sys.exit(app.exec_())
 
 #   --add-data egyes.py;.  --add-data kettes.py;.   --add-data harmas.py;.   --add-data negyes.py;.   --add-data otos.py;.    --add-data hatos.py;.  --add-data hetes.py;.  --add-data nyolc.py;. --add-data kilenc.py;. --hidden-import=PyQt5.QtNetwork --hidden-import=PyQt5.QtPrintSupport --hidden-import=appdirs --hidden-import matplotlib.backends.backend_qt5agg --hidden-import matplotlib.backends.qt_compat  --hidden-import pefile --hidden-import numpy   --hidden-import pyodbc  --hidden-import mysql.connector --hidden-import docx   --hidden-import openpyxl   --hidden-import PyPDF2   --hidden-import PyQt5.QtMultimedia   --hidden-import PyQt5.QtMultimediaWidgets --hidden-import psutil --hidden-import GPUtil  --add-binary C:\Users\ap\AppData\Local\Programs\Python\Python313\Lib\site-packages\PyQt5\Qt5\plugins\imageformats;PyQt5\Qt5\plugins\multimedia  
r"""
pyinstaller --noconfirm --onedir --windowed --clean `
--name "Szita-suite" `
--icon "C:\Users\ap\Documents\fajlkezelo-suite\icon.ico" `
--upx-dir "D:\upx\upx-5.0.1-win64" `
--add-data "egyes.py;." `
--add-data "kettes.py;." `
--add-data "harmas.py;." `
--add-data "negyes.py;." `
--add-data "otos.py;." `
--add-data "hatos.py;." `
--add-data "hetes.py;." `
--add-data "hetesregi.py;." `
--add-data "nyolc.py;." `
--add-data "kilenc.py;." `
--add-data "profiles.json;." `
--add-data "C:/Users/ap/Documents/fajlkezelo-suite/icon.ico;." `
--add-data "C:/Users/ap/Documents/fajlkezelo-suite/icon.png;." `
--hidden-import=mysql.connector `
--hidden-import=mysql.connector.locales.eng.client_error `
--hidden-import=pyodbc `
--hidden-import=PyQt5.QtNetwork `
--hidden-import=PyQt5.QtPrintSupport `
--hidden-import=PyQt5.QtMultimedia `
--hidden-import=PyQt5.QtMultimediaWidgets `
--hidden-import=matplotlib.backends.backend_qt5agg `
--hidden-import=matplotlib.backends.qt_compat `
--hidden-import=appdirs `
--hidden-import=pefile `
--hidden-import=numpy `
--hidden-import=pandas `
--hidden-import=docx `
--hidden-import=openpyxl `
--hidden-import=PyPDF2 `
--hidden-import=psutil `
--hidden-import=GPUtil `
--collect-all mysql.connector `
--collect-all pyodbc `
"sablon.py"
"""