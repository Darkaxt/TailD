#ifndef Payload
  #error Payload directory required
#endif
#ifndef ProductVersion
  #error Exact upstream-plus-subversion required
#endif
#ifndef OutputPath
  #error Exact build output directory required
#endif
[Setup]
AppId={{04905050-B54D-4D29-9880-39F10B3BCA7E}
AppName=TailD
AppVersion={#ProductVersion}
AppPublisher=Darkaxt
AppPublisherURL=https://github.com/Darkaxt/TailD
DefaultDirName={commonpf64}\Tailscale\TailD
UsePreviousAppDir=no
DisableDirPage=yes
DisableProgramGroupPage=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
CloseApplications=no
RestartApplications=no
AllowCancelDuringInstall=no
SetupMutex=Darkaxt.TailD.Setup
WizardStyle=modern dynamic
OutputDir={#OutputPath}
OutputBaseFilename=TailD-{#ProductVersion}-windows-amd64-setup
Compression=lzma2/fast
SolidCompression=yes
UninstallDisplayIcon={app}\TailD.exe
LicenseFile=LICENSE
[Files]
Source: "{#Payload}\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion
[Icons]
Name: "{commonprograms}\TailD"; Filename: "{app}\TailD.exe"; Comment: "TailD network analytics"
[Run]
Filename: "{app}\TailD.exe"; Description: "Open TailD"; Flags: postinstall nowait skipifsilent runasoriginaluser
[UninstallDelete]
Type: files; Name: "{app}\installation.json"
[Code]
var
  Candidate: String;
  Prepared: Boolean;
  Finished: Boolean;
  OwnerFile: String;
  DeleteHistory: Boolean;
  HelperSequence: Integer;

function Helper(const ProgramPath, Arguments: String): Boolean;
var Code: Integer; Diagnostic: String; Content: AnsiString;
begin
  HelperSequence := HelperSequence + 1;
  Diagnostic := ExpandConstant('{tmp}\taild-helper-') + IntToStr(HelperSequence) + '.json';
  Result := Exec(ProgramPath, Arguments + ' --result "' + Diagnostic + '"', '', SW_HIDE, ewWaitUntilTerminated, Code) and (Code = 0);
  if LoadStringFromFile(Diagnostic, Content) then Log(String(Content));
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var OwnerExitCode: Integer;
begin
  Result := '';
  if CompareText(ExpandConstant('{app}'), ExpandConstant('{commonpf64}\Tailscale\TailD')) <> 0 then begin
    Result := 'TailD must use its fixed analytics directory under the existing Tailscale installation.';
    exit;
  end;
  ExtractTemporaryFiles('{app}\*');
  Candidate := ExpandConstant('{tmp}\') + '{app}';
  if OwnerFile = '' then begin
    OwnerFile := ExpandConstant('{tmp}\taild-original-owner.txt');
    if not ExecAsOriginalUser(Candidate + '\TailD.Setup.exe', 'owner --owner-file "' + OwnerFile + '"', '', SW_HIDE, ewWaitUntilTerminated, OwnerExitCode) then begin
      OwnerFile := '';
      Result := 'Could not identify the original owning account.';
      exit;
    end;
    if OwnerExitCode <> 0 then begin
      OwnerFile := '';
      Result := 'Could not identify the original owning account.';
      exit;
    end;
  end;
  if not Helper(Candidate + '\TailD.Setup.exe', 'prepare --candidate "' + Candidate + '" --owner-file "' + OwnerFile + '"') then begin
    Result := 'Package validation or preparation failed. Close TailD and explicitly stop collection before upgrading. Existing Tailscale connectivity is unchanged.';
    exit;
  end;
  Prepared := True;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then begin
    if not Helper(Candidate + '\TailD.Setup.exe', 'finish --owner-file "' + OwnerFile + '"') then
      RaiseException('TailD reader setup failed; previous analytics binaries will be restored where available.');
    Finished := True;
  end;
end;

procedure DeinitializeSetup;
begin
  if Prepared and not Finished then begin
    if not Helper(Candidate + '\TailD.Setup.exe', 'abort --candidate "' + Candidate + '"') then
      Log('TailD recovery did not complete; retain the verified rollback directory for explicit recovery.');
  end;
end;

function InitializeUninstall: Boolean;
begin
  Result := Helper(ExpandConstant('{app}\TailD.Setup.exe'), 'check-uninstall');
  if not Result and not UninstallSilent then
    MsgBox('Close TailD and explicitly stop collection before uninstalling. No connectivity client is removed.', mbError, MB_OK);
  if Result and not UninstallSilent then
    if MsgBox('Also remove your own local TailD analytics history? GlassWire, Control D, credentials and tailnet nodes are never deleted.', mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES then
      DeleteHistory := True;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var Arguments: String;
begin
  if CurUninstallStep = usUninstall then begin
    Arguments := 'uninstall';
    if DeleteHistory then Arguments := Arguments + ' --delete-history';
    if not Helper(ExpandConstant('{app}\TailD.Setup.exe'), Arguments) then
      RaiseException('TailD uninstall preparation failed; connectivity and source data remain untouched.');
  end;
end;
