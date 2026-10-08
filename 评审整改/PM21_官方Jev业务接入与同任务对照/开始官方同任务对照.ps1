$ErrorActionPreference = 'Stop'
if ([string]::IsNullOrWhiteSpace($env:JEV_API_KEY) -and [string]::IsNullOrWhiteSpace($env:TYPESAFE_API_KEY)) {
    Write-Host '请从已配置官方凭据的PowerShell窗口启动，无需重新配置。'
    exit 2
}
& python -X utf8 (Join-Path $PSScriptRoot 'run_comparison.py') --run
$runExit = $LASTEXITCODE
if (Get-ChildItem -LiteralPath $PSScriptRoot -Directory -Filter 'run_*') {
    & python -X utf8 (Join-Path $PSScriptRoot 'build_comparison_report.py')
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
exit $runExit
