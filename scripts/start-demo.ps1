param(
    [ValidateSet('simulation','official-preview','official','shadow','dual')][string]$Mode='simulation',
    [int]$Port=8765,
    [int]$MaxRequests=20
)
$ErrorActionPreference='Stop'
$demoDirectory=Join-Path (Split-Path $PSScriptRoot -Parent) 'demo'
$pythonCommand=(Get-Command python -ErrorAction Stop).Source
if($Mode -eq 'official-preview') {
    & $pythonCommand -X utf8 (Join-Path $demoDirectory 'official_workbench.py') --preview --port $Port
} elseif($Mode -eq 'official') {
    if([string]::IsNullOrWhiteSpace($env:JEV_API_KEY) -and [string]::IsNullOrWhiteSpace($env:TYPESAFE_API_KEY)) {
        throw 'Set JEV_API_KEY or TYPESAFE_API_KEY in this PowerShell session before using official mode.'
    }
    & $pythonCommand -X utf8 (Join-Path $demoDirectory 'official_workbench.py') --port $Port --max-requests $MaxRequests
} else {
    & $pythonCommand -X utf8 (Join-Path $demoDirectory 'app.py') --mode $Mode --port $Port
}
exit $LASTEXITCODE
