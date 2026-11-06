; Inno Setup script for Finance Manager.
; Builds FinanceManager-Setup.exe from the PyInstaller output in dist\FinanceManager.
;
; To build by hand (with Inno Setup installed): open this file in Inno Setup
; and click Compile, or run from a command prompt:
;   "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer\FinanceManager.iss
; The build-kit's build_offline.bat does this for you automatically.

#define MyAppName "Finance Manager"
#define MyAppVersion "1.5"
#define MyAppPublisher "Ireneo John II Colet"
#define MyAppURL "https://john.colet.ca"
#define MyAppExeName "FinanceManager.exe"

[Setup]
AppId={{B6B8C9E4-3E7A-4E1B-9B6B-7C3A1F2D5E6A}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
DefaultDirName={autopf}\FinanceManager
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
OutputDir=installer_output
OutputBaseFilename=FinanceManager-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#MyAppExeName}
DisableProgramGroupPage=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional shortcuts:"

[Files]
Source: "..\dist\FinanceManager\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent

; NOTE: Uninstalling deliberately does NOT touch %LOCALAPPDATA%\FinanceManager --
; that folder holds the user's real financial data and backups, and must survive
; an uninstall/reinstall or an upgrade to a newer version.

[Code]
var
  DBLocationPage: TInputDirWizardPage;

procedure InitializeWizard;
begin
  DBLocationPage := CreateInputDirPage(wpSelectDir,
    'Choose Database Location', 'Where should your financial data be stored?',
    'Finance Manager keeps all your data in a single database file. Choose the folder ' +
    'for it below (the default is fine for most people).' + #13#10 + #13#10 +
    'Moving data from an older computer? Just finish installing, then use ' +
    '"Backup & Restore" inside the app (as an Administrator) to restore a backup ' +
    'file copied over from the old computer.',
    False, '');
  DBLocationPage.Add('');
  DBLocationPage.Values[0] := ExpandConstant('{localappdata}\FinanceManager');
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  AppDataDir, LocationFile, DBFolder: String;
begin
  if CurStep = ssPostInstall then
  begin
    AppDataDir := ExpandConstant('{localappdata}\FinanceManager');
    ForceDirectories(AppDataDir);
    LocationFile := AppDataDir + '\db_location.txt';
    { Only set the location if this is a first install (don't overwrite an existing choice). }
    if not FileExists(LocationFile) then
    begin
      DBFolder := DBLocationPage.Values[0];
      ForceDirectories(DBFolder);
      SaveStringToFile(LocationFile, DBFolder + '\FinanceManager.db', False);
    end;
  end;
end;
