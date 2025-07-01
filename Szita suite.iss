[Setup]
AppName=Szita suite
AppVersion=1.0.1
AppPublisher=Szita_Team
DefaultDirName={commonpf}\Szita suite
OutputBaseFilename=Szita suite_telepito
DefaultGroupName=Szita suite
SetupIconFile=icon.ico
Compression=lzma
SolidCompression=yes
WizardStyle=modern
LanguageDetectionMethod=none
AppContact=https://bankkontir.hu
AppCopyright=Szita_Team
SignTool=mysign

[Languages]
Name: "hu"; MessagesFile: "compiler:Languages\Hungarian.isl"

[Files]
Source: "dist\Szita suite\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs


[Icons]
Name: "{group}\Szita suite"; Filename: "{app}\Szita suite.exe"
Name: "{commondesktop}\Szita suite"; Filename: "{app}\Szita suite.exe"; Tasks: desktopikon

[Tasks]
Name: desktopikon; Description: "Asztali ikon létrehozása"; GroupDescription: "Kiegészítő lehetőségek"; Flags: unchecked
Name: deleteinstaller; Description: "Telepítő törlése telepítés után"; GroupDescription: "Kiegészítő lehetőségek"; Flags: unchecked

[Run]
Filename: "{app}\Szita suite.exe"; Description: "Alkalmazás indítása"; Flags: nowait postinstall skipifsilent

Filename: "cmd.exe";   Parameters: "/C timeout /T 5 /NOBREAK >nul & del ""{srcexe}""";   Flags: runhidden shellexec; Tasks: deleteinstaller
