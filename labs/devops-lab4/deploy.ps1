# DVO-L4-3C8B52
param([ValidateSet('dev','prod')][string]$Environment = 'dev')
. "$PSScriptRoot/../devops-lab3/common.ps1"
$helm = Join-Path $LabRoot '.lab-cache/helm3/windows-amd64/helm.exe'
if (-not (Test-Path $helm)) { throw 'Install Helm 3 as described in the lab 4 README.' }
M start --driver=docker --cpus=2 --memory=4096
M addons enable ingress
M addons enable metrics-server
M image load galactic-auction:1.0.0
M image load galactic-auction:1.1.0
$chart = Join-Path $LabRoot 'helm/galactic-auction'
Invoke-Checked $helm @('--kube-context', $LabProfile, 'upgrade', '--install', 'auction', $chart, '-n', 'galactic-auction-helm', '--create-namespace', '--reset-values', '-f', "$chart/values-$Environment.yaml", '--wait', '--wait-for-jobs', '--timeout', '5m')
if ($Environment -eq 'dev') {
    Invoke-Checked kubectl @('--context', $LabProfile, '-n', 'galactic-auction-helm', 'exec', 'deployment/auction-galactic-auction-app', '-c', 'app', '--', 'python', '-m', 'app.cli', 'seed-demo')
}
