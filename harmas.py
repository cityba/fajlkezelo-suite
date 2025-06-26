import os
import subprocess
import platform
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTreeWidget,
    QTreeWidgetItem, QFileDialog, QAbstractItemView, QHeaderView,
    QLabel, QCheckBox, QSplitter, QMessageBox, QSizePolicy, QProgressBar,
    QGraphicsView, QGraphicsScene
)
from PyQt5.QtCore import Qt, QUrl, QObject, pyqtSignal, QThread, QSize
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
from PyQt5.QtMultimediaWidgets import QVideoWidget
from PyQt5.QtGui import QPixmap, QFont, QImage, QColor, QBrush, QPainter
 
class MediaScanner(QThread):
    media_found = pyqtSignal(str, str, float, str)  # file, path, size, file_type
    progress = pyqtSignal(int)
    finished = pyqtSignal()

    def __init__(self, folder):
        super().__init__()
        self.folder = folder
        self._is_running = True
        self.media_exts = ['.mp3', '.mp4', '.jpg', '.jpeg', '.png', '.gif', '.mov', '.avi', '.wav', '.mkv', '.bmp', '.tiff']

    def run(self):
        total_files = 0
        for root, _, files in os.walk(self.folder):
            total_files += len(files)
            
        if total_files == 0:
            self.finished.emit()
            return
            
        processed = 0
        for root, _, files in os.walk(self.folder):
            for file in files:
                if not self._is_running:
                    return
                    
                if any(file.lower().endswith(ext) for ext in self.media_exts):
                    path = os.path.join(root, file)
                    try:
                        size = os.path.getsize(path) / (1024 * 1024)
                        file_type = self.get_file_type(file)
                        self.media_found.emit(file, path, size, file_type)
                    except Exception:
                        continue
                
                processed += 1
                if processed % 10 == 0:
                    self.progress.emit(int((processed / total_files) * 100))
        
        self.finished.emit()
    
    def get_file_type(self, filename):
        """Pontos fájltípus meghatározás a kiterjesztés alapján"""
        ext = os.path.splitext(filename)[1].lower()
        if ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff']:
            return "Kép"
        elif ext in ['.mp4', '.mov', '.avi', '.mkv']:
            return "Videó"
        elif ext in ['.mp3', '.wav']:
            return "Hang"
        return "Egyéb média"
    
    def stop(self):
        self._is_running = False
        self.quit()
        self.wait()

class ImageViewer(QGraphicsView):
    """Egyedi képnézegető komponens zoom és görgetés támogatással"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.setRenderHint(QPainter.Antialiasing)
        self.setRenderHint(QPainter.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        self.pixmap_item = None
        self.setStyleSheet("background-color: black;")
        
    def display_image(self, path):
        """Kép betöltése és megjelenítése"""
        self.scene.clear()
        
        try:
            pixmap = QPixmap(path)
            if pixmap.isNull():
                raise Exception("Nem támogatott képformátum")
                
            self.pixmap_item = self.scene.addPixmap(pixmap)
            self.fit_to_view()
        except Exception as e:
            # Hiba esetén szöveg megjelenítése
            text = self.scene.addText(f"Hiba: {str(e)}")
            text.setDefaultTextColor(Qt.white)
            text.setScale(2)
            
    def fit_to_view(self):
        """Kép méretezése az ablak méretéhez"""
        if self.pixmap_item:
            self.fitInView(self.scene.sceneRect(), Qt.KeepAspectRatio)
            
    def wheelEvent(self, event):
        """Egérgörgővel zoomolás"""
        zoom_factor = 1.15
        if event.angleDelta().y() > 0:
            self.scale(zoom_factor, zoom_factor)
        else:
            self.scale(1/zoom_factor, 1/zoom_factor)
            
    def resizeEvent(self, event):
        """Ablak átméretezésekor a kép méretezése"""
        super().resizeEvent(event)
        self.fit_to_view()

class MediaFinder(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.selected_folder = ""
        self.player = QMediaPlayer()
        self.scanner = None
        self.init_ui()
        self.set_style()

    def set_style(self):
        self.setStyleSheet("""
            QWidget {
                background-color: #2d2d2d;
                color: #ffffff;
                font-family: 'Segoe UI';
            }
            QLabel {
                color: #ffffff;
                font-weight: bold;
            }
            QPushButton {
                padding: 8px 16px;
                background-color: #3498db;
                color: white;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
            QPushButton:disabled {
                background-color: #95a5a6;
            }
            QTreeWidget {
                background-color: #3c3c3c;
                alternate-background-color: #454545;
                color: #ffffff;
                font-size: 13px;
                border: 1px solid #555555;
                border-radius: 4px;
            }
            QHeaderView::section {
                background-color: #34495e;
                color: white;
                padding: 6px;
                font-weight: bold;
                border: none;
            }
            QProgressBar {
                border: 1px solid #555555;
                border-radius: 4px;
                text-align: center;
                background-color: #3c3c3c;
                color: white;
            }
            QProgressBar::chunk {
                background-color: #9b59b6;
                width: 10px;
            }
            QCheckBox {
                color: #ffffff;
                font-size: 12px;
            }
        """)

    def init_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)

        # Cím
        title = QLabel("Médiafájl Kezelő")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #3498db;")
        title.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title)

        # Mappa választó
        folder_layout = QHBoxLayout()
        self.btn_select = QPushButton("Mappa kiválasztása")
        self.btn_select.setFixedHeight(40)
        self.btn_select.clicked.connect(self.select_folder)
        
        self.lbl_folder = QLabel("Nincs mappa kiválasztva")
        self.lbl_folder.setStyleSheet("color: #bdc3c7; font-weight: bold; padding-left: 10px;")
        self.lbl_folder.setFont(QFont("Arial", 10))
        
        folder_layout.addWidget(self.btn_select)
        folder_layout.addWidget(self.lbl_folder, 1)
        main_layout.addLayout(folder_layout)

        # Splitter: fájllista és média nézet
        splitter = QSplitter(Qt.Horizontal)

        # Fájllista
        file_widget = QWidget()
        file_layout = QVBoxLayout(file_widget)
        file_layout.setContentsMargins(0, 0, 0, 0)
        
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Fájl", "Típus", "Méret (MB)", "Törlés"])
        self.tree.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tree.setSortingEnabled(True)
        self.tree.setAlternatingRowColors(True)
        self.tree.header().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.tree.itemSelectionChanged.connect(self.preview_media)
        self.tree.itemDoubleClicked.connect(self.open_with_default)
        file_layout.addWidget(self.tree)

        # Törlés gomb
        self.btn_delete = QPushButton("Kijelöltek törlése")
        self.btn_delete.setFixedHeight(40)
        self.btn_delete.clicked.connect(self.delete_files)
        self.btn_delete.setEnabled(False)
        file_layout.addWidget(self.btn_delete)

        # Média nézet
        media_widget = QWidget()
        media_layout = QVBoxLayout(media_widget)
        media_layout.setContentsMargins(10, 0, 10, 10)
        
        # Képnézegető
        self.image_viewer = ImageViewer()
        media_layout.addWidget(self.image_viewer, 1)
        
        # Videólejátszó
        self.video_widget = QVideoWidget()
        self.video_widget.setStyleSheet("background-color: black;")
        self.player.setVideoOutput(self.video_widget)
        media_layout.addWidget(self.video_widget)
        self.video_widget.hide()
        
        # Állapotsor
        self.lbl_status = QLabel("Kész")
        self.lbl_status.setAlignment(Qt.AlignCenter)
        self.lbl_status.setStyleSheet("color: #95a5a6; font-size: 12px; padding-top: 5px;")
        media_layout.addWidget(self.lbl_status)

        splitter.addWidget(file_widget)
        splitter.addWidget(media_widget)
        splitter.setSizes([400, 600])
        
        main_layout.addWidget(splitter, 1)

        # Folyamatjelző
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.progress.setFixedHeight(20)
        main_layout.addWidget(self.progress)

        self.setLayout(main_layout)
        self.setWindowTitle("Médiafájl Kezelő")
        self.resize(1200, 700)
    
    def open_with_default(self, item, column):
        """Fájl megnyitása alapértelmezett programmal"""
        path = item.data(0, Qt.UserRole)
        if not os.path.exists(path):
            QMessageBox.warning(self, "Hiba", "A fájl nem található!")
            return
            
        try:
            if platform.system() == 'Windows':
                os.startfile(path)
            elif platform.system() == 'Darwin':  # macOS
                subprocess.call(('open', path))
            else:  # Linux
                subprocess.call(('xdg-open', path))
        except Exception as e:
            QMessageBox.critical(self, "Hiba", f"Nem sikerült megnyitni a fájlt: {str(e)}")

    def select_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Válassz mappát")
        if folder:
            self.selected_folder = folder
            self.lbl_folder.setText(folder)
            self.lbl_folder.setStyleSheet("color: #2ecc71; font-weight: bold;")
            self.load_media()

    def load_media(self):
        self.tree.clear()
        self.image_viewer.scene.clear()
        self.video_widget.hide()
        self.player.stop()
        self.btn_delete.setEnabled(False)
        self.lbl_status.setText("Mappabeolvasás...")
        
        if not self.selected_folder or not os.path.isdir(self.selected_folder):
            QMessageBox.warning(self, "Hiba", "Érvénytelen mappa!")
            return
            
        if self.scanner and self.scanner.isRunning():
            self.scanner.stop()
            self.scanner.wait()
            
        self.progress.setVisible(True)
        self.progress.setValue(0)
        
        self.scanner = MediaScanner(self.selected_folder)
        self.scanner.media_found.connect(self.add_media_item)
        self.scanner.progress.connect(self.progress.setValue)
        self.scanner.finished.connect(self.on_scan_finished)
        self.scanner.start()

    def add_media_item(self, file, path, size, file_type):
        item = QTreeWidgetItem([
            file, 
            file_type,
            f"{size:.2f}"
        ])
        item.setData(0, Qt.UserRole, path)
        
        # Színezés fájltípus szerint
        if file_type == "Kép":
            item.setForeground(1, QBrush(QColor(52, 152, 219)))  # Kék
        elif file_type == "Videó":
            item.setForeground(1, QBrush(QColor(231, 76, 60)))    # Piros
        elif file_type == "Hang":
            item.setForeground(1, QBrush(QColor(46, 204, 113)))  # Zöld
        
        chk = QCheckBox()
        chk.stateChanged.connect(lambda state: self.btn_delete.setEnabled(True))
        self.tree.addTopLevelItem(item)
        self.tree.setItemWidget(item, 3, chk)

    def on_scan_finished(self):
        self.progress.setVisible(False)
        count = self.tree.topLevelItemCount()
        self.lbl_status.setText(f"{count} médiafájl betöltve")
        
        if count == 0:
            QMessageBox.information(self, "Információ", "Nincsenek médiafájlok a mappában.")
        else:
            self.btn_delete.setEnabled(False)
            self.tree.sortItems(0, Qt.AscendingOrder)

    def preview_media(self):
        """Média előnézet megjelenítése"""
        selected = self.tree.selectedItems()
        if not selected:
            return
            
        item = selected[0]
        path = item.data(0, Qt.UserRole)
        if not os.path.exists(path):
            QMessageBox.warning(self, "Hiba", "A fájl nem található!")
            return
            
        file_type = item.text(1)
        
        self.video_widget.hide()
        self.player.stop()
        self.lbl_status.setText(f"Előnézet: {os.path.basename(path)}")
        
        if file_type == "Kép":
            # Kép megjelenítése az egyedi nézegetőben
            self.image_viewer.display_image(path)
            self.image_viewer.show()
        else:
            # Egyéb fájltípusok esetén csak állapotsor frissítés
            self.image_viewer.scene.clear()
            self.image_viewer.scene.addText("Kattints duplán a fájl megnyitásához").setDefaultTextColor(Qt.white)

    def delete_files(self):
        to_delete = []
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            chk = self.tree.itemWidget(item, 3)
            if chk and chk.isChecked():
                to_delete.append(item.data(0, Qt.UserRole))
        
        if not to_delete:
            return

        reply = QMessageBox.question(
            self, 'Megerősítés',
            f"{len(to_delete)} fájl törlése?",
            QMessageBox.Yes | QHeaderView.No
        )
        
        if reply == QMessageBox.Yes:
            errors = []
            for path in to_delete:
                try:
                    os.remove(path)
                except Exception as e:
                    errors.append(f"{os.path.basename(path)}: {str(e)}")
            
            if errors:
                error_msg = "\n".join(errors[:5])
                if len(errors) > 5:
                    error_msg += f"\n... és további {len(errors)-5} hiba"
                QMessageBox.critical(self, "Hiba", f"{len(errors)} fájl törlése sikertelen:\n{error_msg}")
            
            self.load_media()

if __name__ == "__main__":
    import sys
    from PyQt5.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    window = MediaFinder()
    window.show()
    
    sys.exit(app.exec_())