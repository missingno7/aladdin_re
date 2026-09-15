param(
    [switch]$Mute,
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$PlayerArgs
)

$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
$previousPythonPath = $env:PYTHONPATH
$previousNativeLibrary = $env:GENESIS_NATIVE_LIBRARY
try {
    $projectPython = Join-Path $PSScriptRoot '.venv/Scripts/python.exe'
    $nativeLibrary = Join-Path $PSScriptRoot 'build/libgenesis_native.dll'
    if (-not (Test-Path -LiteralPath $projectPython)) {
        throw 'Build the project first using the commands in README.md.'
    }
    if (-not (Test-Path -LiteralPath $nativeLibrary)) {
        throw 'Build the native DLL first using the commands in README.md.'
    }
    $source = Join-Path $PSScriptRoot 'src'
    $env:PYTHONPATH = if ($env:PYTHONPATH) { "$source;$env:PYTHONPATH" } else { $source }
    $env:GENESIS_NATIVE_LIBRARY = $nativeLibrary
    $args = @('-m', 'genesis_re', 'play') + $PlayerArgs
    if ($Mute) { $args += '--mute' }
    & $projectPython @args
    if ($LASTEXITCODE -ne 0) { throw "Player exited with code $LASTEXITCODE" }
} finally {
    if ($null -eq $previousPythonPath) { Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue }
    else { $env:PYTHONPATH = $previousPythonPath }
    if ($null -eq $previousNativeLibrary) { Remove-Item Env:GENESIS_NATIVE_LIBRARY -ErrorAction SilentlyContinue }
    else { $env:GENESIS_NATIVE_LIBRARY = $previousNativeLibrary }
    Pop-Location
}
