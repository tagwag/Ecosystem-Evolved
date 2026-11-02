# GPU setup for Ecosystem-Evolved on Windows (RTX 3080).
# Run via setup_gpu.bat. Everything printed also goes to setup_gpu_log.txt next to this file.
# Changes nothing system-wide: makes a .venv folder here and installs Python packages into it.
$ErrorActionPreference = 'Continue'
Set-Location $PSScriptRoot
$log = Join-Path $PSScriptRoot 'setup_gpu_log.txt'
Start-Transcript -Path $log -Force | Out-Null

Write-Host "`n=== 0. Closing background apps (Windows, security, drivers and Claude left alone) ==="
# Steam first, politely, so it saves its state; the rest are closed directly.
$steam = 'C:\Program Files (x86)\Steam\steam.exe'
if ((Get-Process steam -ErrorAction SilentlyContinue) -and (Test-Path $steam)) { & $steam -shutdown; Start-Sleep 8 }
foreach ($n in @('wallpaper64', 'wallpaper32', 'steam', 'steamwebhelper', 'PhoneExperienceHost',
                 'AcrobatNotificationClient', 'SystemSettings')) {
    $p = Get-Process $n -ErrorAction SilentlyContinue
    if ($p) { $p | Stop-Process -Force -ErrorAction SilentlyContinue; Write-Host "closed: $n" }
}

Write-Host "`n=== 1. GPU driver ==="
$smi = Get-Command nvidia-smi -ErrorAction SilentlyContinue
if (-not $smi) { $smi = Get-Item 'C:\Windows\System32\nvidia-smi.exe' -ErrorAction SilentlyContinue }
if (-not $smi) { Write-Host 'NO_NVIDIA_SMI: NVIDIA driver not found. Install it from nvidia.com/drivers, then rerun.'; Stop-Transcript; exit 1 }
& nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv
$drv = [double]((& nvidia-smi --query-gpu=driver_version --format=csv,noheader).Split('.')[0])
if ($drv -lt 570) { Write-Host "DRIVER_TOO_OLD: driver $drv, need 570 or newer. Update via GeForce/NVIDIA app or nvidia.com/drivers, then rerun."; Stop-Transcript; exit 1 }

Write-Host "`n=== 2. Python ==="
$py = $null
foreach ($c in @('py -3.12', 'py -3.13', 'py -3.11', 'py -3', 'python')) {
    $exe, $rest = $c.Split(' ')
    $rest = @($rest | Where-Object { $_ })
    $v = (& $exe @rest --version 2>&1 | Out-String).Trim()
    if ($LASTEXITCODE -eq 0 -and $v -match '^Python 3\.(1[0-4])\b') { $pyExe = $exe; $pyArgs = $rest; $py = $c; Write-Host "Using: $c ($v)"; break }
}
if (-not $py) {
    Write-Host 'No Python 3.10-3.14 found. Installing Python 3.12 for this user with winget...'
    winget install -e --id Python.Python.3.12 --scope user --accept-package-agreements --accept-source-agreements
    $pyExe = "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe"; $pyArgs = @()
    if (-not (Test-Path $pyExe)) { Write-Host 'PYTHON_INSTALL_FAILED: install Python 3.12 from python.org, then rerun.'; Stop-Transcript; exit 1 }
}

Write-Host "`n=== 3. Virtual environment (.venv) ==="
if (-not (Test-Path .venv\Scripts\python.exe)) { & $pyExe @pyArgs -m venv .venv }
$vpy = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $vpy)) { Write-Host 'VENV_FAILED'; Stop-Transcript; exit 1 }
$vpy = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
& $vpy -m pip install --upgrade pip --quiet

Write-Host "`n=== 4. PyTorch (CUDA 12.8 build) + project packages (big download, ~3 GB) ==="
& $vpy -m pip install torch --index-url https://download.pytorch.org/whl/cu128
& $vpy -m pip install -r requirements.txt

Write-Host "`n=== 5. GPU check: CPU vs GPU brain, speed ==="
& $vpy -m ecosim.gpu_check

Write-Host "`n=== 6. What else is using the machine (report only, nothing closed) ==="
Write-Host '-- Programs using the GPU:'
& nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv
& nvidia-smi | Select-String -Pattern 'MiB \|' | Select-Object -Last 25
Write-Host '-- Top 25 by memory:'
Get-Process | Sort-Object WorkingSet64 -Descending | Select-Object -First 25 Id, ProcessName, @{n='MB';e={[int]($_.WorkingSet64/1MB)}}, MainWindowTitle | Format-Table -AutoSize | Out-String -Width 200
Write-Host '-- Top 25 by CPU right now (2 s sample):'
$a = Get-Process | Select-Object Id, ProcessName, CPU
Start-Sleep 2
$b = Get-Process | Select-Object Id, ProcessName, CPU
$b | ForEach-Object { $p = $_; $o = $a | Where-Object Id -eq $p.Id; [pscustomobject]@{Id=$p.Id; Name=$p.ProcessName; CPUsec=[math]::Round(($p.CPU - $o.CPU),2)} } |
  Sort-Object CPUsec -Descending | Select-Object -First 25 | Format-Table -AutoSize | Out-String -Width 200
Write-Host '-- Power plan:'
powercfg /getactivescheme
Write-Host "`nDONE_SETUP"
Stop-Transcript | Out-Null
