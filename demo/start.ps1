param([int]$Port = 8765, [switch]$NoBrowser)
$ErrorActionPreference = 'Stop'
$demoRoot = $PSScriptRoot
$runtimeDir = Join-Path $demoRoot 'runtime'
New-Item -ItemType Directory -Path $runtimeDir -Force | Out-Null
$demoPython = 'C:\Users\liuko\AppData\Local\Programs\Python\Python313\python.exe'
if (-not (Test-Path -LiteralPath $demoPython)) {
    $demoPython = (Get-Command python -ErrorAction Stop).Source
}
$demoUrl = "http://127.0.0.1:$Port"
$existingDemo = $null
try { $existingDemo = Invoke-RestMethod -Uri "$demoUrl/api/health" -TimeoutSec 2 } catch {}
if ($existingDemo -and $existingDemo.app -ne 'jev-credit-demo') { throw 'Port is occupied by a different application. Choose another port.' }
if (-not $existingDemo) {
    $appPath = Join-Path $demoRoot 'app.py'
    $proc = Start-Process -FilePath $demoPython -ArgumentList @('"' + $appPath + '"', '--port', "$Port") -WorkingDirectory $demoRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $runtimeDir 'server.log') -RedirectStandardError (Join-Path $runtimeDir 'server-error.log') -PassThru
    $proc.Id | Set-Content -LiteralPath (Join-Path $runtimeDir 'server.pid')
    $ready = $false
    for ($attempt = 0; $attempt -lt 20; $attempt++) {
        Start-Sleep -Milliseconds 250
        try { $health = Invoke-RestMethod -Uri "$demoUrl/api/health" -TimeoutSec 1; if ($health.app -eq 'jev-credit-demo') { $ready=$true; break } } catch {}
        if ($proc.HasExited) { break }
    }
    if (-not $ready) { throw 'Demo failed to start. Check runtime/server-error.log.' }
}
Write-Output "Demo running: $demoUrl (workflow simulation, no model loaded)"
if (-not $NoBrowser) { Start-Process $demoUrl }
