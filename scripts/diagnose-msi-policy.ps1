$ErrorActionPreference = 'Stop'
$dir = 'C:\Users\Public\vs-msi-policy'
New-Item -ItemType Directory -Force $dir | Out-Null
& icacls $dir /grant '*S-1-5-32-545:(OI)(CI)M' | Out-Null
$msi = Join-Path $dir 'preview153-current-user.msi'
Invoke-WebRequest 'https://github.com/debpalash/VoiceStudio/releases/download/preview/VoiceStudio_Current_User_0.5.2-153_x64_en-US.msi' -OutFile $msi
$hash = (Get-FileHash $msi -Algorithm SHA256).Hash.ToLowerInvariant()
if ($hash -ne '00af1eef7a96474c697ebd4216cd266624da244350dabf576659b46c75ea0cc1') { throw 'Unexpected MSI bytes' }
$installer = New-Object -ComObject WindowsInstaller.Installer
$db = $installer.OpenDatabase($msi, 0)
$summary = $db.SummaryInformation(0)
"SummaryWordCount=$($summary.Property(15))" | Set-Content "$dir/msi-properties.txt"
$view = $db.OpenView('SELECT `Property`, `Value` FROM `Property`')
$view.Execute()
while ($record = $view.Fetch()) {
    if ($record.StringData(1) -in @('ALLUSERS','MSIINSTALLPERUSER','ProductName','ProductVersion')) {
        "$($record.StringData(1))=$($record.StringData(2))" | Add-Content "$dir/msi-properties.txt"
    }
}
$policy = 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\Installer'
$hadPolicy = Test-Path $policy
$before = if ($hadPolicy) { Get-ItemProperty $policy } else { $null }
$hadDisable = $null -ne $before -and $null -ne $before.PSObject.Properties['DisableMSI']
$oldDisable = if ($hadDisable) { $before.DisableMSI } else { $null }
Get-ItemProperty $policy,'HKCU:\SOFTWARE\Policies\Microsoft\Windows\Installer' -ErrorAction SilentlyContinue | Format-List * | Out-File "$dir/policies-before.txt"
$user = 'VoiceStudioPolicyTest'
$password = 'VsPolicy-' + [guid]::NewGuid().ToString('N') + '!'
$secure = ConvertTo-SecureString $password -AsPlainText -Force
$credential = New-Object System.Management.Automation.PSCredential("$env:COMPUTERNAME\$user", $secure)
$created = $false
$changed = $false
try {
    & net user $user $password /add | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'Cannot create standard user' }
    $created = $true
    foreach ($mode in @('baseline','allow-unmanaged-host')) {
        if ($mode -eq 'allow-unmanaged-host') {
            $baseline = Get-Content "$dir/baseline.log" -Raw
            if ($baseline -notmatch "(?im)(Machine policy value 'DisableMsi' is [12]|DisableMSI[^\r\n]*[=:][ ]*[12])") {
                'No effective disabling Installer policy found; refusing policy experiment.' | Add-Content "$dir/results.txt"
                break
            }
            New-Item -Path $policy -Force | Out-Null
            New-ItemProperty -Path $policy -Name DisableMSI -Value 0 -PropertyType DWord -Force | Out-Null
            $changed = $true
        }
        $log = "$dir/$mode.log"
        $process = Start-Process msiexec.exe -Credential $credential -LoadUserProfile -Wait -PassThru -ArgumentList @('/i',"`"$msi`"",'/qn','/norestart','DISABLEWEBVIEW2BOOTSTRAP=1','AUTOLAUNCHAPP=0','/l*v',"`"$log`"")
        "$mode=$($process.ExitCode)" | Add-Content "$dir/results.txt"
        if ($process.ExitCode -eq 0) {
            $root = "C:\Users\$user\AppData\Local\VoiceStudio (Current User)"
            "shell=$(Test-Path "$root\omnivoice-studio.exe") uv=$(Test-Path "$root\uv.exe")" | Add-Content "$dir/results.txt"
            $uninstall = Start-Process msiexec.exe -Credential $credential -LoadUserProfile -Wait -PassThru -ArgumentList @('/x',"`"$msi`"",'/qn','/norestart','/l*v',"`"$dir/$mode-uninstall.log`"")
            "uninstall=$($uninstall.ExitCode)" | Add-Content "$dir/results.txt"
            break
        }
    }
} finally {
    if ($changed) {
        if ($hadDisable) { Set-ItemProperty $policy DisableMSI $oldDisable }
        else { Remove-ItemProperty $policy DisableMSI -ErrorAction SilentlyContinue }
        if (-not $hadPolicy) { Remove-Item $policy -ErrorAction SilentlyContinue }
    }
    if ($created) { & net user $user /delete | Out-Null }
    Get-ItemProperty $policy -ErrorAction SilentlyContinue | Format-List * | Out-File "$dir/policies-after.txt"
    Get-Content "$dir/results.txt" -ErrorAction SilentlyContinue
    Remove-Item $msi -ErrorAction SilentlyContinue
}
