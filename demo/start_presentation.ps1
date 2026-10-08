param(
    [ValidateSet('shadow','simulation','dual')][string]$Mode='shadow',
    [int]$Port=8767
)
$ErrorActionPreference='Stop'
$demoRoot=$PSScriptRoot
$runtimeDir=Join-Path $demoRoot 'runtime'
New-Item -ItemType Directory -Path $runtimeDir -Force | Out-Null
$demoPython='C:\Users\liuko\AppData\Local\Programs\Python\Python313\python.exe'
$demoUrl="http://127.0.0.1:$Port"
$health=$null
try {$health=Invoke-RestMethod -Uri "$demoUrl/api/health" -TimeoutSec 2} catch {}
if($health){
    $actual=if(-not $health.model_loaded){'simulation'}elseif($health.model.dual_system){'dual'}else{'shadow'}
    if($health.app -ne 'jev-credit-demo' -or $health.app_revision -ne '2026-10-02-pm12-showcase' -or $actual -ne $Mode){throw 'Port is occupied by a different application revision or mode. Select another port.'}
    Write-Output "Presentation ready: $demoUrl ($Mode)"
    exit
}
$dbPath=Join-Path $runtimeDir "presentation-$Mode.sqlite3"
$appPath=Join-Path $demoRoot 'app.py'
$proc=Start-Process -FilePath $demoPython -ArgumentList @('"'+$appPath+'"','--port',"$Port",'--mode',$Mode,'--db','"'+$dbPath+'"') -WorkingDirectory $demoRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $runtimeDir "presentation-$Mode.log") -RedirectStandardError (Join-Path $runtimeDir "presentation-$Mode-error.log") -PassThru
$proc.Id | Set-Content -LiteralPath (Join-Path $runtimeDir "presentation-$Mode.pid")
Write-Output "Starting local presentation: $demoUrl ($Mode), PID $($proc.Id)."
Write-Output 'Model loading is separate from inference time. Check /api/health before opening.'
