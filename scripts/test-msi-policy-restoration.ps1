param([string]$Case)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$dir = 'C:\Users\Public\vs-msi-policy'
New-Item -ItemType Directory -Force $dir | Out-Null
$msi = "$dir/preview153-current-user.msi"
Invoke-WebRequest 'https://github.com/debpalash/VoiceStudio/releases/download/preview/VoiceStudio_Current_User_0.5.2-153_x64_en-US.msi' -OutFile $msi
if ((Get-FileHash $msi -Algorithm SHA256).Hash.ToLowerInvariant() -ne '00af1eef7a96474c697ebd4216cd266624da244350dabf576659b46c75ea0cc1') { throw 'Unexpected MSI bytes' }
$path = 'SOFTWARE\Policies\Microsoft\Windows\Installer'
[Microsoft.Win32.Registry]::LocalMachine.DeleteSubKeyTree($path, $false)
if ($Case -ne 'absent') {
    $key = [Microsoft.Win32.Registry]::LocalMachine.CreateSubKey($path)
    if ($Case -eq 'string') { $key.SetValue('DisableMSI', '1', [Microsoft.Win32.RegistryValueKind]::String) }
    else { $key.SetValue('DisableMSI', 1, [Microsoft.Win32.RegistryValueKind]::DWord) }
    $key.Dispose()
}
if ($Case -eq 'invalid-msi') { 'not an MSI' | Set-Content $msi }
$failed = $false
try { & "$PSScriptRoot/smoke-per-user-msi.ps1" -MsiPath $msi -PrepareHostedRunner }
catch { $failed = $true; $_ | Out-String | Set-Content "$dir/caught-error.txt" }
$key = [Microsoft.Win32.Registry]::LocalMachine.OpenSubKey($path)
if ($Case -eq 'absent') { if ($null -ne $key) { throw 'Originally absent policy key remains' } }
else {
    if ($null -eq $key) { throw 'Original policy key missing' }
    $expected = if ($Case -eq 'string') { [Microsoft.Win32.RegistryValueKind]::String } else { [Microsoft.Win32.RegistryValueKind]::DWord }
    if ($key.GetValueKind('DisableMSI') -ne $expected -or $key.GetValue('DisableMSI').ToString() -ne '1') { throw 'Policy value/type not restored' }
    $key.Dispose()
}
if ($failed -ne ($Case -eq 'invalid-msi')) { throw "Unexpected helper failure state: $failed" }
"PASS $Case; policy value/type/absence restored; expected failure=$failed" | Tee-Object "$dir/results.txt"
Remove-Item $msi -Force
