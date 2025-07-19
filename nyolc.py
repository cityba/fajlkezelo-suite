import os
import shutil
import sys
import time
import threading
from datetime import datetime
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QFileDialog, QMessageBox, QTreeWidget, QTreeWidgetItem,
    QHeaderView, QProgressBar, QSizePolicy, QAbstractItemView
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QFont, QBrush, QColor


class SearchThread(QThread):
    update_progress = pyqtSignal(int, int)
    found_file = pyqtSignal(str, float, str, str)
    finished = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, folder, size_limit):
        super().__init__()
        self.folder = folder
        self.size_limit = size_limit * 1024 * 1024  # MB to bytes
        self.stop_search = False
        self.total_files = 0
        self.scanned_files = 0
        self.found_files = 0

    def run(self):
        try:
            self.total_files = self.count_files(self.folder)
            self.scanned_files = 0
            self.found_files = 0
            self.search_files(self.folder)
        except Exception as e:
            self.error.emit(str(e))
        finally:
            self.finished.emit()

    def count_files(self, folder):
        count = 0
        for entry in os.scandir(folder):
            if self.stop_search:
                return count
            if entry.is_file():
                count += 1
            elif entry.is_dir():
                try:
                    count += self.count_files(entry.path)
                except PermissionError:
                    continue
        return count

    def search_files(self, folder):
        for entry in os.scandir(folder):
            if self.stop_search:
                return

            if entry.is_file():
                self.scanned_files += 1
                progress = int((self.scanned_files / self.total_files) * 100) if self.total_files > 0 else 0
                self.update_progress.emit(self.scanned_files, progress)

                if entry.stat().st_size > self.size_limit:
                    size = entry.stat().st_size
                    modification_time = datetime.fromtimestamp(entry.stat().st_mtime)
                    date = modification_time.strftime("%Y-%m-%d")
                    self.found_file.emit(entry.name, size, date, entry.path)
                    self.found_files += 1

            elif entry.is_dir():
                try:
                    self.search_files(entry.path)
                except PermissionError:
                    continue

    def stop(self):
        self.stop_search = True


class FileFinderApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Fájlkereső és Törlő")
        self.setGeometry(100, 100, 1000, 650)
        
        # Set dark theme colors
        self.setStyleSheet("""
            QMainWindow, QWidget {
                background-color: #2D2D30;
                color: #FFFFFF;
                font-family: 'Segoe UI';
            }
            QLabel {
                color: #DCDCDC;
            }
            QLineEdit {
                background-color: #3E3E42;
                border: 1px solid #555555;
                color: #FFFFFF;
                padding: 5px;
                border-radius: 3px;
            }
            QPushButton {
                background-color: #007ACC;
                color: white;
                font-weight: bold;
                padding: 8px 15px;
                border-radius: 3px;
                border: none;
            }
            QPushButton:hover {
                background-color: #1C97EA;
            }
            QPushButton:disabled {
                background-color: #505050;
                color: #808080;
            }
            QPushButton#deleteButton {
                background-color: #D9534F;
            }
            QPushButton#deleteButton:hover {
                background-color: #FF5733;
            }
            QTreeWidget {
                background-color: #252526;
                color: #DCDCDC;
                border: 1px solid #3F3F46;
                font-size: 11pt;
                alternate-background-color: #2D2D30;
                gridline-color: #3F3F46;
            }
            QHeaderView::section {
                background-color: #3E3E42;
                color: #FFFFFF;
                padding: 5px;
                border: none;
                font-weight: bold;
            }
            QProgressBar {
                background-color: #3E3E42;
                border: 1px solid #555555;
                border-radius: 3px;
                text-align: center;
                color: white;
            }
            QProgressBar::chunk {
                background-color: #007ACC;
                width: 10px;
            }
        """)
        
        self.folder_path = ""
        self.size_limit = 100.0
        self.search_thread = None
        self.selected_files = []
        self.added_files = set()

        self.create_ui()
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self.update_remaining_time)
        self.remaining_time = 0
        self.start_time = 0

    def create_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)

        # Header area
        header_layout = QHBoxLayout()
        
        folder_layout = QVBoxLayout()
        folder_layout.addWidget(QLabel("Mappa kiválasztása:"))
        self.folder_entry = QLineEdit()
        self.folder_entry.setPlaceholderText("Válassz mappát...")
        folder_layout.addWidget(self.folder_entry)
        header_layout.addLayout(folder_layout)
        
        browse_btn = QPushButton("Tallózás")
        browse_btn.clicked.connect(self.browse_folder)
        browse_btn.setFixedWidth(100)
        header_layout.addWidget(browse_btn)
        
        size_layout = QVBoxLayout()
        size_layout.addWidget(QLabel("Fájlméret minimum limit (MB):"))
        self.size_entry = QLineEdit()
        self.size_entry.setText("100.0")
        size_layout.addWidget(self.size_entry)
        header_layout.addLayout(size_layout)
        
        search_btn = QPushButton("Keresés")
        search_btn.clicked.connect(self.start_search)
        search_btn.setFixedWidth(100)
        header_layout.addWidget(search_btn)
        
        main_layout.addLayout(header_layout)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("Keresés előkészítése...")
        main_layout.addWidget(self.progress_bar)
        
        # Status label
        self.status_label = QLabel("Kész. Válassz mappát és méretlimit, majd indítsd a keresést!")
        main_layout.addWidget(self.status_label)
        
        # File list table
        self.tree = QTreeWidget()
        self.tree.setColumnCount(4)
        self.tree.setHeaderLabels(["Fájlnév", "Méret (MB)", "Módosítás dátuma", "Fájl elérési útja"])
        self.tree.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.tree.setSortingEnabled(True)
        self.tree.setAlternatingRowColors(True)
        self.tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.tree.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.tree.header().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.tree.header().setSectionResizeMode(3, QHeaderView.Stretch)
        self.tree.itemSelectionChanged.connect(self.update_selected_files)
        main_layout.addWidget(self.tree, 1)
        
        # Delete button
        self.delete_btn = QPushButton("Kijelöltek törlése")
        self.delete_btn.setObjectName("deleteButton")
        self.delete_btn.setEnabled(False)
        self.delete_btn.clicked.connect(self.delete_selected_files)
        self.delete_btn.setFixedHeight(40)
        self.delete_btn.setFont(QFont("Segoe UI", 10, QFont.Bold))
        main_layout.addWidget(self.delete_btn)

    def browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Válassz mappát")
        if folder:
            self.folder_path = folder
            self.folder_entry.setText(folder)

    def start_search(self):
        if not self.folder_path or not os.path.isdir(self.folder_path):
            QMessageBox.critical(self, "Hiba", "Érvényes mappát kell kiválasztani!")
            return
        
        try:
            self.size_limit = float(self.size_entry.text())
            if self.size_limit <= 0:
                raise ValueError
        except ValueError:
            QMessageBox.critical(self, "Hiba", "Érvényes pozitív számot adj meg méretlimitnek!")
            return
        
        # Clear previous results
        self.tree.clear()
        self.selected_files.clear()
        self.added_files.clear()
        self.delete_btn.setEnabled(False)
        
        # Initialize progress
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("Fájlok számolása...")
        self.status_label.setText("Fájlok számolása...")
        QApplication.processEvents()
        
        # Start search thread
        if self.search_thread and self.search_thread.isRunning():
            self.search_thread.stop()
            self.search_thread.wait()
        
        self.search_thread = SearchThread(self.folder_path, self.size_limit)
        self.search_thread.found_file.connect(self.add_file_to_tree)
        self.search_thread.update_progress.connect(self.update_progress)
        self.search_thread.finished.connect(self.on_search_finished)
        self.search_thread.error.connect(self.on_search_error)
        
        self.start_time = time.time()
        self.remaining_time = 0
        self.update_timer.start(1000)  # Update every second
        
        self.search_thread.start()

    def update_progress(self, scanned_files, progress):
        self.progress_bar.setValue(progress)
        scanned_text = f"{scanned_files:,}".replace(",", " ")
        self.status_label.setText(f"Keresés folyamatban... ({scanned_text} fájl átvizsgálva)")

    def update_remaining_time(self):
        if self.search_thread and self.search_thread.isRunning():
            elapsed = time.time() - self.start_time
            if self.search_thread.scanned_files > 0 and self.search_thread.total_files > 0:
                remaining = (elapsed / self.search_thread.scanned_files) * (self.search_thread.total_files - self.search_thread.scanned_files)
                self.remaining_time = max(0, remaining)
            else:
                self.remaining_time = 0
                
            mins, secs = divmod(int(self.remaining_time), 60)
            self.progress_bar.setFormat(f"Keresés folyamatban... Hátralévő idő: {mins:02d}:{secs:02d}")

    def on_search_finished(self):
        self.update_timer.stop()
        self.progress_bar.setValue(100)
        self.progress_bar.setFormat("Keresés befejeződött")
        
        found_text = f"{self.search_thread.found_files:,}".replace(",", " ")
        total_text = f"{self.search_thread.scanned_files:,}".replace(",", " ")
        self.status_label.setText(f"Keresés kész! {found_text} fájl találat {total_text} fájlból")
        
        if self.search_thread.found_files > 0:
            self.delete_btn.setEnabled(True)

    def on_search_error(self, message):
        self.update_timer.stop()
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("Hiba történt")
        self.status_label.setText(f"Hiba: {message}")
        QMessageBox.critical(self, "Hiba", message)

    def add_file_to_tree(self, file_name, size, date, filepath):
        if filepath in self.added_files:
            return
            
        self.added_files.add(filepath)
        size_mb = size / (1024 * 1024)
        
        item = QTreeWidgetItem(self.tree)
        item.setText(0, file_name)
        item.setText(1, f"{size_mb:.2f}")
        item.setText(2, date)
        item.setText(3, filepath)
        
        # Store full path for later access
        item.setData(0, Qt.UserRole, filepath)

    def update_selected_files(self):
        self.selected_files = []
        for item in self.tree.selectedItems():
            filepath = item.data(0, Qt.UserRole)
            if filepath:
                self.selected_files.append(filepath)
        
        self.delete_btn.setEnabled(len(self.selected_files) > 0)

    def delete_selected_files(self):
        if not self.selected_files:
            QMessageBox.warning(self, "Figyelem", "Nincs kijelölt fájl törlésre!")
            return

        confirm = QMessageBox.question(
            self, 
            "Megerősítés", 
            f"Biztosan törölni szeretnéd a {len(self.selected_files)} kijelölt fájlt?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if confirm == QMessageBox.Yes:
            deleted_count = 0
            trash_path = "C:/lomtár"
            os.makedirs(trash_path, exist_ok=True)
            
            for filepath in self.selected_files:
                try:
                    filename = os.path.basename(filepath)
                    destination = os.path.join(trash_path, filename)
                    
                    # Handle filename conflicts
                    counter = 1
                    while os.path.exists(destination):
                        name, ext = os.path.splitext(filename)
                        destination = os.path.join(trash_path, f"{name}_{counter}{ext}")
                        counter += 1
                    
                    shutil.move(filepath, destination)
                    deleted_count += 1
                    
                    # Remove from tree
                    for i in range(self.tree.topLevelItemCount()):
                        item = self.tree.topLevelItem(i)
                        if item.data(0, Qt.UserRole) == filepath:
                            self.tree.takeTopLevelItem(i)
                            break
                    
                except Exception as e:
                    QMessageBox.warning(self, "Hiba", f"A(z) {filepath} törlése sikertelen: {str(e)}")
            
            self.selected_files.clear()
            self.delete_btn.setEnabled(False)
            self.status_label.setText(f"{deleted_count} fájl sikeresen törölve!")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    # Set high DPI scaling
    app.setAttribute(Qt.AA_EnableHighDpiScaling)
    
    window = FileFinderApp()
    window.show()
    sys.exit(app.exec_())