# Capture frames of a scripted run in RenderDoc, unattended (from graw360-recomp's RenderDoc use):
# starts lotrc.exe under renderdoccmd with a fresh test profile and an autopilot script; the game
# triggers one capture at each of -Times seconds from its first frame through RenderDoc's in-app
# API (--lotrc_rdoc_capture_at, src/frame_timing.cpp), and the test instance is stopped after
# -Seconds. (RenderDoc's remote trigger, which GRAW used, never fired here.) Its window appears on the user's
# screen: say so first. Captures go to private/rdoc/<time>/.
#   pwsh -NoProfile -File tools/rdoc_capture.ps1 -Times 200,215,230 -Seconds 260
# -Play is for a person playing to a bug: the player's own profile and saves (port/user), no
# autopilot, no time limit (the script returns at once and the game runs until quit), and F9 in
# the game captures the next two game frames.
#   pwsh -NoProfile -File tools/rdoc_capture.ps1 -Play
# Under renderdoccmd the game didn't see --lotrc_rdoc_capture_at at all, so the capture times go
# through the environment (the SDK reads every option from REX_<NAME IN CAPITALS> too); pass other
# options that way as well (-Env @{ RENDER_TARGET_PATH_VULKAN = 'fsi' }).
[CmdletBinding()]
param(
    # A string: with pwsh -File, an [int[]] parameter turned '200,215,230' into one number.
    [string]$Times = '200,215,230',
    [ValidateRange(10, 1800)][int]$Seconds = 260,
    [string]$Autopilot = 'tools/autopilot/newgame.txt',
    # Extra game options, split on whitespace (so no value with a space in it).
    [string]$Extra = '',
    [hashtable]$Env = @{},
    [string]$RenderDocDir = '',
    [switch]$Play
)
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$port = Join-Path $root 'port'
if (!$RenderDocDir) {
    $RenderDocDir = Get-ChildItem (Join-Path $root '..\graw360-recomp\private\tools\renderdoc'), (Join-Path $root 'private\tools\renderdoc') -Recurse -Filter renderdoccmd.exe -ErrorAction SilentlyContinue |
        Where-Object { $_.DirectoryName -notmatch '\\x86$' } | Select-Object -First 1 -ExpandProperty DirectoryName
}
if (!$RenderDocDir -or !(Test-Path "$RenderDocDir\renderdoccmd.exe")) { throw 'RenderDoc not found: pass -RenderDocDir.' }
if (Get-Process -Name lotrc -ErrorAction SilentlyContinue) { throw 'lotrc is running: quit it first.' }
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$out = Join-Path $root "private\rdoc\$stamp"
New-Item -ItemType Directory -Force $out | Out-Null
$exe = Join-Path $port 'out\build\win-amd64-relwithdebinfo\lotrc.exe'
$log = Join-Path $port "logs\rdoc-$stamp.log"
$gameArgs = @('--no-fullscreen', '--resolution', '720p', '--game_data_root', "$port\assets",
    '--log_file', $log, '--log_level', 'debug', '--log_flush_interval', '1')
if ($Play) {
    $gameArgs += @('--user_data_root', "$port\user", '--cache_root', "$port\cache")
    $env:REX_LOTRC_RDOC_CAPTURE_AT = ''
} else {
    Remove-Item -Recurse -Force (Join-Path $port 'user-smoke') -ErrorAction SilentlyContinue
    $gameArgs += @('--user_data_root', "$port\user-smoke", '--cache_root', "$port\cache-smoke",
        '--lotrc_autopilot', (Resolve-Path (Join-Path $root $Autopilot)).Path)
    $env:REX_LOTRC_RDOC_CAPTURE_AT = $Times
}
$gameArgs += @($Extra -split '\s+' | Where-Object { $_ })
# Vulkan is captured through RenderDoc's layer, which a portable (unzipped) RenderDoc hasn't
# registered: enable it for this process tree only, without touching the system's layer settings.
# As an implicit layer (how RenderDoc registers it; renderdoccmd then enables it through
# ENABLE_VULKAN_RENDERDOC_CAPTURE): loading it explicitly through VK_INSTANCE_LAYERS made
# vkCreateInstance fail with ErrorExtensionNotPresent.
$env:VK_ADD_IMPLICIT_LAYER_PATH = $RenderDocDir
foreach ($k in $Env.Keys) { Set-Item "env:REX_$($k.ToUpperInvariant())" $Env[$k] }
$rdocArgs = @('capture', '-d', $port, '-c', (Join-Path $out 'lotrc'), $exe) + $gameArgs
# Start-Process joins -ArgumentList with spaces and quotes nothing: quote every argument that holds
# a space (a checkout under C:\Users\Jane Doe\...), so each path stays one argument. -Extra is
# split on whitespace, so its own values can't hold spaces.
$quoted = $rdocArgs | ForEach-Object { if ("$_" -match '\s') { '"' + "$_" + '"' } else { "$_" } }
Start-Process -FilePath "$RenderDocDir\renderdoccmd.exe" -WorkingDirectory $port -ArgumentList $quoted -WindowStyle Hidden
$start = Get-Date
# renderdoccmd returns once the game is launched and injected: wait on the game itself.
$game = $null
while (!$game -and ((Get-Date) - $start).TotalSeconds -lt 30) {
    $game = Get-Process -Name lotrc -ErrorAction SilentlyContinue | Where-Object { $_.StartTime -ge $start.AddSeconds(-5) } | Select-Object -First 1
    Start-Sleep -Milliseconds 500
}
if (!$game) { throw 'lotrc did not start under RenderDoc.' }
if ($Play) {
    "pid $($game.Id), log $log; F9 in the game captures into $out"
    return
}
while (((Get-Date) - $start).TotalSeconds -lt $Seconds -and !$game.HasExited) { Start-Sleep -Seconds 2 }
Get-Process -Name lotrc -ErrorAction SilentlyContinue | Where-Object { $_.StartTime -ge $start.AddSeconds(-5) } | Stop-Process -Force
Start-Sleep -Seconds 2
"log $log"
Select-String -Path $log -Pattern 'RenderDoc capture|RenderDoc isn' | ForEach-Object { $_.Line }
Get-ChildItem $out -Filter *.rdc | ForEach-Object { "capture $($_.FullName) $([Math]::Round($_.Length / 1MB)) MB" }
