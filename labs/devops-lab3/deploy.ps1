# DVO-L3-7F2A91
param([switch]$SkipBuild)
. "$PSScriptRoot/common.ps1"
Push-Location $LabRoot
try {
    Invoke-Checked docker @('info', '--format', '{{.OSType}}')
    M start --driver=docker --cpus=2 --memory=4096
    M addons enable metrics-server
    M addons enable ingress
    if (-not $SkipBuild) {
        foreach ($version in @('1.0.0', '1.1.0')) {
            Invoke-Checked docker @('build', '-f', 'labs/devops-lab3/Dockerfile', '--build-arg', "APP_VERSION=$version", '-t', "galactic-auction:$version", '.')
        }
    }
    M image load galactic-auction:1.0.0
    M image load galactic-auction:1.1.0
    # One apply command, including Namespace and database initialization.
    K apply -f k8s/
    K wait --for=condition=complete job/auction-migrations --timeout=600s
    K rollout status deployment/auction --timeout=300s
    K wait --for=condition=Ready pod/traffic-probe --timeout=120s
    K exec deployment/auction -c app '--' python -m app.cli seed-demo
    K get 'pods,deployments,replicasets,services,pvc,jobs'
    Write-Host 'Ready. Run labs/devops-lab3/open.ps1 and open http://127.0.0.1:8080'
} finally { Pop-Location }
