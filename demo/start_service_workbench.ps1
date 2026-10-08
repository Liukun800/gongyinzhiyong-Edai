param([int]$Port=8778,[int]$JudgePort=8148)
$ErrorActionPreference='Stop'
$demoRoot=$PSScriptRoot
$runtimeDir=Join-Path $demoRoot 'runtime'
$demoPython='C:\Users\liuko\AppData\Local\Programs\Python\Python313\python.exe'
$tokenPath=Join-Path $runtimeDir 'judgement-service.token'
if(-not (Test-Path -LiteralPath $tokenPath)){throw 'Start start_judgement_service.ps1 first.'}
$token=(Get-Content -Raw -LiteralPath $tokenPath).Trim()
$info=Invoke-RestMethod -Uri "http://127.0.0.1:$JudgePort/api/info" -Headers @{Authorization="Bearer $token"} -TimeoutSec 3
if($info.api_version -ne 'credit.judgement.v1' -or $info.status -ne 'ready'){throw 'Judgement service not ready.'}
try {
    $connection=New-Object System.Net.Sockets.TcpClient
    $connection.Connect('127.0.0.1',$Port)
    $connection.Dispose()
    $occupied=$true
} catch { $occupied=$false }
if($occupied){throw 'Workbench port occupied; select another port.'}
$appPath=Join-Path $demoRoot 'app.py'
$dbPath=Join-Path $runtimeDir "service-workbench-$Port.sqlite3"
$proc=Start-Process -FilePath $demoPython -ArgumentList @('"'+$appPath+'"','--port',"$Port",'--mode','shadow','--model-backend','service','--judge-url',"http://127.0.0.1:$JudgePort",'--judge-token-file','"'+$tokenPath+'"','--db','"'+$dbPath+'"') -WorkingDirectory $demoRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $runtimeDir "service-workbench-$Port.log") -RedirectStandardError (Join-Path $runtimeDir "service-workbench-$Port-error.log") -PassThru
$proc.Id | Set-Content -LiteralPath (Join-Path $runtimeDir "service-workbench-$Port.pid")
Write-Output "Service-backed workbench starting: http://127.0.0.1:$Port (PID $($proc.Id))"
