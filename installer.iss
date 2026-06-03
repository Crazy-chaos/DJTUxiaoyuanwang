[Setup]
AppName=大连交通大学有线网认证
AppVersion=0.1.1
DefaultDirName={pf}\大连交通大学有线网认证
DefaultGroupName=大连交通大学有线网认证
OutputDir=.\dist
OutputBaseFilename=DJTU v0.1.1_Setup
Compression=lzma
SolidCompression=yes
SetupIconFile=.\icon.ico
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64
CloseApplications=force

[Tasks]
Name: "desktopicon"; Description: "在桌面创建快捷方式"; GroupDescription: "附加选项:"

[Files]
Source: ".\dist\大连交通大学有线网认证.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: ".\Ruijie Supplicant\*"; DestDir: "{app}\Ruijie Supplicant"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: ".\rjrzkhd4.99.exe"; DestDir: "{tmp}"; Flags: deleteafterinstall ignoreversion
Source: ".\vcredist_x86.exe"; DestDir: "{tmp}"; Flags: deleteafterinstall ignoreversion

[Icons]
Name: "{group}\大连交通大学有线网认证"; Filename: "{app}\大连交通大学有线网认证.exe"
Name: "{commondesktop}\大连交通大学有线网认证"; Filename: "{app}\大连交通大学有线网认证.exe"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\RunOnce"; ValueType: string; ValueName: "DJTUNetworkConfigurator"; ValueData: """{app}\大连交通大学有线网认证.exe"""; Flags: uninsdeletevalue; Check: IsRuijieNotInstalled

[Run]
Filename: "{tmp}\vcredist_x86.exe"; Parameters: "/q"; Flags: waituntilterminated; StatusMsg: "正在安装VS运行时库，请稍候..."
Filename: "{tmp}\rjrzkhd4.99.exe"; Flags: waituntilterminated; Check: IsRuijieNotInstalled; StatusMsg: "正在启动锐捷客户端安装程序 (安装完成后可能需重启)..."
Filename: "{app}\大连交通大学有线网认证.exe"; Description: "安装完成后立刻运行程序"; Flags: nowait postinstall skipifsilent

[Code]
var
  IsUpdate: Boolean;

procedure KillApp;
var
  ResultCode: Integer;
begin
  Exec('taskkill.exe', '/F /IM "大连交通大学有线网认证.exe" /T', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Exec('taskkill.exe', '/F /IM "network_configurator.exe" /T', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
end;

function InitializeSetup(): Boolean;
begin
  KillApp;
  IsUpdate := RegKeyExists(HKEY_LOCAL_MACHINE, 'SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\大连交通大学有线网认证_is1') or
              RegKeyExists(HKEY_LOCAL_MACHINE, 'SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\大连交通大学有线网认证_is1') or
              RegKeyExists(HKEY_CURRENT_USER, 'SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\大连交通大学有线网认证_is1');
  Result := True;
end;

function InitializeUninstall(): Boolean;
begin
  KillApp;
  Result := True;
end;

function IsRuijieNotInstalled: Boolean;
begin
  if IsUpdate then
    Result := False
  else
    Result := not (
      FileExists(ExpandConstant('{pf32}\锐捷网络\Ruijie Supplicant\RuijieSupplicant.exe')) or
      FileExists(ExpandConstant('{pf64}\锐捷网络\Ruijie Supplicant\RuijieSupplicant.exe')) or
      FileExists(ExpandConstant('{pf32}\Ruijie Networks\Ruijie Supplicant\RuijieSupplicant.exe')) or
      FileExists(ExpandConstant('{pf64}\Ruijie Networks\Ruijie Supplicant\RuijieSupplicant.exe')) or
      FileExists('C:\Ruijie Supplicant\RuijieSupplicant.exe')
    );
end;
