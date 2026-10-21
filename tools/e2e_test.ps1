$AppDir = "C:\Users\MT-110326\Documents\Programas\AICascadeWidget"
Get-Process pythonw,python -ErrorAction SilentlyContinue | Where-Object { $_.Path -like "*AICascadeWidget*" } | Stop-Process -Force
Start-Sleep 1

Write-Host "[TEST1] Lanzando desktop_app.py via pythonw (como el acceso real)..."
Start-Process -FilePath (Join-Path $AppDir "venv\Scripts\pythonw.exe") -ArgumentList "`"$AppDir\desktop_app.py`"" -WorkingDirectory $AppDir

Start-Sleep 6
$webv = Get-Process | Where-Object { $_.MainWindowTitle -match "AICascade" }
Write-Host "[TEST2] Ventana visibles: $($webv | Select-Object -ExpandProperty ProcessName -ErrorAction SilentlyContinue)"
Write-Host ("[TEST3] Puerto 8000: " + (Test-NetConnection 127.0.0.1 -Port 8000 -InformationLevel Quiet -WarningAction SilentlyContinue))
Write-Host ("[TEST4] Puerto 8765: " + (Test-NetConnection 127.0.0.1 -Port 8765 -InformationLevel Quiet -WarningAction SilentlyContinue))

Start-Sleep 16
Write-Host "[TEST5] Estado tras watchdog (15s):"
Get-Process | Where-Object { $_.MainWindowTitle -match "AICascade" } | Select-Object ProcessName,MainWindowTitle | Format-Table -AutoSize | Out-Host
$browser = Get-Process chrome,msedge -ErrorAction SilentlyContinue | Where-Object { try { ((Get-CimInstance Win32_Process -Filter "ProcessId=$($_.Id)" -ErrorAction SilentlyContinue).CommandLine) -like "*engine-profile*" } catch { $false } }
Write-Host ("[TEST6] Browser --app con perfil AICascade: " + ($browser | Measure-Object).Count)

Write-Host "[TEST7] Limpiando..."
$mine = Get-Process pythonw,python -ErrorAction SilentlyContinue | Where-Object { $_.Path -like "*AICascadeWidget*" }
$mine += $browser
foreach ($p in $mine) { try { Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue } catch {} }
Write-Host "[TEST8] Fin."
