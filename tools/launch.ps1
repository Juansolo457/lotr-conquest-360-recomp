# Launch the LOTRC recomp for playing (Vulkan). The guest is told it is on a 1280x720 display (as
# a 360 on an HD TV; this also avoids ReXGlue's 4:3 squeeze at 200% Windows scaling) and renders
# at a multiple of that. This opens a window on the user's screen. Never kill a running lotrc.exe.
#   pwsh -NoProfile -File tools/launch.ps1 -Windowed            # 720p internal (the 360's), windowed
#   pwsh -NoProfile -File tools/launch.ps1                      # fullscreen
#   pwsh -NoProfile -File tools/launch.ps1 -Windowed -Scale 3   # 4K internal
#   pwsh -NoProfile -File tools/launch.ps1 -Windowed -Trace     # every kernel call in the log
[CmdletBinding()]
param(
    # Internal resolution: 1 = 720p (the default until the optimisation pass, the user's call
    # 2026-10-27), 2 = 1440p, 3 = 4K.
    [ValidateRange(1,3)][int]$Scale = 1,
    [ValidateSet(-1,0,1,2,3,4,5)][int]$Anisotropic = 5,  # SDK enum: 5 = 16x, -1 = the game's own
    [switch]$Windowed,
    [switch]$Trace,
    # The refresh rate the guest's display reports (0 = the SDK's 60 Hz).
    [ValidateRange(0,240)][double]$RefreshRate = 0,
    [string]$Extra = '',
    [ValidateSet('Release','RelWithDebInfo')][string]$Configuration = 'RelWithDebInfo'
)
$ErrorActionPreference = 'Stop'
$port = Join-Path $PSScriptRoot '..\port' | Resolve-Path
$running = Get-Process -Name lotrc -ErrorAction SilentlyContinue
if ($running) { throw "LOTRC is already running (pid $($running.Id -join ', ')). Quit it first." }
$executable = Join-Path $port "out\build\win-amd64-$($Configuration.ToLowerInvariant())\lotrc.exe"
if (!(Test-Path $executable)) { throw "Not built: tools/build.ps1" }
New-Item -ItemType Directory -Force (Join-Path $port 'logs') | Out-Null
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$log = Join-Path $port "logs\run-$stamp.log"
$fullscreen = if ($Windowed) { '--no-fullscreen' } else { '--fullscreen' }
# Options that live in the renderer plugin (resolution_scale, anisotropic_override,
# render_target_path_vulkan, ...) must be written --name=value: the plugin is loaded after the
# command line is parsed, and only that form is kept for options registered later.
$arguments = @($fullscreen,
    '--resolution', '720p', "--resolution_scale=$Scale", "--anisotropic_override=$Anisotropic",
    '--game_data_root', "$port\assets", '--user_data_root', "$port\user",
    '--cache_root', "$port\cache", '--log_file', $log, '--log_flush_interval', '1') +
    $(if ($RefreshRate -gt 0) { @('--video_mode_refresh_rate', "$RefreshRate") } else { @() }) +
    $(if ($Trace) { @('--log_level', 'trace', '--log_noisy') } else { @('--log_level', 'debug') }) +
    @($Extra -split '\s+' | Where-Object { $_ })
$process = Start-Process -FilePath $executable -WorkingDirectory $port -ArgumentList $arguments -PassThru
"pid $($process.Id), log $log"
