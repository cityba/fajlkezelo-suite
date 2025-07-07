# Szita Fájlkezelő Suite 2025

## Áttekintés
A Szita Fájlkezelő Suite egy Python alapú, moduláris rendszer, amely különböző fájlkezelési és hálózati feladatokat egyesít modern felhasználói felületen. Az alkalmazás öt fő modult tartalmaz:

- **Fájlkezelő** – Másolás, duplikációk kezelése, üres mappák törlése
- **Fájlkereső** – Tartalomalapú keresés fájlformátumokban
- **Médiafájl-kezelő** – Képek, videók előnézete és törlése
- **Hálózati eszközkereső** – Aktív eszközök felderítése LAN-on
- **EXE Gyártó** – Python szkriptekből végrehajtható fájlok készítése

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

---

## Technológiai háttér

- **Nyelv**: Python 3.10+
- **GUI**: PyQt5
- **Függőségek**:
  - `PyPDF2`, `python-docx`, `openpyxl`
  - `psutil`, `GPUtil`, `PyQt5.QtMultimedia`

---

## Telepítés és futtatás

### Függőségek telepítése
```bash
pip install -r requirements.txt
Alkalmazás futtatása
 
python sablon.py
EXE fordítás PyInstaller-rel
 
pyinstaller --noconfirm --onefile --windowed --icon "icon.ico" --upx-dir "upx" --name "Szita suite" \
--add-data "egyes.py;." --add-data "kettes.py;." --add-data "harmas.py;." --add-data "negyes.py;." \
--add-data "otos.py;." \
--hidden-import docx --hidden-import openpyxl --hidden-import PyPDF2 \
--hidden-import PyQt5.QtMultimedia --hidden-import PyQt5.QtMultimediaWidgets \
--hidden-import psutil --hidden-import GPUtil \
--add-binary "PyQt5\Qt5\plugins\imageformats;PyQt5\Qt5\plugins\multimedia" \
--clean "sablon.py"
Képernyőképek
Fájlkezelő	Médiafájlok
	

Fájlkereső	EXE Gyártó
	

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

🇬🇧 English Version
Szita File Manager Suite 2025
Overview
Szita Suite is a modular Python-based toolset combining file operations, search, media handling, networking, and executable creation in a single unified interface.

Modules:

File Manager

File Search

Media Files

Network Scanner

EXE Builder

Technologies:
Python 3.10+, PyQt5, PyPDF2, openpyxl, python-docx, psutil, GPUtil

Install:

 
pip install -r requirements.txt
python sablon.py
Build EXE:

 
pyinstaller --onefile sablon.py [...options...]
Use cases:

Clean and manage file systems

Search document collections

Preview and delete media

Scan LAN devices

Build signed EXE installers from Python

Features:

Dark UI, responsive design

Multithreading, GPU optimization

Cross-platform (Windows/macOS/Linux)
