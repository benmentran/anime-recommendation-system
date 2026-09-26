# Periodic Postgres backup (pg_dump custom format). Run via Task Scheduler / cron.
# Usage: powershell -File scripts/backup_postgres.ps1 (run from repo root so `docker compose` finds the project)
$ErrorActionPreference = "Stop"
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$outDir = Join-Path $PSScriptRoot "..\backups"
New-Item -ItemType Directory -Force -Path $outDir | Out-Null
$out = Join-Path $outDir "anime-$stamp.dump"
docker compose exec -T postgres pg_dump -U anime -Fc anime > $out
Write-Output "backup -> $out"
