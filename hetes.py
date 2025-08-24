import sys
import os
import json
import traceback
import tempfile
import pyodbc
import appdirs
import platform

try:
    import winreg
except ImportError:
    winreg = None

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QPushButton, QTreeWidget, QTreeWidgetItem, QMessageBox,
    QInputDialog, QComboBox, QLineEdit, QTableWidget,
    QTableWidgetItem, QGroupBox, QStyleFactory
)
from PyQt5.QtCore import Qt, QProcess, QThread, pyqtSignal
from PyQt5.QtGui import QPalette, QColor


# ============ MSSQL THREADS ============

class ConnectionThread(QThread):
    connection_error = pyqtSignal(str)
    databases_ready = pyqtSignal(dict)

    def __init__(self, db_settings, parent=None):
        super().__init__(parent)
        self.db_settings = db_settings
        self.is_cancelled = False

    def cancel(self):
        self.is_cancelled = True

    def run(self):
        if self.db_settings["engine"] == "MySQL":
            return
        conn = None
        try:
            conn_str = (
                f"DRIVER={{ODBC Driver 17 for SQL Server}};"
                f"SERVER={self.db_settings['server']};"
                f"UID={self.db_settings['user']};"
                f"PWD={self.db_settings['password']}"
            )
            conn = pyodbc.connect(conn_str, timeout=5)
            cursor = conn.cursor()

            databases = {}
            cursor.execute("SELECT name FROM sys.databases WHERE name NOT IN ('master','tempdb','model','msdb')")
            db_list = [row[0] for row in cursor.fetchall()]

            for db_name in db_list:
                if self.is_cancelled:
                    break
                databases[db_name] = {}
                cursor.execute(f"USE [{db_name}]")
                cursor.execute("""
                    SELECT TABLE_SCHEMA, TABLE_NAME 
                    FROM INFORMATION_SCHEMA.TABLES 
                    WHERE TABLE_TYPE='BASE TABLE'
                    ORDER BY TABLE_SCHEMA, TABLE_NAME
                """)
                for row in cursor.fetchall():
                    schema_name, table_name = row
                    if schema_name not in databases[db_name]:
                        databases[db_name][schema_name] = []
                    databases[db_name][schema_name].append(table_name)

            if not self.is_cancelled:
                self.databases_ready.emit(databases)

        except Exception as e:
            self.connection_error.emit(str(e))
        finally:
            if conn:
                conn.close()


class MSSQLUpdateThread(QThread):
    update_done = pyqtSignal(bool, str)

    def __init__(self, settings, db_name, schema, table, column, new_value, pk_col, pk_val, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.db_name = db_name
        self.schema = schema
        self.table = table
        self.column = column
        self.new_value = new_value
        self.pk_col = pk_col
        self.pk_val = pk_val

    def run(self):
        conn = None
        try:
            conn_str = (
                f"DRIVER={{ODBC Driver 17 for SQL Server}};"
                f"SERVER={self.settings['server']};"
                f"UID={self.settings['user']};"
                f"PWD={self.settings['password']}"
            )
            conn = pyodbc.connect(conn_str, timeout=5)
            cur = conn.cursor()
            cur.execute(f"USE [{self.db_name}]")
            sql = f"UPDATE [{self.schema}].[{self.table}] SET [{self.column}] = ? WHERE [{self.pk_col}] = ?"
            cur.execute(sql, self.new_value, self.pk_val)
            conn.commit()
            self.update_done.emit(True, "Mentve.")
        except Exception as e:
            if conn:
                conn.rollback()
            self.update_done.emit(False, f"Hiba: {e}")
        finally:
            if conn:
                conn.close()


class MSSQLDropThread(QThread):
    drop_done = pyqtSignal(bool, str)

    def __init__(self, settings, db_name, schema, table, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.db_name = db_name
        self.schema = schema
        self.table = table

    def run(self):
        conn = None
        try:
            conn_str = (
                f"DRIVER={{ODBC Driver 17 for SQL Server}};"
                f"SERVER={self.settings['server']};"
                f"UID={self.settings['user']};"
                f"PWD={self.settings['password']}"
            )
            conn = pyodbc.connect(conn_str, timeout=5)
            cur = conn.cursor()
            cur.execute(f"USE [{self.db_name}]")
            cur.execute(f"DROP TABLE [{self.schema}].[{self.table}]")
            conn.commit()
            self.drop_done.emit(True, "Tábla törölve.")
        except Exception as e:
            if conn:
                conn.rollback()
            self.drop_done.emit(False, f"Hiba: {e}")
        finally:
            if conn:
                conn.close()


# ============ FŐ WIDGET ============

class DatabaseBrowser(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("DB Browser")
        self.db_settings = {
            "engine": "MySQL",
            "server": "localhost",
            "user": "root",
            "password": "",
            "database": ""
        }
        self.conn = None
        self.profiles = {}
        self.connection_thread = None

        self.loading_data = False
        self.current_db = ""
        self.current_schema = ""
        self.current_table = ""
        self.pk_col_name = ""
        self.pk_col_index = 0

        self.app_data_dir = appdirs.user_data_dir("HETES", "Szita")
        os.makedirs(self.app_data_dir, exist_ok=True)
        self.PROFILE_FILE = os.path.join(self.app_data_dir, "profiles.json")
        self.MYSQL_WORKER_SCRIPT = os.path.join(self.app_data_dir, "mysql_worker.py")
        self.mysql_process = QProcess(self)

        self.create_mysql_worker_script()
        self.load_profiles()
        self.init_ui()
        self.set_dark_widget_palette()

    # ---------- MySQL külső worker létrehozása ----------
    def create_mysql_worker_script(self):
        content = """import sys, json, mysql.connector
def get_pk_column(cur, db, table):
    try:
        cur.execute("USE `{}`".format(db))
        cur.execute(\"\"\"
            SELECT k.COLUMN_NAME
            FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS t
            JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE k
              ON t.CONSTRAINT_NAME = k.CONSTRAINT_NAME
              AND t.TABLE_SCHEMA = k.TABLE_SCHEMA
              AND t.TABLE_NAME = k.TABLE_NAME
            WHERE t.CONSTRAINT_TYPE = 'PRIMARY KEY'
              AND t.TABLE_SCHEMA = %s
              AND t.TABLE_NAME = %s
            ORDER BY k.ORDINAL_POSITION
        \"\"\", (db, table))
        rows = cur.fetchall()
        if rows:
            return rows[0][0]
    except:
        pass
    cur.execute("SELECT * FROM `{}` LIMIT 1".format(table))
    return cur.column_names[0] if cur.column_names else ""
def run(settings, command, *args):
    try:
        conn = mysql.connector.connect(
            host=settings['server'],
            user=settings['user'],
            password=settings['password'],
            database=(settings.get('database') or None),
            connection_timeout=5
        )
        cur = conn.cursor()
        res = {}
        if command == 'databases':
            cur.execute("SHOW DATABASES")
            res['databases'] = [r[0] for r in cur.fetchall()]
        elif command == 'tables':
            db = args[0]
            cur.execute("USE `{}`".format(db))
            cur.execute("SHOW TABLES")
            res['tables'] = [r[0] for r in cur.fetchall()]
        elif command == 'data':
            db, table = args
            cur.execute("USE `{}`".format(db))
            cur.execute("SELECT * FROM `{}` LIMIT 1000".format(table))
            cols = [d[0] for d in cur.description]
            rows = cur.fetchall()
            res['columns'] = cols
            res['rows'] = []
            for row in rows:
                res['rows'].append([None if v is None else str(v) for v in row])
            pk = get_pk_column(cur, db, table)
            res['primary_key'] = pk
        elif command == 'update_cell':
            db, table, column, new_value, pk_col, pk_val = args
            cur.execute("USE `{}`".format(db))
            if new_value == "NULL":
                sql = "UPDATE `{}` SET `{}` = NULL WHERE `{}` = %s".format(table, column, pk_col)
                cur.execute(sql, (pk_val,))
            else:
                sql = "UPDATE `{}` SET `{}` = %s WHERE `{}` = %s".format(table, column, pk_col)
                cur.execute(sql, (new_value, pk_val))
            conn.commit()
            res['status'] = 'ok'
        elif command == 'delete_table':
            db, table = args
            cur.execute("USE `{}`".format(db))
            cur.execute("DROP TABLE `{}`".format(table))
            conn.commit()
            res['status'] = 'ok'
        else:
            res['status'] = 'error'
            res['msg'] = 'Ismeretlen parancs: ' + command
        cur.close()
        conn.close()
        print(json.dumps(res))
    except Exception as e:
        print(json.dumps({'status':'error','msg':str(e), 'error_code': e.errno if hasattr(e, 'errno') else None}))
if __name__=='__main__':
    settings=json.loads(open(sys.argv[1], encoding='utf-8').read())
    run(settings, sys.argv[2], *sys.argv[3:])
"""
        try:
            with open(self.MYSQL_WORKER_SCRIPT, "w", encoding="utf-8") as f:
                f.write(content)
        except Exception:
            pass

    def find_system_python(self):
        """Megkeresi a rendszerbeli Python elérési útját"""
        for path in os.environ.get("PATH", "").split(os.pathsep):
            python_path = os.path.join(path, "python.exe")
            if os.path.isfile(python_path):
                return python_path
        
        if platform.system() == "Windows":
            for version in ["3.11", "3.10", "3.9", "3.8"]:
                paths = [
                    f"C:\\Python{version}\\python.exe",
                    f"C:\\Program Files\\Python{version}\\python.exe",
                    f"C:\\Program Files (x86)\\Python{version}\\python.exe"
                ]
                for path in paths:
                    if os.path.isfile(path):
                        return path
            
            if winreg:
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

    def run_mysql_command(self, command, *args):
        """MySQL parancs futtatása külső folyamatban"""
        
        settings_json = json.dumps(self.db_settings)
        tmp = tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8", suffix=".json")
        json.dump(self.db_settings, tmp, ensure_ascii=False)
        tmp.close()
        
        cmd_args = [self.MYSQL_WORKER_SCRIPT, tmp.name, command] + list(args)
        
        if getattr(sys, 'frozen', False):
            python_exe = self.find_system_python()
            if not python_exe:
                QMessageBox.critical(self, "Hiba", "Nem található Python interpreter!")
                os.unlink(tmp.name)
                return None
            
            self.mysql_process.start(python_exe, cmd_args)
        else:
            self.mysql_process.start(sys.executable, cmd_args)
        
        if not self.mysql_process.waitForFinished(10000):
            QMessageBox.critical(self, "Időtúllépés", "A MySQL művelet túl sokáig tartott.")
            self.mysql_process.kill()
            os.unlink(tmp.name)
            return None
        
        out = bytes(self.mysql_process.readAllStandardOutput()).decode("utf-8", errors="replace")
        
        os.unlink(tmp.name)
        
        try:
            result = json.loads(out)
            if 'status' in result and result['status'] == 'error':
                QMessageBox.critical(self, "MySQL Hiba", f"Hibaüzenet: {result.get('msg', 'Ismeretlen hiba')}")
                return None
            return result
        except json.JSONDecodeError:
            QMessageBox.critical(self, "Hiba", f"Érvénytelen JSON válasz: {out}")
            return None

    # ---------- UI ----------
    def init_ui(self):
        layout = QVBoxLayout(self)
        top_layout = QHBoxLayout()

        login_group = QGroupBox("Adatbázis kapcsolat")
        login_layout = QFormLayout()

        self.engine_combo = QComboBox()
        self.engine_combo.addItems(["MySQL", "MSSQL"])
        self.engine_combo.setCurrentText(self.db_settings["engine"])
        login_layout.addRow("Motor:", self.engine_combo)

        self.server_input = QLineEdit(self.db_settings["server"])
        login_layout.addRow("Szerver:", self.server_input)

        self.user_input = QLineEdit(self.db_settings["user"])
        login_layout.addRow("Felhasználó:", self.user_input)

        self.password_input = QLineEdit(self.db_settings["password"])
        self.password_input.setEchoMode(QLineEdit.Password)
        login_layout.addRow("Jelszó:", self.password_input)

        self.database_input = QLineEdit(self.db_settings.get("database", ""))
        login_layout.addRow("Adatbázis (MySQL):", self.database_input)

        btn_row = QHBoxLayout()
        self.connect_btn = QPushButton("Csatlakozás / Frissítés")
        self.connect_btn.clicked.connect(self.connect_to_db)
        btn_row.addWidget(self.connect_btn)

        self.save_profile_button = QPushButton("Profil mentése")
        self.save_profile_button.clicked.connect(self.save_current_profile)
        btn_row.addWidget(self.save_profile_button)

        self.load_profile_button = QPushButton("Profil betöltése")
        self.load_profile_button.clicked.connect(self.load_existing_profile)
        btn_row.addWidget(self.load_profile_button)

        self.delete_profile_button = QPushButton("Profil törlése")
        self.delete_profile_button.clicked.connect(self.delete_current_profile)
        btn_row.addWidget(self.delete_profile_button)

        login_layout.addRow(btn_row)
        login_group.setLayout(login_layout)
        top_layout.addWidget(login_group)

        right_layout = QVBoxLayout()
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Adatbázis / Séma / Tábla"])
        self.tree.itemClicked.connect(self.on_item_clicked)
        right_layout.addWidget(self.tree)

        action_row = QHBoxLayout()
        self.refresh_table_btn = QPushButton("Frissítés (Táblára)")
        self.refresh_table_btn.clicked.connect(self.refresh_current_table)
        action_row.addWidget(self.refresh_table_btn)

        self.delete_table_btn = QPushButton("Tábla törlése")
        self.delete_table_btn.clicked.connect(self.delete_current_table)
        action_row.addWidget(self.delete_table_btn)

        right_layout.addLayout(action_row)
        top_layout.addLayout(right_layout)
        layout.addLayout(top_layout)

        from PyQt5.QtWidgets import QHeaderView
        self.table = QTableWidget()
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table.cellChanged.connect(self.on_cell_changed)
        layout.addWidget(self.table)

    def set_dark_widget_palette(self):
        app = QApplication.instance()
        app.setStyle(QStyleFactory.create("Fusion"))
        dark_palette = QPalette()
        dark_palette.setColor(QPalette.Window, QColor(53, 53, 53))
        dark_palette.setColor(QPalette.WindowText, Qt.white)
        dark_palette.setColor(QPalette.Base, QColor(25, 25, 25))
        dark_palette.setColor(QPalette.AlternateBase, QColor(53, 53, 53))
        dark_palette.setColor(QPalette.ToolTipBase, Qt.black)
        dark_palette.setColor(QPalette.ToolTipText, Qt.white)
        dark_palette.setColor(QPalette.Text, Qt.white)
        dark_palette.setColor(QPalette.Button, QColor(53, 53, 53))
        dark_palette.setColor(QPalette.ButtonText, Qt.white)
        dark_palette.setColor(QPalette.BrightText, Qt.red)
        dark_palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
        dark_palette.setColor(QPalette.HighlightedText, Qt.black)
        app.setPalette(dark_palette)

    # ---------- Kapcsolódás / fa feltöltése ----------
    def connect_to_db(self):
        self.db_settings["engine"] = self.engine_combo.currentText()
        self.db_settings["server"] = self.server_input.text()
        self.db_settings["user"] = self.user_input.text()
        self.db_settings["password"] = self.password_input.text()
        self.db_settings["database"] = self.database_input.text().strip()

        if self.db_settings["engine"] == "MySQL":
            res = self.run_mysql_command("databases")
            if not res: return
            
            self.tree.clear()
            for db in res.get("databases", []):
                if db in ("information_schema", "mysql", "performance_schema", "sys"):
                    continue
                db_item = QTreeWidgetItem([db])
                self.tree.addTopLevelItem(db_item)
                tables = self.run_mysql_command("tables", db)
                if tables and tables.get("status") != "error":
                    for t in tables.get("tables", []):
                        db_item.addChild(QTreeWidgetItem([t]))
        else:
            self.connection_thread = ConnectionThread(self.db_settings, parent=self)
            self.connection_thread.databases_ready.connect(self.on_databases_ready)
            self.connection_thread.connection_error.connect(self.on_mssql_conn_error)
            self.connection_thread.start()

    def on_mssql_conn_error(self, msg):
        QMessageBox.critical(self, "Hiba (MSSQL)", msg)

    def on_databases_ready(self, databases):
        self.tree.clear()
        for db, schemas in databases.items():
            db_item = QTreeWidgetItem([db])
            self.tree.addTopLevelItem(db_item)
            for schema, tables in schemas.items():
                schema_item = QTreeWidgetItem([schema])
                db_item.addChild(schema_item)
                for t in tables:
                    schema_item.addChild(QTreeWidgetItem([t]))

    # ---------- Tábla megnyitás / betöltés ----------
    def on_item_clicked(self, item, col):
        parent = item.parent()
        if not parent:
            return

        engine = self.db_settings["engine"]
        if engine == "MySQL":
            self.current_db = parent.text(0)
            self.current_schema = ""
            self.current_table = item.text(0)
            self.load_mysql_table(self.current_db, self.current_table)
        else:
            if parent.parent() is None:
                return
            self.current_db = parent.parent().text(0)
            self.current_schema = parent.text(0)
            self.current_table = item.text(0)
            self.load_mssql_table(self.current_db, self.current_schema, self.current_table)

    def load_mysql_table(self, db, table):
        res = self.run_mysql_command("data", db, table)
        if not res: return
        
        columns = res.get("columns", [])
        rows = res.get("rows", [])
        self.pk_col_name = res.get("primary_key", columns[0] if columns else "")
        self.pk_col_index = columns.index(self.pk_col_name) if self.pk_col_name in columns else 0
        self.fill_table(columns, rows)

    def load_mssql_table(self, db, schema, table):
        try:
            conn_str = (
                f"DRIVER={{ODBC Driver 17 for SQL Server}};"
                f"SERVER={self.db_settings['server']};"
                f"UID={self.db_settings['user']};"
                f"PWD={self.db_settings['password']}"
            )
            conn = pyodbc.connect(conn_str, timeout=5)
            cur = conn.cursor()
            cur.execute(f"USE [{db}]")
            cur.execute(f"SELECT TOP 1000 * FROM [{schema}].[{table}]")
            columns = [d[0] for d in cur.description]
            rows = cur.fetchall()
            rows = [[None if v is None else str(v) for v in r] for r in rows]
            self.pk_col_name = columns[0] if columns else ""
            self.pk_col_index = 0
            self.fill_table(columns, rows)
        except Exception as e:
            QMessageBox.critical(self, "Hiba (MSSQL)", str(e))

    # ---------- Tábla kitöltése ----------
    def fill_table(self, cols, rows):
        self.loading_data = True
        try:
            self.table.clear()
            self.table.setRowCount(len(rows))
            self.table.setColumnCount(len(cols))
            self.table.setHorizontalHeaderLabels(cols)
            for r, row in enumerate(rows):
                for c, val in enumerate(row):
                    it = QTableWidgetItem("NULL" if val is None else str(val))
                    it.setFlags(it.flags() | Qt.ItemIsEditable)
                    self.table.setItem(r, c, it)
                if cols:
                    pk_val = row[self.pk_col_index] if (0 <= self.pk_col_index < len(row)) else None
                    pk_item = self.table.item(r, self.pk_col_index)
                    if pk_item:
                        pk_item.setData(Qt.UserRole, pk_val)
        finally:
            self.loading_data = False

    # ---------- Cellaváltozás -> mentés ----------
    def on_cell_changed(self, row, column):
        if self.loading_data:
            return
        if not self.current_table:
            return

        new_value = self.table.item(row, column).text() if self.table.item(row, column) else ""
        col_name = self.table.horizontalHeaderItem(column).text()
        pk_item = self.table.item(row, self.pk_col_index)
        orig_pk_val = pk_item.data(Qt.UserRole) if pk_item else None

        if orig_pk_val is None and pk_item is not None:
            orig_pk_val = pk_item.text()

        engine = self.db_settings["engine"]
        if engine == "MySQL":
            res = self.run_mysql_command(
                "update_cell",
                self.current_db, self.current_table,
                col_name, new_value,
                self.pk_col_name, str(orig_pk_val) if orig_pk_val is not None else ""
            )
            if not res: return
            
            if column == self.pk_col_index and pk_item is not None:
                pk_item.setData(Qt.UserRole, new_value)
        else:
            th = MSSQLUpdateThread(
                self.db_settings, self.current_db, self.current_schema,
                self.current_table, col_name, new_value,
                self.pk_col_name, str(orig_pk_val) if orig_pk_val is not None else ""
            )
            th.update_done.connect(self.on_mssql_update_done)
            th.start()

    def on_mssql_update_done(self, ok, msg):
        if not ok:
            QMessageBox.critical(self, "Mentési hiba (MSSQL)", msg)

    # ---------- Frissítés ----------
    def refresh_current_table(self):
        if not self.current_table:
            return
        if self.db_settings["engine"] == "MySQL":
            self.load_mysql_table(self.current_db, self.current_table)
        else:
            self.load_mssql_table(self.current_db, self.current_schema, self.current_table)

    # ---------- Törlés ----------
    def delete_current_table(self):
        if not self.current_table:
            return
        reply = QMessageBox.question(self, "Tábla törlése",
                                     f"Biztosan törlöd a(z) '{self.current_table}' táblát?",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply != QMessageBox.Yes:
            return

        engine = self.db_settings["engine"]
        if engine == "MySQL":
            res = self.run_mysql_command("delete_table", self.current_db, self.current_table)
            if not res: return
            
            QMessageBox.information(self, "Kész", "Tábla törölve.")
            self.connect_to_db()
            self.table.clear()
            self.current_table = ""
        else:
            th = MSSQLDropThread(self.db_settings, self.current_db, self.current_schema, self.current_table)
            th.drop_done.connect(self.on_mssql_drop_done)
            th.start()

    def on_mssql_drop_done(self, ok, msg):
        if not ok:
            QMessageBox.critical(self, "Törlési hiba (MSSQL)", msg)
            return
        QMessageBox.information(self, "Kész", "Tábla törölve.")
        self.connect_to_db()
        self.table.clear()
        self.current_table = ""

    # ---------- Profilok ----------
    def save_current_profile(self):
        profile_name, ok = QInputDialog.getText(self, "Profil mentése", "Profil neve:")
        if ok and profile_name:
            self.profiles[profile_name] = {
                "engine": self.engine_combo.currentText(),
                "server": self.server_input.text(),
                "user": self.user_input.text(),
                "password": self.password_input.text(),
                "database": self.database_input.text().strip(),
            }
            self.save_profiles()
            QMessageBox.information(self, "Siker", f"A(z) '{profile_name}' profil elmentve.")

    def load_existing_profile(self):
        if not self.profiles:
            QMessageBox.warning(self, "Nincs profil", "Nincsenek mentett profilok.")
            return
        names = list(self.profiles.keys())
        profile, ok = QInputDialog.getItem(self, "Profil betöltése", "Válassz profilt:", names, 0, False)
        if ok and profile:
            self.db_settings.update(self.profiles[profile])
            self.engine_combo.setCurrentText(self.db_settings.get("engine", "MySQL"))
            self.server_input.setText(self.db_settings.get("server", "localhost"))
            self.user_input.setText(self.db_settings.get("user", "root"))
            self.password_input.setText(self.db_settings.get("password", ""))
            self.database_input.setText(self.db_settings.get("database", ""))
            

    def delete_current_profile(self):
        if not self.profiles:
            QMessageBox.warning(self, "Nincs profil", "Nincsenek mentett profilok.")
            return
        names = list(self.profiles.keys())
        profile, ok = QInputDialog.getItem(self, "Profil törlése", "Válassz profilt:", names, 0, False)
        if ok and profile:
            del self.profiles[profile]
            self.save_profiles()
            QMessageBox.information(self, "Siker", f"A(z) '{profile}' profil törölve.")

    def save_profiles(self):
        try:
            with open(self.PROFILE_FILE, "w", encoding="utf-8") as f:
                json.dump(self.profiles, f, indent=4, ensure_ascii=False)
        except Exception as e:
            QMessageBox.critical(self, "Hiba", f"Profil mentése sikertelen: {str(e)}")

    def load_profiles(self):
        try:
            if os.path.exists(self.PROFILE_FILE):
                with open(self.PROFILE_FILE, "r", encoding="utf-8") as f:
                    self.profiles = json.load(f)
                    if self.profiles:
                        first = next(iter(self.profiles.values()))
                        self.db_settings.update({
                            "engine": first.get("engine", self.db_settings["engine"]),
                            "server": first.get("server", self.db_settings["server"]),
                            "user": first.get("user", self.db_settings["user"]),
                            "password": first.get("password", self.db_settings["password"]),
                            "database": first.get("database", self.db_settings["database"]),
                        })
        except Exception as e:
            QMessageBox.critical(self, "Hiba", f"Profil betöltése sikertelen: {str(e)}")


# ============ MAIN WINDOW ============

 
        
         


if __name__ == "__main__":
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    win = DatabaseBrowser()
    win.show()
    sys.exit(app.exec_())