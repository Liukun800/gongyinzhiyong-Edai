param([int]$Port=8767)
$ErrorActionPreference='Stop'
$demoRoot=$PSScriptRoot
$runtimeDir=Join-Path $demoRoot 'runtime'
New-Item -ItemType Directory -Path $runtimeDir -Force | Out-Null
$demoPython='C:\Users\liuko\AppData\Local\Programs\Python\Python313\python.exe'
$demoUrl="http://127.0.0.1:$Port"
$health=$null
try {$health=Invoke-RestMethod -Uri "$demoUrl/api/health" -TimeoutSec 2} catch {}
if ($health) {
    if ($health.app -ne 'jev-credit-demo' -or -not $health.model_loaded) {throw 'Port is occupied by a different mode or application.'}
    Write-Output "Real shadow service already ready: $demoUrl"
    exit
}
$appPath=Join-Path $demoRoot 'app.py'
$proc=Start-Process -FilePath $demoPython -ArgumentList @('"'+$appPath+'"','--port',"$Port",'--mode','shadow') -WorkingDirectory $demoRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $runtimeDir 'shadow.log') -RedirectStandardError (Join-Path $runtimeDir 'shadow-error.log') -PassThru
$proc.Id | Set-Content -LiteralPath (Join-Path $runtimeDir 'shadow.pid')
Write-Output "Real shadow service starting (PID $($proc.Id)): $demoUrl"
Write-Output 'Check runtime/shadow.log for ready status. Initial loading may take about a minute on this CPU.'
