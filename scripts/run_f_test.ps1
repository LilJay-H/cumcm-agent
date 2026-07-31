param(
  [Parameter(Mandatory = $true)]
  [ValidateScript({ Test-Path -LiteralPath $_ -PathType Leaf })]
  [string]$ProblemPath,
  [string]$RunId = ("f-test-" + (Get-Date -Format "yyyyMMdd-HHmmss"))
)

$ErrorActionPreference = "Stop"

$project = Split-Path -Parent $PSScriptRoot
$problem = (Resolve-Path -LiteralPath $ProblemPath).Path

Set-Location $project
python -m cumcm_agent run `
  --problem $problem `
  --run-id $RunId `
  --config "config\f_test.json" `
  --auto-approve
