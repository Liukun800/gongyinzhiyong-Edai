param([int]$Port = 8771, [int]$MaxRequests = 20)
$ErrorActionPreference = 'Stop'
if ([string]::IsNullOrWhiteSpace($env:JEV_API_KEY) -and [string]::IsNullOrWhiteSpace($env:TYPESAFE_API_KEY)) {
    Write-Host '请从已配置官方凭据的PowerShell窗口启动；本脚本不接收或保存密钥。'
    exit 2
}
$runtime = Join-Path $PSScriptRoot 'runtime'
New-Item -ItemType Directory -Path $runtime -Force | Out-Null
$stamp = Get-Date -Format 'yyyyMMdd_HHmmss_fff'
$db = Join-Path $runtime "official-$stamp.sqlite3"
& python -X utf8 (Join-Path $PSScriptRoot 'official_workbench.py') --port $Port --db $db --max-requests $MaxRequests
exit $LASTEXITCODE
