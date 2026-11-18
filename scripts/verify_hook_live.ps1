# Live verification of the SpecWeft Stop hook inside a real Claude Code session.
# Prerequisite: the Claude Code CLI is logged in (`claude /login`).
# Creates a sandbox clone of full-stack-fastapi-template + sqlmodel, indexes them, installs the Stop hook,
# asks Claude Code to make a contract-breaking edit, then prints what the hook returned.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Sb = Join-Path $env:TEMP "specweft-hook-live"
if (Test-Path $Sb) { Remove-Item -Recurse -Force $Sb }
New-Item -ItemType Directory -Force $Sb | Out-Null
git clone -q (Join-Path $Root "data/repos/full-stack-fastapi-template") "$Sb/full-stack-fastapi-template"
git clone -q (Join-Path $Root "data/repos/sqlmodel") "$Sb/sqlmodel"
$Db = "$Sb/hook.db" -replace '\\', '/'
python -m specweft.cli --db $Db scan "$Sb/full-stack-fastapi-template" --name full-stack-fastapi-template --group fastapi-stack --no-index | Out-Null
python -m specweft.cli --db $Db scan "$Sb/sqlmodel" --name sqlmodel --group fastapi-stack --exclude "docs/*" | Out-Null
$Py = (Get-Command python).Source -replace '\\', '/'
$HookScript = (Join-Path $Root "scripts/specweft_hook.py") -replace '\\', '/'
$Repo = "$Sb/full-stack-fastapi-template"
New-Item -ItemType Directory -Force "$Repo/.claude" | Out-Null
@"
{"hooks": {"Stop": [{"hooks": [{"type": "command", "command": "\"$Py\" $HookScript --db $Db", "timeout": 120}]}]}}
"@ | Set-Content -Encoding utf8 "$Repo/.claude/settings.json"
$env:SPECWEFT_HOOK_LOG = "$Sb/hook_log.jsonl" -replace '\\', '/'
Push-Location $Repo
try {
  claude -p "Edit backend/app/core/config.py: rename the Settings field PROJECT_NAME to APP_TITLE in that file only. Do not edit any other file in this first step. Keep your answer short." `
    --permission-mode acceptEdits --allowedTools "Read Edit Grep Glob" --max-turns 12 --output-format json | Set-Content -Encoding utf8 "$Sb/claude_run.json"
} finally { Pop-Location }
Write-Host "`n== Claude result =="; (Get-Content "$Sb/claude_run.json" -Raw | ConvertFrom-Json).result
Write-Host "`n== Hook invocations (data/hook_log.jsonl format) =="; Get-Content "$Sb/hook_log.jsonl"
Write-Host "`n== Files changed in sandbox =="; git -C $Repo status --short
