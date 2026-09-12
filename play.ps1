param([switch]$Mute)
$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try {
    $projectPython = Join-Path $PSScriptRoot '.venv/Scripts/python.exe'
    if (-not (Test-Path -LiteralPath $projectPython)) {
        throw 'Build the project first using the commands in README.md.'
    }
    $playerArgs = @('-m', 'aladdin_sega', 'play', '--mode', 'original')
    if ($Mute) { $playerArgs += '--mute' }
    & $projectPython @playerArgs
    if ($LASTEXITCODE -ne 0) { throw "Player exited with code $LASTEXITCODE" }
} finally {
    Pop-Location
}
