# hatos.py - SQL adatbázis kezelő modul
import os
import json
import csv
import sys
import subprocess
import tempfile
import pyodbc
import mysql.connector
import platform
import appdirs
import winreg
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QTreeWidget, QTreeWidgetItem,
    QListWidget, QPushButton, QLabel, QMessageBox, QDialog, QLineEdit,
    QComboBox, QMenu, QAction, QInputDialog, QHeaderView, QFileDialog,
    QGridLayout, QApplication, QStyle, QStyleFactory, QCheckBox, QProgressDialog
)
from PyQt5.QtCore import Qt, QDateTime, QProcess
from PyQt5.QtGui import QFont, QColor, QPalette

PROFILE_FILE = "db_profiles.json"

class SmartTreeWidgetItem(QTreeWidgetItem):
    def __lt__(self, other):
        column = self.treeWidget().sortColumn()
        try:
            # Próbáljuk meg float-ként értelmezni
            return float(self.text(column)) < float(other.text(column))
        except ValueError:
            try:
                # Próbáljuk meg dátumként értelmezni
                d1 = QDateTime.fromString(self.text(column), Qt.ISODate)
                d2 = QDateTime.fromString(other.text(column), Qt.ISODate)
                if d1.isValid() and d2.isValid():
                    return d1 < d2
            except:
                pass
        # Alapértelmezett: szöveges rendezés
        return self.text(column) < other.text(column)

class DatabaseBrowser(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        # Alkalmazás adatkönyvtárának meghatározása
        self.app_data_dir = appdirs.user_data_dir("HATOS", "Szita")
        os.makedirs(self.app_data_dir, exist_ok=True)
        
        # MySQL worker szkript elérési útja
        self.MYSQL_WORKER_SCRIPT = self.get_mysql_worker_path()
        
        self.setWindowTitle("HATOS SQL Adatbázis Kezelő")
        self.setMinimumSize(1200, 800)
        self.profiles = self.load_profiles()
        
        # Alapértelmezett beállítások
        self.db_settings = {
            "engine": "MSSQL",
            "server": "localhost\\SQLEXPRESS",
            "user": "Swiet",
            "password": "Swiet123",
            "database": "Swiet",
            "windows_auth": False
        }
        
        if self.profiles:
            first_key = sorted(self.profiles.keys())[0]
            self.db_settings = self.profiles[first_key]
            # Kompatibilitás régebbi profilokkal
            if "windows_auth" not in self.db_settings:
                self.db_settings["windows_auth"] = False
        
        self.conn = None
        self.cursor = None
        self.current_table = ""
        self.aktualis_tabla_oszlopai = []
        self.mysql_worker = None
        self.mysql_process = None
        self.textst = ""  # A külső folyamat kimenetének tárolására
        
        self.init_ui()
        self.apply_styles()
        self.connect_to_db()

    def get_mysql_worker_path(self):
        """Visszaadja a MySQL worker szkript elérési útját"""
        # Ha EXE-ből futunk, az alkalmazás mappáját használjuk
        #if getattr(sys, 'frozen', False):
        #    base_dir = os.path.dirname(sys.executable)
        #    return os.path.join(base_dir, "mysql_worker.py")
        # Pythonból futtatáskor az app adatkönyvtár
        return os.path.join(self.app_data_dir, "mysql_worker.py")

    def load_profiles(self):
        profile_path = os.path.join(self.app_data_dir, PROFILE_FILE)
        if os.path.exists(profile_path):
            try:
                with open(profile_path, 'r', encoding='utf-8') as f:
                    profiles = json.load(f)
                    
                    # Kompatibilitás régebbi profilokkal
                    for name, settings in profiles.items():
                        if "windows_auth" not in settings:
                            settings["windows_auth"] = False
                    
                    return profiles
            except Exception as e:
                print(f"Profil betöltési hiba: {str(e)}")
                return {}
        return {}

    def save_profiles(self):
        profile_path = os.path.join(self.app_data_dir, PROFILE_FILE)
        try:
            with open(profile_path, 'w', encoding='utf-8') as f:
                json.dump(self.profiles, f, indent=4)
        except Exception as e:
            print(f"Profil mentési hiba: {str(e)}")
    
    def create_mysql_worker_script(self):
        """Létrehozza a MySQL worker szkriptet az alkalmazás adatkönyvtárában"""
        # Ha már létezik, nem kell létrehozni
        if os.path.exists(self.MYSQL_WORKER_SCRIPT):
            return
        
        try:
            with open(self.MYSQL_WORKER_SCRIPT, 'w', encoding='utf-8') as f:
                f.write("""import sys
import os
import json
import mysql.connector
from mysql.connector import errorcode

def run_command(settings, command, *args):
    try:
        conn = mysql.connector.connect(
            host=settings['server'],
            user=settings['user'],
            password=settings['password'],
            database=settings['database']
        )
        cursor = conn.cursor()
        
        result = {}
        
        if command == 'connect':
            # Csak a kapcsolat tesztelése
            result['status'] = 'success'
            result['message'] = 'Sikeres kapcsolódás'
        
        elif command == 'get_tables':
            cursor.execute("SHOW TABLES")
            tables = [row[0] for row in cursor.fetchall()]
            result['tables'] = tables
        
        elif command == 'get_table_data':
            table_name = args[0]
            cursor.execute(f"SELECT * FROM `{table_name}` LIMIT 500")
            columns = [desc[0] for desc in cursor.description]
            rows = cursor.fetchall()
            
            # Konvertáljuk az adatokat JSON-kompatibilis formátumba
            converted_rows = []
            for row in rows:
                converted_row = []
                for value in row:
                    if value is None:
                        converted_row.append(None)
                    elif isinstance(value, (bytes, bytearray)):
                        converted_row.append("<BINÁRIS ADAT>")
                    else:
                        converted_row.append(str(value))
                converted_rows.append(converted_row)
            
            result['columns'] = columns
            result['rows'] = converted_rows
        
        elif command == 'execute_query':
            query = args[0]
            cursor.execute(query)
            if query.strip().lower().startswith('select'):
                columns = [desc[0] for desc in cursor.description]
                rows = cursor.fetchall()
                
                converted_rows = []
                for row in rows:
                    converted_row = []
                    for value in row:
                        if value is None:
                            converted_row.append(None)
                        elif isinstance(value, (bytes, bytearray)):
                            converted_row.append("<BINÁRIS ADAT>")
                        else:
                            converted_row.append(str(value))
                    converted_rows.append(converted_row)
                
                result['columns'] = columns
                result['rows'] = converted_rows
            else:
                conn.commit()
                result['rowcount'] = cursor.rowcount
                result['status'] = 'success'
        
        elif command == 'delete_row':
            table_name = args[0]
            pk_col = args[1]
            pk_value = args[2]
            query = f"DELETE FROM `{table_name}` WHERE `{pk_col}` = %s"
            cursor.execute(query, (pk_value,))
            conn.commit()
            result['rowcount'] = cursor.rowcount
            result['status'] = 'success'
        
        elif command == 'update_cell':
            table_name = args[0]
            pk_col = args[1]
            pk_value = args[2]
            col_name = args[3]
            new_value = args[4]
            query = f"UPDATE `{table_name}` SET `{col_name}` = %s WHERE `{pk_col}` = %s"
            cursor.execute(query, (new_value, pk_value))
            conn.commit()
            result['rowcount'] = cursor.rowcount
            result['status'] = 'success'
        
        elif command == 'update_record':
            table_name = args[0]
            pk_col = args[1]
            pk_value = args[2]
            updates = args[3]
            
            set_parts = []
            params = []
            for col_name, new_value in updates.items():
                set_parts.append(f"`{col_name}` = %s")
                params.append(new_value)
            params.append(pk_value)
            
            query = f"UPDATE `{table_name}` SET {', '.join(set_parts)} WHERE `{pk_col}` = %s"
            cursor.execute(query, params)
            conn.commit()
            result['rowcount'] = cursor.rowcount
            result['status'] = 'success'
        
        elif command == 'drop_table':
            table_name = args[0]
            query = f"DROP TABLE `{table_name}`"
            cursor.execute(query)
            conn.commit()
            result['status'] = 'success'
        
        cursor.close()
        conn.close()
        return result
    
    except mysql.connector.Error as err:
        return {
            'status': 'error',
            'error_code': err.errno,
            'error_message': err.msg
        }
    except Exception as e:
        return {
            'status': 'error',
            'error_message': str(e)
        }

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Hibás argumentumok")
        sys.exit(1)

    arg1 = sys.argv[1]
    if os.path.isfile(arg1):
        with open(arg1, "r", encoding="utf-8") as f:
            settings = json.load(f)
    else:
        settings = json.loads(arg1)
 

    command = sys.argv[2]
    args = sys.argv[3:]

    result = run_command(settings, command, *args)
    print(json.dumps(result))

""")
            print(f"MySQL worker szkript létrehozva: {self.MYSQL_WORKER_SCRIPT}")
        except Exception as e:
            QMessageBox.critical(self, "Hiba", f"A MySQL worker szkript létrehozása sikertelen: {str(e)}")

    def find_system_python(self):
        """Megkeresi a rendszerbeli Python elérési útját"""
        # Próbálkozás a PATH-ból
        for path in os.environ["PATH"].split(os.pathsep):
            python_path = os.path.join(path, "python.exe")
            if os.path.isfile(python_path):
                return python_path
        
        # Platform-specifikus keresés
        if platform.system() == "Windows":
            # Gyakori telepítési helyek
            for version in ["3.11", "3.10", "3.9", "3.8"]:
                paths = [
                    f"C:\\Python{version}\\python.exe",
                    f"C:\\Program Files\\Python{version}\\python.exe",
                    f"C:\\Program Files (x86)\\Python{version}\\python.exe"
                ]
                for path in paths:
                    if os.path.isfile(path):
                        return path
        
        # Regisztrációs adatbázis keresése Windows-on
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Python\PythonCore") as key:
                for i in range(winreg.QueryInfoKey(key)[0]):
                    subkey_name = winreg.EnumKey(key, i)
                    try:
                        with winreg.OpenKey(key, subkey_name + r"\InstallPath") as install_key:
                            install_path = winreg.QueryValue(install_key, "")
                            python_path = os.path.join(install_path, "python.exe")
                            if os.path.isfile(python_path):
                                return python_path
                    except:
                        continue
        except:
            pass
        
        return None

    def read_stdout(self):             
        self.textst = bytes(self.mysql_process.readAllStandardOutput()).decode('utf-8')
    
    def run_mysql_command(self, command, *args):
        """MySQL parancs futtatása külső folyamatban"""
        
        if not self.mysql_process or self.mysql_process.state() == QProcess.NotRunning:
            self.mysql_process = QProcess(self)
            self.mysql_process.finished.connect(self.handle_mysql_result)
            self.mysql_process.readyReadStandardOutput.connect(self.read_stdout)
            

        settings_json = json.dumps(self.db_settings)

        with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8", suffix=".json") as f:
            f.write(settings_json)
            f.flush()
            settings_file = f.name

        cmd_args = [settings_file, command] + list(args)
        
        # Környezet detektálása és megfelelő Python interpreter kiválasztása
        if getattr(sys, 'frozen', False):
            # EXE környezet - rendszerbeli Python keresése
            python_exe = self.find_system_python()
            if not python_exe:
                QMessageBox.critical(self, "Hiba", "Nem található Python interpreter!")
                return None
            
            # EXE esetén csak a szkriptet és a paramétereket adjuk át
            self.mysql_process.start(python_exe, [self.MYSQL_WORKER_SCRIPT] + cmd_args)
        else:
            # Normál Python környezet
            self.mysql_process.start(sys.executable, [self.MYSQL_WORKER_SCRIPT] + cmd_args)
        
        # Várakozás a folyamat befejezésére (max 30 másodperc)
        if not self.mysql_process.waitForFinished(30000):
             
            QMessageBox.critical(self, "Időtúllépés", "A MySQL művelet túl sokáig tartott.")
            return None
        
         
        
        try:
            result = json.loads(self.textst)
            
            if 'status' in result and result['status'] == 'error':
                QMessageBox.critical(self, "MySQL Hiba", 
                                    f"Hiba kód: {result.get('error_code', 'N/A')}\n"
                                    f"Hibaüzenet: {result.get('error_message', 'Ismeretlen hiba')}")
                return None
            return result
        except json.JSONDecodeError:
            QMessageBox.critical(self, "Hiba", f"Érvénytelen JSON válasz: {self.textst}")
            return None
 

    def handle_mysql_result(self, exit_code, exit_status):
        """Feldolgozza a MySQL folyamat eredményét"""
         
        
        if exit_status != QProcess.NormalExit or exit_code != 0:
            error = self.mysql_process.readAllStandardError().data().decode('utf-8')
            QMessageBox.critical(self, "Folyamat Hiba", 
                                f"A MySQL folyamat hibával kilépett.\n"
                                f"Kilépési kód: {exit_code}\n"
                                f"Hibaüzenet: {error}")

    def apply_styles(self):
        # Modern stílus alkalmazása
        QApplication.setStyle(QStyleFactory.create("Fusion"))
        
        # Színpaletta beállítása
        palette = QPalette()
        palette.setColor(QPalette.Window, QColor(240, 240, 240))
        palette.setColor(QPalette.WindowText, QColor(0, 0, 0))
        palette.setColor(QPalette.Base, QColor(255, 255, 255))
        palette.setColor(QPalette.AlternateBase, QColor(233, 241, 255))
        palette.setColor(QPalette.ToolTipBase, QColor(255, 255, 255))
        palette.setColor(QPalette.ToolTipText, QColor(0, 0, 0))
        palette.setColor(QPalette.Text, QColor(0, 0, 0))
        palette.setColor(QPalette.Button, QColor(240, 240, 240))
        palette.setColor(QPalette.ButtonText, QColor(0, 0, 0))
        palette.setColor(QPalette.BrightText, QColor(255, 0, 0))
        palette.setColor(QPalette.Highlight, QColor(76, 163, 224))
        palette.setColor(QPalette.HighlightedText, QColor(255, 255, 255))
        self.setPalette(palette)
        
        # Általános stílusok
        self.setStyleSheet("""
            QWidget {
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 10pt;
            }
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
                min-width: 100px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
            QPushButton#danger {
                background-color: #f44336;
            }
            QPushButton#danger:hover {
                background-color: #d32f2f;
            }
            QPushButton#info {
                background-color: #2196F3;
            }
            QPushButton#info:hover {
                background-color: #0b7dda;
            }
            QPushButton#warning {
                background-color: #ff9800;
            }
            QPushButton#warning:hover {
                background-color: #e68a00;
            }
            QLabel {
                font-weight: bold;
                color: #333333;
            }
            QListWidget, QTreeWidget {
                background-color: white;
                border: 1px solid #cccccc;
                border-radius: 4px;
            }
            QListWidget::item:selected, QTreeWidget::item:selected {
                background-color: #4CAF50;
                color: white;
            }
            QHeaderView::section {
                background-color: #e0e0e0;
                padding: 4px;
                border: 1px solid #cccccc;
            }
            QSplitter::handle {
                background-color: #cccccc;
            }
        """)

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(12)
        main_layout.setContentsMargins(15, 15, 15, 15)
        
        # Felső sáv - gyorsműveletek
        top_layout = QHBoxLayout()
        top_layout.setSpacing(10)
        
        self.settings_btn = QPushButton("Beállítások")
        self.settings_btn.setObjectName("info")
        self.settings_btn.setIcon(self.style().standardIcon(QStyle.SP_FileDialogDetailedView))
        self.settings_btn.clicked.connect(self.open_settings)
        top_layout.addWidget(self.settings_btn)
        
        self.table_label = QLabel("Nincs kiválasztott tábla")
        self.table_label.setFont(QFont("Arial", 10, QFont.Bold))
        top_layout.addWidget(self.table_label, 1)
        
        self.export_btn = QPushButton("Export CSV")
        self.export_btn.setObjectName("info")
        self.export_btn.setIcon(self.style().standardIcon(QStyle.SP_DialogSaveButton))
        self.export_btn.clicked.connect(self.export_csv)
        top_layout.addWidget(self.export_btn)
        
        self.refresh_btn = QPushButton("Frissítés")
        self.refresh_btn.setObjectName("info")
        self.refresh_btn.setIcon(self.style().standardIcon(QStyle.SP_BrowserReload))
        self.refresh_btn.clicked.connect(self.refresh_table)
        top_layout.addWidget(self.refresh_btn)
        
        self.fix_record_btn = QPushButton("Rekord javítása")
        self.fix_record_btn.setObjectName("warning")
        self.fix_record_btn.setIcon(self.style().standardIcon(QStyle.SP_FileDialogContentsView))
        self.fix_record_btn.clicked.connect(self.fix_current_record)
        top_layout.addWidget(self.fix_record_btn)
        
        self.drop_btn = QPushButton("Tábla Törlése")
        self.drop_btn.setObjectName("danger")
        self.drop_btn.setIcon(self.style().standardIcon(QStyle.SP_TrashIcon))
        self.drop_btn.clicked.connect(self.drop_table)
        top_layout.addWidget(self.drop_btn)
        
        main_layout.addLayout(top_layout)
        
        # Fő tartalom
        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)
        
        # Táblalista
        tables_widget = QWidget()
        tables_layout = QVBoxLayout(tables_widget)
        tables_layout.setContentsMargins(0, 0, 0, 0)
        
        tables_label = QLabel("Táblák")
        tables_label.setFont(QFont("Arial", 9, QFont.Bold))
        tables_layout.addWidget(tables_label)
        
        self.table_list = QListWidget()
        self.table_list.itemSelectionChanged.connect(self.table_selected)
        tables_layout.addWidget(self.table_list)
        
        splitter.addWidget(tables_widget)
        
        # Adatok
        data_widget = QWidget()
        data_layout = QVBoxLayout(data_widget)
        data_layout.setContentsMargins(0, 0, 0, 0)
        
        data_label = QLabel("Adatok")
        data_label.setFont(QFont("Arial", 9, QFont.Bold))
        data_layout.addWidget(data_label)
        
        self.data_tree = QTreeWidget()
        self.data_tree.setHeaderLabels([])
        self.data_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.data_tree.customContextMenuRequested.connect(self.show_context_menu)
        self.data_tree.itemDoubleClicked.connect(self.edit_cell)
        self.data_tree.setSortingEnabled(True)  # Oszlop rendezés engedélyezése
        data_layout.addWidget(self.data_tree)
        
        splitter.addWidget(data_widget)
        
        splitter.setSizes([250, 750])
        main_layout.addWidget(splitter, 1)
        
        # Állapotsor
        self.status_label = QLabel("Kész")
        self.status_label.setFont(QFont("Arial", 9))
        main_layout.addWidget(self.status_label)
        
        # MySQL worker szkript létrehozása
        self.create_mysql_worker_script()

    def connect_to_db(self):
        try:
            if self.conn:
                try:
                    self.conn.close()
                except:
                    pass
                self.conn = None
                self.cursor = None
                
            engine = self.db_settings["engine"]
            
            # MySQL esetén külön folyamatban csatlakozunk
            if engine == "MySQL":
                result = self.run_mysql_command("connect")
                if result is None:
                    self.status_label.setText("MySQL kapcsolódási hiba")
                    return False
                
                self.status_label.setText("MySQL kapcsolódva: " + self.db_settings["database"])
                self.load_table_list()
                return True
            
            # MSSQL esetén normál csatlakozás
            try:
                self.status_label.setText("Kapcsolódás az adatbázishoz...")
                QApplication.processEvents()
                
                server = self.db_settings["server"]
                
                # Kiszolgáló név formázása
                if "\\" in server and not server.startswith("."):
                    server = f".\\{server.split('\\')[-1]}"
                
                # Windows hitelesítés támogatása
                if self.db_settings.get("windows_auth", False):
                    conn_str = (
                        f"DRIVER={{SQL Server}};"
                        f"SERVER={server};"
                        f"DATABASE={self.db_settings['database']};"
                        f"Trusted_Connection=yes;"
                    )
                else:
                    conn_str = (
                        f"DRIVER={{SQL Server}};"
                        f"SERVER={server};"
                        f"DATABASE={self.db_settings['database']};"
                        f"UID={self.db_settings['user']};"
                        f"PWD={self.db_settings['password']}"
                    )
                
                self.conn = pyodbc.connect(conn_str)
                self.cursor = self.conn.cursor()
                self.load_table_list()
                self.status_label.setText("Kapcsolódva: " + self.db_settings["database"])
                return True
                
            except Exception as e:
                error_msg = f"Kapcsolódási hiba: {str(e)}"
                self.status_label.setText(error_msg)
                QMessageBox.critical(
                    self, 
                    "Kapcsolódási hiba", 
                    f"Hiba a kapcsolódás során:\n\n{error_msg}\n\n"
                    f"Kérlek ellenőrizd a beállításokat:\n"
                    f"Szerver: {self.db_settings['server']}\n"
                    f"Adatbázis: {self.db_settings['database']}\n"
                    f"Felhasználó: {self.db_settings['user']}"
                )
                return False
                
        except Exception as e:
            self.status_label.setText("Váratlan hiba: " + str(e))
            QMessageBox.critical(self, "Váratlan hiba", str(e))
            return False

    def load_table_list(self):
        if self.db_settings["engine"] == "MySQL":
            # MySQL esetén külön folyamatban töltjük be a táblákat
            result = self.run_mysql_command("get_tables")
            if result is None:
                return
                
            tables = result.get('tables', [])
            self.table_list.clear()
            self.table_list.addItems(tables)
            self.status_label.setText(f"{len(tables)} tábla betöltve")
            
            # Automatikusan kiválasztjuk az első táblát
            if tables:
                self.table_list.setCurrentRow(0)
            return
        
        # MSSQL esetén normál módon
        if not self.conn or not self.cursor:
            return
            
        self.table_list.clear()
        try:
            self.status_label.setText("Táblalista betöltése...")
            QApplication.processEvents()
            
            # Rendszertáblák kizárása
            self.cursor.execute("""
                SELECT name 
                FROM sys.tables 
                WHERE name NOT IN (
                    'sysdiagrams', 'dtproperties', 
                    'MSreplication_options', 'spt_fallback_db'
                )
                ORDER BY name
            """)
            tables = [row[0] for row in self.cursor.fetchall()]
            
            self.table_list.addItems(tables)
            self.status_label.setText(f"{len(tables)} tábla betöltve")
            
            # Automatikusan kiválasztjuk az első táblát
            if tables:
                self.table_list.setCurrentRow(0)
                
        except Exception as e:
            error_msg = f"Hiba a táblalista betöltésekor: {str(e)}"
            self.status_label.setText(error_msg)
            QMessageBox.critical(
                self, 
                "Táblalista hiba", 
                error_msg + "\n\nKérlek ellenőrizd az adatbázis kapcsolatot."
            )

    def table_selected(self):
        selected = self.table_list.selectedItems()
        if not selected:
            return
            
        table_name = selected[0].text()
        self.current_table = table_name
        self.table_label.setText(f"Tábla: {table_name}")
        
        # MySQL esetén külön folyamatban töltjük be az adatokat
        if self.db_settings["engine"] == "MySQL":
            result = self.run_mysql_command("get_table_data", table_name)
            if result is None:
                return
                
            columns = result.get('columns', [])
            rows = result.get('rows', [])
            self.aktualis_tabla_oszlopai = columns
            
            self.data_tree.clear()
            self.data_tree.setColumnCount(len(columns))
            self.data_tree.setHeaderLabels(columns)
            self.data_tree.setSortingEnabled(True)
            
            for row in rows:
                values = []
                for value in row:
                    if value is None:
                        values.append("NULL")
                    else:
                        values.append(str(value))
                item = SmartTreeWidgetItem(values)
                self.data_tree.addTopLevelItem(item)
                
            for i in range(len(columns)):
                self.data_tree.header().setSectionResizeMode(i, QHeaderView.Interactive)
                self.data_tree.header().resizeSection(i, 150)
                
            self.data_tree.sortByColumn(0, Qt.AscendingOrder)
            self.status_label.setText(f"{table_name}: {len(rows)} rekord betöltve")
            return
        
        # MSSQL esetén normál adatbetöltés
        if not self.conn or not self.cursor:
            return
            
        try:
            self.status_label.setText(f"{table_name} adatainak betöltése...")
            QApplication.processEvents()
            
            # Tábla nevének kezelése
            safe_table_name = f"[{table_name}]"
            
            # Adatbázis motorfüggő LIMIT záradék
            self.cursor.execute(f"SELECT TOP 500 * FROM {safe_table_name}")
            
            columns = [desc[0] for desc in self.cursor.description]
            self.aktualis_tabla_oszlopai = columns
            
            self.data_tree.clear()
            self.data_tree.setColumnCount(len(columns))
            self.data_tree.setHeaderLabels(columns)
            self.data_tree.setSortingEnabled(True)  # Rendezés engedélyezése
            
            rows = self.cursor.fetchall()
            for row in rows:
                values = []
                for value in row:
                    if value is None:
                        values.append("NULL")
                    elif isinstance(value, (bytes, bytearray)):
                        values.append("<BINÁRIS ADAT>")
                    else:
                        values.append(str(value))
                item = SmartTreeWidgetItem(values)
                self.data_tree.addTopLevelItem(item)
                
            for i in range(len(columns)):
                self.data_tree.header().setSectionResizeMode(i, QHeaderView.Interactive)
                self.data_tree.header().resizeSection(i, 150)
                
            # Rendezés alaphelyzetbe állítása
            self.data_tree.sortByColumn(0, Qt.AscendingOrder)
                
            self.status_label.setText(f"{table_name}: {len(rows)} rekord betöltve")
                
        except Exception as e:
            self.status_label.setText("Hiba: " + str(e))
            QMessageBox.critical(self, "Hiba", str(e))

    def show_context_menu(self, position):
        item = self.data_tree.currentItem()
        if not item:
            return
            
        menu = QMenu()
        
        delete_action = QAction("Sor törlése", self)
        delete_action.setIcon(self.style().standardIcon(QStyle.SP_TrashIcon))
        delete_action.triggered.connect(self.delete_row)
        menu.addAction(delete_action)
        
        fix_action = QAction("Rekord javítása", self)
        fix_action.setIcon(self.style().standardIcon(QStyle.SP_FileDialogContentsView))
        fix_action.triggered.connect(self.fix_current_record)
        menu.addAction(fix_action)
        
        menu.exec_(self.data_tree.viewport().mapToGlobal(position))

    def delete_row(self):
        item = self.data_tree.currentItem()
        if not item or not self.table_list.selectedItems():
            return
            
        table_name = self.table_list.selectedItems()[0].text()
        pk_col = self.data_tree.headerItem().text(0)
        pk_value = item.text(0)
        
        if not pk_col:
            QMessageBox.warning(self, "Hiba", "Nincs elsődleges kulcs azonosítva!")
            return
            
        reply = QMessageBox.question(
            self, "Megerősítés",
            f"Törlöd ezt a sort? ({pk_col} = {pk_value})",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                self.status_label.setText("Sor törlése...")
                QApplication.processEvents()
                
                if self.db_settings["engine"] == "MySQL":
                    # MySQL esetén külső folyamat
                    result = self.run_mysql_command("delete_row", table_name, pk_col, pk_value)
                    if result is None:
                        return
                    
                    # Ha sikeres, eltávolítjuk a sorból
                    index = self.data_tree.indexOfTopLevelItem(item)
                    if index >= 0:
                        self.data_tree.takeTopLevelItem(index)
                    
                    self.status_label.setText(f"Sor törölve: {pk_col}={pk_value}")
                    return
                
                # Tábla nevének kezelése
                safe_table_name = f"[{table_name}]" if self.db_settings["engine"] == "MSSQL" else f"`{table_name}`"
                safe_pk_col = f"[{pk_col}]" if self.db_settings["engine"] == "MSSQL" else f"`{pk_col}`"
                
                if self.db_settings["engine"] == "MSSQL":
                    self.cursor.execute(f"DELETE FROM {safe_table_name} WHERE {safe_pk_col} = ?", (pk_value,))
                else:
                    self.cursor.execute(f"DELETE FROM {safe_table_name} WHERE {safe_pk_col} = %s", (pk_value,))
                    
                self.conn.commit()
                
                # Remove from tree without reloading entire table
                index = self.data_tree.indexOfTopLevelItem(item)
                if index >= 0:
                    self.data_tree.takeTopLevelItem(index)
                    
                self.status_label.setText(f"Sor törölve: {pk_col}={pk_value}")
            except Exception as e:
                self.status_label.setText("Hiba: " + str(e))
                QMessageBox.critical(self, "Hiba", str(e))

    def edit_cell(self, item, column):
        if not self.table_list.selectedItems():
            return
            
        old_value = item.text(column)
        col_name = self.data_tree.headerItem().text(column)
        table_name = self.current_table
        pk_col = self.data_tree.headerItem().text(0)
        pk_value = item.text(0)
        
        new_value, ok = QInputDialog.getText(
            self, "Szerkesztés",
            f"{col_name} új értéke:",
            text=old_value
        )
        
        if ok and new_value != old_value:
            try:
                self.status_label.setText("Cella frissítése...")
                QApplication.processEvents()
                
                if self.db_settings["engine"] == "MySQL":
                    # MySQL esetén külső folyamat
                    result = self.run_mysql_command("update_cell", table_name, pk_col, pk_value, col_name, new_value)
                    if result is None:
                        return
                    
                    # Ha sikeres, frissítjük a cellát
                    item.setText(column, new_value)
                    self.status_label.setText("Cella frissítve")
                    return
                
                # Tábla nevének kezelése
                safe_table_name = f"[{table_name}]" if self.db_settings["engine"] == "MSSQL" else f"`{table_name}`"
                safe_col_name = f"[{col_name}]" if self.db_settings["engine"] == "MSSQL" else f"`{col_name}`"
                safe_pk_col = f"[{pk_col}]" if self.db_settings["engine"] == "MSSQL" else f"`{pk_col}`"
                
                if self.db_settings["engine"] == "MSSQL":
                    self.cursor.execute(
                        f"UPDATE {safe_table_name} SET {safe_col_name} = ? WHERE {safe_pk_col} = ?",
                        (new_value, pk_value)
                    )
                else:
                    self.cursor.execute(
                        f"UPDATE {safe_table_name} SET {safe_col_name} = %s WHERE {safe_pk_col} = %s",
                        (new_value, pk_value)
                    )
                    
                self.conn.commit()
                item.setText(column, new_value)
                self.status_label.setText("Cella frissítve")
            except Exception as e:
                self.status_label.setText("Hiba: " + str(e))
                QMessageBox.critical(self, "Hiba", str(e))

    def fix_current_record(self):
        item = self.data_tree.currentItem()
        if not item or not self.table_list.selectedItems():
            QMessageBox.warning(self, "Figyelmeztetés", "Nincs kiválasztott rekord!")
            return
            
        table_name = self.table_list.selectedItems()[0].text()
        pk_col = self.data_tree.headerItem().text(0)
        pk_value = item.text(0)
        
        if not pk_col:
            QMessageBox.warning(self, "Hiba", "Nincs elsődleges kulcs azonosítva!")
            return
            
        try:
            # Tábla nevének kezelése
            safe_table_name = f"[{table_name}]" if self.db_settings["engine"] == "MSSQL" else f"`{table_name}`"
            safe_pk_col = f"[{pk_col}]" if self.db_settings["engine"] == "MSSQL" else f"`{pk_col}`"
            
            if self.db_settings["engine"] == "MySQL":
                # MySQL esetén külső folyamat
                result = self.run_mysql_command("execute_query", f"SELECT * FROM `{table_name}` WHERE `{pk_col}` = '{pk_value}'")
                if result is None or 'rows' not in result or not result['rows']:
                    QMessageBox.warning(self, "Hiba", "A rekord nem található!")
                    return
                
                record = result['rows'][0]
            else:
                if self.db_settings["engine"] == "MSSQL":
                    self.cursor.execute(f"SELECT * FROM {safe_table_name} WHERE {safe_pk_col} = ?", (pk_value,))
                else:
                    self.cursor.execute(f"SELECT * FROM {safe_table_name} WHERE {safe_pk_col} = %s", (pk_value,))
                    
                record = self.cursor.fetchone()
                if not record:
                    QMessageBox.warning(self, "Hiba", "A rekord nem található!")
                    return
                
            dialog = QDialog(self)
            dialog.setWindowTitle(f"Rekord szerkesztése: {pk_col} = {pk_value}")
            dialog.setMinimumSize(600, 400)
            layout = QVBoxLayout(dialog)
            
            form_layout = QGridLayout()
            editors = {}
            
            for i, col_name in enumerate(self.aktualis_tabla_oszlopai):
                lbl = QLabel(f"{col_name}:")
                form_layout.addWidget(lbl, i, 0)
                
                if self.db_settings["engine"] == "MySQL":
                    value = record[i] if record[i] is not None else ""
                else:
                    value = record[i] if record[i] is not None else ""
                editor = QLineEdit(str(value))
                if col_name == pk_col:
                    editor.setEnabled(False)  # Elsődleges kulcs nem szerkeszthető
                form_layout.addWidget(editor, i, 1)
                editors[col_name] = editor
                
            layout.addLayout(form_layout)
            
            btn_layout = QHBoxLayout()
            btn_save = QPushButton("Mentés")
            btn_save.setObjectName("info")
            btn_save.clicked.connect(lambda: self.save_record_changes(dialog, editors, item, pk_col, table_name, pk_value))
            
            btn_cancel = QPushButton("Mégse")
            btn_cancel.setObjectName("danger")
            btn_cancel.clicked.connect(dialog.reject)
            
            btn_layout.addWidget(btn_save)
            btn_layout.addWidget(btn_cancel)
            layout.addLayout(btn_layout)
            
            dialog.exec_()
        except Exception as e:
            self.status_label.setText("Hiba: " + str(e))
            QMessageBox.critical(self, "Hiba", str(e))

    def save_record_changes(self, dialog, editors, item, pk_col, table_name, pk_value):
        try:
            update_parts = []
            params = []
            
            if self.db_settings["engine"] == "MySQL":
                updates = {}
                for col_name, editor in editors.items():
                    if col_name == pk_col:
                        continue
                    new_value = editor.text()
                    updates[col_name] = new_value
                
                result = self.run_mysql_command("update_record", table_name, pk_col, pk_value, updates)
                if result is None:
                    return
                
                # Update tree item directly
                for col_idx, col_name in enumerate(self.aktualis_tabla_oszlopai):
                    if col_name in editors:
                        item.setText(col_idx, editors[col_name].text())
                
                self.status_label.setText("Rekord sikeresen frissítve")
                dialog.accept()
                return
            
            for col_name, editor in editors.items():
                new_value = editor.text()
                if col_name == pk_col:
                    continue
                    
                # Tábla nevének kezelése
                safe_col_name = f"[{col_name}]" if self.db_settings["engine"] == "MSSQL" else f"`{col_name}`"
                
                if self.db_settings["engine"] == "MSSQL":
                    update_parts.append(f"{safe_col_name} = ?")
                else:
                    update_parts.append(f"{safe_col_name} = %s")
                params.append(new_value)
            
            params.append(pk_value)
            
            safe_table_name = f"[{table_name}]" if self.db_settings["engine"] == "MSSQL" else f"`{table_name}`"
            safe_pk_col = f"[{pk_col}]" if self.db_settings["engine"] == "MSSQL" else f"`{pk_col}`"
            
            update_query = f"UPDATE {safe_table_name} SET {', '.join(update_parts)} WHERE {safe_pk_col} = "
            
            if self.db_settings["engine"] == "MSSQL":
                update_query += "?"
            else:
                update_query += "%s"
            
            self.status_label.setText("Rekord frissítése...")
            QApplication.processEvents()
            
            self.cursor.execute(update_query, params)
            self.conn.commit()
            
            # Update tree item directly
            for col_idx, col_name in enumerate(self.aktualis_tabla_oszlopai):
                if col_name in editors:
                    item.setText(col_idx, editors[col_name].text())
            
            self.status_label.setText("Rekord sikeresen frissítve")
            dialog.accept()
        except Exception as e:
            self.status_label.setText("Hiba: " + str(e))
            QMessageBox.critical(dialog, "Hiba", str(e))

    def drop_table(self):
        selected = self.table_list.selectedItems()
        if not selected:
            return
            
        table_name = selected[0].text()
        reply = QMessageBox.question(
            self, "Megerősítés",
            f"Biztos törlöd a(z) '{table_name}' táblát?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                self.status_label.setText(f"{table_name} tábla törlése...")
                QApplication.processEvents()
                
                if self.db_settings["engine"] == "MySQL":
                    # MySQL esetén külső folyamat
                    result = self.run_mysql_command("drop_table", table_name)
                    if result is None:
                        return
                    
                    self.load_table_list()
                    self.data_tree.clear()
                    self.table_label.setText("Nincs kiválasztott tábla")
                    self.current_table = ""
                    self.status_label.setText(f"Tábla törölve: {table_name}")
                    return
                
                # Tábla nevének kezelése
                safe_table_name = f"[{table_name}]" if self.db_settings["engine"] == "MSSQL" else f"`{table_name}`"
                
                self.cursor.execute(f"DROP TABLE {safe_table_name}")
                self.conn.commit()
                
                self.load_table_list()
                self.data_tree.clear()
                self.table_label.setText("Nincs kiválasztott tábla")
                self.current_table = ""
                
                self.status_label.setText(f"Tábla törölve: {table_name}")
            except Exception as e:
                self.status_label.setText("Hiba: " + str(e))
                QMessageBox.critical(self, "Hiba", str(e))

    def refresh_table(self):
        if self.current_table:
            self.table_selected()
            self.status_label.setText("Tábla frissítve")

    def export_csv(self):
        if not self.current_table:
            QMessageBox.warning(self, "Figyelmeztetés", "Nincs kiválasztott tábla!")
            return
            
        file_path, _ = QFileDialog.getSaveFileName(
            self, "CSV fájl mentése", self.current_table + ".csv", "CSV fájlok (*.csv);;Összes fájl (*)"
        )
        
        if not file_path:
            return
            
        try:
            self.status_label.setText("CSV exportálás...")
            QApplication.processEvents()
            
            # MySQL esetén külön folyamatban exportálunk
            if self.db_settings["engine"] == "MySQL":
                # Tábla nevének kezelése
                safe_table_name = f"`{self.current_table}`"
                
                result = self.run_mysql_command("execute_query", f"SELECT * FROM {safe_table_name}")
                if result is None:
                    return
                    
                columns = result.get('columns', [])
                rows = result.get('rows', [])
                
                with open(file_path, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f, delimiter=';')
                    writer.writerow(columns)
                    for row in rows:
                        writer.writerow([str(x) if x is not None else "" for x in row])
                
                self.status_label.setText(f"Exportálás kész: {file_path}")
                QMessageBox.information(self, "Siker", f"Adatok sikeresen exportálva: {file_path}")
                return
            
            # MSSQL esetén normál exportálás
            # Tábla nevének kezelése
            safe_table_name = f"[{self.current_table}]"
            
            self.cursor.execute(f"SELECT * FROM {safe_table_name}")
            columns = [desc[0] for desc in self.cursor.description]
            rows = self.cursor.fetchall()
            
            with open(file_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f, delimiter=';')
                writer.writerow(columns)
                for row in rows:
                    writer.writerow([str(x) if x is not None else "" for x in row])
            
            self.status_label.setText(f"Exportálás kész: {file_path}")
            QMessageBox.information(self, "Siker", f"Adatok sikeresen exportálva: {file_path}")
        except Exception as e:
            self.status_label.setText("Hiba: " + str(e))
            QMessageBox.critical(self, "Hiba", str(e))

    def open_settings(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Adatbázis Beállítások")
        dialog.setMinimumSize(500, 500)
        layout = QVBoxLayout(dialog)
        
        grid_layout = QGridLayout()
        grid_layout.setSpacing(10)
        
        # Profil neve
        grid_layout.addWidget(QLabel("Profil neve:"), 0, 0)
        self.profile_name_entry = QLineEdit()
        grid_layout.addWidget(self.profile_name_entry, 0, 1)
        
        # Mentett profilok
        grid_layout.addWidget(QLabel("Mentett profilok:"), 1, 0)
        self.profile_listbox = QListWidget()
        grid_layout.addWidget(self.profile_listbox, 1, 1, 3, 1)
        
        # Profil törlése gomb
        self.btn_delete_profile = QPushButton("Profil törlése")
        self.btn_delete_profile.setObjectName("danger")
        grid_layout.addWidget(self.btn_delete_profile, 4, 1)
        
        # Adatbázis beállítások
        grid_layout.addWidget(QLabel("Adatbázis típusa:"), 5, 0)
        self.engine_combo = QComboBox()
        self.engine_combo.addItems(["MSSQL", "MySQL"])
        self.engine_combo.setCurrentText(self.db_settings["engine"])
        grid_layout.addWidget(self.engine_combo, 5, 1)
        
        grid_layout.addWidget(QLabel("Szerver:"), 6, 0)
        self.server_entry = QLineEdit(self.db_settings["server"])
        grid_layout.addWidget(self.server_entry, 6, 1)
        
        grid_layout.addWidget(QLabel("Felhasználónév:"), 7, 0)
        self.user_entry = QLineEdit(self.db_settings["user"])
        grid_layout.addWidget(self.user_entry, 7, 1)
        
        grid_layout.addWidget(QLabel("Jelszó:"), 8, 0)
        self.pass_entry = QLineEdit(self.db_settings["password"])
        self.pass_entry.setEchoMode(QLineEdit.Password)
        grid_layout.addWidget(self.pass_entry, 8, 1)
        
        grid_layout.addWidget(QLabel("Adatbázis neve:"), 9, 0)
        self.db_entry = QLineEdit(self.db_settings["database"])
        grid_layout.addWidget(self.db_entry, 9, 1)
        
        # Windows hitelesítés
        grid_layout.addWidget(QLabel("Windows hitelesítés:"), 10, 0)
        self.windows_auth_check = QCheckBox()
        self.windows_auth_check.setChecked(self.db_settings.get("windows_auth", False))
        grid_layout.addWidget(self.windows_auth_check, 10, 1)
        
        layout.addLayout(grid_layout)
        
        # Gombok
        btn_layout = QHBoxLayout()
        self.btn_save = QPushButton("Mentés és újracsatlakozás")
        self.btn_save.setObjectName("info")
        btn_layout.addWidget(self.btn_save)
        
        self.btn_cancel = QPushButton("Mégse")
        self.btn_cancel.setObjectName("danger")
        btn_layout.addWidget(self.btn_cancel)
        layout.addLayout(btn_layout)
        
        # Frissítsük a profil listát
        self.update_profile_list()
        
        # Kiválasztott profil betöltése
        self.profile_listbox.itemSelectionChanged.connect(self.load_selected_profile)
        
        # Profil törlése
        self.btn_delete_profile.clicked.connect(self.delete_profile)
        
        # Mentés és bezárás
        self.btn_save.clicked.connect(lambda: self.save_settings(dialog))
        self.btn_cancel.clicked.connect(dialog.reject)
        
        dialog.exec_()

    def update_profile_list(self):
        self.profile_listbox.clear()
        for name in sorted(self.profiles.keys()):
            self.profile_listbox.addItem(name)

    def load_selected_profile(self):
        selected = self.profile_listbox.selectedItems()
        if not selected:
            return
        name = selected[0].text()
        self.profile_name_entry.setText(name)
        prof = self.profiles.get(name)
        if not prof:
            return
        self.engine_combo.setCurrentText(prof.get("engine", "MSSQL"))
        self.server_entry.setText(prof.get("server", ""))
        self.user_entry.setText(prof.get("user", ""))
        self.pass_entry.setText(prof.get("password", ""))
        self.db_entry.setText(prof.get("database", ""))
        self.windows_auth_check.setChecked(prof.get("windows_auth", False))

    def delete_profile(self):
        selected = self.profile_listbox.selectedItems()
        if not selected:
            return
        name = selected[0].text()
        if QMessageBox.question(self, "Törlés", f"Törlöd a '{name}' profilt?") == QMessageBox.Yes:
            self.profiles.pop(name, None)
            self.save_profiles()
            self.update_profile_list()
            QMessageBox.information(self, "Siker", f"'{name}' profil törölve")

    def save_settings(self, dialog):
        name = self.profile_name_entry.text().strip()
        if not name:
            QMessageBox.warning(dialog, "Hiba", "Adj meg egy profilt nevet!")
            return

        self.db_settings = {
            "engine": self.engine_combo.currentText(),
            "server": self.server_entry.text(),
            "user": self.user_entry.text(),
            "password": self.pass_entry.text(),
            "database": self.db_entry.text(),
            "windows_auth": self.windows_auth_check.isChecked()
        }

        self.profiles[name] = self.db_settings
        self.save_profiles()
        self.connect_to_db()
        dialog.accept()
 
if __name__ == "__main__":
    import sys
    app = QApplication(sys.argv)
    window = DatabaseBrowser()
    if "--embed" not in sys.argv:
        window.show()   
                    
    sys.exit(app.exec_())