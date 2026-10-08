$ErrorActionPreference = 'Stop'
# Invoke from the PowerShell window where the user configured the session key.
if ([string]::IsNullOrWhiteSpace($env:JEV_API_KEY) -and [string]::IsNullOrWhiteSpace($env:TYPESAFE_API_KEY)) {
    Write-Host '当前窗口未发现 Jev 凭据，未发起调用。请在已配置密钥的窗口运行本脚本。'
    exit 2
}
& python -X utf8 (Join-Path $PSScriptRoot 'run_minimum.py') --run
$runExitCode = $LASTEXITCODE
if ($runExitCode -eq 0) {
    & python -X utf8 (Join-Path $PSScriptRoot 'summarize_minimum.py')
    exit $LASTEXITCODE
}
exit $runExitCode
