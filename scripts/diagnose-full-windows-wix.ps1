# Nonpublishing full production-resource reproduction. No release API or signing keys.
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
$artifacts = Join-Path $repo 'full-wix-diagnostic-artifacts'
New-Item -ItemType Directory -Force $artifacts | Out-Null
$target = 'x86_64-pc-windows-msvc'
Push-Location "$repo/frontend"
try {
    '{"bundle":{"createUpdaterArtifacts":false}}' | Set-Content -Encoding utf8 'diagnostic-unsigned.json'
    foreach ($scope in @('system', 'per-user-original', 'per-user-restored-resources')) {
        if ($scope -eq 'per-user-original') {
            & python ../scripts/render-per-user-wix.py --source src-tauri/wix/main.wxs --system-wxs "src-tauri/target/$target/release/wix/x64/main.wxs" --output src-tauri/target/wix-per-user/main.wxs
            if ($LASTEXITCODE -ne 0) { throw 'Renderer failed' }
            Copy-Item dist "$artifacts/system-dist" -Recurse
        }
        if ($scope -eq 'per-user-restored-resources') {
            Remove-Item dist -Recurse -Force
            Copy-Item "$artifacts/system-dist" dist -Recurse
        }
        $log = "$artifacts/$scope.log"
        $ErrorActionPreference = 'Continue'
        if ($scope -eq 'system') {
            & bun x tauri build -vv --target $target --bundles msi --config diagnostic-unsigned.json *> $log
        } elseif ($scope -eq 'per-user-original') {
            & bun x tauri build -vv --target $target --bundles msi --config src-tauri/tauri.per-user.conf.json --config diagnostic-unsigned.json *> $log
        } else {
            & bun x tauri bundle -vv --target $target --bundles msi --config src-tauri/tauri.per-user.conf.json --config diagnostic-unsigned.json *> $log
        }
        $code = $LASTEXITCODE
        $ErrorActionPreference = 'Stop'
        Get-Content $log
        "$scope=$code" | Add-Content "$artifacts/results.txt"
        $capture = "$artifacts/$scope"
        New-Item -ItemType Directory -Force $capture | Out-Null
        Get-ChildItem "src-tauri/target/$target/release" -Recurse -File |
            Where-Object { $_.Extension -in @('.wxs','.wxl','.wixobj','.wixpdb') } |
            Copy-Item -Destination $capture -Force
        Get-ChildItem dist/assets -File | Select-Object Name,Length | ConvertTo-Json | Set-Content "$capture/dist-files.json"
        if ($scope -eq 'system' -and $code -ne 0) { throw 'System baseline failed' }
        if ($scope -eq 'per-user-restored-resources' -and $code -ne 0) { throw 'Restored-resource bundle failed' }
    }
} finally {
    Pop-Location
}
