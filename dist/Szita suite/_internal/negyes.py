import socket
import threading
import subprocess
import re
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QTreeWidget, QTreeWidgetItem,
    QHeaderView, QLabel, QPushButton, QProgressBar
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QColor, QBrush

class NetworkScannerThread(QThread):
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(list)
    device_found = pyqtSignal(dict)
    
    def __init__(self):
        super().__init__()
        self._is_running = True
        self.active_ips = set()
    
    def run(self):
        devices = []
        try:
            # 1. ARP cache elemzés (gyors és megbízható)
            arp_devices = self.scan_arp_cache()
            for device in arp_devices:
                self.device_found.emit(device)
                devices.append(device)
            
            # 2. ICMP ping sweep (minden IP ellenőrzése)
            self.scan_ping_sweep()
            
            # 3. Portvizsgálat a talált eszközökön
            self.scan_ports(devices)
            
        except Exception as e:
            self.progress.emit(0, f"Hiba: {str(e)}")
        
        self.finished.emit(devices)
    
    def scan_arp_cache(self):
        """ARP cache elemzése a hálózati eszközök azonosításához"""
        devices = []
        try:
            # ARP parancs futtatása
            result = subprocess.run(['arp', '-a'], capture_output=True, text=True)
            
            # Eredmény feldolgozása
            for line in result.stdout.split('\n'):
                if re.search(r'\d+\.\d+\.\d+\.\d+', line):
                    parts = line.split()
                    ip = parts[0]
                    mac = parts[1] if len(parts) > 1 else "Ismeretlen"
                    device_type = "Eszköz"
                    
                    devices.append({
                        'ip': ip,
                        'mac': mac,
                        'hostname': "Feltérképezés alatt...",
                        'type': device_type,
                        'status': "ARP cache"
                    })
                    self.active_ips.add(ip)
            
            self.progress.emit(30, "ARP cache elemzve")
        except Exception as e:
            self.progress.emit(0, f"ARP hiba: {str(e)}")
        
        return devices
    
    def scan_ping_sweep(self):
        """ICMP ping segítségével aktív eszközök keresése"""
        try:
            # Helyi IP és alhálózat meghatározása
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
            
            base_ip = ".".join(local_ip.split(".")[:-1]) + "."
            
            # Párhuzamos ping kérések
            threads = []
            for i in range(1, 255):
                if not self._is_running:
                    break
                    
                ip = base_ip + str(i)
                if ip in self.active_ips or ip == local_ip:
                    continue
                
                t = threading.Thread(target=self.ping_ip, args=(ip,))
                t.daemon = True
                threads.append(t)
                t.start()
            
            # Várakozás a szálakra
            for i, t in enumerate(threads):
                if not self._is_running:
                    break
                t.join(timeout=0.01)
                self.progress.emit(30 + int((i/254)*40), f"Ping szkennelés: {i+1}/254")
        
        except Exception as e:
            self.progress.emit(0, f"Ping hiba: {str(e)}")
    
    def ping_ip(self, ip):
        """Egyedi IP cím pingelése"""
        try:
            # Windows ping parancs (2 próbálkozás, 150ms timeout)
            result = subprocess.run(
                ['ping', '-n', '1', '-w', '150', ip],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            if result.returncode == 0 and b"TTL=" in result.stdout:
                hostname = self.get_hostname(ip)
                
                self.device_found.emit({
                    'ip': ip,
                    'mac': "Feltérképezés alatt...",
                    'hostname': hostname,
                    'type': "Eszköz",
                    'status': "Ping válasz"
                })
                self.active_ips.add(ip)
                
        except:
            pass
    
    def get_hostname(self, ip):
        """Hosztnév lekérdezése IP cím alapján"""
        try:
            return socket.gethostbyaddr(ip)[0]
        except:
            return "Ismeretlen"
    
    def scan_ports(self, devices):
        """Portvizsgálat az eszközök típusának meghatározásához"""
        try:
            for i, device in enumerate(devices):
                if not self._is_running:
                    break
                    
                ip = device['ip']
                
                # Kamera portok ellenőrzése
                if self.is_camera(ip):
                    device['type'] = "IP Kamera"
                # NVR portok ellenőrzése
                elif self.is_nvr(ip):
                    device['type'] = "NVR"
                
                # MAC cím lekérdezése
                if device['mac'] == "Feltérképezés alatt...":
                    device['mac'] = self.get_mac_address(ip)
                
                # Frissítés a GUI-ban
                self.device_found.emit(device)
                self.progress.emit(70 + int((i/len(devices))*30, f"Eszköz elemzés: {i+1}/{len(devices)}"))
        
        except Exception as e:
            self.progress.emit(0, f"Portszkennelési hiba: {str(e)}")
    
    def get_mac_address(self, ip):
        """MAC cím lekérdezése ARP cache-ből"""
        try:
            result = subprocess.run(
                ['arp', '-a', ip],
                capture_output=True,
                text=True
            )
            
            for line in result.stdout.split('\n'):
                if ip in line:
                    parts = line.split()
                    return parts[1] if len(parts) > 1 else "Ismeretlen"
        except:
            return "Ismeretlen"
    
    def is_camera(self, ip):
        """IP kamera azonosítása portvizsgálattal"""
        try:
            ports = [80, 554, 37777]
            for port in ports:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(0.5)
                result = sock.connect_ex((ip, port))
                sock.close()
                if result == 0:
                    return True
        except:
            pass
        return False
    
    def is_nvr(self, ip):
        """NVR azonosítása portvizsgálattal"""
        try:
            ports = [8000, 34567, 37777]
            for port in ports:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(0.5)
                result = sock.connect_ex((ip, port))
                sock.close()
                if result == 0:
                    return True
        except:
            pass
        return False
    
    def stop(self):
        self._is_running = False
        self.quit()
        self.wait()

class NetworkScanner(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()
        self.set_style()

    def set_style(self):
        self.setStyleSheet("""
            QWidget {
                background-color: #2D2D2D;
                color: #FFFFFF;
                font-family: 'Segoe UI';
            }
            QLabel {
                color: #FFFFFF;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton {
                padding: 8px 16px;
                background-color: #9b59b6;
                color: white;
                border-radius: 4px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #8e44ad;
            }
            QTreeWidget {
                background-color: #3C3C3C;
                alternate-background-color: #454545;
                color: #FFFFFF;
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
                background-color: #3C3C3C;
                color: white;
            }
            QProgressBar::chunk {
                background-color: #9b59b6;
                width: 10px;
            }
        """)

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Cím
        title = QLabel("Hálózati Eszköz Feltérképező")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #9b59b6;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # Szkennelés gomb
        self.btn_scan = QPushButton("Hálózat Szkennelése")
        self.btn_scan.clicked.connect(self.start_scan)
        layout.addWidget(self.btn_scan)

        # Állapotsor
        self.lbl_status = QLabel("Kész a szkennelésre. Kattints a 'Hálózat Szkennelése' gombra.")
        self.lbl_status.setAlignment(Qt.AlignCenter)
        self.lbl_status.setWordWrap(True)
        layout.addWidget(self.lbl_status)

        # Folyamatjelző
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        # Eredménytáblázat
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["IP Cím", "Eszköznév", "MAC Cím", "Típus", "Státusz"])
        self.tree.setAlternatingRowColors(True)
        self.tree.header().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.tree.setSortingEnabled(True)
        self.tree.setMinimumHeight(400)
        layout.addWidget(self.tree, 1)

        self.setLayout(layout)
        self.setWindowTitle("Hálózati Eszköz Feltérképező")
        self.resize(900, 600)

    def start_scan(self):
        self.tree.clear()
        self.btn_scan.setEnabled(False)
        self.lbl_status.setText("Hálózat feltérképezése...")
        self.progress.setVisible(True)
        self.progress.setValue(0)
        
        self.scanner = NetworkScannerThread()
        self.scanner.device_found.connect(self.add_device)
        self.scanner.progress.connect(self.update_progress)
        self.scanner.finished.connect(self.on_scan_complete)
        self.scanner.start()

    def update_progress(self, value, message):
        self.progress.setValue(value)
        self.lbl_status.setText(message)

    def add_device(self, device):
        # Ellenőrizzük, hogy az eszköz már szerepel-e a listában
        existing = self.find_device_item(device['ip'])
        
        if existing:
            # Frissítjük a meglévő elemet
            existing.setText(1, device['hostname'])
            existing.setText(2, device['mac'])
            existing.setText(3, device['type'])
            existing.setText(4, device.get('status', 'Aktív'))
        else:
            # Új elem létrehozása
            item = QTreeWidgetItem([
                device['ip'],
                device['hostname'],
                device['mac'],
                device['type'],
                device.get('status', 'Aktív')
            ])
            
            # Színezés típus alapján
            if "kamera" in device['type'].lower():
                color = QColor(52, 152, 219)  # Kék
                for i in range(5):
                    item.setBackground(i, QBrush(color))
                    item.setForeground(i, QBrush(Qt.white))
            elif "nvr" in device['type'].lower():
                color = QColor(46, 204, 113)  # Zöld
                for i in range(5):
                    item.setBackground(i, QBrush(color))
                    item.setForeground(i, QBrush(Qt.white))
            elif "útválasztó" in device['type'].lower():
                color = QColor(155, 89, 182)  # Lila
                for i in range(5):
                    item.setBackground(i, QBrush(color))
                    item.setForeground(i, QBrush(Qt.white))
            
            self.tree.addTopLevelItem(item)
        
        # Rendezés IP cím szerint
        self.tree.sortItems(0, Qt.AscendingOrder)

    def find_device_item(self, ip):
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            if item.text(0) == ip:
                return item
        return None

    def on_scan_complete(self, devices):
        self.btn_scan.setEnabled(True)
        self.progress.setVisible(False)
        self.lbl_status.setText(f"Szkennelés kész! {len(devices)} eszköz található a hálózaton.")
        
        # Szkanner leállítása
        self.scanner.stop()
        self.scanner.wait()

if __name__ == "__main__":
    import sys
    from PyQt5.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    scanner = NetworkScanner()
    scanner.show()
    
    sys.exit(app.exec_())