# DVO-L4-3C8B52
param([switch]$RemoveLab3)
. "$PSScriptRoot/../devops-lab3/common.ps1"
$helm = Join-Path $LabRoot '.lab-cache/helm3/windows-amd64/helm.exe'
$chart = Join-Path $LabRoot 'helm/galactic-auction'
$ns = 'galactic-auction-helm'
$evidence = Join-Path $PSScriptRoot 'evidence'
function Helm-Lab { Invoke-Checked $helm (@('--kube-context', $LabProfile, '-n', $ns) + $args) }
function Q { Invoke-Checked kubectl (@('--context', $LabProfile, '-n', $ns) + $args) }
Push-Location $LabRoot
Start-Transcript -Path "$evidence/lifecycle.txt"
try {
    Helm-Lab version --short
    if ($RemoveLab3) {
        K get pods
        K exec deployment/auction -c app '--' python -c 'import urllib.request; print(urllib.request.urlopen("http://localhost:8000/health/db").read().decode())'
        # Preserve existing lab 3 database outside Git before removing its PVC.
        $backup = & kubectl --context $LabProfile -n $LabProfile exec deployment/postgres -- pg_dump -U lab_user -d galactic_auction_lab
        if ($LASTEXITCODE -ne 0) { throw 'Database backup failed' }
        [IO.File]::WriteAllText((Join-Path $LabRoot '.lab-cache/lab3-before-helm.sql'), ($backup -join "`n"), [Text.UTF8Encoding]::new($false))
        K delete -f k8s/ --timeout=180s
    }
    foreach ($envName in @('dev','prod')) {
        Helm-Lab lint $chart -f "$chart/values-$envName.yaml" --strict
        $rendered = & $helm template auction $chart -n $ns -f "$chart/values-$envName.yaml"
        if ($LASTEXITCODE -ne 0) { throw 'Rendering failed' }
        [IO.File]::WriteAllText("$evidence/rendered-$envName.yaml", "# DVO-L4-3C8B52`n" + ($rendered -join "`n") + "`n", [Text.UTF8Encoding]::new($false))
    }
    Helm-Lab install auction $chart --create-namespace -f "$chart/values-dev.yaml" --wait --wait-for-jobs --timeout=5m
    Helm-Lab list
    Helm-Lab status auction
    Helm-Lab get values auction --all
    Q get secrets -l owner=helm
    Helm-Lab test auction --timeout=2m
    Helm-Lab upgrade auction $chart --reuse-values --set image.tag=1.1.0 --wait --wait-for-jobs --timeout=5m
    Helm-Lab upgrade auction $chart --reset-values -f "$chart/values-prod.yaml" --wait --wait-for-jobs --timeout=5m
    Q get 'pods,deployments,services,ingress,pvc,jobs'
    Helm-Lab test auction --timeout=2m
    Helm-Lab history auction
    Helm-Lab rollback auction 1 --wait --wait-for-jobs --timeout=5m
    Helm-Lab history auction
    Helm-Lab test auction --timeout=2m
    # A second release in the SAME namespace proves names/selectors are isolated.
    Helm-Lab install second $chart -f "$chart/values-dev.yaml" --set replicaCount=1 --wait --wait-for-jobs --timeout=5m
    Helm-Lab list
    Helm-Lab test second --timeout=2m
    Q get services
    Helm-Lab uninstall second --wait --timeout=3m
    Helm-Lab uninstall auction --wait --timeout=3m
    Helm-Lab list --all
    Q get 'all,configmaps,secrets,pvc,ingresses'
    Q get 'all,configmaps,secrets,pvc,ingresses' -l app.kubernetes.io/managed-by=Helm
} finally {
    Stop-Transcript
    $path = "$evidence/lifecycle.txt"
    $text = [IO.File]::ReadAllText($path)
    $text = (($text -split '\r?\n' | ForEach-Object { $_.TrimEnd() }) -join "`n").TrimEnd()
    [IO.File]::WriteAllText($path, "# DVO-L4-3C8B52`n$text`n", [Text.UTF8Encoding]::new($false))
    Pop-Location
}
