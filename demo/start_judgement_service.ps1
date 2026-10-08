param([int]$Port=8148)
$ErrorActionPreference='Stop'
$demoRoot=$PSScriptRoot
$runtimeDir=Join-Path $demoRoot 'runtime'
New-Item -ItemType Directory -Path $runtimeDir -Force | Out-Null
$demoPython='C:\Users\liuko\AppData\Local\Programs\Python\Python313\python.exe'
$tokenPath=Join-Path $runtimeDir 'judgement-service.token'
$token=$null
if(Test-Path -LiteralPath $tokenPath){$token=(Get-Content -Raw -LiteralPath $tokenPath).Trim()}
try {
    $connection=New-Object System.Net.Sockets.TcpClient
    $connection.Connect('127.0.0.1',$Port)
    $connection.Dispose()
    $occupied=$true
} catch { $occupied=$false }
if($occupied){
    if(-not $token){throw 'Port occupied; select another port.'}
    $info=Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/info" -Headers @{Authorization="Bearer $token"} -TimeoutSec 3
    if($info.api_version -ne 'credit.judgement.v1' -or $info.status -ne 'ready'){throw 'Different service on this port.'}
    Write-Output "Judgement service ready: http://127.0.0.1:$Port"
    exit
}
$servicePath=Join-Path $demoRoot 'judgement_service.py'
$proc=Start-Process -FilePath $demoPython -ArgumentList @('"'+$servicePath+'"','--port',"$Port",'--token-file','"'+$tokenPath+'"') -WorkingDirectory $demoRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $runtimeDir "judgement-$Port.log") -RedirectStandardError (Join-Path $runtimeDir "judgement-$Port-error.log") -PassThru
$proc.Id | Set-Content -LiteralPath (Join-Path $runtimeDir "judgement-$Port.pid")
Write-Output "Judgement service starting: http://127.0.0.1:$Port (PID $($proc.Id))"
Write-Output 'Wait for ready in the log before starting the service-backed workbench. Token stays in runtime.'
