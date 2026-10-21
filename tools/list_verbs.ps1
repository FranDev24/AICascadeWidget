$s=New-Object -ComObject Shell.Application
$f=$s.Namespace('C:\Users\MT-110326\Desktop')
$item=$f.ParseName('AICascade Widget.lnk')
foreach($v in $item.Verbs()) { Write-Host $v.Name }