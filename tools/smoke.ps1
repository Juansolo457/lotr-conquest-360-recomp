# Boot check: start lotrc.exe (its own profile and cache, debug logging), stop it after N
# seconds and print the end of the log. Its window DOES appear on the user's screen (--headless
# does not hide it) and they can play in it: say so before running. Surviving proves nothing about rendering.
# -Captures N saves N screenshots 400 ms apart just before stopping; -CaptureEvery N saves one
# every N seconds during the run (private/captures/<project>-<time>/ either way).
# -Autopilot <script> plays a controller script (port/src/autopilot.h; scripts in tools/autopilot/).
# --headless (passed unless -Autopilot is given) makes the runtime answer the game's dialogs by
# itself (the save-name keyboard returns its default text at once, message boxes their default
# button): fine for boot checks, wrong for scripted play, where the controller answers them.
#   pwsh -NoProfile -File tools/smoke.ps1 [-Seconds 40] [-Captures 2] [-Extra '--gpu_plugin xenos']
#   pwsh -NoProfile -File tools/smoke.ps1 -Seconds 120 -CaptureEvery 5 -Autopilot tools/autopilot/<script>.txt
[CmdletBinding()]
param(
    [ValidateRange(5,1800)][int]$Seconds = 40,
    [ValidateRange(0,20)][int]$Captures = 0,
    [ValidateRange(0,600)][int]$CaptureEvery = 0,
    [string]$Autopilot = '',
    [string]$Tag = '',       # names the captures folder (<program>-<tag>-<time>)
    [string]$Extra = '',
    # only port/ (lotrc.exe) for now
    [ValidateSet('port')][string]$Project = 'port',
    [switch]$FreshProfile,   # start from an empty test profile (the same path through the menus every run)
    # Every thread's backtrace (recompiled functions show as sub_<360 address>) into
    # logs/stacks-<time>-<n>.txt, written by the toolchain's lldb attaching for a few seconds and
    # detaching: at the end of the run before it is stopped (-StackDump), and/or at these seconds
    # from the start (-StackDumpAt 20,60). For hangs: the game is paused while lldb walks it.
    [switch]$StackDump,
    [int[]]$StackDumpAt = @(),
    [ValidateSet('Release','RelWithDebInfo')][string]$Configuration = 'RelWithDebInfo'
)
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$port = Join-Path $root $Project | Resolve-Path
$exeName = 'lotrc'
$executable = Join-Path $port "out\build\win-amd64-$($Configuration.ToLowerInvariant())\$exeName.exe"
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
New-Item -ItemType Directory -Force (Join-Path $port 'logs') | Out-Null
$log = Join-Path $port "logs\smoke-$stamp.log"
$captureDir = Join-Path $root ("private\captures\$exeName-" + $(if ($Tag) { "$Tag-" } else { "" }) + $stamp)
if ($FreshProfile) { Remove-Item -Recurse -Force (Join-Path $port 'user-smoke') -ErrorAction SilentlyContinue }
$info = [Diagnostics.ProcessStartInfo]::new($executable)
$info.WorkingDirectory = $port
$info.UseShellExecute = $false
$info.CreateNoWindow = $true
$extraArguments = @($Extra -split '\s+' | Where-Object { $_ })
if ($Autopilot) { $extraArguments += @('--lotrc_autopilot', (Resolve-Path (Join-Path $root $Autopilot)).Path) }
$headless = if ($Autopilot) { @() } else { @('--headless=true') }
foreach ($argument in @('--no-fullscreen', '--resolution', '720p',
    '--game_data_root', "$port\assets", '--user_data_root', "$port\user-smoke",
    '--cache_root', "$port\cache-smoke", '--log_file', $log, '--log_level', 'debug', '--log_flush_interval', '1') + $extraArguments + $headless) {
    $info.ArgumentList.Add($argument)
}
$capture = { & (Join-Path $PSScriptRoot 'capture_window.ps1') -ProcessId $process.Id -Out $captureDir | Out-Null }
$lldb = Join-Path $root '.tools\llvm\bin\lldb.exe'
$dumps = 0
$writeStacks = {
    if (!(Test-Path $lldb)) { Write-Warning "lldb not found at ${lldb}: no stack dump"; return }
    $script:dumps++
    $out = Join-Path $port "logs\stacks-$stamp-$($script:dumps).txt"
    $at = [Math]::Round(((Get-Date) - $start).TotalSeconds)
    "# lotrc pid $($process.Id) at +$at s" | Set-Content $out
    # The attach stops on a breakpoint exception, which --batch treats as a crash: the -o commands
    # stop there, so the same commands also go in -k (run on a crash stop).
    & $lldb --batch -p $process.Id -o 'thread backtrace all -c 40' -o 'process detach' -k 'thread backtrace all -c 40' -k 'process detach' 2>&1 | Add-Content $out
    "stack dump at +$at s: $out"
}
$process = [Diagnostics.Process]::Start($info)
$start = Get-Date
$deadline = [Math]::Max(1, $Seconds - $Captures)
$next = $CaptureEvery
$dumpTimes = [Collections.Generic.Queue[int]]::new()
foreach ($t in ($StackDumpAt | Sort-Object)) { $dumpTimes.Enqueue($t) }
while (!$process.HasExited) {
    $elapsed = ((Get-Date) - $start).TotalSeconds
    if ($elapsed -ge $deadline) { break }
    if ($dumpTimes.Count -and $elapsed -ge $dumpTimes.Peek()) { [void]$dumpTimes.Dequeue(); & $writeStacks }
    if ($CaptureEvery -gt 0 -and $elapsed -ge $next) {
        New-Item -ItemType Directory -Force $captureDir | Out-Null
        try { & $capture } catch { }
        $next += $CaptureEvery
    }
    Start-Sleep -Milliseconds 250
}
$stopped = !$process.HasExited
if ($stopped) {
    New-Item -ItemType Directory -Force $captureDir | Out-Null
    for ($i = 0; $i -lt $Captures; $i++) {
        try { & $capture } catch { }
        Start-Sleep -Milliseconds 400
    }
    if ($StackDump) { & $writeStacks }
    $process.Kill()
    $process.WaitForExit()
}
"stoppedByHarness=$stopped exitCode=$($process.ExitCode) extra='$Extra' log=$log captures=$captureDir"
if (Test-Path $log) { Get-Content $log -Tail 40 }
