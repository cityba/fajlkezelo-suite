import sys
import os
import filecmp
import multiprocessing
from concurrent.futures import ProcessPoolExecutor
from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, 
                             QLineEdit, QPushButton, QFileDialog, QTextEdit, 
                             QLabel, QGroupBox, QProgressBar, QGridLayout)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont

# --- ÜZLETI LOGIKA (Külön folyamatban fut) ---
def get_all_files_and_dirs(directory):
    file_list = []
    dir_list = []
    for root, dirs, files in os.walk(directory):
        for d in dirs:
            dir_list.append(os.path.relpath(os.path.join(root, d), directory))
        for f in files:
            file_list.append(os.path.relpath(os.path.join(root, f), directory))
    return set(file_list), set(dir_list)

def compare_file_pair(args):
    f1, f2, rel_path, name2 = args
    if not os.path.exists(f2):
        folder = os.path.dirname(rel_path) or "Gyökér"
        return f"[-] Hiányzik a(z) [{name2}] mappából | Elérési út: {folder} | Fájl: {os.path.basename(rel_path)}"
    if not filecmp.cmp(f1, f2, shallow=False):
        folder = os.path.dirname(rel_path) or "Gyökér"
        return f"[!] ELTÉRŐ TARTALOM | Mappa: {folder} | Fájl: {os.path.basename(rel_path)}"
    return None

# --- HÁTTÉRBEN FUTÓ SZÁL ---
class CompareWorker(QThread):
    progress_sig = pyqtSignal(int)
    result_sig = pyqtSignal(list)
    status_sig = pyqtSignal(str)

    def __init__(self, dir1, dir2):
        super().__init__()
        self.dir1 = dir1
        self.dir2 = dir2
        self.name1 = os.path.basename(self.dir1.rstrip(os.sep))
        self.name2 = os.path.basename(self.dir2.rstrip(os.sep))

    def run(self):
        try:
            self.status_sig.emit("Struktúra elemzése...")
            files1, dirs1 = get_all_files_and_dirs(self.dir1)
            files2, dirs2 = get_all_files_and_dirs(self.dir2)
            
            results = []
            
            # 1. Teljes mappák hiánya
            left_dirs_only = dirs1 - dirs2
            for d in sorted(left_dirs_only):
                results.append(f"!!! HIÁNYZIK A(Z) [{self.name2}] MAPPÁBÓL (TELJES KÖNYVTÁR): {d}")

            right_dirs_only = dirs2 - dirs1
            for d in sorted(right_dirs_only):
                results.append(f"!!! HIÁNYZIK A(Z) [{self.name1}] MAPPÁBÓL (TELJES KÖNYVTÁR): {d}")

            # 2. Fájlok hiánya
            left_files_only = files1 - files2
            for f in left_files_only:
                results.append(f"[-] Hiányzik a(z) [{self.name2}] mappából | Mappa: {os.path.dirname(f) or 'Gyökér'} | Fájl: {os.path.basename(f)}")

            right_files_only = files2 - files1
            for f in right_files_only:
                results.append(f"[-] Hiányzik a(z) [{self.name1}] mappából | Mappa: {os.path.dirname(f) or 'Gyökér'} | Fájl: {os.path.basename(f)}")

            # 3. Bináris tartalom ellenőrzése
            common = list(files1 & files2)
            if common:
                self.status_sig.emit(f"Fájltartalom ellenőrzése ({len(common)} db)...")
                tasks = [(os.path.join(self.dir1, f), os.path.join(self.dir2, f), f, self.name2) for f in common]
                
                with ProcessPoolExecutor(max_workers=multiprocessing.cpu_count()) as executor:
                    for i, res in enumerate(executor.map(compare_file_pair, tasks)):
                        if res:
                            results.append(res)
                        prog = int(((i + 1) / len(common)) * 100)
                        self.progress_sig.emit(prog)
            
            self.result_sig.emit(results)
            self.status_sig.emit("Kész!")
        except Exception as e:
            self.status_sig.emit(f"Hiba történt: {str(e)}")

# --- GUI ---
class ProFolderDiff(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        self.setWindowTitle('Profi Multi-Core Mappa Összehasonlító')
        self.setGeometry(100, 100, 1200, 800)
        
        layout = QVBoxLayout()
        
        # Mappa választók
        grid = QGridLayout()
        self.path1 = QLineEdit()
        self.path2 = QLineEdit()
        btn1 = QPushButton("Tallózás (Bal)")
        btn2 = QPushButton("Tallózás (Jobb)")
        btn1.clicked.connect(lambda: self.select_dir(self.path1))
        btn2.clicked.connect(lambda: self.select_dir(self.path2))
        
        grid.addWidget(QLabel("Referencia mappa:"), 0, 0)
        grid.addWidget(self.path1, 0, 1)
        grid.addWidget(btn1, 0, 2)
        grid.addWidget(QLabel("Összehasonlítandó:"), 1, 0)
        grid.addWidget(self.path2, 1, 1)
        grid.addWidget(btn2, 1, 2)
        layout.addLayout(grid)

        self.run_btn = QPushButton("ELEMZÉS INDÍTÁSA")
        self.run_btn.setFixedHeight(50)
        self.run_btn.setStyleSheet("background-color: #2c3e50; color: white; font-weight: bold; font-size: 14px;")
        self.run_btn.clicked.connect(self.start_work)
        layout.addWidget(self.run_btn)

        self.status_label = QLabel("Állapot: Készenlétben")
        layout.addWidget(self.status_label)
        self.pbar = QProgressBar()
        layout.addWidget(self.pbar)

        self.results = QTextEdit()
        self.results.setReadOnly(True)
        self.results.setFont(QFont("Consolas", 10))
        layout.addWidget(self.results)

        self.setLayout(layout)

    def select_dir(self, edit):
        d = QFileDialog.getExistingDirectory(self, "Válaszd ki a mappát")
        if d: edit.setText(d)

    def start_work(self):
        d1, d2 = self.path1.text(), self.path2.text()
        if not os.path.isdir(d1) or not os.path.isdir(d2):
            return

        self.results.clear()
        self.run_btn.setEnabled(False)
        self.worker = CompareWorker(d1, d2)
        self.worker.progress_sig.connect(self.pbar.setValue)
        self.worker.status_sig.connect(self.status_label.setText)
        self.worker.result_sig.connect(self.finish_work)
        self.worker.start()

    def finish_work(self, results):
        if not results:
            self.results.setText("A két mappa tartalma megegyezik!")
        else:
            header = f"ELEMZÉS EREDMÉNYE\n" + "="*80 + "\n\n"
            self.results.setText(header + "\n".join(results))
        self.run_btn.setEnabled(True)
        self.pbar.setValue(100)

if __name__ == '__main__':
    multiprocessing.freeze_support()
    app = QApplication(sys.argv)
    window = ProFolderDiff()
    window.show()
    sys.exit(app.exec_())