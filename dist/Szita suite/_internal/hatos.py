import sys
import os
import threading
import time
import psutil
import pefile
import math
import random
import queue
from collections import deque, defaultdict
import textwrap
from datetime import datetime
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import pandas as pd
import numpy as np
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QLabel, QComboBox, QPushButton, QSpinBox, QTabWidget, QListWidget,
    QStatusBar, QMessageBox, QGridLayout, QScrollArea, QFormLayout, QSizePolicy
)
from PyQt5.QtCore import Qt, QTimer, QPointF, QRectF, QLineF
from PyQt5.QtGui import QPainter, QColor, QFont, QPen, QBrush, QLinearGradient

class DLLNode:
    def __init__(self, name, x, y):
        self.name = name
        self.x = x
        self.y = y
        self.is_active = False
        self.is_root = False
        self.radius = 30
        self.target_x = x
        self.target_y = y
        self.velocity_x = 0
        self.velocity_y = 0
        self.last_activity = 0
        self.activity_pulse = 0
        self.is_visible = True
        self.heat_value = 0

    def draw(self, painter):
        pulse = 0
        current_time = time.time()
        if current_time - self.last_activity < 1.0:
            pulse = math.sin(self.activity_pulse * 10) * 3
            self.activity_pulse += 0.1
        
        if self.is_active:
            color = QColor(208, 240, 208)
            border_color = QColor(0, 160, 0)
            text_color = QColor(0, 96, 0)
            border_width = 3
        elif self.is_root:
            color = QColor(208, 208, 240)
            border_color = QColor(0, 0, 160)
            text_color = QColor(0, 0, 96)
            border_width = 3
        else:
            if self.heat_value > 0:
                intensity = min(255, int(self.heat_value * 200))
                color = QColor(255, 255 - intensity, 255 - intensity)
            else:
                color = QColor(240, 240, 240)
            border_color = QColor(128, 128, 128)
            text_color = QColor(64, 64, 64)
            border_width = 1
        
        painter.setPen(QPen(border_color, border_width))
        painter.setBrush(QBrush(color))
        painter.drawEllipse(
            QPointF(self.x, self.y), 
            self.radius - pulse, 
            self.radius - pulse
        )
        
        painter.setPen(QPen(text_color))
        painter.setFont(QFont("Arial", 9, QFont.Bold if self.is_active else QFont.Normal))
        
        wrapped_name = textwrap.fill(self.name, width=10, break_long_words=True)
        
        text_rect = QRectF(
            self.x - self.radius,
            self.y - self.radius,
            self.radius * 2,
            self.radius * 2
        )
        painter.drawText(text_rect, Qt.AlignCenter, wrapped_name)


class GraphWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(800, 500)
        self.setStyleSheet("background-color: white;")
        
        self.nodes = {}
        self.edges = {}
        self.drag_data = {"x": 0, "y": 0, "item": None}
        self.offset_x = 0
        self.offset_y = 0
        self.scale = 1.0
        self.center_x = self.width() / 2
        self.center_y = self.height() / 2
        
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.animate)
        self.timer.start(20)
        
    def resizeEvent(self, event):
        self.center_x = self.width() / 2
        self.center_y = self.height() / 2
        super().resizeEvent(event)
        
    def mousePressEvent(self, event):
        self.drag_data["x"] = event.x()
        self.drag_data["y"] = event.y()
        self.drag_data["item"] = None
        
        for node_id, node in self.nodes.items():
            dx = node.x - event.x()
            dy = node.y - event.y()
            distance = math.sqrt(dx*dx + dy*dy)
            if distance < node.radius:
                self.drag_data["item"] = node
                return
                
    def mouseMoveEvent(self, event):
        dx = event.x() - self.drag_data["x"]
        dy = event.y() - self.drag_data["y"]
        
        if self.drag_data["item"]:
            node = self.drag_data["item"]
            node.x += dx
            node.y += dy
            node.target_x = node.x
            node.target_y = node.y
        else:
            self.offset_x += dx
            self.offset_y += dy
            
            for node in self.nodes.values():
                node.x += dx
                node.y += dy
                node.target_x += dx
                node.target_y += dy
        
        self.drag_data["x"] = event.x()
        self.drag_data["y"] = event.y()
        self.update()
                
    def wheelEvent(self, event):
        factor = 1.1 if event.angleDelta().y() > 0 else 0.9
        self.scale *= factor
        self.scale = max(0.5, min(self.scale, 3.0))
        
        center_x = event.x()
        center_y = event.y()
        
        for node in self.nodes.values():
            node.x = center_x + (node.x - center_x) * factor
            node.y = center_y + (node.y - center_y) * factor
            node.target_x = center_x + (node.target_x - center_x) * factor
            node.target_y = center_y + (node.target_y - center_y) * factor
            node.radius = max(10, min(60, node.radius * factor))
        
        self.update()
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        for (source, target), edge_data in self.edges.items():
            src_node = self.nodes.get(source)
            tgt_node = self.nodes.get(target)
            
            if src_node and tgt_node and src_node.is_visible and tgt_node.is_visible:
                dx = tgt_node.x - src_node.x
                dy = tgt_node.y - src_node.y
                distance = max(1, math.sqrt(dx*dx + dy*dy))
                
                nx = dx / distance
                ny = dy / distance
                
                start_x = src_node.x + nx * src_node.radius
                start_y = src_node.y + ny * src_node.radius
                end_x = tgt_node.x - nx * tgt_node.radius
                end_y = tgt_node.y - ny * tgt_node.radius
                
                color = QColor(0, 160, 0) if tgt_node.is_active else QColor(160, 160, 160)
                width = 2 if tgt_node.is_active else 1
                
                pen = QPen(color, width)
                if not tgt_node.is_active:
                    pen.setStyle(Qt.DashLine)
                painter.setPen(pen)
                painter.drawLine(QLineF(start_x, start_y, end_x, end_y))
                
                arrow_size = 6
                angle = math.atan2(dy, dx)
                
                arrow_x = end_x - arrow_size * math.cos(angle)
                arrow_y = end_y - arrow_size * math.sin(angle)
                
                # FIXED: Corrected arrow drawing syntax
                painter.drawLine(QLineF(
                    arrow_x, arrow_y,
                    arrow_x + arrow_size * math.cos(angle - math.pi/6),
                    arrow_y + arrow_size * math.sin(angle - math.pi/6)
                ))
                painter.drawLine(QLineF(
                    arrow_x, arrow_y,
                    arrow_x + arrow_size * math.cos(angle + math.pi/6),
                    arrow_y + arrow_size * math.sin(angle + math.pi/6)
                ))
        
        for node in self.nodes.values():
            if node.is_visible:
                node.draw(painter)
                
    def animate(self):
        for node in self.nodes.values():
            if not node.is_visible:
                continue
            
            dx = node.target_x - node.x
            dy = node.target_y - node.y
            distance = max(1, math.sqrt(dx*dx + dy*dy))
            
            node.velocity_x = node.velocity_x * 0.7 + dx * 0.1
            node.velocity_y = node.velocity_y * 0.7 + dy * 0.1
            
            node.x += node.velocity_x
            node.y += node.velocity_y
            
            if self.width() > 0 and self.height() > 0:
                node.x = max(node.radius, min(node.x, self.width() - node.radius))
                node.y = max(node.radius, min(node.y, self.height() - node.radius))
        
        self.update()


class ProcessMonitorApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Totál Komplex Process Monitor")
        self.setGeometry(100, 100, 1400, 900)
        
        self.current_user = psutil.Process().username().split('\\')[-1].lower()
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)
        
        header_label = QLabel("Totál Komplex Process Monitor")
        header_label.setStyleSheet("""
            font-size: 16pt; 
            font-weight: bold; 
            color: #2c3e50;
        """)
        main_layout.addWidget(header_label)
        
        control_group = QGroupBox("Folyamat Vezérlés")
        control_layout = QGridLayout(control_group)
        control_layout.setSpacing(10)
         
        control_group.setStyleSheet("""            
            font-weight: bold; 
            color: #ffffff;
        """)
        
        control_layout.addWidget(QLabel("Folyamat:"), 0, 0)
        self.proc_combo = QComboBox()
        self.proc_combo.setMinimumWidth(400)
        self.proc_combo.setEditable(False)
        control_layout.addWidget(self.proc_combo, 0, 1)
        self.proc_combo.setStyleSheet("""
                QComboBox {
                    color: black; 
                }
                QComboBox QAbstractItemView {
                    color: black;  
                    
                }
            """)
                    
        refresh_btn = QPushButton("Frissítés")
        refresh_btn.clicked.connect(self.refresh_process_list)
        refresh_btn.setStyleSheet("""
            
            QPushButton {
                background-color: #4a7abc; 
                color: white; 
                font-weight: bold;
                padding: 5px 10px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #3a6aac;
            }
            
        """)
        control_layout.addWidget(refresh_btn, 0, 2)
        
        control_layout.addWidget(QLabel("Rekurzió mélység:"), 1, 0)
        self.depth_spin = QSpinBox()
        self.depth_spin.setRange(1, 5)
        self.depth_spin.setValue(2)
        control_layout.addWidget(self.depth_spin, 1, 1)
        self.depth_spin.setStyleSheet(""" color: black; """)
        
        
        
        
        
        control_layout.addWidget(QLabel("Max csomópontok:"), 1, 2)
        self.node_limit_spin = QSpinBox()
        self.node_limit_spin.setRange(5, 100)
        self.node_limit_spin.setValue(20)
        control_layout.addWidget(self.node_limit_spin, 1, 3)
        self.node_limit_spin.setStyleSheet(""" color: black;  """)
        
        self.start_btn = QPushButton("Start Monitorozás")
        self.start_btn.clicked.connect(self.start_auto_refresh)
        self.start_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50; 
                color: white; 
                font-weight: bold;
                padding: 8px 15px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        control_layout.addWidget(self.start_btn, 2, 0)
        
        self.stop_btn = QPushButton("Stop Monitorozás")
        self.stop_btn.clicked.connect(self.stop_auto_refresh)
        self.stop_btn.setEnabled(False)
        self.stop_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336; 
                color: white; 
                font-weight: bold;
                padding: 8px 15px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #d32f2f;
            }
        """)
        control_layout.addWidget(self.stop_btn, 2, 1)
        
        main_layout.addWidget(control_group)
        
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)
        
        graph_tab = QWidget()
        graph_layout = QVBoxLayout(graph_tab)
        self.graph_widget = GraphWidget()
        graph_layout.addWidget(self.graph_widget)
        self.tabs.addTab(graph_tab, "DLL Függőségi Gráf")
        
        perf_tab = QWidget()
        perf_layout = QGridLayout(perf_tab)
        
        cpu_group = QGroupBox("CPU Használat (%)")
        cpu_group.setStyleSheet("QGroupBox { color: white; }")
        cpu_layout = QVBoxLayout(cpu_group)
        self.cpu_fig = Figure(figsize=(6, 3), dpi=100)
        self.cpu_ax = self.cpu_fig.add_subplot(111)
        self.cpu_canvas = FigureCanvas(self.cpu_fig)
        cpu_layout.addWidget(self.cpu_canvas)
        perf_layout.addWidget(cpu_group, 0, 0)
        
        mem_group = QGroupBox("Memória Használat (MB)")
        mem_group.setStyleSheet("QGroupBox { color: white; }")
        mem_layout = QVBoxLayout(mem_group)
        self.mem_fig = Figure(figsize=(6, 3), dpi=100)
        self.mem_ax = self.mem_fig.add_subplot(111)
        self.mem_canvas = FigureCanvas(self.mem_fig)
        mem_layout.addWidget(self.mem_canvas)
        perf_layout.addWidget(mem_group, 0, 1)
        
        heatmap_group = QGroupBox("EXE Struktúra Elemzés")
        heatmap_group.setStyleSheet("QGroupBox { color: white; }")
        heatmap_layout = QVBoxLayout(heatmap_group)
        self.heatmap_fig = Figure(figsize=(6, 3), dpi=100)
        self.heatmap_ax = self.heatmap_fig.add_subplot(111)
        self.heatmap_canvas = FigureCanvas(self.heatmap_fig)
        heatmap_layout.addWidget(self.heatmap_canvas)
        perf_layout.addWidget(heatmap_group, 1, 0, 1, 2)
        
        self.tabs.addTab(perf_tab, "Teljesítmény Monitor")
        
        info_tab = QWidget()
        info_layout = QVBoxLayout(info_tab)
        
        info_group = QGroupBox("Processz Információ")
        info_group.setStyleSheet("QGroupBox { color: white; }")
        info_grid = QFormLayout(info_group)
        
        info_grid.setLabelAlignment(Qt.AlignLeft)
        info_grid.setFormAlignment(Qt.AlignLeft)
        
        self.info_labels = {}
        info_fields = [
            ("Folyamat neve", "process_name"),
            ("PID", "pid"),
            ("Futtatható elérési út", "exe_path"),
            ("Indítási idő", "start_time"),
            ("Felhasználó", "username"),
            ("CPU %", "cpu_percent"),
            ("Memória használat", "memory_usage"),
            ("Állapot", "status"),
            ("Szülő PID", "ppid"),
            ("Parancssori argumentumok", "cmdline"),
        ]
        
        for label, key in info_fields:
            value_label = QLabel("-")
            value_label.setStyleSheet("font: 10pt;color: white;")
            self.info_labels[key] = value_label
             
            label_widget = QLabel(f"{label}:")
            label_widget.setStyleSheet("color: white;")
            info_grid.addRow(label_widget, value_label)
            
        
        info_layout.addWidget(info_group)
        
        dll_group = QGroupBox("Betöltött DLL-ek")
        dll_group.setStyleSheet("QGroupBox { color: white; }")
        dll_layout = QVBoxLayout(dll_group)
        self.dll_list = QListWidget()
        self.dll_list.setStyleSheet("""
            QListWidget {
                font: 9pt 'Consolas';
                background-color: white;
            }
            QListWidget::item:selected {
                background-color: #4a7abc;
                color: white;
            }
        """)
        dll_layout.addWidget(self.dll_list)
        info_layout.addWidget(dll_group)
        
        self.tabs.addTab(info_tab, "Processz Információ")
        
        self.status_bar = QStatusBar()
        self.status_bar.setStyleSheet("QStatusBar{ color: white; }")
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Kész. Válassz egy folyamatot és indítsd el a monitorozást!")
         
        self.auto_refresh = False
        self.refresh_interval = 1.0
        self.current_pid = None
        self.process_name = ""
        
        self.perf_data = {
            'timestamps': deque(maxlen=60),
            'cpu_percent': deque(maxlen=60),
            'memory_mb': deque(maxlen=60),
            'exe_analysis': {}
        }
        
        self.update_queue = queue.Queue()
        
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.process_updates)
        self.update_timer.start(100)
        
        self.plot_timer = QTimer()
        self.plot_timer.timeout.connect(self.update_perf_plots)
        self.plot_timer.start(1000)
        
        self.refresh_process_list()
        
    def refresh_process_list(self):
        self.status_bar.showMessage("Folyamatlista frissítése...")
        QApplication.processEvents()
        
        procs = []
        
        for p in psutil.process_iter(['pid', 'name', 'username']):
            try:
                if p.info['username'] and p.info['username'].split('\\')[-1].lower() == self.current_user:
                    procs.append(f"{p.info['pid']:6d} : {p.info['name']}")
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
        
        procs.sort(key=lambda x: x.split(':')[1].strip().lower())
        self.proc_combo.clear()
        self.proc_combo.addItems(procs)
        if procs:
            self.proc_combo.setCurrentIndex(0)
        self.status_bar.showMessage("Kész. Válassz egy folyamatot!")

    def start_auto_refresh(self):
        sel = self.proc_combo.currentText()
        if not sel:
            QMessageBox.critical(self, "Hiba", "Válassz egy folyamatot a listából!")
            return
        
        try:
            self.current_pid = int(sel.split(':')[0].strip())
            self.process_name = sel.split(':')[1].strip()
        except Exception:
            QMessageBox.critical(self, "Hiba", "Érvénytelen folyamat kiválasztás")
            return
        
        self.auto_refresh = True
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.status_bar.showMessage(f"Figyelés: {self.process_name} (PID: {self.current_pid})")
        
        self.graph_widget.nodes.clear()
        self.graph_widget.edges.clear()
        self.perf_data = {
            'timestamps': deque(maxlen=60),
            'cpu_percent': deque(maxlen=60),
            'memory_mb': deque(maxlen=60),
            'exe_analysis': {}
        }
        self.dll_list.clear()
        
        threading.Thread(target=self._monitor_process, daemon=True).start()

    def stop_auto_refresh(self):
        self.auto_refresh = False
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.status_bar.showMessage("Figyelés leállítva")

    def _monitor_process(self):
        while self.auto_refresh:
            try:
                proc = psutil.Process(self.current_pid)
                
                cpu_percent = proc.cpu_percent(interval=0.1)
                memory_info = proc.memory_info()
                memory_mb = memory_info.rss / (1024 * 1024)
                
                current_time = datetime.now().strftime('%H:%M:%S')
                
                self.perf_data['timestamps'].append(current_time)
                self.perf_data['cpu_percent'].append(cpu_percent)
                self.perf_data['memory_mb'].append(memory_mb)
                self.update_queue.put(("perf", None))
                
                process_info = {
                    'process_name': proc.name(),
                    'pid': str(proc.pid),
                    'exe_path': proc.exe() if proc.exe() else "N/A",
                    'start_time': datetime.fromtimestamp(proc.create_time()).strftime('%Y-%m-%d %H:%M:%S'),
                    'username': proc.username(),
                    'cpu_percent': f"{cpu_percent:.1f}%",
                    'memory_usage': f"{memory_mb:.2f} MB",
                    'status': proc.status(),
                    'ppid': str(proc.ppid()),
                    'cmdline': " ".join(proc.cmdline()) if proc.cmdline() else "N/A"
                }
                self.update_queue.put(("info", process_info))
                
                dll_names = []
                for m in proc.memory_maps():
                    try:
                        if m.path and m.path.lower().endswith('.dll'):
                            dll_name = os.path.basename(m.path)
                            dll_names.append(dll_name)
                    except Exception:
                        continue
                self.update_queue.put(("dll_list", dll_names))
                
                active_dlls = {dll.lower() for dll in dll_names}
                
                if not self.perf_data['exe_analysis']:
                    try:
                        exe_path = proc.exe()
                        if exe_path and os.path.exists(exe_path):
                            self.perf_data['exe_analysis'] = self.analyze_exe(exe_path)
                            self.update_queue.put(("exe_heatmap", None))
                    except Exception as e:
                        print(f"EXE analysis error: {e}")
                
                depth = self.depth_spin.value()
                node_limit = self.node_limit_spin.value()
                graph_data = self.build_graph_data(proc.exe(), depth, active_dlls, node_limit)
                
                self.update_queue.put(("graph", graph_data))
                
                total_dlls = len(graph_data['nodes'])
                active_dlls = len([n for n in graph_data['nodes'] if graph_data['nodes'][n]['is_active']])
                status = (
                    f"Figyelés: {self.process_name} | "
                    f"DLL-ek: {total_dlls}/{node_limit} | "
                    f"Aktív DLL-ek: {active_dlls} | "
                    f"CPU: {cpu_percent:.1f}% | "
                    f"Memória: {memory_mb:.2f} MB"
                )
                self.update_queue.put(("status", status))
                
                time.sleep(self.refresh_interval)
                
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                self.update_queue.put(("status", "Hiba: A folyamat már nem elérhető!"))
                self.update_queue.put(("stop", None))
            except Exception as e:
                self.update_queue.put(("status", f"Hiba: {str(e)}"))
                time.sleep(self.refresh_interval)

    def build_graph_data(self, exe_path, depth, active_dlls, node_limit):
        graph_data = {
            'nodes': {},
            'edges': {}
        }
        
        try:
            root_name = os.path.basename(exe_path).lower() if exe_path else "unknown.exe"
            
            queue = deque([(root_name, 0)])
            visited = set([root_name])
            levels = defaultdict(list)
            levels[0].append(root_name)
            node_count = 1
            
            while queue and node_count < node_limit:
                current_dll, current_depth = queue.popleft()
                
                if current_depth >= depth:
                    continue
                
                try:
                    dll_path = self._find_dll_path(current_dll, exe_path)
                    if not dll_path:
                        continue
                    
                    pe = pefile.PE(dll_path)
                    
                    if hasattr(pe, 'DIRECTORY_ENTRY_IMPORT'):
                        for entry in pe.DIRECTORY_ENTRY_IMPORT:
                            try:
                                dep_name = entry.dll.decode('utf-8', 'ignore').lower()
                                if not dep_name.endswith('.dll'):
                                    dep_name += '.dll'
                                
                                edge_key = (current_dll, dep_name)
                                graph_data['edges'][edge_key] = True
                                
                                if dep_name not in visited and node_count < node_limit:
                                    visited.add(dep_name)
                                    node_count += 1
                                    
                                    next_depth = current_depth + 1
                                    levels[next_depth].append(dep_name)
                                    
                                    queue.append((dep_name, next_depth))
                                
                            except Exception:
                                continue
                except Exception:
                    continue
            
            for node_name in visited:
                graph_data['nodes'][node_name] = {
                    'is_active': node_name in active_dlls,
                    'is_root': node_name == root_name,
                    'heat_value': self.perf_data['exe_analysis'].get(node_name, 0)
                }
            
            self._layout_nodes(graph_data, levels)
            
        except Exception as e:
            self.update_queue.put(("status", f"Gráfépítési hiba: {str(e)}"))
        
        return graph_data

    def analyze_exe(self, exe_path):
        analysis = {}
        
        try:
            pe = pefile.PE(exe_path)
            
            if hasattr(pe, 'DIRECTORY_ENTRY_IMPORT'):
                for entry in pe.DIRECTORY_ENTRY_IMPORT:
                    try:
                        dll_name = entry.dll.decode('utf-8', 'ignore').lower()
                        if not dll_name.endswith('.dll'):
                            dll_name += '.dll'
                        
                        import_count = len(entry.imports)
                        analysis[dll_name] = min(1.0, import_count / 100.0)
                    except Exception:
                        continue
            
            for section in pe.sections:
                try:
                    section_name = section.Name.decode('utf-8', 'ignore').rstrip('\x00')
                    entropy = section.get_entropy()
                    analysis[section_name] = min(1.0, entropy / 8.0)
                except Exception:
                    continue
        
        except Exception as e:
            print(f"EXE analysis error: {e}")
        
        return analysis

    def _layout_nodes(self, graph_data, levels):
        if not levels:
            return
            
        canvas_width = self.graph_widget.width()
        canvas_height = self.graph_widget.height()
        
        for depth, dlls in levels.items():
            y = canvas_height * (depth + 1) / (len(levels) + 1)
            
            count = len(dlls)
            for i, dll_name in enumerate(dlls):
                x = canvas_width * (i + 1) / (count + 1)
                
                if dll_name in graph_data['nodes']:
                    graph_data['nodes'][dll_name]['x'] = x
                    graph_data['nodes'][dll_name]['y'] = y

    def _find_dll_path(self, dll_name, referrer_path):
        try:
            search_paths = [
                os.path.dirname(referrer_path) if referrer_path else "",
                r'C:\Windows\System32',
                r'C:\Windows\SysWOW64',
                r'C:\Windows\System',
                os.environ.get('SYSTEMROOT', ''),
                *os.environ.get('PATH', '').split(os.pathsep)
            ]
            
            for path in search_paths:
                if not path:
                    continue
                
                candidate = os.path.join(path, dll_name)
                if os.path.isfile(candidate):
                    return candidate
                
                candidate_lower = os.path.join(path, dll_name.lower())
                if os.path.isfile(candidate_lower):
                    return candidate_lower
                
                candidate_upper = os.path.join(path, dll_name.upper())
                if os.path.isfile(candidate_upper):
                    return candidate_upper
                
                if os.path.exists(path):
                    for file in os.listdir(path):
                        if file.lower() == dll_name.lower():
                            return os.path.join(path, file)
        except Exception:
            pass
            
        return None

    def process_updates(self):
        try:
            while not self.update_queue.empty():
                update_type, data = self.update_queue.get_nowait()
                
                if update_type == "graph":
                    self.update_graph(data)
                elif update_type == "status":
                    self.status_bar.showMessage(data)
                elif update_type == "info":
                    self.update_process_info(data)
                elif update_type == "dll_list":
                    self.update_dll_list(data)
                elif update_type == "perf":
                    pass
                elif update_type == "exe_heatmap":
                    self.update_exe_heatmap()
                elif update_type == "stop":
                    self.stop_auto_refresh()
        except queue.Empty:
            pass
        except Exception as e:
            print(f"Update error: {e}")

    def update_graph(self, graph_data):
        for node_name, node_info in graph_data['nodes'].items():
            if node_name in self.graph_widget.nodes:
                node = self.graph_widget.nodes[node_name]
                node.is_active = node_info['is_active']
                node.is_root = node_info['is_root']
                node.is_visible = True
                node.heat_value = node_info.get('heat_value', 0)
                
                if node_info['is_active']:
                    node.last_activity = time.time()
            else:
                x = node_info.get('x', random.randint(100, self.graph_widget.width()-100))
                y = node_info.get('y', random.randint(100, self.graph_widget.height()-100))
                
                new_node = DLLNode(node_name, x, y)
                new_node.is_active = node_info['is_active']
                new_node.is_root = node_info['is_root']
                new_node.target_x = x
                new_node.target_y = y
                new_node.heat_value = node_info.get('heat_value', 0)
                
                if node_info['is_active']:
                    new_node.last_activity = time.time()
                
                self.graph_widget.nodes[node_name] = new_node
        
        for node_name in list(self.graph_widget.nodes.keys()):
            if node_name not in graph_data['nodes']:
                self.graph_widget.nodes[node_name].is_visible = False
        
        self.graph_widget.edges = {}
        for edge_key in graph_data['edges']:
            if edge_key[0] in self.graph_widget.nodes and edge_key[1] in self.graph_widget.nodes:
                self.graph_widget.edges[edge_key] = True

    # FIXED: Changed set to setText
    def update_process_info(self, process_info):
        for key, value in process_info.items():
            if key in self.info_labels:
                self.info_labels[key].setText(value)

    def update_dll_list(self, dll_names):
        self.dll_list.clear()
        self.dll_list.addItems(dll_names)

    def update_perf_plots(self):
        if self.auto_refresh:
            self.cpu_ax.clear()
            if self.perf_data['timestamps'] and self.perf_data['cpu_percent']:
                timestamps = list(self.perf_data['timestamps'])
                cpu_values = list(self.perf_data['cpu_percent'])
                
                window_size = 5
                if len(cpu_values) > window_size:
                    moving_avg = pd.Series(cpu_values).rolling(window_size).mean().dropna().tolist()
                    self.cpu_ax.plot(
                        timestamps[-len(moving_avg):], 
                        moving_avg,
                        'g-', linewidth=2, label='Mozgóátlag'
                    )
                
                self.cpu_ax.plot(
                    timestamps, 
                    cpu_values,
                    'b-', linewidth=1, alpha=0.5, label='Valós érték'
                )
                self.cpu_ax.fill_between(
                    timestamps, 
                    0, 
                    cpu_values,
                    color='blue', alpha=0.1
                )
                
                max_cpu = max(cpu_values) if cpu_values else 0
                self.cpu_ax.set_ylim(0, max(10, max_cpu * 1.2))
                
                if len(cpu_values) > window_size:
                    self.cpu_ax.legend()
            
            self.cpu_ax.set_title('CPU Használat (%)', fontsize=12)
            self.cpu_ax.grid(True, linestyle='--', alpha=0.7)
            self.cpu_ax.set_facecolor('#f8f9fa')
            self.cpu_canvas.draw()
            
            self.mem_ax.clear()
            if self.perf_data['timestamps'] and self.perf_data['memory_mb']:
                timestamps = list(self.perf_data['timestamps'])
                mem_values = list(self.perf_data['memory_mb'])
                
                window_size = 5
                if len(mem_values) > window_size:
                    moving_avg = pd.Series(mem_values).rolling(window_size).mean().dropna().tolist()
                    self.mem_ax.plot(
                        timestamps[-len(moving_avg):], 
                        moving_avg,
                        'g-', linewidth=2, label='Mozgóátlag'
                    )
                
                self.mem_ax.plot(
                    timestamps, 
                    mem_values,
                    'r-', linewidth=1, alpha=0.5, label='Valós érték'
                )
                self.mem_ax.fill_between(
                    timestamps, 
                    0, 
                    mem_values,
                    color='red', alpha=0.1
                )
                
                max_mem = max(mem_values) if mem_values else 0
                self.mem_ax.set_ylim(0, max(10, max_mem * 1.2))
                
                if len(mem_values) > window_size:
                    self.mem_ax.legend()
            
            self.mem_ax.set_title('Memória Használat (MB)', fontsize=12)
            self.mem_ax.grid(True, linestyle='--', alpha=0.7)
            self.mem_ax.set_facecolor('#f8f9fa')
            self.mem_canvas.draw()
    
    def update_exe_heatmap(self):
        if not self.perf_data['exe_analysis']:
            return
            
        self.heatmap_ax.clear()
        
        labels = list(self.perf_data['exe_analysis'].keys())
        values = list(self.perf_data['exe_analysis'].values())
        
        sorted_indices = np.argsort(values)[::-1]
        sorted_labels = [labels[i] for i in sorted_indices]
        sorted_values = [values[i] for i in sorted_indices]
        
        colors = plt.cm.Reds(np.linspace(0.3, 1, len(sorted_values)))
        
        bars = self.heatmap_ax.barh(sorted_labels, sorted_values, color=colors)
        
        for bar in bars:
            width = bar.get_width()
            self.heatmap_ax.text(
                width + 0.01, 
                bar.get_y() + bar.get_height()/2,
                f'{width:.2f}', 
                ha='left', 
                va='center',
                fontsize=9
            )
        
        self.heatmap_ax.set_title('EXE Struktúra Elemzés (Referencia Hőtérkép)', fontsize=12)
        self.heatmap_ax.set_xlabel('Intenzitás')
        self.heatmap_ax.set_xlim(0, 1.1)
        self.heatmap_ax.grid(True, axis='x', linestyle='--', alpha=0.3)
        self.heatmap_ax.set_facecolor('#f8f9fa')
        self.heatmap_canvas.draw()


if __name__ == '__main__':
    # FIXED: Set DPI awareness before creating QApplication
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    window = ProcessMonitorApp()
    if "--embed" not in sys.argv:
        window.show()   
                    
    sys.exit(app.exec_())
 
 