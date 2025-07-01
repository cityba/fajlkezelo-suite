Szita Fájlkezelő Suite 2025
 
Áttekintés
A Szita Fájlkezelő Suite egy átfogó Python alapú eszközkészlet, amely különböző fájl- és rendszerkezelési feladatokat egységes felületen integrál. Az alkalmazás 5 fő modult tartalmaz, amelyek a következő területeket fedik le:

Fájlkezelés - Másolás, duplikátumkezelés, üres mappák kezelése
=======
exe fájl készítése "pyinstaller szita.spec"     


Fájlkereső - Tartalom- és fájlnév alapú keresés

Médiafájlok - Képek, videók és hangfájlok kezelése

Hálózat - Hálózati eszközök felderítése

EXE Gyártó - Python szkriptekből aláírt végrehajtható fájlok készítése

Főbb funkciók
Fájlkezelő modul
Fájlok másolása forrás- és célmappa között

Duplikált fájlok keresése és kezelése

Üres mappák azonosítása és törlése

Fájltípus szerinti szűrés (.py, .html, .js, stb.)

Fájlba Kereső
Tartalomkeresés különböző fájlformátumokban (docx, xlsx, pdf)

Dátumtartomány szerinti szűrés

Fájlkiterjesztések kizárása

Találatok exportálása Excel fájlba

Médiafájlok
Képek és videók előnézete

Fájlok törlése

Képek nagyítása/kicsinyítése

Videók lejátszása beépített lejátszóval

Fájlok megnyitása alapértelmezett alkalmazással

Hálózati eszközök
Aktív eszközök felderítése ARP és ping segítségével

Eszköztípusok automatikus azonosítása (IP kamera, NVR)

MAC címek és hosztnevek megjelenítése

Eszközök színes megkülönböztetése típus szerint

EXE Gyártó
Python szkriptekből .exe fájlok készítése

Digitális aláírás hozzáadása PFX fájllal

Telepítőkészítő generálása Inno Setup segítségével

Teljesítményoptimalizálás (GPU gyorsítás, párhuzamos feldolgozás)

Technológiai háttér
Programozási nyelv: Python 3.10+

GUI keretrendszer: PyQt5

Függőségek:

PyPDF2 (PDF fájlok kezeléséhez)

python-docx (Word fájlok kezeléséhez)

openpyxl (Excel fájlok kezeléséhez)

psutil (erőforrás-felhasználás monitorozásához)

GPUtil (GPU használat monitorozásához)

Telepítés és futtatás
Függőségek telepítése:

bash
pip install -r requirements.txt
Alkalmazás indítása:

bash
python sablon.py
EXE fordításhoz
Az alkalmazás PyInstaller segítségével fordítható végrehajtható fájllá:

bash
pyinstaller --noconfirm --onefile --windowed --icon "icon.ico" --upx-dir "upx" --name "Szita suite" --add-data "egyes.py;." --add-data "kettes.py;." --add-data "harmas.py;." --add-data "negyes.py;." --hidden-import docx --hidden-import openpyxl --hidden-import PyPDF2 --hidden-import PyQt5.QtMultimedia --hidden-import PyQt5.QtMultimediaWidgets --add-data "otos.py;." --hidden-import psutil --hidden-import GPUtil --add-binary "PyQt5\Qt5\plugins\imageformats;PyQt5\Qt5\plugins\multimedia" --clean "sablon.py"
Képernyőképek
Fájlkezelő	Médiafájlok
https://file_manager.png	https://media_files.png
Fájlkereső	EXE Gyártó
https://file_search.png	https://exe_builder.png
Használati esetek
Fájlok rendszerezése és tisztítása

Tartalomkeresés nagy dokumentumgyűjteményekben

Médiafájlok gyors áttekintése és kezelése

Hálózati biztonság ellenőrzése

Python alkalmazások terjesztésre kész .exe fájljainak létrehozása

Jellemzők
Modern, sötét téma

Reszponzív felület

Többszálas feldolgozás

Erőforrás-hatékony megvalósítás

Platformfüggetlen működés (Windows, macOS, Linux)

