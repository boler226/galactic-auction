# DVO-L4-3C8B52
. "$PSScriptRoot/../devops-lab3/common.ps1"
Write-Host 'Keep this terminal open: http://127.0.0.1:8090'
Invoke-Checked kubectl @('--context', $LabProfile, '-n', 'galactic-auction-helm', 'port-forward', 'service/auction-galactic-auction-app', '8090:80', '--address=127.0.0.1')
