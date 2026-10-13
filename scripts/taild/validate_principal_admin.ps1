param([Parameter(Mandatory)][string]$Probe, [Parameter(Mandatory)][string]$History,
    [Parameter(Mandatory)][string]$Pipe, [Parameter(Mandatory)][string]$Credential,
    [Parameter(Mandatory)][string]$Output)
$ErrorActionPreference='Stop'
$taskName='TailD-Isolated-Principal-'+[guid]::NewGuid().ToString('N')
# The LocalService task runs in session 0; its interactive supervisor does not.
# Global named events with the explicit three-principal DACL cross that boundary.
$eventPrefix='Global\Darkaxt.TailD.Principal.'+[guid]::NewGuid().ToString('N')
$readyName=$eventPrefix+'.Ready'
$releaseName=$eventPrefix+'.Release'
$security=New-Object System.Security.AccessControl.EventWaitHandleSecurity
foreach($sid in @([Security.Principal.WindowsIdentity]::GetCurrent().User.Value,'S-1-5-18','S-1-5-19')){
    $rule=New-Object System.Security.AccessControl.EventWaitHandleAccessRule(
        (New-Object Security.Principal.SecurityIdentifier($sid)),[Security.AccessControl.EventWaitHandleRights]::FullControl,
        [Security.AccessControl.AccessControlType]::Allow)
    $security.AddAccessRule($rule)
}
$created=$false
$ready=New-Object Threading.EventWaitHandle($false,[Threading.EventResetMode]::ManualReset,$readyName,[ref]$created,$security)
$release=New-Object Threading.EventWaitHandle($false,[Threading.EventResetMode]::ManualReset,$releaseName,[ref]$created,$security)
$process=$null
$registered=$false
try{
    # Only generated test binaries/output receive service-principal access.
    # The product history, source data and current-user vault ACLs stay unchanged.
    & icacls (Split-Path -Parent $Probe) /grant '*S-1-5-19:(OI)(CI)RX' | Out-Null
    if($LASTEXITCODE -ne 0){throw 'Cannot grant isolated probe executable access'}
    if(Test-Path -LiteralPath $Output){throw 'Probe output already exists'}
    New-Item -ItemType File -Path $Output | Out-Null
    & icacls $Output /grant '*S-1-5-19:W' | Out-Null
    if($LASTEXITCODE -ne 0){throw 'Cannot grant isolated probe output access'}
    $arguments='--history "'+$History+'" --pipe "'+$Pipe+'" --credential "'+$Credential+'" --output "'+$Output+
        '" --ready "'+$readyName+'" --release "'+$releaseName+'"'
    $action=New-ScheduledTaskAction -Execute $Probe -Argument $arguments -WorkingDirectory (Split-Path -Parent $Probe)
    $principal=New-ScheduledTaskPrincipal -UserId 'S-1-5-19' -LogonType ServiceAccount -RunLevel Limited
    # Explicitly no execution-kill limit. Completion is a native event and owned
    # process exit, not elapsed time. The WinExe action cannot open a console.
    $settings=New-ScheduledTaskSettingsSet -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew
    Register-ScheduledTask -TaskName $taskName -Action $action -Principal $principal -Settings $settings | Out-Null
    $registered=$true
    Start-ScheduledTask -TaskName $taskName
    $ready.WaitOne() | Out-Null
    $report=Get-Content -LiteralPath $Output -Raw | ConvertFrom-Json
    $process=[Diagnostics.Process]::GetProcessById([int]$report.pid)
    $null=$process.Handle
    if($process.MainModule.FileName -ne (Resolve-Path -LiteralPath $Probe).Path){
        $process.Dispose();$process=$null;throw 'Probe process identity mismatch'
    }
    $release.Set() | Out-Null
    $process.WaitForExit()
    if($process.ExitCode -ne 0 -or $report.sid -ne 'S-1-5-19' -or $report.administrator -or
       -not $report.history_denied -or -not $report.pipe_denied -or $report.credential_read){
        throw 'Other-principal isolation probe failed'
    }
    $report | ConvertTo-Json -Compress
} finally {
    $release.Set() | Out-Null
    if($null -ne $process){$process.WaitForExit();$process.Dispose()}
    if($registered){
        Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
        if(Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue){throw 'Temporary task removal not verified'}
        Write-Output '{"temporary_task_removed":true}'
    }
    $ready.Dispose();$release.Dispose()
}
