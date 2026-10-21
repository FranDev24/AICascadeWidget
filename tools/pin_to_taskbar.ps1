param([string]$ShortcutPath)
$shell = New-Object -ComObject Shell.Application
$folder = $shell.Namespace((Split-Path $ShortcutPath))
$item = $folder.ParseName((Split-Path $ShortcutPath -Leaf))
$verb = $item.Verbs() | Where-Object { $_.Name -match "Taskbar" -or $_.Name -match "anclar" }
if ($verb) { $verb.DoIt(); Write-Host "Anclado a barra de tareas" } else { Write-Host "No se encontro verbo anclar" }