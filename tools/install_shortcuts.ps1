# AICascadeWidget - Crear accesos directos (Escritorio + Menu Inicio + Barra de tareas)
# Estrategia profesional: lanzar venv\Scripts\pythonw.exe desktop_app.py (sin consola),
# icono app.ico en .lnk + exe. Ancla la barra copiando el .lnk al folder User Pinned.
param([string]$AppDir)
$ErrorActionPreference = "Stop"

Write-Host "== AICascadeWidget: instalando accesos directos =="

$pyw = Join-Path $AppDir "venv\Scripts\pythonw.exe"
$desktopApp = Join-Path $AppDir "desktop_app.py"
$icon = Join-Path $AppDir "app.ico"
if (!(Test-Path $desktopApp)) { throw "No existe $desktopApp" }
if (!(Test-Path $pyw)) { $pyw = (Get-Command pythonw.exe -ErrorAction SilentlyContinue).Source }
if (-not $pyw) { throw "No se encontro pythonw.exe" }

$Wsh = New-Object -ComObject WScript.Shell
$desktop = [Environment]::GetFolderPath("Desktop")
$programs = [Environment]::GetFolderPath("Programs")
$pinnedTask = Join-Path $env:APPDATA "Microsoft\Internet Explorer\Quick Launch\User Pinned\TaskBar"

# Limpiar duplicados viejos
foreach ($old in @("AICascade Widget.lnk", "AICascadeWidget.lnk")) {
  foreach ($dir in @($desktop, $programs)) {
    $p = Join-Path $dir $old
    if (Test-Path $p) { Remove-Item $p -Force; Write-Host "Limpio $p" }
  }
}

$targets = @(
  (Join-Path $desktop "AICascade Widget.lnk"),
  (Join-Path $programs "AICascade Widget.lnk")
)
foreach ($lnk in $targets) {
  $sc = $Wsh.CreateShortcut($lnk)
  $sc.TargetPath = $pyw
  $sc.Arguments = "`"$desktopApp`""
  $sc.WorkingDirectory = $AppDir
  $sc.Description = "AICascade Widget - Gestor de cascada IA"
  $sc.WindowStyle = 1
  if (Test-Path $icon) { $sc.IconLocation = "$icon,0" }
  $sc.Save()
  Write-Host "OK $lnk"
}

# Pinned TaskBar (aparece en el proximo arranque de Explorer / sesion Win11)
try {
  New-Item -ItemType Directory -Force -Path $pinnedTask | Out-Null
  Copy-Item (Join-Path $desktop "AICascade Widget.lnk") $pinnedTask -Force
  Write-Host "OK copia anclada en TaskBar User Pinned"
} catch { Write-Host "TaskBar pin copia no disponible: $_" }

Write-Host "Listo. Escritorio + Menu Inicio + Barra de Tareas (visible proximo inicio de explorer)."
Write-Host "Si no aparece en la barra: clic derecho sobre 'AICascade Widget' (Inicio/Escritorio) > Anclar a la barra de tareas."
