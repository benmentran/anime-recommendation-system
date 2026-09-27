<#
.SYNOPSIS
  Crash-proof chunked runner: invokes a WSL job in bounded rounds, resumes
  via done-files, survives VM bounces between rounds.
.DESCRIPTION
  Each round runs ONE foreground WSL command (never backgrounded) with a
  timeout, then counts the done-file. Stops when done-count >= ExpectedTotal.
  If WSL is dead, waits and retries (MaxFails consecutive failures aborts).
.EXAMPLE
  ./scripts/run_chunked.ps1 -WslScript /mnt/f/netflix-movie-recommendation-system/scripts/wsl_translate_run.sh `
    -ScriptArgs @("--limit","500") -DoneFile F:\netflix-movie-recommendation-system\data\raw\translate_ids.txt `
    -ExpectedTotal 5132 -RoundTimeoutSec 600
#>
param(
  [Parameter(Mandatory)][string]$WslScript,
  [string[]]$ScriptArgs = @(),
  [Parameter(Mandatory)][string]$DoneFile,
  [Parameter(Mandatory)][int]$ExpectedTotal,
  [int]$RoundTimeoutSec = 600,
  [int]$MaxFails = 5
)

function Get-DoneCount {
  if (Test-Path $DoneFile) {
    return @(Get-Content $DoneFile | Where-Object { $_.Trim() -ne "" }).Count
  }
  return 0
}

$fails = 0
$round = 0
while ($true) {
  $done = Get-DoneCount
  Write-Output "ROUND $round done=$done/$ExpectedTotal fails=$fails"
  if ($done -ge $ExpectedTotal) { Write-Output "CHUNKED_DONE"; exit 0 }
  if ($fails -ge $MaxFails) { Write-Output "CHUNKED_ABORT: too many failures"; exit 1 }
  $round++

  # NOTE: Start-Process -Wait has no timeout; use Process.WaitForExit(ms) instead.
  $psi = New-Object System.Diagnostics.ProcessStartInfo
  $psi.FileName = "wsl"
  $psi.Arguments = ((@("-d", "Ubuntu-22.04", "--", "bash", $WslScript) + $ScriptArgs) -join " ")
  $psi.UseShellExecute = $false
  try {
    $p = [System.Diagnostics.Process]::Start($psi)
    if (-not $p.WaitForExit($RoundTimeoutSec * 1000)) {
      try { $p.Kill() } catch {}
      throw "timeout after ${RoundTimeoutSec}s"
    }
    if ($p.ExitCode -ne 0) { throw "exit=$($p.ExitCode)" }
    $fails = 0
  } catch {
    $fails++
    Write-Output "ROUND $round failed: $_ - waiting 60s for VM recovery"
    Start-Sleep -Seconds 60
  }
}
