# AetherLearn AI — Full-Stack Startup Script
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$nodeCommand = Get-Command node.exe -ErrorAction SilentlyContinue
$nodeExe = if ($nodeCommand) { $nodeCommand.Source } else { $null }
if (-not $nodeExe -and $env:LOCALAPPDATA) {
    $runtimeRoot = Join-Path $env:LOCALAPPDATA "OpenAI\Codex\runtimes\cua_node"
    $nodeExe = Get-ChildItem -Path (Join-Path $runtimeRoot "*\bin\node.exe") -File -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1 -ExpandProperty FullName
}
if (-not $nodeExe -or -not (Test-Path -LiteralPath $nodeExe)) {
    throw "Node.js was not found. Install Node.js or add node.exe to PATH."
}
$nodeDir = Split-Path -Parent $nodeExe
$env:PATH = "$nodeDir;$env:PATH"

$pyExe = Join-Path $env:LOCALAPPDATA "Programs\Python\Python314\python.exe"
if (-not (Test-Path -LiteralPath $pyExe)) {
    $pythonCommand = Get-Command python.exe -ErrorAction SilentlyContinue
    $pyExe = if ($pythonCommand) { $pythonCommand.Source } else { $null }
}
if (-not $pyExe -or -not (Test-Path -LiteralPath $pyExe)) {
    throw "Python was not found. Install Python 3.11 or newer and add python.exe to PATH."
}

$distIndex = Join-Path $PSScriptRoot "dist\index.html"
$frontendFiles = Get-ChildItem -LiteralPath (Join-Path $PSScriptRoot "src") -File -Recurse
$frontendChanged = $frontendFiles | Where-Object { $_.LastWriteTimeUtc -gt (Get-Item -LiteralPath $distIndex -ErrorAction SilentlyContinue).LastWriteTimeUtc } | Select-Object -First 1
if (-not (Test-Path -LiteralPath $distIndex) -or $frontendChanged) {
    Write-Host "Building frontend production bundle..."
    & $nodeExe "node_modules\typescript\bin\tsc" -b
    if ($LASTEXITCODE -ne 0) { throw "TypeScript build failed with exit code $LASTEXITCODE." }
    & $nodeExe "node_modules\vite\bin\vite.js" build
    if ($LASTEXITCODE -ne 0) { throw "Vite build failed with exit code $LASTEXITCODE." }
}

Write-Host "Starting AetherLearn AI Full-Stack Platform at http://127.0.0.1:8000 ..."
& $pyExe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

