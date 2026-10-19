$origen = "C:\Users\MT-110326\Documents\Programas\AICascadeWidget"
$destino = "$env:USERPROFILE\Desktop\AICascadeWidget_Compartir.zip"

if (Test-Path $destino) { Remove-Item $destino -Force }

Compress-Archive -Path "$origen\*" -DestinationPath $destino -Force

Write-Host "`n✅ ZIP creado en:`n$destino`n" -ForegroundColor Green
Write-Host "Listo para enviar por WhatsApp o subir a GitHub Pages / Netlify." -ForegroundColor Cyan
