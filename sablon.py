import sys
import os
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QAction, QTabWidget, QWidget, 
    QVBoxLayout, QLabel, QSizePolicy, QFileDialog, QMessageBox
)
from PyQt5.QtGui import QIcon, QFont
from PyQt5.QtCore import Qt, QSize
import platform

# Import modules with error handling
modules = {}
module_names = ["egyes", "kettes", "harmas", "negyes", "otos"]

for module_name in module_names:
    try:
        module = __import__(module_name)
        modules[module_name] = module
    except ImportError as e:
        # Create dummy classes for missing modules
        class Dummy(QWidget):
            def __init__(self, parent=None):
                super().__init__(parent)
                layout = QVBoxLayout()
                layout.addWidget(QLabel(f"Modul {module_name} nem elérhető"))
                self.setLayout(layout)
        setattr(sys.modules[__name__], module_name.capitalize(), Dummy)

class MainApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Szita Fájlkezelő Suite 2025")
        self.setGeometry(100, 100, 1200, 900)
        self.setStyleSheet("""
            QMainWindow {
                background-color: #2c3e50;
                color: #ecf0f1;
            }
            QTabWidget::pane {
                border: 0;
            }
            QLabel#title {
                color: #ecf0f1;
                font-size: 28px;
                font-weight: bold;
            }
        """)
        
        # Beállítjuk az alkalmazás ikonját
        self.get_icon_path()
        self.icon_path = self.get_icon_path()
        if self.get_icon_path:
            self.setWindowIcon(QIcon(self.icon_path))
        self.init_ui()
        self.init_menu()

    def get_icon_path(self):
        base_path = getattr(sys, '_MEIPASS', os.path.abspath('.'))
        
        # Try .ico file (Windows)
        ico_path = os.path.join(base_path, 'icon.ico')
        if os.path.exists(ico_path):
            return ico_path
        
        # Try .png file (cross-platform)
        png_path = os.path.join(base_path, 'icon.png')
        if os.path.exists(png_path):
            return png_path
        
        return None

    def init_ui(self):
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout(central_widget)
        layout.setAlignment(Qt.AlignCenter)
        
        title = QLabel("Fájlkezelő Suite 2025", self)
        title.setObjectName("title")
        title.setAlignment(Qt.AlignCenter)
        title.setFont(QFont("Arial", 28, QFont.Bold))
        layout.addWidget(title)
        
        self.tabs = QTabWidget()
        self.tabs.setTabPosition(QTabWidget.West)
        self.tabs.setStyleSheet("""
            QTabBar::tab {
                background: #34495e;
                color: #ecf0f1;
                padding: 15px;
                margin: 2px;
                border-radius: 5px;
            }
            QTabBar::tab:selected {
                background: #1abc9c;
            }
        """)
        
        # Add tabs dynamically
        tab_data = [
            ("Fájl kezelő", "egyes", "FileCopyApp"),
            ("Fájlba kereső", "kettes", "FileSearchApp"),
            ("Médiafájlok", "harmas", "MediaFinder"),
            ("Hálózat", "negyes", "NetworkScanner"),
            ("Sig és exe gyártó", "otos", "BuildApp")
        ]
        
        for name, module_name, class_name in tab_data:
            if module_name in modules:
                module = modules[module_name]
                widget_class = getattr(module, class_name)
                self.tabs.addTab(widget_class(), name)
            else:
                dummy = QLabel(f"{name} modul nem elérhető")
                self.tabs.addTab(dummy, name)
        
        layout.addWidget(self.tabs)

    def init_menu(self):
        menubar = self.menuBar()
        menubar.setStyleSheet("""
            QMenuBar {
                background-color: #34495e;
                color: #ecf0f1;
                padding: 5px;
            }
            QMenuBar::item:selected {
                background: #1abc9c;
            }
            QMenu {
                background-color: #34495e;
                color: #ecf0f1;
            }
            QMenu::item:selected {
                background: #1abc9c;
            }
        """)
        
        file_menu = menubar.addMenu("Fájl")
        exit_action = QAction("Kilépés", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        tools_menu = menubar.addMenu("Eszközök")
        for i, (name, _, _) in enumerate([
            ("Fájl kezelő", "egyes", "FileCopyApp"),
            ("Fájlba kereső", "kettes", "FileSearchApp"),
            ("Médiafájlok", "harmas", "MediaFinder"),
            ("Hálózat", "negyes", "NetworkScanner"),
            ("Sig és exe gyártó", "otos", "BuildApp")
        ]):
            tools_menu.addAction(name, lambda idx=i: self.tabs.setCurrentIndex(idx))
        
        help_menu = menubar.addMenu("Segítség")
        about_action = QAction("Névjegy", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    def show_about(self):
        about_text = """
        <b>Fájlkezelő Suite 2025</b><br><br>
        Verzió: 1.0<br>
        Készült: Python 3.10 + PyQt5<br><br>
        <i>Teljes körű fájlkezelési megoldások</i>
        """
        QMessageBox.information(self, "Névjegy", about_text)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Windows DPI awareness
    if platform.system() == 'Windows':
        try:
            from ctypes import windll
            windll.shcore.SetProcessDpiAwareness(1)
        except:
            pass
    
    window = MainApp()
    window.show()
    sys.exit(app.exec_())
    
 # jó  --add-data egyes.py;.  --add-data kettes.py;.   --add-data harmas.py;.   --add-data negyes.py;.  --hidden-import docx   --hidden-import openpyxl   --hidden-import PyPDF2   --hidden-import PyQt5.QtMultimedia   --hidden-import PyQt5.QtMultimediaWidgets  --add-data otos.py;.  --hidden-import psutil --hidden-import GPUtil  --add-binary C:\Users\ap\AppData\Local\Programs\Python\Python313\Lib\site-packages\PyQt5\Qt5\plugins\imageformats;PyQt5\Qt5\plugins\multimedia   --add-binary C:\Users\ap\AppData\Local\Programs\Python\Python313\Lib\site-packages\PyQt5\Qt5\plugins\imageformats;PyQt5\Qt5\plugins\multimedia 

 #megy  pyinstaller --noconfirm --onefile --windowed `  --icon "C:\Users\ap\Downloads\favicon.ico" `  --upx-dir "D:\upx" `  --name "Szita suite" `  --add-data "egyes.py;." `  --add-data "kettes.py;." `  --add-data "harmas.py;." `  --add-data "negyes.py;." `  --hidden-import docx `  --hidden-import openpyxl `  --hidden-import PyPDF2 `  --hidden-import PyQt5.QtMultimedia `  --hidden-import PyQt5.QtMultimediaWidgets ` --add-data "otos.py;."  --hidden-import psutil --hidden-import GPUtil  --add-binary "C:\Users\ap\AppData\Local\Programs\Python\Python313\Lib\site-packages\PyQt5\Qt5\plugins\imageformats;PyQt5\Qt5\plugins\multimedia" `  --add-binary "C:\Users\ap\AppData\Local\Programs\Python\Python313\Lib\site-packages\PyQt5\Qt5\plugins\imageformats;PyQt5\Qt5\plugins\multimedia" `  --clean "sablon.py"