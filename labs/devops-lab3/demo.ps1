# DVO-L3-7F2A91
. "$PSScriptRoot/common.ps1"
$evidence = Join-Path $PSScriptRoot 'evidence'
New-Item -ItemType Directory -Force $evidence | Out-Null
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$log = Join-Path $evidence "$stamp-demo.txt"
Start-Transcript -Path $log
$monitor = $null
try {
    Write-Host '=== 5: cluster, resources and configuration ==='
    K get nodes
    Invoke-Checked kubectl @('--context', $LabProfile, '-n', 'kube-system', 'get', 'pods')
    K get 'pods,deployments,replicasets,services,pvc,jobs'
    $checkEnv = 'import os; print({k:os.environ[k] for k in ["APP_ENV","APP_NAME","POSTGRES_HOST"]}); print({k:bool(os.environ.get(k)) for k in ["POSTGRES_PASSWORD","SECRET_KEY"]})'
    $checkEnv | kubectl --context $LabProfile -n $LabProfile exec -i deployment/auction -c app '--' python - | Out-Host
    if ($LASTEXITCODE -ne 0) { throw 'Environment check failed' }
    Write-Host '=== 6a: self healing ==='
    $oldPod = kubectl --context $LabProfile -n $LabProfile get pods -l app=auction -o jsonpath='{.items[0].metadata.name}'
    K delete pod $oldPod
    K rollout status deployment/auction --timeout=180s
    K get pods -l app=auction -o wide
    Write-Host '=== 6b: scaling and traffic distribution ==='
    K scale deployment/auction --replicas=3
    K rollout status deployment/auction --timeout=180s
    Get-Content "$PSScriptRoot/traffic.py" -Raw | kubectl --context $LabProfile -n $LabProfile exec -i traffic-probe '--' python - 15 | Out-Host
    if ($LASTEXITCODE -ne 0) { throw 'Traffic check failed' }
    Write-Host '=== 6c-e: rolling update, history, rollback, continuous traffic ==='
    $monitor = Start-Job -ArgumentList $PSScriptRoot, $LabProfile -ScriptBlock {
        param($directory, $profileName)
        . "$directory/common.ps1"
        Get-Content "$directory/traffic.py" -Raw | kubectl --context $profileName -n $profileName exec -i traffic-probe '--' python - 60
        if ($LASTEXITCODE -ne 0) { throw 'Availability check failed' }
    }
    Start-Sleep -Seconds 3
    K set image deployment/auction app=galactic-auction:1.1.0
    K rollout status deployment/auction --timeout=180s
    K get pods -l app=auction -o wide
    K rollout history deployment/auction
    K exec deployment/auction -c app '--' printenv APP_VERSION
    K rollout undo deployment/auction
    K rollout status deployment/auction --timeout=180s
    $monitor | Wait-Job | Out-Null
    $samples = @($monitor | Receive-Job -ErrorAction Stop)
    $samples | Write-Output
    [IO.File]::WriteAllText((Join-Path $evidence "$stamp-availability.txt"), "# DVO-L3-7F2A91`n" + ($samples -join "`n") + "`n", [Text.UTF8Encoding]::new($false))
    Write-Host '=== 7: intentional failure, diagnosis and repair ==='
    K set image deployment/auction app=galactic-auction:does-not-exist-lab3
    $deadline = (Get-Date).AddMinutes(4)
    $badPod = $null
    do {
        $state = kubectl --context $LabProfile -n $LabProfile get pods -l app=auction -o json | ConvertFrom-Json
        foreach ($pod in $state.items) {
            if ($pod.status.containerStatuses.state.waiting.reason -contains 'ImagePullBackOff') {
                $badPod = $pod.metadata.name
            }
        }
        if (-not $badPod) { Start-Sleep -Seconds 3 }
    } until ($badPod -or (Get-Date) -gt $deadline)
    if (-not $badPod) { throw 'ImagePullBackOff was not observed within timeout' }
    K get pods -l app=auction
    K describe pod $badPod
    K get events --sort-by=.metadata.creationTimestamp
    K logs deployment/auction -c app --tail=30
    K exec deployment/auction -c app '--' sh -c 'id; hostname; pwd'
    K set image deployment/auction app=galactic-auction:1.0.0
    K rollout status deployment/auction --timeout=180s
    K scale deployment/auction --replicas=2
    K rollout status deployment/auction --timeout=180s
    K get 'pods,deployments,replicasets,services'
} finally {
    # Always restore the intended version and replica count, including failed demos.
    & kubectl --context $LabProfile -n $LabProfile set image deployment/auction app=galactic-auction:1.0.0
    & kubectl --context $LabProfile -n $LabProfile scale deployment/auction --replicas=2
    if ($monitor) { $monitor | Stop-Job; $monitor | Remove-Job }
    Stop-Transcript
    $saved = [IO.File]::ReadAllText($log)
    [IO.File]::WriteAllText($log, "# DVO-L3-7F2A91`n" + $saved.Replace("`r`n", "`n"), [Text.UTF8Encoding]::new($false))
}
