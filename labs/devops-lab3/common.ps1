# DVO-L3-7F2A91
$ErrorActionPreference = 'Stop'
$LabRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$LabProfile = 'galactic-auction'
# Keep large minikube downloads on the project drive.
$env:MINIKUBE_HOME = Join-Path $LabRoot '.lab-cache'
$minikubeDir = 'C:\Program Files\Kubernetes\Minikube'
$dockerDir = Join-Path $env:LOCALAPPDATA 'Programs\DockerDesktop\resources\bin'
$env:PATH = "$minikubeDir;$dockerDir;$env:PATH"
function Invoke-Checked {
    param([string]$Program, [string[]]$Arguments)
    # Route native stdout through the host so Start-Transcript records it too.
    & $Program @Arguments | Out-Host
    if ($LASTEXITCODE -ne 0) { throw "$Program failed (exit $LASTEXITCODE): $Arguments" }
}
function K {
    Invoke-Checked kubectl (@('--context', $LabProfile, '-n', $LabProfile) + $args)
}
function M {
    Invoke-Checked minikube (@('-p', $LabProfile) + $args)
}
