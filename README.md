# Szita Fájlkezelő Suite 2025

## Áttekintés
A Szita Fájlkezelő Suite egy Python alapú, moduláris rendszer, amely különböző fájlkezelési és hálózati feladatokat egyesít modern felhasználói felületen. Az alkalmazás öt fő modult tartalmaz:

- **Fájlkezelő** – Másolás, duplikációk kezelése, üres mappák törlése
- **Fájlkereső** – Tartalomalapú keresés fájlformátumokban
- **Médiafájl-kezelő** – Képek, videók előnézete és törlése
- **Hálózati eszközkereső** – Aktív eszközök felderítése LAN-on
- **EXE Gyártó** – Python szkriptekből végrehajtható fájlok készítése
- **EXE elemző** – DLL függőségi gráf megjelenítése,processz információk megjelenítése
- **SQL Adatbázis Kezelő** – MSSQL és MySQL adatbázisok kezelése,táblák szerkesztése

---

## Főbb funkciók

### 📁 Fájlkezelő
- Fájlmásolás forrás és célmappák között
- Duplikált fájlok azonosítása és törlése
- Üres mappák keresése
- Fájltípus alapú szűrés (.py, .html, .js stb.)

### 🔍 Fájlkereső
- Keresés `.docx`, `.xlsx`, `.pdf` tartalom alapján
- Dátumszűrés, fájltípus kizárás
- Eredmények exportja Excelbe

### 🎞️ Médiafájl-kezelő
- Képek/videók előnézete, törlése
- Videólejátszó beépítve
- Nagyítás/kicsinyítés képeken
- Alapértelmezett appal megnyitás

### 🌐 Hálózati eszközkereső
- ARP és ping alapú eszközfelderítés
- Eszköztípusok automatikus azonosítása
- MAC-címek, hosztnevek megjelenítése
- Színkódolt lista

### 🛠️ EXE Gyártó
- `.py` fájlokból `.exe` generálás
- Digitális aláírás (PFX fájl)
- Inno Setup alapú telepítőkészítés
- GPU-gyorsítás, párhuzamosítás támogatás
  
### 📈 EXE Elemző 
- DLL függőségi gráf megjelenítése
- Valós idejű CPU és memóriahasználat monitorozás
- Processz információk megjelenítése
    
### 🗄️SQL Adatbázis Kezelő
- MSSQL és MySQL adatbázisok kezelése
- Táblák és rekordok szerkesztése
- Adatok exportálása CSV formátumba

---

## Technológiai háttér

- **Nyelv**: Python 3.10+
- **GUI**: PyQt5
- **Függőségek**:
  - `PyPDF2`, `python-docx`, `openpyxl`
  - `psutil`, `GPUtil`, `PyQt5.QtMultimedia` ...

---

## Telepítés és futtatás
windows
Output mappába lévő exe fájl, letöltés, telepítés
### Függőségek telepítése
```bash
 
python sablon.py
EXE fordítás PyInstaller-rel
 
pyinstaller --noconfirm --onedir --windowed --clean `
--name "Szita-suite" `
--icon "C:\Users\ap\Documents\fajlkezelo-suite\icon.ico" `
--upx-dir "D:\upx\upx-5.0.1-win64" `
--add-data "egyes.py;." `
--add-data "kettes.py;." `
--add-data "harmas.py;." `
--add-data "negyes.py;." `
--add-data "otos.py;." `
--add-data "hatos.py;." `
--add-data "hetes.py;." `
--add-data "hetesregi.py;." `
--add-data "nyolc.py;." `
--add-data "kilenc.py;." `
--add-data "C:/Users/ap/Documents/fajlkezelo-suite/icon.ico;." `
--add-data "C:/Users/ap/Documents/fajlkezelo-suite/icon.png;." `
--hidden-import=mysql.connector `
--hidden-import=mysql.connector.locales.eng.client_error `
--hidden-import=pyodbc `
--hidden-import=PyQt5.QtNetwork `
--hidden-import=PyQt5.QtPrintSupport `
--hidden-import=PyQt5.QtMultimedia `
--hidden-import=PyQt5.QtMultimediaWidgets `
--hidden-import=matplotlib.backends.backend_qt5agg `
--hidden-import=matplotlib.backends.qt_compat `
--hidden-import=appdirs `
--hidden-import=pefile `
--hidden-import=numpy `
--hidden-import=pandas `
--hidden-import=docx `
--hidden-import=openpyxl `
--hidden-import=PyPDF2 `
--hidden-import=psutil `
--hidden-import=GPUtil `
--collect-all mysql.connector `
--collect-all pyodbc `
"sablon.py"


Használati esetek
Fájlrendszer tisztítás, karbantartás

Dokumentumgyűjtemények gyors átvizsgálása

Médiafájlok előnézete, gyors kezelése

Hálózati eszközök feltérképezése

Python alkalmazások .exe formátumba fordítása

Jellemzők
Sötét téma

Reszponzív PyQt5 felület

Többszálas működés

Erőforrás-optimalizált megvalósítás

Platformfüggetlen (Windows, macOS, Linux)


# Szit File Manager Suite 2025

## Overview
Szit File Manager Suite is a Python-based, modular system that combines various file management and networking tasks in a modern user interface. The application contains five main modules:

- **File Manager** – Copy, manage duplicates, delete empty folders
- **File Finder** – Content-based search in file formats
- **Media File Manager** – Preview and delete images, videos
- **Network Device Finder** – Detect active devices on LAN
- **EXE Maker** – Create executable files from Python scripts
- **EXE Analyzer** – Display DLL dependency graph, display process information
- **SQL Database Manager** – Manage MSSQL and MySQL databases, edit tables

---

## Main features

### 📁 File Manager
- Copy files between source and destination folders
- Identify and delete duplicate files
- Search for empty folders
- Filter by file type (.py, .html, .js, etc.)

### 🔍 File Finder
- Search by `.docx`, `.xlsx`, `.pdf` content
- Date filtering, file type exclusion
- Export results to Excel

### 🎞️ Media File Manager
- Preview and delete images/videos
- Built-in video player
- Zoom in/out on images
- Open with default app

### 🌐 Network Device Finder
- ARP and ping based device discovery
- Automatic identification of device types
- Display MAC addresses, hostnames
- Color-coded list

### 🛠️ EXE Builder
- Generate `.exe` from `.py` files
- Digital signature (PFX file)
- Inno Setup based installer creation
- GPU acceleration, parallelization support

### 📈 EXE Analyzer
- Display DLL dependency graph
- Real-time CPU and memory usage monitoring
- Show process information

### 🗄️SQL Database Manager
- Manage MSSQL and MySQL databases
- Edit tables and records
- Export data to CSV format

---

## Technology background

- **Language**: Python 3.10+
- **GUI**: PyQt5
- **Dependencies**:
- `PyPDF2`, `python-docx`, `openpyxl`
- `psutil`, `GPUtil`, `PyQt5.QtMultimedia` ...

---

## Installation and execution

### Installing dependencies
```bash

python template.py

EXE compilation with PyInstaller

pyinstaller --noconfirm --onefile --windowed --icon "icon.ico" --upx-dir "upx" --name "Sieve suite" \
--add-data "single.py;." --add-data "two.py;." --add-data "harmas.py;." --add-data "four.py;." \
--add-data "otos.py;." --add-data "six.py;." --add-data "hetes.py;." \
--add-data "nyolc.py;." --hidden-import=PyQt5.QtNetwork --hidden-import=PyQt5.QtPrintSupport --hidden-import=appdirs \ 
--hidden-import matplotlib.backends.backend_qt5agg --hidden-import matplotlib.backends.qt_compat \
--hidden-import pefile --hidden-import numpy --hidden import pyodbc --hidden import mysql.connector \
--hidden-import docx --hidden-import openpyxl --hidden-import PyPDF2 \
--hidden-import PyQt5.QtMultimedia --hidden-import PyQt5.QtMultimediaWidgets \
--hidden-import psutil --hidden-import GPUtil \
--add-binary "PyQt5\Qt5\plugins\imageformats;PyQt5\Qt5\plugins\multimedia" \
--clean "sablon.py"

Use cases
File system cleaning, maintenance

Quick scanning of document collections

Preview, quick management of media files

Network tools mapping

Compile Python applications to .exe format

Features
Dark theme

Responsive PyQt5 interface

Multithreaded operation

Resource-optimized implementation

Platform-independent (Windows, macOS, Linux)
