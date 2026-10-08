param([int]$Port=8769)
$ErrorActionPreference='Stop'
$demoRoot=$PSScriptRoot
$runtimeDir=Join-Path $demoRoot 'runtime'
New-Item -ItemType Directory -Path $runtimeDir -Force | Out-Null
$demoPython='C:\Users\liuko\AppData\Local\Programs\Python\Python313\python.exe'
$demoUrl="http://127.0.0.1:$Port"
try { $existing=Invoke-RestMethod -Uri "$demoUrl/api/health" -TimeoutSec 2 } catch { $existing=$null }
if($existing){
 if($existing.app -eq 'jev-credit-demo' -and $existing.model.dual_system){Write-Output "Dual experiment ready: $demoUrl";exit}
 throw 'Port occupied by another mode; select a different port.'
}
$appPath=Join-Path $demoRoot 'app.py'
$database=Join-Path $runtimeDir 'dual-experiment.sqlite3'
$process=Start-Process -FilePath $demoPython -ArgumentList @('"'+$appPath+'"','--port',"$Port",'--mode','dual','--db','"'+$database+'"') -WorkingDirectory $demoRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $runtimeDir 'dual.log') -RedirectStandardError (Join-Path $runtimeDir 'dual-error.log') -PassThru
$process.Id | Set-Content -LiteralPath (Join-Path $runtimeDir 'dual.pid')
Write-Output "Experimental dual model service starting: $demoUrl (PID $($process.Id))."
Write-Output 'This explicit experiment is not the default. Current small slow model has not demonstrated quality improvement.'
