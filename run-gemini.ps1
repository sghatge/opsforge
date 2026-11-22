$ErrorActionPreference = 'Stop'

$repoRoot = $PSScriptRoot
$port = 8766
if (-not [string]::IsNullOrWhiteSpace($env:OPSFORGE_PORT)) {
    $port = [int]$env:OPSFORGE_PORT
}
$embeddedPython = Join-Path $repoRoot '.python-runtime\python.exe'
$useEmbeddedPython = Test-Path -LiteralPath $embeddedPython

if ($useEmbeddedPython) {
    $pythonPath = $embeddedPython
    $pathConfig = Join-Path (Split-Path -Parent $embeddedPython) 'python314._pth'
    if (Test-Path -LiteralPath $pathConfig) {
        $configuredPaths = Get-Content -LiteralPath $pathConfig
        if ($configuredPaths -notcontains $repoRoot) {
            Add-Content -LiteralPath $pathConfig -Value $repoRoot
        }
    }
} else {
    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if (-not $pythonCommand) {
        throw 'Python 3.10 or later is required. Install Python or place an embeddable runtime in .python-runtime.'
    }
    $pythonPath = $pythonCommand.Source
}

$secureKey = Read-Host 'Gemini API key (input is hidden)' -AsSecureString
$keyPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureKey)
try {
    $apiKey = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($keyPointer)
    if ([string]::IsNullOrWhiteSpace($apiKey)) {
        throw 'A Gemini API key is required.'
    }

    $env:GEMINI_API_KEY = $apiKey
    $env:OPSFORGE_LLM_PROVIDER = 'gemini'
    if ([string]::IsNullOrWhiteSpace($env:GEMINI_MODEL)) {
        $env:GEMINI_MODEL = 'gemini-3.6-flash'
    }

    Push-Location $repoRoot
    try {
        if ($useEmbeddedPython) {
            $bootstrap = "import sys; from opsforge.__main__ import main; main()"
            & $pythonPath -c $bootstrap --demo --db .opsforge-gemini.db --port $port
        } else {
            & $pythonPath -m opsforge --demo --db .opsforge-gemini.db --port 8765
        }
    } finally {
        Pop-Location
    }
} finally {
    Remove-Item Env:GEMINI_API_KEY -ErrorAction SilentlyContinue
    $apiKey = $null
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($keyPointer)
    $secureKey.Dispose()
}
