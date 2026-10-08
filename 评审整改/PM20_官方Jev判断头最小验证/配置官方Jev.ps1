param([switch]$RunMinimum)

$ErrorActionPreference = 'Stop'
$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    throw '未找到 Python，请先安装 Python 3 后再运行。'
}

# Keep credentials in this console session; never persist them to disk.
if ([string]::IsNullOrWhiteSpace($env:JEV_API_KEY) -and [string]::IsNullOrWhiteSpace($env:TYPESAFE_API_KEY)) {
    $secureKey = Read-Host '输入官方 Jev API Key（隐藏输入，仅当前窗口生效）' -AsSecureString
    $keyPointer = [IntPtr]::Zero
    try {
        $keyPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureKey)
        $env:JEV_API_KEY = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($keyPointer).Trim()
    }
    finally {
        if ($keyPointer -ne [IntPtr]::Zero) {
            [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($keyPointer)
        }
        $secureKey.Dispose()
    }
    if ([string]::IsNullOrWhiteSpace($env:JEV_API_KEY)) {
        throw '未输入密钥，配置停止；没有发起网络调用。'
    }
}

if ([string]::IsNullOrWhiteSpace($env:JEV_API_BASE_URL)) {
    $env:JEV_API_BASE_URL = 'https://api.typesafe.ai/v1/systemone'
}
if ([string]::IsNullOrWhiteSpace($env:JEV_MODEL)) {
    $env:JEV_MODEL = 'jev-latest'
}

& $python.Source -X utf8 (Join-Path $PSScriptRoot 'run_minimum.py')
if ($LASTEXITCODE -ne 0) {
    throw '配置检查未通过，请按上方错误类别修正地址或模型；没有发起网络调用。'
}
Write-Host '本窗口配置检查通过。密钥未落盘，网络调用为 0。'

if ($RunMinimum) {
    & (Join-Path $PSScriptRoot '开始官方最小验证.ps1')
}
