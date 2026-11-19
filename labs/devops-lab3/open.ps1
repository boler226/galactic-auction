# DVO-L3-7F2A91
. "$PSScriptRoot/common.ps1"
Write-Host 'Keep this terminal open. Browser: http://127.0.0.1:8080 (API docs: /docs)'
K port-forward service/auction 8080:80 --address=127.0.0.1
