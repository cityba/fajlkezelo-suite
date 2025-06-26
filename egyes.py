import os
import shutil
import datetime
import platform
import fnmatch
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTreeWidget,
    QTreeWidgetItem, QFileDialog, QAbstractItemView, QHeaderView,
    QLabel, QCheckBox, QMessageBox, QSplitter, QLineEdit, QFrame,
    QDialog, QListWidget, QProgressBar
)
from PyQt5.QtCore import Qt, QSize, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QIcon

class FileCopyApp(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.file_vars = {}  # Kulcs: fájl elérési út, érték: { "item": QTreeWidgetItem, "selected": bool, "duplicate": bool }
        self.duplicates = {}
        self.selected_items = set()  # Elérési utakat tárolunk
        self.empty_folders = []
        self.sort_column = None
        self.sort_reverse = False
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(10, 10, 10, 10)
        
        # Input frame
        input_frame = QFrame()
        input_frame.setFrameShape(QFrame.StyledPanel)
        input_layout = QVBoxLayout(input_frame)
        
        # Source folder
        source_layout = QHBoxLayout()
        lbl_source = QLabel("Forrás mappa:")
        lbl_source.setStyleSheet("color: white; font-weight: bold;")
        self.source_entry = QLineEdit()
        btn_browse_source = QPushButton("Tallóz...")
        btn_browse_source.clicked.connect(self.browse_source)
        source_layout.addWidget(lbl_source)
        source_layout.addWidget(self.source_entry)
        source_layout.addWidget(btn_browse_source)
        input_layout.addLayout(source_layout)
        
        # Target folder
        target_layout = QHBoxLayout()
        lbl_target = QLabel("Cél mappa:")
        lbl_target.setStyleSheet("color: white; font-weight: bold;")
        self.target_entry = QLineEdit()
        btn_browse_target = QPushButton("Tallóz...")
        btn_browse_target.clicked.connect(self.browse_target)
        target_layout.addWidget(lbl_target)
        target_layout.addWidget(self.target_entry)
        target_layout.addWidget(btn_browse_target)
        input_layout.addLayout(target_layout)
        
        # File types
        filetype_layout = QHBoxLayout()
        lbl_filetype = QLabel("Fájltípusok (pl: .py, .jpg, *):")
        lbl_filetype.setStyleSheet("color: white; font-weight: bold;")
        self.filetype_entry = QLineEdit()
        self.filetype_entry.setText(".py, .html, .js, .jpg, .png")
        btn_search = QPushButton("Keresés")
        btn_search.clicked.connect(self.search_files)
        filetype_layout.addWidget(lbl_filetype)
        filetype_layout.addWidget(self.filetype_entry)
        filetype_layout.addWidget(btn_search)
        input_layout.addLayout(filetype_layout)
        
        main_layout.addWidget(input_frame)
        
        # Tree widget
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Kijelölés", "Fájlnév", "Méret (KB)", "Módosítva", "Duplikátum"])
        self.tree.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.tree.setSortingEnabled(True)
        self.tree.setAlternatingRowColors(True)
        self.tree.header().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.tree.itemClicked.connect(self.on_tree_click)
        main_layout.addWidget(self.tree, 1)
        
        # Progress bar
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        main_layout.addWidget(self.progress)
        
        # Action buttons
        btn_layout = QHBoxLayout()
        btn_select_all = QPushButton("Összes kijelölése")
        btn_select_all.clicked.connect(self.select_all)
        btn_deselect_all = QPushButton("Kijelölés visszavonása")
        btn_deselect_all.clicked.connect(self.deselect_all)
        btn_duplicates = QPushButton("Duplikáltak kezelése")
        btn_duplicates.clicked.connect(self.manage_duplicates)
        btn_empty_folders = QPushButton("Üres mappák kezelése")
        btn_empty_folders.clicked.connect(self.manage_empty_folders)
        btn_copy = QPushButton("Másolás")
        btn_copy.clicked.connect(self.copy_files)
        
        btn_layout.addWidget(btn_select_all)
        btn_layout.addWidget(btn_deselect_all)
        btn_layout.addWidget(btn_duplicates)
        btn_layout.addWidget(btn_empty_folders)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_copy)
        
        main_layout.addLayout(btn_layout)
        
        # Status bar
        self.status_label = QLabel("Kész")
        self.status_label.setStyleSheet("background-color: #e0e0e0; padding: 5px;")
        main_layout.addWidget(self.status_label)
        
        self.setLayout(main_layout)
        
        # DPI awareness for Windows
        if platform.system() == 'Windows':
            try:
                from ctypes import windll
                windll.shcore.SetProcessDpiAwareness(1)
            except:
                pass

    def browse_source(self):
        folder = QFileDialog.getExistingDirectory(self, "Válassz forrás mappát")
        if folder:
            self.source_entry.setText(folder)

    def browse_target(self):
        folder = QFileDialog.getExistingDirectory(self, "Válassz cél mappát")
        if folder:
            self.target_entry.setText(folder)

    def search_files(self):
        # Reset previous search
        self.file_vars = {}
        self.duplicates = {}
        self.selected_items = set()
        self.empty_folders = []
        self.tree.clear()
        
        # Get parameters
        source_folder = self.source_entry.text()
        if not source_folder or not os.path.isdir(source_folder):
            QMessageBox.critical(self, "Hiba", "Érvénytelen forrás mappa!")
            return
        
        # Process file types
        raw_file_types = self.filetype_entry.text().split(',')
        file_types = [ft.strip().lower() for ft in raw_file_types if ft.strip()]
        
        if not file_types:
            QMessageBox.critical(self, "Hiba", "Érvénytelen fájltípusok!")
            return
        
        # Start search in a thread
        self.scanner = FileScanner(source_folder, file_types)
        self.scanner.file_found.connect(self.add_file_item)
        self.scanner.progress.connect(self.progress.setValue)
        self.scanner.finished.connect(self.on_search_finished)
        self.scanner.empty_folders_found.connect(self.set_empty_folders)
        
        self.progress.setVisible(True)
        self.progress.setValue(0)
        self.scanner.start()

    def set_empty_folders(self, folders):
        self.empty_folders = folders

    def on_search_finished(self, count):
        self.progress.setVisible(False)
        self.status_label.setText(f"Keresés kész: {count} fájl találat")
        if count == 0:
            QMessageBox.information(self, "Info", "Nincs találat a megadott feltételek mellett!")

    def add_file_item(self, file, path, size, mod_time, is_duplicate):
        item = QTreeWidgetItem([
            "☐", 
            file, 
            str(size),
            mod_time,
            "Igen" if is_duplicate else "Nem"
        ])
        item.setData(0, Qt.UserRole, path)
        self.tree.addTopLevelItem(item)
        
        # Store file data
        self.file_vars[path] = {
            "item": item,
            "selected": False,
            "duplicate": is_duplicate
        }
        
        # Highlight duplicates
        if is_duplicate:
            for i in range(5):
                item.setBackground(i, Qt.yellow)

    def on_tree_click(self, item, column):
        if column == 0:  # Selection column
            current_value = item.text(0)
            new_value = "☑" if current_value == "☐" else "☐"
            item.setText(0, new_value)
            
            path = item.data(0, Qt.UserRole)
            if path in self.file_vars:
                self.file_vars[path]["selected"] = (new_value == "☑")
                
                if new_value == "☑":
                    self.selected_items.add(path)
                else:
                    self.selected_items.discard(path)

    def select_all(self):
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            item.setText(0, "☑")
            
            path = item.data(0, Qt.UserRole)
            if path in self.file_vars:
                self.file_vars[path]["selected"] = True
                self.selected_items.add(path)

    def deselect_all(self):
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            item.setText(0, "☐")
            
            path = item.data(0, Qt.UserRole)
            if path in self.file_vars:
                self.file_vars[path]["selected"] = False
        self.selected_items = set()

    def manage_duplicates(self):
        # Collect duplicates
        duplicates = {}
        for path, file_data in self.file_vars.items():
            if file_data["duplicate"]:
                file_name = os.path.basename(path)
                if file_name not in duplicates:
                    duplicates[file_name] = []
                duplicates[file_name].append(path)
        
        if not duplicates:
            QMessageBox.information(self, "Info", "Nincsenek duplikált fájlok")
            return
            
        manager = DuplicateManager(self, duplicates)
        manager.exec_()
    
    def manage_empty_folders(self):
        if not self.empty_folders:
            QMessageBox.information(self, "Info", "Nincsenek üres mappák")
            return
            
        manager = EmptyFolderManager(self, self.empty_folders)
        manager.exec_()    

    def copy_files(self):
        # Get selected files
        selected_files = []
        for path, file_data in self.file_vars.items():
            if file_data["selected"]:
                selected_files.append(path)
        
        if not selected_files:
            QMessageBox.information(self, "Info", "Nincsenek kijelölt fájlok")
            return
        
        target_folder = self.target_entry.text()
        if not target_folder:
            QMessageBox.critical(self, "Hiba", "Nincs célmappa kiválasztva!")
            return
        
        # Create target folder
        os.makedirs(target_folder, exist_ok=True)
        
        # Copy files
        copied_count = 0
        for src_path in selected_files:
            try:
                file_name = os.path.basename(src_path)
                dst_path = os.path.join(target_folder, file_name)
                shutil.copy2(src_path, dst_path)
                copied_count += 1
            except Exception as e:
                QMessageBox.critical(self, "Hiba", f"Hiba történt: {str(e)}")
        
        self.status_label.setText(f"{copied_count} fájl sikeresen másolva")
        QMessageBox.information(self, "Siker", f"{copied_count} fájl sikeresen átmásolva a célmappába!")

class FileScanner(QThread):
    file_found = pyqtSignal(str, str, int, str, bool)
    progress = pyqtSignal(int)
    finished = pyqtSignal(int)
    empty_folders_found = pyqtSignal(list)

    def __init__(self, folder, file_types):
        super().__init__()
        self.folder = folder
        self.file_types = file_types
        self._is_running = True
        self.seen_files = set()

    def run(self):
        # Find empty folders
        self.empty_folders_found.emit(self.find_empty_folders(self.folder))
        
        # Find files
        found_files = []
        total_files = sum(len(files) for _, _, files in os.walk(self.folder))
        
        if total_files == 0:
            self.finished.emit(0)
            return
            
        processed = 0
        for root, _, files in os.walk(self.folder):
            for file in files:
                if not self._is_running:
                    return
                
                file_lower = file.lower()
                matched = False
                
                # Check file types
                if "*" in self.file_types:
                    matched = True
                else:
                    for pattern in self.file_types:
                        if fnmatch.fnmatch(file_lower, pattern) or fnmatch.fnmatch(file_lower, f"*{pattern}"):
                            matched = True
                            break
                
                if matched:
                    path = os.path.join(root, file)
                    size = os.path.getsize(path) // 1024  # KB
                    mod_time = datetime.datetime.fromtimestamp(os.path.getmtime(path)).strftime('%Y-%m-%d %H:%M')
                    
                    # Check for duplicates
                    file_key = (file, size)
                    is_duplicate = file_key in self.seen_files
                    self.seen_files.add(file_key)
                    
                    self.file_found.emit(file, path, size, mod_time, is_duplicate)
                    found_files.append(path)
                
                processed += 1
                self.progress.emit(int((processed / total_files) * 100))
        
        self.finished.emit(len(found_files))
    
    def find_empty_folders(self, start_folder):
        empty_folders = []
        for root, dirs, files in os.walk(start_folder, topdown=False):
            if not os.listdir(root):
                empty_folders.append(root)
        return empty_folders
    
    def stop(self):
        self._is_running = False
        self.quit()
        self.wait()

class DuplicateManager(QDialog):
    def __init__(self, parent, duplicates):
        super().__init__(parent)
        self.duplicates = duplicates
        self.setWindowTitle("Duplikált fájlok kezelése")
        self.setGeometry(100, 100, 1000, 700)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        
        # Group tree
        group_layout = QVBoxLayout()
        lbl_groups = QLabel("Duplikált fájlcsoportok")
        lbl_groups.setFont(QFont("Arial", 10, QFont.Bold))
        group_layout.addWidget(lbl_groups)
        
        self.group_tree = QTreeWidget()
        self.group_tree.setHeaderLabels(["Fájlnév", "Példányok"])
        self.group_tree.itemSelectionChanged.connect(self.on_group_selected)
        group_layout.addWidget(self.group_tree)
        
        # File tree
        file_layout = QVBoxLayout()
        lbl_files = QLabel("Fájlpéldányok")
        lbl_files.setFont(QFont("Arial", 10, QFont.Bold))
        file_layout.addWidget(lbl_files)
        
        self.file_tree = QTreeWidget()
        self.file_tree.setHeaderLabels(["Státusz", "Fájlnév", "Méret (KB)", "Módosítva", "Elérési út"])
        file_layout.addWidget(self.file_tree)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_delete_older = QPushButton("Régebbiek törlése")
        btn_delete_older.clicked.connect(self.delete_older)
        btn_delete_selected = QPushButton("Kijelöltek törlése")
        btn_delete_selected.clicked.connect(self.delete_selected)
        btn_close = QPushButton("Bezárás")
        btn_close.clicked.connect(self.close)
        
        btn_layout.addWidget(btn_delete_older)
        btn_layout.addWidget(btn_delete_selected)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_close)
        
        # Add to main layout
        layout.addLayout(group_layout)
        layout.addLayout(file_layout)
        layout.addLayout(btn_layout)
        
        self.setLayout(layout)
        
        # Populate groups
        self.populate_groups()

    def populate_groups(self):
        for file_name, paths in self.duplicates.items():
            item = QTreeWidgetItem([file_name, str(len(paths))])
            item.setData(0, Qt.UserRole, paths)
            self.group_tree.addTopLevelItem(item)

    def on_group_selected(self):
        selected = self.group_tree.selectedItems()
        if not selected:
            return
            
        item = selected[0]
        paths = item.data(0, Qt.UserRole)
        self.file_tree.clear()
        
        # Sort by modification time
        sorted_paths = sorted(paths, key=lambda p: os.path.getmtime(p))
        
        for i, path in enumerate(sorted_paths):
            file_name = os.path.basename(path)
            size = os.path.getsize(path) // 1024
            mod_time = datetime.datetime.fromtimestamp(os.path.getmtime(path)).strftime('%Y-%m-%d %H:%M')
            status = "✅ MEGŐRIZENDŐ" if i == len(sorted_paths)-1 else "❌ TÖRÖLHETŐ"
            
            item = QTreeWidgetItem([status, file_name, str(size), mod_time, path])
            self.file_tree.addTopLevelItem(item)

    def delete_older(self):
        to_delete = []
        for i in range(self.file_tree.topLevelItemCount()):
            item = self.file_tree.topLevelItem(i)
            if item.text(0) == "❌ TÖRÖLHETŐ":
                to_delete.append(item.text(4))  # Path is in column 4
        
        self.delete_files(to_delete)

    def delete_selected(self):
        to_delete = [item.text(4) for item in self.file_tree.selectedItems()]
        self.delete_files(to_delete)

    def delete_files(self, paths):
        if not paths:
            QMessageBox.information(self, "Info", "Nincsenek törölhető fájlok")
            return
            
        reply = QMessageBox.question(
            self, 'Megerősítés',
            f"{len(paths)} fájl törlése?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            deleted = 0
            errors = []
            
            for path in paths:
                try:
                    os.remove(path)
                    deleted += 1
                except Exception as e:
                    errors.append(f"{path}: {str(e)}")
            
            # Refresh file list
            self.on_group_selected()
            
            # Show result
            if errors:
                error_msg = "\n".join(errors[:5])
                if len(errors) > 5:
                    error_msg += f"\n... és további {len(errors)-5} hiba"
                QMessageBox.critical(self, "Hiba", f"{len(errors)} fájl törlése sikertelen:\n{error_msg}")
            
            if deleted > 0:
                QMessageBox.information(self, "Siker", f"{deleted} fájl sikeresen törölve!")

class EmptyFolderManager(QDialog):
    def __init__(self, parent, empty_folders):
        super().__init__(parent)
        self.empty_folders = empty_folders
        self.setWindowTitle("Üres mappák kezelése")
        self.setGeometry(100, 100, 800, 500)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        
        # Label
        lbl = QLabel("Üres mappák listája")
        lbl.setFont(QFont("Arial", 10, QFont.Bold))
        layout.addWidget(lbl)
        
        # List widget
        self.list_widget = QListWidget()
        self.list_widget.addItems(self.empty_folders)
        self.list_widget.setSelectionMode(QListWidget.ExtendedSelection)
        layout.addWidget(self.list_widget, 1)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_select_all = QPushButton("Összes kijelölése")
        btn_select_all.clicked.connect(lambda: self.list_widget.selectAll())
        btn_deselect_all = QPushButton("Kijelölés visszavonása")
        btn_deselect_all.clicked.connect(lambda: self.list_widget.clearSelection())
        btn_delete = QPushButton("Kijelöltek törlése")
        btn_delete.clicked.connect(self.delete_selected)
        btn_close = QPushButton("Bezárás")
        btn_close.clicked.connect(self.close)
        
        btn_layout.addWidget(btn_select_all)
        btn_layout.addWidget(btn_deselect_all)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_delete)
        btn_layout.addWidget(btn_close)
        
        layout.addLayout(btn_layout)
        self.setLayout(layout)

    def delete_selected(self):
        selected = [item.text() for item in self.list_widget.selectedItems()]
        if not selected:
            QMessageBox.information(self, "Info", "Nincsenek kijelölt mappák")
            return
            
        reply = QMessageBox.question(
            self, 'Megerősítés',
            f"{len(selected)} mappa törlése?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            deleted = 0
            errors = []
            
            for folder in selected:
                try:
                    os.rmdir(folder)
                    deleted += 1
                    # Remove from list
                    items = self.list_widget.findItems(folder, Qt.MatchExactly)
                    if items:
                        row = self.list_widget.row(items[0])
                        self.list_widget.takeItem(row)
                except Exception as e:
                    errors.append(f"{folder}: {str(e)}")
            
            if errors:
                error_msg = "\n".join(errors[:5])
                if len(errors) > 5:
                    error_msg += f"\n... és további {len(errors)-5} hiba"
                QMessageBox.critical(self, "Hiba", f"{len(errors)} mappa törlése sikertelen:\n{error_msg}")
            
            if deleted > 0:
                QMessageBox.information(self, "Siker", f"{deleted} mappa sikeresen törölve!")