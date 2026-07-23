param(
    [ValidateSet("Project", "Global")]
    [string]$Scope = "Project",
    [string]$Target = (Get-Location).Path,
    [switch]$DryRun
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
if (Get-Command py -ErrorAction SilentlyContinue) {
    $Command = "py"; $Prefix = @("-3")
} elseif (Get-Command python3 -ErrorAction SilentlyContinue) {
    $Command = "python3"; $Prefix = @()
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $Command = "python"; $Prefix = @()
} else {
    throw "Python 3를 찾을 수 없습니다."
}

$ArgsList = @("$ScriptDir\uninstall.py", "--scope", $Scope.ToLower())
if ($Scope -eq "Project") {
    $ArgsList += @("--target", $Target)
}
if ($DryRun) {
    $ArgsList += "--dry-run"
}

& $Command @Prefix @ArgsList
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
