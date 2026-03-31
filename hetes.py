import sys
import os
import json
import traceback
import tempfile
import pyodbc
import appdirs
import platform
import pandas as pd
from io import StringIO



from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QPushButton, QTreeWidget, QTreeWidgetItem, QMessageBox,
    QInputDialog, QComboBox, QLineEdit, QTableWidget,
    QTableWidgetItem, QGroupBox, QStyleFactory, QHeaderView,
    QFileDialog
)
from PyQt5.QtCore import Qt, QProcess, QThread, pyqtSignal
from PyQt5.QtGui import QPalette, QColor


# ============ MSSQL THREADS ============
# A szálkezelés logikája mostantól a fő widgetben van, a szálak csak a munkát végzik.

class ConnectionThread(QThread):
    connection_error = pyqtSignal(str)
    databases_ready = pyqtSignal(dict)

    def __init__(self, db_settings, parent=None):
        super().__init__(parent)
        self.db_settings = db_settings

    def run(self):
        conn = None
        try:
            conn_str = (
                f"DRIVER={{ODBC Driver 17 for SQL Server}};"
                f"SERVER={self.db_settings['server']};"
                f"UID={self.db_settings['user']};"
                f"PWD={self.db_settings['password']}"
            )
            conn = pyodbc.connect(conn_str, timeout=5, autocommit=True)
            cursor = conn.cursor()

            databases = {}
            cursor.execute("SELECT name FROM sys.databases WHERE name NOT IN ('master','tempdb','model','msdb')")
            db_list = [row[0] for row in cursor.fetchall()]

            for db_name in db_list:
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
        self.settings, self.db_name, self.schema, self.table = settings, db_name, schema, table
        self.column, self.new_value, self.pk_col, self.pk_val = column, new_value, pk_col, pk_val

    def run(self):
        conn = None
        try:
            conn_str = (
                f"DRIVER={{ODBC Driver 17 for SQL Server}};"
                f"SERVER={self.settings['server']};"
                f"UID={self.settings['user']};"
                f"PWD={self.settings['password']}"
            )
            conn = pyodbc.connect(conn_str, timeout=5, autocommit=False)
            cur = conn.cursor()
            cur.execute(f"USE [{self.db_name}]")
            sql = f"UPDATE [{self.schema}].[{self.table}] SET [{self.column}] = ? WHERE [{self.pk_col}] = ?"
            cur.execute(sql, self.new_value, self.pk_val)
            conn.commit()
            self.update_done.emit(True, "Mentve.")
        except Exception as e:
            if conn: conn.rollback()
            self.update_done.emit(False, f"Hiba: {e}")
        finally:
            if conn: conn.close()


class MSSQLDropThread(QThread):
    drop_done = pyqtSignal(bool, str)

    def __init__(self, settings, db_name, schema, table, parent=None):
        super().__init__(parent)
        self.settings, self.db_name, self.schema, self.table = settings, db_name, schema, table

    def run(self):
        conn = None
        try:
            conn_str = (
                f"DRIVER={{ODBC Driver 17 for SQL Server}};"
                f"SERVER={self.settings['server']};"
                f"UID={self.settings['user']};"
                f"PWD={self.settings['password']}"
            )
            conn = pyodbc.connect(conn_str, timeout=5, autocommit=False)
            cur = conn.cursor()
            cur.execute(f"USE [{self.db_name}]")
            cur.execute(f"DROP TABLE [{self.schema}].[{self.table}]")
            conn.commit()
            self.drop_done.emit(True, "Tábla törölve.")
        except Exception as e:
            if conn: conn.rollback()
            self.drop_done.emit(False, f"Hiba: {e}")
        finally:
            if conn: conn.close()


# ============ FŐ WIDGET ============

class DatabaseBrowser(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("DB Browser")
        self.db_settings = {"engine": "MySQL", "server": "localhost", "user": "root", "password": "", "database": ""}
        
        # --- KRITIKUS VÁLTOZÓK A STABIL MŰKÖDÉSHEZ ---
        self.is_busy = False
        self.worker_thread = None
        # ---------------------------------------------

        self.loading_data = False
        self.current_db, self.current_schema, self.current_table = "", "", ""
        self.pk_col_name, self.pk_col_index = "", 0
        self.data_rows = [] # Itt tároljuk a beolvasott adatokat

        self.app_data_dir = appdirs.user_data_dir("HETES", "Szita")
        os.makedirs(self.app_data_dir, exist_ok=True)
        self.PROFILE_FILE = os.path.join(self.app_data_dir, "profiles.json")
        self.MYSQL_WORKER_SCRIPT = os.path.join(self.app_data_dir, "mysql_worker.py")
        self.mysql_process = QProcess(self)

        self.create_mysql_worker_script()
        self.load_profiles()
        self.init_ui()
        self.set_dark_widget_palette()

    def create_mysql_worker_script(self):
        # Ez a rész változatlan maradhat, a MySQL kezelés nem okozott hibát
        content = """import sys, json, mysql.connector
def get_pk_column(cur, db, table):
    try:
        cur.execute("USE `{}`".format(db))
        cur.execute("SHOW KEYS FROM `{}` WHERE Key_name = 'PRIMARY'".format(table))
        rows = cur.fetchall()
        if rows: return rows[0][4]
    except: pass
    cur.execute("SELECT * FROM `{}` LIMIT 1".format(table))
    return cur.column_names[0] if cur.column_names else ""
def run(settings, command, *args):
    try:
        conn = mysql.connector.connect(host=settings['server'],user=settings['user'],password=settings['password'],database=(settings.get('database') or None),connection_timeout=5)
        cur = conn.cursor()
        res = {}
        if command == 'databases':
            cur.execute("SHOW DATABASES")
            res['databases'] = [r[0] for r in cur.fetchall()]
        elif command == 'tables':
            db = args[0]
            cur.execute("USE `{}`".format(db)); cur.execute("SHOW TABLES"); res['tables'] = [r[0] for r in cur.fetchall()]
        elif command == 'data':
            db, table = args
            cur.execute("USE `{}`".format(db)); cur.execute("SELECT * FROM `{}` LIMIT 1000".format(table))
            cols = [d[0] for d in cur.description]
            rows = [[None if v is None else str(v) for v in r] for r in cur.fetchall()]
            res.update({'columns': cols, 'rows': rows, 'primary_key': get_pk_column(cur, db, table)})
        elif command == 'update_cell':
            db, table, column, new_value, pk_col, pk_val = args
            cur.execute("USE `{}`".format(db))
            sql = f"UPDATE `{table}` SET `{column}` = %s WHERE `{pk_col}` = %s"
            params = (None if new_value == "NULL" else new_value, pk_val)
            cur.execute(sql, params)
            conn.commit(); res['status'] = 'ok'
        elif command == 'delete_table':
            db, table = args
            cur.execute("USE `{}`".format(db)); cur.execute(f"DROP TABLE `{table}`"); conn.commit(); res['status'] = 'ok'
        else: res = {'status':'error', 'msg': f'Ismeretlen parancs: {command}'}
        cur.close(); conn.close()
        print(json.dumps(res))
    except Exception as e: print(json.dumps({'status':'error','msg':str(e), 'error_code': e.errno if hasattr(e, 'errno') else None}))
if __name__=='__main__': run(json.loads(open(sys.argv[1], encoding='utf-8').read()), sys.argv[2], *sys.argv[3:])
"""
        with open(self.MYSQL_WORKER_SCRIPT, "w", encoding="utf-8") as f: f.write(content)
    
    def find_system_python(self):
        # Ez a rész változatlan maradhat
        paths = os.environ.get("PATH", "").split(os.pathsep)
        for path in paths:
            python_path = os.path.join(path, "python.exe")
            if os.path.isfile(python_path): return python_path
        return sys.executable # Visszaesés a jelenlegi futtatóra

    def run_mysql_command(self, command, *args):
        # Ez a rész változatlan maradhat
        with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8", suffix=".json") as tmp:
            json.dump(self.db_settings, tmp, ensure_ascii=False)
            tmp_path = tmp.name
        
        python_exe = sys.executable if not getattr(sys, 'frozen', False) else self.find_system_python()
        if not python_exe:
            QMessageBox.critical(self, "Hiba", "Nem található Python interpreter!")
            os.unlink(tmp_path); return None

        self.mysql_process.start(python_exe, [self.MYSQL_WORKER_SCRIPT, tmp_path, command] + list(args))
        if not self.mysql_process.waitForFinished(10000):
            QMessageBox.critical(self, "Időtúllépés", "A MySQL művelet túl sokáig tartott."); self.mysql_process.kill()
            os.unlink(tmp_path); return None
        
        out = bytes(self.mysql_process.readAllStandardOutput()).decode("utf-8", errors="replace")
        os.unlink(tmp_path)
        
        try:
            result = json.loads(out)
            if result.get('status') == 'error':
                QMessageBox.critical(self, "MySQL Hiba", f"Hibaüzenet: {result.get('msg', 'Ismeretlen hiba')}")
                return None
            return result
        except json.JSONDecodeError:
            QMessageBox.critical(self, "Hiba", f"Érvénytelen JSON válasz: {out}")
            return None

    def init_ui(self):
        layout = QVBoxLayout(self)
        top_layout = QHBoxLayout()
        login_group = QGroupBox("Adatbázis kapcsolat"); login_layout = QFormLayout()
        self.engine_combo = QComboBox(); self.engine_combo.addItems(["MySQL", "MSSQL"])
        self.server_input = QLineEdit(self.db_settings["server"])
        self.user_input = QLineEdit(self.db_settings["user"])
        self.password_input = QLineEdit(self.db_settings["password"]); self.password_input.setEchoMode(QLineEdit.Password)
        self.database_input = QLineEdit(self.db_settings.get("database", ""))
        login_layout.addRow("Motor:", self.engine_combo); login_layout.addRow("Szerver:", self.server_input)
        login_layout.addRow("Felhasználó:", self.user_input); login_layout.addRow("Jelszó:", self.password_input)
        login_layout.addRow("Adatbázis (MySQL):", self.database_input)
        btn_row = QHBoxLayout(); self.connect_btn = QPushButton("Csatlakozás / Frissítés")
        self.save_profile_button = QPushButton("Profil mentése"); self.load_profile_button = QPushButton("Profil betöltése")
        self.delete_profile_button = QPushButton("Profil törlése");
        btn_row.addWidget(self.connect_btn); btn_row.addWidget(self.save_profile_button)
        btn_row.addWidget(self.load_profile_button); btn_row.addWidget(self.delete_profile_button); login_layout.addRow(btn_row)
        login_group.setLayout(login_layout); top_layout.addWidget(login_group)
        right_layout = QVBoxLayout(); self.tree = QTreeWidget(); self.tree.setHeaderLabels(["Adatbázis / Séma / Tábla"])
        right_layout.addWidget(self.tree); 
        action_row = QHBoxLayout()
        self.refresh_table_btn = QPushButton("Frissítés (Táblára)"); self.delete_table_btn = QPushButton("Tábla törlése")
        self.export_table_btn = QPushButton("Exportálás CSV/XLS") # Export gomb hozzáadva
        action_row.addWidget(self.refresh_table_btn); action_row.addWidget(self.delete_table_btn); action_row.addWidget(self.export_table_btn)
        right_layout.addLayout(action_row); top_layout.addLayout(right_layout); layout.addLayout(top_layout)
        self.table = QTableWidget(); self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        layout.addWidget(self.table)
        # Eseménykezelők
        self.connect_btn.clicked.connect(self.connect_to_db)
        self.save_profile_button.clicked.connect(self.save_current_profile)
        self.load_profile_button.clicked.connect(self.load_existing_profile)
        self.delete_profile_button.clicked.connect(self.delete_current_profile)
        self.tree.itemClicked.connect(self.on_item_clicked)
        self.refresh_table_btn.clicked.connect(self.refresh_current_table)
        self.delete_table_btn.clicked.connect(self.delete_current_table)
        self.export_table_btn.clicked.connect(self.export_table) # Export eseménykezelő
        self.table.cellChanged.connect(self.on_cell_changed)
        self.table.horizontalHeader().sectionClicked.connect(self.sort_table) # Rendezés eseménykezelő

    def set_dark_widget_palette(self):
        # Ez változatlan
        app = QApplication.instance(); app.setStyle(QStyleFactory.create("Fusion"))
        p = QPalette(); p.setColor(QPalette.Window, QColor(53, 53, 53)); p.setColor(QPalette.WindowText, Qt.white)
        p.setColor(QPalette.Base, QColor(25, 25, 25)); p.setColor(QPalette.AlternateBase, QColor(53, 53, 53))
        p.setColor(QPalette.ToolTipBase, Qt.black); p.setColor(QPalette.ToolTipText, Qt.white); p.setColor(QPalette.Text, Qt.white)
        p.setColor(QPalette.Button, QColor(53, 53, 53)); p.setColor(QPalette.ButtonText, Qt.white); p.setColor(QPalette.BrightText, Qt.red)
        p.setColor(QPalette.Highlight, QColor(42, 130, 218)); p.setColor(QPalette.HighlightedText, Qt.black); app.setPalette(p)

    # ---------- ÚJ, BIZTONSÁGOS SZÁLKEZELŐ RENDSZER ----------
    def start_worker(self, worker_class, *args):
        if self.is_busy:
            QMessageBox.warning(self, "Foglalt", "Egy művelet már folyamatban van. Kérem, várjon.")
            return
        self.is_busy = True
        self.set_controls_enabled(False)
        self.worker_thread = worker_class(*args)
        self.worker_thread.finished.connect(self.on_worker_finished)
        
        # Eredmény signálok csatlakoztatása
        if hasattr(self.worker_thread, 'databases_ready'): self.worker_thread.databases_ready.connect(self.on_databases_ready)
        if hasattr(self.worker_thread, 'connection_error'): self.worker_thread.connection_error.connect(self.on_mssql_conn_error)
        if hasattr(self.worker_thread, 'update_done'): self.worker_thread.update_done.connect(self.on_mssql_update_done)
        if hasattr(self.worker_thread, 'drop_done'): self.worker_thread.drop_done.connect(self.on_mssql_drop_done)
        
        self.worker_thread.start()

    def on_worker_finished(self):
        self.worker_thread.deleteLater()
        self.worker_thread = None
        self.is_busy = False
        self.set_controls_enabled(True)

    def set_controls_enabled(self, enabled):
        self.connect_btn.setEnabled(enabled)
        self.delete_table_btn.setEnabled(enabled)
        self.refresh_table_btn.setEnabled(enabled)
        self.export_table_btn.setEnabled(enabled)
    # ----------------------------------------------------

    def connect_to_db(self):
        self.db_settings["engine"] = self.engine_combo.currentText(); self.db_settings["server"] = self.server_input.text()
        self.db_settings["user"] = self.user_input.text(); self.db_settings["password"] = self.password_input.text()
        self.db_settings["database"] = self.database_input.text().strip()

        if self.db_settings["engine"] == "MySQL":
            res = self.run_mysql_command("databases");
            if not res: return
            self.tree.clear()
            for db in res.get("databases", []):
                if db in ("information_schema", "mysql", "performance_schema", "sys"): continue
                db_item = QTreeWidgetItem([db]); self.tree.addTopLevelItem(db_item)
                tables = self.run_mysql_command("tables", db)
                if tables and tables.get("status") != "error":
                    for t in tables.get("tables", []): db_item.addChild(QTreeWidgetItem([t]))
        else:
            self.start_worker(ConnectionThread, self.db_settings)

    def on_mssql_conn_error(self, msg): QMessageBox.critical(self, "Hiba (MSSQL)", msg)
    def on_databases_ready(self, databases):
        self.tree.clear()
        for db, schemas in databases.items():
            db_item = QTreeWidgetItem([db]); self.tree.addTopLevelItem(db_item)
            for schema, tables in schemas.items():
                schema_item = QTreeWidgetItem([schema]); db_item.addChild(schema_item)
                for t in tables: schema_item.addChild(QTreeWidgetItem([t]))

    def on_item_clicked(self, item, col):
        if not item.parent(): return
        engine = self.db_settings["engine"]
        if engine == "MySQL":
            self.current_db, self.current_schema, self.current_table = item.parent().text(0), "", item.text(0)
            self.load_mysql_table(self.current_db, self.current_table)
        else: # MSSQL
            if not item.parent().parent(): return # Ha sémára kattintunk
            self.current_db, self.current_schema, self.current_table = item.parent().parent().text(0), item.parent().text(0), item.text(0)
            self.load_mssql_table(self.current_db, self.current_schema, self.current_table)

    def load_mysql_table(self, db, table):
        res = self.run_mysql_command("data", db, table)
        if not res: return
        columns = res.get("columns", []); rows = res.get("rows", [])
        self.data_rows = rows # Adatok mentése a memóriába
        self.pk_col_name = res.get("primary_key", columns[0] if columns else "")
        self.pk_col_index = columns.index(self.pk_col_name) if self.pk_col_name in columns else 0
        self.fill_table(columns, rows)

    def load_mssql_table(self, db, schema, table):
        # Ez mostantól nem futtat szálat, csak sima lekérdezés.
        conn = None
        try:
            conn_str = f"DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={self.db_settings['server']};UID={self.db_settings['user']};PWD={self.db_settings['password']}"
            conn = pyodbc.connect(conn_str, timeout=5, autocommit=True)
            cur = conn.cursor()
            cur.execute(f"USE [{db}]")
            cur.execute(f"SELECT TOP 100000 * FROM [{schema}].[{table}]")
            columns = [d[0] for d in cur.description]
            rows = [[None if v is None else str(v) for v in r] for r in cur.fetchall()]
            self.data_rows = rows # Adatok mentése a memóriába
            
            # PK lekérdezése
            pk_sql = """
                SELECT K.COLUMN_NAME FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS AS C 
                JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE AS K ON C.TABLE_NAME = K.TABLE_NAME 
                AND C.CONSTRAINT_CATALOG = K.CONSTRAINT_CATALOG AND C.CONSTRAINT_SCHEMA = K.CONSTRAINT_SCHEMA 
                AND C.CONSTRAINT_NAME = K.CONSTRAINT_NAME WHERE C.CONSTRAINT_TYPE = 'PRIMARY KEY' 
                AND K.TABLE_NAME = ? AND K.TABLE_SCHEMA = ?
            """
            pk_res = cur.execute(pk_sql, table, schema).fetchone()
            self.pk_col_name = pk_res[0] if pk_res else (columns[0] if columns else "")
            self.pk_col_index = columns.index(self.pk_col_name) if self.pk_col_name in columns else 0
            
            self.fill_table(columns, rows)
        except Exception as e: QMessageBox.critical(self, "Hiba (MSSQL)", str(e))
        finally:
            if conn: conn.close()

    def fill_table(self, cols, rows):
        self.loading_data = True
        try:
            self.table.clear(); self.table.setRowCount(len(rows)); self.table.setColumnCount(len(cols))
            self.table.setHorizontalHeaderLabels(cols)
            for r, row in enumerate(rows):
                for c, val in enumerate(row):
                    it = QTableWidgetItem("NULL" if val is None else str(val)); self.table.setItem(r, c, it)
                if cols and (0 <= self.pk_col_index < len(row)):
                    pk_item = self.table.item(r, self.pk_col_index)
                    if pk_item: pk_item.setData(Qt.UserRole, row[self.pk_col_index])
        finally:
            self.loading_data = False

    def on_cell_changed(self, row, column):
        if self.loading_data or not self.current_table: return
        new_value = self.table.item(row, column).text() if self.table.item(row, column) else ""
        col_name = self.table.horizontalHeaderItem(column).text()
        pk_item = self.table.item(row, self.pk_col_index)
        pk_val = pk_item.data(Qt.UserRole) if pk_item and pk_item.data(Qt.UserRole) is not None else (pk_item.text() if pk_item else None)
        
        if self.db_settings["engine"] == "MySQL":
            res = self.run_mysql_command("update_cell", self.current_db, self.current_table, col_name, new_value, self.pk_col_name, str(pk_val))
            if res and column == self.pk_col_index and pk_item: pk_item.setData(Qt.UserRole, new_value)
        else:
            self.start_worker(MSSQLUpdateThread, self.db_settings, self.current_db, self.current_schema, self.current_table, col_name, new_value, self.pk_col_name, str(pk_val))

    def on_mssql_update_done(self, ok, msg):
        if not ok: QMessageBox.critical(self, "Mentési hiba (MSSQL)", msg)
        else: # Sikeres mentéskor frissítjük a UserRole adatot, ha a PK változott
            row = self.table.currentRow(); col = self.table.currentColumn()
            if col == self.pk_col_index:
                pk_item = self.table.item(row, self.pk_col_index)
                if pk_item: pk_item.setData(Qt.UserRole, pk_item.text())

    def refresh_current_table(self):
        if not self.current_table: return
        if self.db_settings["engine"] == "MySQL":
            self.load_mysql_table(self.current_db, self.current_table)
        else:
            self.load_mssql_table(self.current_db, self.current_schema, self.current_table)

    def delete_current_table(self):
        if not self.current_table: return
        reply = QMessageBox.question(self, "Tábla törlése", f"Biztosan törlöd a(z) '{self.current_table}' táblát?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply != QMessageBox.Yes: return

        if self.db_settings["engine"] == "MySQL":
            if self.run_mysql_command("delete_table", self.current_db, self.current_table):
                QMessageBox.information(self, "Kész", "Tábla törölve."); self.connect_to_db(); self.table.clear(); self.current_table = ""
        else:
            self.start_worker(MSSQLDropThread, self.db_settings, self.current_db, self.current_schema, self.current_table)

    def on_mssql_drop_done(self, ok, msg):
        if not ok:
            QMessageBox.critical(self, "Törlési hiba (MSSQL)", msg); return
        QMessageBox.information(self, "Kész", "Tábla törölve.")
        self.connect_to_db()
        self.table.clear(); self.current_table = ""

    def save_current_profile(self):
        name, ok = QInputDialog.getText(self, "Profil mentése", "Profil neve:")
        if ok and name:
            self.profiles[name] = {"engine": self.engine_combo.currentText(), "server": self.server_input.text(), "user": self.user_input.text(), "password": self.password_input.text(), "database": self.database_input.text().strip()}
            self.save_profiles(); QMessageBox.information(self, "Siker", f"A(z) '{name}' profil elmentve.")

    def load_existing_profile(self):
        if not self.profiles: QMessageBox.warning(self, "Nincs profil", "Nincsenek mentett profilok."); return
        name, ok = QInputDialog.getItem(self, "Profil betöltése", "Válassz profilt:", list(self.profiles.keys()), 0, False)
        if ok and name:
            p = self.profiles[name]
            self.engine_combo.setCurrentText(p.get("engine", "MySQL")); self.server_input.setText(p.get("server", "")); self.user_input.setText(p.get("user", ""))
            self.password_input.setText(p.get("password", "")); self.database_input.setText(p.get("database", ""))

    def delete_current_profile(self):
        if not self.profiles: QMessageBox.warning(self, "Nincs profil", "Nincsenek mentett profilok."); return
        name, ok = QInputDialog.getItem(self, "Profil törlése", "Válassz profilt:", list(self.profiles.keys()), 0, False)
        if ok and name: del self.profiles[name]; self.save_profiles(); QMessageBox.information(self, "Siker", f"A(z) '{name}' profil törölve.")

    def save_profiles(self):
        try:
            with open(self.PROFILE_FILE, "w", encoding="utf-8") as f: json.dump(self.profiles, f, indent=4)
        except Exception as e: QMessageBox.critical(self, "Hiba", f"Profil mentése sikertelen: {e}")

    def load_profiles(self):
        if not os.path.exists(self.PROFILE_FILE): return
        try:
            with open(self.PROFILE_FILE, "r", encoding="utf-8") as f: self.profiles = json.load(f)
        except Exception as e: QMessageBox.critical(self, "Hiba", f"Profil betöltése sikertelen: {e}")
    
    def sort_table(self, col_index):
        if not self.data_rows: return
        
        # Típus alapján rendezés: szám vs. szöveg
        try:
            # Első nem None elem alapján próbáljuk meg a típust meghatározni
            first_val = next((row[col_index] for row in self.data_rows if row[col_index] is not None and row[col_index] != "NULL"), None)
            if first_val is not None:
                try:
                    float(first_val.replace(',', '.')) # Próba: szám
                    self.data_rows.sort(key=lambda x: float(x[col_index].replace(',', '.')) if x[col_index] is not None and x[col_index] != "NULL" else float('-inf'))
                except (ValueError, TypeError):
                    # Visszaesés: szöveg
                    self.data_rows.sort(key=lambda x: str(x[col_index] or '').lower())
            
            # Visszaváltás, ha már rendezve volt (váltakozó sorrend)
            if hasattr(self, '_last_sort_col') and self._last_sort_col == col_index:
                self.data_rows.reverse()
            self._last_sort_col = col_index
            
            # Frissítjük a táblázatot a rendezett adatokkal
            self.fill_table(self.get_table_columns(), self.data_rows)
        
        except Exception as e:
            QMessageBox.critical(self, "Rendezési hiba", f"Hiba történt a rendezés során: {e}")
    
    def get_table_columns(self):
        cols = []
        for c in range(self.table.columnCount()):
            header_item = self.table.horizontalHeaderItem(c)
            if header_item:
                cols.append(header_item.text())
        return cols
    
    def export_table(self):
        if not self.data_rows:
            QMessageBox.warning(self, "Nincs adat", "Nincsenek adatok a táblázatban az exportáláshoz.")
            return

        file_path, selected_filter = QFileDialog.getSaveFileName(
            self,
            "Exportálás",
            f"{self.current_table}",
            "CSV fájl (*.csv);;Excel fájl (*.xlsx)"
        )
        if not file_path:
            return

        # Pandas DataFrame létrehozása
        cols = self.get_table_columns()
        df = pd.DataFrame(self.data_rows, columns=cols)

        # NULL értékek kezelése
        df = df.fillna('NULL')

        # Ha nincs kiterjesztés, adjuk hozzá a választott filter alapján
        if selected_filter.startswith("CSV"):
            if not file_path.lower().endswith(".csv"):
                file_path += ".csv"
            df.to_csv(file_path, index=False, encoding='utf-8', sep=';')
            QMessageBox.information(self, "Exportálás", f"Adatok sikeresen exportálva a(z) {file_path} fájlba.")
        elif selected_filter.startswith("Excel"):
            if not file_path.lower().endswith(".xlsx"):
                file_path += ".xlsx"
            df.to_excel(file_path, index=False, engine='xlsxwriter')
            QMessageBox.information(self, "Exportálás", f"Adatok sikeresen exportálva a(z) {file_path} fájlba.")


if __name__ == "__main__":
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    app = QApplication(sys.argv)
    win = DatabaseBrowser()
    win.show()
    sys.exit(app.exec_())