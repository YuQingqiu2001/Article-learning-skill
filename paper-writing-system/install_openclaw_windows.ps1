param(
  [string]$CodexHome = "",
  [switch]$Force,
  [switch]$DryRun,
  [switch]$WithVenv
)

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$installer = Join-Path $scriptDir "scripts\install_openclaw.py"

$argsList = @($installer)
if ($CodexHome -ne "") { $argsList += @("--codex-home", $CodexHome) }
if ($Force) { $argsList += "--force" }
if ($DryRun) { $argsList += "--dry-run" }
if ($WithVenv) { $argsList += "--with-venv" }

python @argsList
