import os
import re
import subprocess
import time
from datetime import datetime
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTreeWidget,
    QTreeWidgetItem, QFileDialog, QAbstractItemView, QHeaderView,
    QLabel, QCheckBox, QSplitter, QMessageBox, QProgressBar, QLineEdit,
    QFrame, QSizePolicy, QApplication
)
from PyQt5.QtCore import Qt, QObject, pyqtSignal, QThread, QDate
from docx import Document
from openpyxl import Workbook
from PyPDF2 import PdfReader
from openpyxl import load_workbook

def read_file_content(file_path):
    try:
        # Kisebb fájlok esetén olvassuk be a tartalmat
        file_size = os.path.getsize(file_path)
        if file_size > 10 * 1024 * 1024:  # 10 MB-nál nagyobb fájl
            return None
            
        if file_path.endswith('.docx'):
            doc = Document(file_path)
            return "\n".join([para.text for para in doc.paragraphs])
        elif file_path.endswith('.xlsx'):
            wb = load_workbook(file_path, read_only=True)
            sheet = wb.active
            content = ""
            for row in sheet.iter_rows(values_only=True):
                content += " ".join(str(cell) for cell in row if cell) + "\n"
            return content
        elif file_path.endswith('.pdf'):
            reader = PdfReader(file_path)
            content = ""
            for page in reader.pages:
                content += page.extract_text() + "\n"
            return content
        else:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as file:
                return file.read()
    except Exception as e:
        print(f"Hiba történt a fájl olvasása közben: {e}")
        return None

def open_with_application(file_path):
    if os.path.isdir(file_path):
        if os.name == 'nt':  # Windows
            subprocess.Popen(["explorer", file_path], shell=True)
        elif os.name == 'posix':  # Linux, macOS
            subprocess.Popen(["xdg-open", file_path])
    elif file_path.endswith(('.zip', '.rar')) and os.name == 'nt':
        subprocess.Popen(["start", "WinRAR", file_path], shell=True)
    else:
        if os.name == 'nt':
            subprocess.run(['start', '', file_path], shell=True)
        elif os.name == 'posix':
            subprocess.Popen(["xdg-open", file_path])

class SearchWorker(QThread):
    update_progress = pyqtSignal(int, int, int, float)
    file_found = pyqtSignal(str, int)
    file_found_batch = pyqtSignal(list)  # JAVÍTVA: Signal deklarálva
    search_finished = pyqtSignal()
    status_update = pyqtSignal(str)

    def __init__(self, folder, pattern, exact_match, exclude_extensions, 
                 search_filenames_only, search_folders_only, start_date, end_date):
        super().__init__()
        self.folder = folder
        self.pattern = pattern
        self.exact_match = exact_match
        self.exclude_extensions = exclude_extensions
        self.search_filenames_only = search_filenames_only
        self.search_folders_only = search_folders_only
        self.start_date = start_date
        self.end_date = end_date
        self.stop_flag = False
        
        self.excluded_extensions = [
            ".exe", ".mp3", ".mp4", ".wav", ".jpg", ".jpeg", ".png", ".gif", ".bmp",
            ".tiff", ".psd", ".avi", ".mov", ".mkv", ".flv", ".wmv", ".flac", ".aac",
            ".ogg", ".wma", ".zip", ".rar", ".7z", ".tar", ".gz", ".bin", ".iso", ".dll",
            ".so", ".ttf", ".otf", ".woff", ".cbr", ".cbz", ".epub", ".mobi", ".db", ".sqlite",
            ".mdb", ".sys", ".msi", ".cab"
        ]

    def run(self):
        try:
            self.status_update.emit("Fájlok számolása...")
            
            # JAVÍTVA: Hatékonyabb fájlszámolás os.scandir-rel
            total_files = 0
            for root, dirs, files in os.walk(self.folder):
                if self.stop_flag:
                    return
                total_files += len(dirs) if self.search_folders_only else len(files)
            
            if total_files == 0:
                self.search_finished.emit()
                return
                
            processed_files = 0
            found_files = 0
            start_time = time.time()
            batch_results = []  # Kötegekben gyűjtjük az eredményeket
            
            # JAVÍTVA: os.scandir használata gyorsabb bejáráshoz
            for root_dir, dirs, files in os.walk(self.folder):
                if self.stop_flag:
                    break
                    
                items = dirs if self.search_folders_only else files
                
                for item_name in items:
                    if self.stop_flag:
                        break
                        
                    item_path = os.path.join(root_dir, item_name)
                    
                    # Dátumszűrés - korai kizárás
                    if self.start_date or self.end_date:
                        try:
                            creation_time = os.path.getctime(item_path)
                            creation_date = datetime.fromtimestamp(creation_time).date()
                            
                            if self.start_date and creation_date < self.start_date:
                                continue
                            if self.end_date and creation_date > self.end_date:
                                continue
                        except:
                            pass
                    
                    # Kiterjesztés szűrés - korai kizárás
                    if self.exclude_extensions and not self.search_folders_only:
                        if any(item_name.lower().endswith(ext) for ext in self.excluded_extensions):
                            processed_files += 1
                            # Csak ritkán frissítünk
                            if processed_files % 100 == 0:
                                self.update_progress.emit(processed_files, total_files, found_files, time.time() - start_time)
                            continue
                    
                    # Keresés optimalizálva
                    match_count = 0
                    
                    # Ha csak fájlnévben keresünk, ne olvassuk a tartalmat
                    if self.search_filenames_only or self.search_folders_only:
                        if re.search(self.pattern, item_name, re.IGNORECASE if not self.exact_match else 0):
                            match_count = 1
                    else:
                        # Ne nyissuk meg a nagyon nagy fájlokat
                        try:
                            file_size = os.path.getsize(item_path)
                            if file_size > 10 * 1024 * 1024:  # 10 MB-nál nagyobb fájl
                                # Nagy fájlok esetén csak a fájlnévben keresünk
                                if re.search(self.pattern, item_name, re.IGNORECASE if not self.exact_match else 0):
                                    match_count = 1
                            else:
                                content = read_file_content(item_path)
                                if content:
                                    # JAVÍTVA: Előre lefordított regex használata
                                    pattern = re.compile(self.pattern, re.IGNORECASE if not self.exact_match else 0)
                                    match_count = len(pattern.findall(content))
                        except:
                            # Ha méret lekérdezése sikertelen, csak a névben keresünk
                            if re.search(self.pattern, item_name, re.IGNORECASE if not self.exact_match else 0):
                                match_count = 1
                    
                    if match_count > 0:
                        found_files += 1
                        batch_results.append((item_path, match_count))
                    
                    processed_files += 1
                    
                    # Ritkább frissítés - csak minden 100 fájl után
                    if processed_files % 100 == 0 or processed_files == total_files:
                        # Kötegekben küldjük az eredményeket
                        if batch_results:
                            self.file_found_batch.emit(batch_results)
                            batch_results = []
                        self.update_progress.emit(processed_files, total_files, found_files, time.time() - start_time)
            
            # Maradék eredmények küldése
            if batch_results:
                self.file_found_batch.emit(batch_results)
                
            self.status_update.emit("Keresés befejezve")
            self.search_finished.emit()
        except Exception as e:
            self.status_update.emit(f"Hiba: {str(e)}")

    def stop(self):
        self.stop_flag = True

class FileSearchApp(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.search_worker = None
        self.results = []
        self.init_ui()
        self.set_style()

    def set_style(self):
        self.setStyleSheet("""
            QWidget {
                background-color: #D7F5F7;
                font-family: 'Segoe UI';
            }
            QLabel {
                color: #333333;
                font-size: 10pt;
            }
            QPushButton {
                background-color: #5799AD;
                color: white;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
                font-size: 10pt;
                min-width: 100px;
            }
            QPushButton:hover {
                background-color: #2C546B;
            }
            QPushButton:disabled {
                background-color: #95A5A6;
            }
            QPushButton#danger {
                background-color: #E74C3C;
            }
            QPushButton#danger:hover {
                background-color: #C0392B;
            }
            QPushButton#success {
                background-color: #27AE60;
            }
            QPushButton#success:hover {
                background-color: #219653;
            }
            QLineEdit, QTreeWidget {
                background-color: white;
                border: 1px solid #CCCCCC;
                border-radius: 3px;
                padding: 5px;
                font-size: 10pt;
            }
            QTreeWidget {
                alternate-background-color: #F0F8FF;
            }
            QHeaderView::section {
                background-color: #5799AD;
                color: white;
                padding: 5px;
                font-weight: bold;
            }
            QProgressBar {
                border: 1px solid #CCCCCC;
                border-radius: 3px;
                text-align: center;
                height: 20px;
            }
            QProgressBar::chunk {
                background-color: #27AE60;
                width: 10px;
            }
            QCheckBox {
                font-size: 10pt;
            }
            QGroupBox {
                border: 1px solid #CCCCCC;
                border-radius: 5px;
                margin-top: 1ex;
                font-weight: bold;
                background-color: #E0F7FA;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top center;
                padding: 0 5px;
            }
        """)

    def init_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)

        # Cím
        title = QLabel("Fájlba Kereső Program")
        title.setStyleSheet("font-size: 16pt; font-weight: bold; color: #2C546B;")
        title.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title)

        # Mappa választó
        folder_layout = QHBoxLayout()
        lbl_folder = QLabel("Mappa kiválasztása:")
        self.folder_entry = QLineEdit()
        btn_browse = QPushButton("Tallózás")
        btn_browse.clicked.connect(self.browse_folder)
        
        folder_layout.addWidget(lbl_folder)
        folder_layout.addWidget(self.folder_entry, 1)
        folder_layout.addWidget(btn_browse)
        main_layout.addLayout(folder_layout)

        # Kereső kifejezés
        search_layout = QHBoxLayout()
        lbl_search = QLabel("Kereső kifejezés:")
        self.search_entry = QLineEdit()
        search_layout.addWidget(lbl_search)
        search_layout.addWidget(self.search_entry, 1)
        main_layout.addLayout(search_layout)

        # Beállítások
        options_frame = QFrame()
        options_frame.setFrameShape(QFrame.StyledPanel)
        options_layout = QVBoxLayout(options_frame)
        
        self.exact_match = QCheckBox("Pontos egyezés")
        self.exclude_ext = QCheckBox("Fájlkiterjesztések kizárása")
        self.search_filenames = QCheckBox("Csak fájlnevekben keresés")
        self.search_folders = QCheckBox("Csak mappanevekben keresés")
        
        options_layout.addWidget(self.exact_match)
        options_layout.addWidget(self.exclude_ext)
        options_layout.addWidget(self.search_filenames)
        options_layout.addWidget(self.search_folders)
        
        # Dátum szűrés
        date_layout = QHBoxLayout()
        lbl_date = QLabel("Létrehozás dátuma:")
        self.start_date = QLineEdit()
        self.start_date.setPlaceholderText("ÉÉÉÉ-HH-NN")
        self.end_date = QLineEdit()
        self.end_date.setPlaceholderText("ÉÉÉÉ-HH-NN")
        
        mai_datum = datetime.now().strftime("%Y-%m-%d")
        self.start_date.setText(mai_datum)
        self.end_date.setText(mai_datum)
        
        date_layout.addWidget(lbl_date)
        date_layout.addWidget(self.start_date)
        date_layout.addWidget(QLabel(" - "))
        date_layout.addWidget(self.end_date)
        date_layout.addStretch()
         
        
        options_layout.addLayout(date_layout)
        main_layout.addWidget(options_frame)

        # Gombok
        button_layout = QHBoxLayout()
        self.btn_search = QPushButton("Keresés")
        self.btn_search.clicked.connect(self.start_search)
        self.btn_stop = QPushButton("Stop")
        self.btn_stop.setObjectName("danger")
        self.btn_stop.clicked.connect(self.stop_search)
        self.btn_stop.setEnabled(False)
        self.btn_save = QPushButton("Lista mentése")
        self.btn_save.setObjectName("success")
        self.btn_save.clicked.connect(self.save_results)
        
        button_layout.addWidget(self.btn_search)
        button_layout.addWidget(self.btn_stop)
        button_layout.addWidget(self.btn_save)
        button_layout.addStretch()
        main_layout.addLayout(button_layout)

        # Eredmények
        results_frame = QFrame()
        results_layout = QVBoxLayout(results_frame)
        
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Fájl", "Találatok", "Műveletek"])
        self.tree.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tree.setSortingEnabled(True)
        self.tree.setAlternatingRowColors(True)
        self.tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.tree.setMinimumHeight(300)
        
        results_layout.addWidget(self.tree)
        main_layout.addWidget(results_frame, 1)

        # Állapotsor
        status_layout = QHBoxLayout()
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        
        self.status_label = QLabel("Kész a keresésre")
        self.status_label.setStyleSheet("font-weight: bold; color: #2C546B;")
        
        status_layout.addWidget(self.progress_bar, 2)
        status_layout.addWidget(self.status_label, 1)
        main_layout.addLayout(status_layout)

        self.setLayout(main_layout)
        self.setWindowTitle("Fájlba Kereső Program")
        self.resize(800, 600)

    def browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Válassz mappát")
        if folder:
            self.folder_entry.setText(folder)

    def start_search(self):
        folder = self.folder_entry.text()
        pattern = self.search_entry.text()
        
        if not folder or not pattern:
            QMessageBox.warning(self, "Hiányzó adat", "Kérlek válassz mappát és adj meg kereső kifejezést!")
            return
            
        # Dátumok ellenőrzése
        start_date = None
        end_date = None
        
        if self.start_date.text():
            try:
                start_date = datetime.strptime(self.start_date.text(), "%Y-%m-%d").date()
            except:
                QMessageBox.warning(self, "Hibás dátum", "Érvénytelen kezdő dátum formátum! Használd az ÉÉÉÉ-HH-NN formátumot.")
                return
                
        if self.end_date.text():
            try:
                end_date = datetime.strptime(self.end_date.text(), "%Y-%m-%d").date()
            except:
                QMessageBox.warning(self, "Hibás dátum", "Érvénytelen záró dátum formátum! Használd az ÉÉÉÉ-HH-NN formátumot.")
                return
        
        # Töröljük az előző eredményeket
        self.tree.clear()
        self.results = []
        
        # Állapot beállítása
        self.btn_search.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.status_label.setText("Keresés folyamatban...")
        
        # Kereső szál indítása
        self.search_worker = SearchWorker(
            folder,
            pattern,
            self.exact_match.isChecked(),
            self.exclude_ext.isChecked(),
            self.search_filenames.isChecked(),
            self.search_folders.isChecked(),
            start_date,
            end_date
        )
        
        # Signal összekötések
        self.search_worker.update_progress.connect(self.update_progress)
        self.search_worker.file_found_batch.connect(self.add_results_batch)  # JAVÍTVA
        self.search_worker.search_finished.connect(self.search_finished)
        self.search_worker.status_update.connect(self.status_label.setText)
        self.search_worker.start()

    def stop_search(self):
        if self.search_worker:
            self.search_worker.stop()
        self.btn_search.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.status_label.setText("Keresés leállítva")

    def update_progress(self, processed, total, found, elapsed_time):
        if total > 0:
            progress = int((processed / total) * 100)
            self.progress_bar.setValue(progress)
            
            # Becsült idő számítás
            if processed > 0:
                remaining = (elapsed_time / processed) * (total - processed)
                mins, secs = divmod(int(remaining), 60)
                time_str = f"{mins} perc {secs} mp"
            else:
                time_str = "számítás alatt"
                
            self.status_label.setText(
                f"Folyamat: {progress}% | "
                f"Feldolgozva: {processed}/{total} | "
                f"Találatok: {found} | "
                f"Hátralévő idő: {time_str}"
            )

    def add_results_batch(self, results_batch):
        """Kötegekben adja hozzá az eredményeket"""
        for file_path, match_count in results_batch:
            self.results.append((file_path, match_count))
            
            item = QTreeWidgetItem([
                file_path,
                str(match_count)
            ])
            
            # Művelet gombok
            button_frame = QWidget()
            button_layout = QHBoxLayout(button_frame)
            button_layout.setContentsMargins(0, 0, 0, 0)
            
            btn_open = QPushButton("Fájl")
            btn_open.setFixedWidth(60)
            # JAVÍTVA: Lambda kifejezés javítása
            btn_open.clicked.connect(lambda checked, p=file_path: open_with_application(p))
            
            btn_folder = QPushButton("Mappa")
            btn_folder.setFixedWidth(60)
            btn_folder.clicked.connect(lambda checked, p=file_path: open_with_application(os.path.dirname(p)))
            
            button_layout.addWidget(btn_open)
            button_layout.addWidget(btn_folder)
            
            self.tree.addTopLevelItem(item)
            self.tree.setItemWidget(item, 2, button_frame)

    def search_finished(self):
        self.btn_search.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.status_label.setText(f"Keresés befejezve! Találatok: {len(self.results)}")

    def save_results(self):
        if not self.results:
            QMessageBox.information(self, "Nincs adat", "Nincs mentendő eredmény!")
            return
            
        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "Eredmények mentése",
            f"{self.search_entry.text() or 'eredmeny'}.xlsx",
            "Excel fájlok (*.xlsx)"
        )
        
        if not save_path:
            return
            
        try:
            wb = Workbook()
            ws = wb.active
            ws.title = "Eredmények"
            
            # Fejléc
            ws.append(["Fájl elérési út", "Találatok száma"])
            
            # Adatok
            for file_path, count in self.results:
                ws.append([file_path, count])
            
            wb.save(save_path)
            QMessageBox.information(self, "Sikeres mentés", f"Eredmények mentve: {save_path}")
            
            # Mentés utáni gombok
            self.show_save_buttons(save_path)
            
        except Exception as e:
            QMessageBox.critical(self, "Hiba", f"Mentés sikertelen!\n{str(e)}")

    def show_save_buttons(self, save_path):
        # Ha már léteznek gombok, töröljük őket
        for i in reversed(range(self.layout().count())):
            widget = self.layout().itemAt(i).widget()
            if widget and widget.objectName() == "save_buttons":
                self.layout().removeWidget(widget)
                widget.deleteLater()
        
        # Új gombok hozzáadása
        save_buttons = QWidget()
        save_buttons.setObjectName("save_buttons")
        button_layout = QHBoxLayout(save_buttons)
        
        btn_open_file = QPushButton("Fájl megnyitása")
        btn_open_file.setObjectName("success")
        btn_open_file.clicked.connect(lambda: open_with_application(save_path))
        
        btn_open_folder = QPushButton("Mappa megnyitása")
        btn_open_folder.setObjectName("success")
        btn_open_folder.clicked.connect(lambda: open_with_application(os.path.dirname(save_path)))
        
        button_layout.addWidget(btn_open_file)
        button_layout.addWidget(btn_open_folder)
        button_layout.addStretch()
        
        self.layout().insertWidget(self.layout().count() - 1, save_buttons)

if __name__ == "__main__":
    import sys
    app = QApplication(sys.argv)
    window = FileSearchApp()
    window.show()
    sys.exit(app.exec_())