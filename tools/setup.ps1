# Set up everything tools/build.ps1 needs that isn't in the repository (docs/SETUP.md):
#   1. the toolchain in .tools/: LLVM 20.1.8, CMake 3.31.8 and Ninja 1.13.1, each downloaded from
#      its official release and checked against its SHA-256;
#   2. third_party/rexglue-sdk-bd833a2: ReXGlue's source at the nightly 0.10.0.24-dev.gbd833a2's
#      commit with this project's patches (tools/patches), checked against the expected tree;
#   3. that SDK built and installed into its out/install/win-amd64 with Vulkan as the ONLY
#      graphics backend (REXGLUE_USE_D3D12=OFF): the runtime, the Xenos renderer plugin, the
#      Vulkan loader and the patched code generator. The game links that install, not ReXGlue's
#      prebuilt package (which is D3D12-only on Windows).
#   pwsh -NoProfile -File tools/setup.ps1            # all of it (skips what is there already)
#   pwsh -NoProfile -File tools/setup.ps1 -Force     # replace the SDK source checkout and rebuild
[CmdletBinding()]
param(
    [switch]$Force,
    [ValidateRange(1,64)][int]$Jobs = [Math]::Max(1, [Environment]::ProcessorCount - 4)
)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'   # Invoke-WebRequest is many times slower with it
$root = Split-Path $PSScriptRoot -Parent
$tools = Join-Path $root '.tools'
$downloads = Join-Path $tools 'downloads'
$sdk = Join-Path $root 'third_party\rexglue-sdk-bd833a2'
$sdkCommit = 'bd833a2ab69d305f99ddf57418fc38ffec8af93d'
# In order: GRAW's patch set (graw360-recomp tools/setup.ps1), the one its native renderer is
# built and tested against. The native renderer (native/, from GRAW) compiles the SDK's shader
# translators from this tree and checks for these patches when it is configured.
#   vpkd3d128-alias            code generator: float16 packs lost the sign when vD == vB
#   freed-page-resolve         renderer plugin: a resolve into freed memory left stale textures
#   vblank-pacing              runtime: vblanks at their own deadlines (even frame pacing)
#   gpu-skip-draws             renderer plugin: --gpu_skip_draws, the plugin keeps the command
#                              ring and the presenter but draws nothing (the native renderer does)
#   pgr4-native/0021, 0022     DXBC translator: pgr4-native's shader modifications (sample_b for
#                              computed LODs; textures known unsigned). Shared modification types
#   implicit-gradients-switch  DXBC translator: a switch for 0021
#   spirv-exp-adjust           SPIR-V translator: texture exponent bias read from the right word
#   spirv-implicit-gradients   SPIR-V translator: 0021's switch for the Vulkan backend
$sdkPatches = @('rexglue-bd833a2-vpkd3d128-alias', 'rexglue-bd833a2-freed-page-resolve',
                'rexglue-bd833a2-vblank-pacing', 'rexglue-bd833a2-gpu-skip-draws',
                'pgr4-native/0021-gpu-sample-computed-LOD-pixel-shader-fetches-with-sa',
                'pgr4-native/0022-gpu-add-a-pixel-shader-modification-for-textures-kno',
                'rexglue-bd833a2-implicit-gradients-switch', 'rexglue-bd833a2-spirv-exp-adjust',
                'rexglue-bd833a2-spirv-implicit-gradients')
$expectedTree = '54ab5932e76ba1b8c9e454891c9ba52c16bfdda0'   # after the last patch (same as GRAW's)
$install = Join-Path $sdk 'out\install\win-amd64'
$stamp = Join-Path $install 'lotrc-sdk-tree'

function Invoke-Git {
    & git.exe @args
    if ($LASTEXITCODE) { throw "git $($args -join ' ') failed ($LASTEXITCODE)." }
}

foreach ($cmd in 'git', 'python') {
    if (!(Get-Command $cmd -ErrorAction SilentlyContinue)) { throw "$cmd is not installed or not on PATH (docs/SETUP.md)." }
}
$vswhere = "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe"
$vs = if (Test-Path $vswhere) {
    & $vswhere -latest -version '[17.0,18.0)' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
}
if (!$vs) { throw "Visual Studio 2022 with the 'Desktop development with C++' workload is not installed (docs/SETUP.md)." }

# 1. Toolchain.
$toolchain = @(
    @{ Name = 'LLVM 20.1.8'; Check = 'llvm/bin/clang++.exe'
       Url = 'https://github.com/llvm/llvm-project/releases/download/llvmorg-20.1.8/LLVM-20.1.8-win64.exe'
       Sha = '3197846a2b19063687dd56e93e34cd941e3548d907f23a6131571321bdf9fe7b'; Into = 'llvm' },
    @{ Name = 'CMake 3.31.8'; Check = 'cmake/cmake-3.31.8-windows-x86_64/bin/cmake.exe'
       Url = 'https://github.com/Kitware/CMake/releases/download/v3.31.8/cmake-3.31.8-windows-x86_64.zip'
       Sha = '81aa9964dbabd71fe02e7ec50472fd3ad56138c49944515ece9001efbff8d719'; Into = 'cmake' },
    @{ Name = 'Ninja 1.13.1'; Check = 'ninja/ninja.exe'
       Url = 'https://github.com/ninja-build/ninja/releases/download/v1.13.1/ninja-win.zip'
       Sha = '26a40fa8595694dec2fad4911e62d29e10525d2133c9a4230b66397774ae25bf'; Into = 'ninja' }
)
foreach ($t in $toolchain) {
    if (Test-Path (Join-Path $tools $t.Check)) { Write-Host "$($t.Name): installed"; continue }
    New-Item -ItemType Directory -Force $downloads | Out-Null
    $file = Join-Path $downloads (Split-Path $t.Url -Leaf)
    if (!(Test-Path $file) -or (Get-FileHash $file -Algorithm SHA256).Hash.ToLowerInvariant() -ne $t.Sha) {
        Write-Host "$($t.Name): downloading $($t.Url)"
        Invoke-WebRequest -Uri $t.Url -OutFile $file
    }
    if ((Get-FileHash $file -Algorithm SHA256).Hash.ToLowerInvariant() -ne $t.Sha) {
        Remove-Item $file
        throw "$($t.Name): the download's SHA-256 doesn't match; try again."
    }
    $dest = Join-Path $tools $t.Into
    Write-Host "$($t.Name): unpacking into $dest"
    if ($file.EndsWith('.exe')) {
        $p = Start-Process -FilePath $file -ArgumentList '/S', "/D=$dest" -Wait -PassThru
        if ($p.ExitCode) { throw "$($t.Name): the installer failed ($($p.ExitCode))." }
    } else {
        Expand-Archive -Path $file -DestinationPath $dest -Force
    }
    if (!(Test-Path (Join-Path $tools $t.Check))) { throw "$($t.Name): $($t.Check) is missing after unpacking." }
}

# 2. The SDK source with this project's patches.
if ((Test-Path $sdk) -and $Force) { Remove-Item -Recurse -Force $sdk }
if (Test-Path $sdk) {
    $head = & git -C $sdk rev-parse --verify --quiet 'HEAD^{tree}' 2>$null
    $changes = & git -C $sdk status --porcelain --ignore-submodules=all 2>$null
    if ($head -ne $expectedTree -or $changes) {
        throw "SDK source: $sdk is incomplete, on another commit or changed by hand. Run tools/setup.ps1 -Force to replace it."
    }
    Write-Host "SDK source: $sdk exists already (-Force replaces it)"
} else {
    Write-Host 'SDK source: cloning ReXGlue'
    New-Item -ItemType Directory -Force (Split-Path $sdk) | Out-Null
    Invoke-Git -c core.longpaths=true clone --no-checkout https://github.com/rexglue/rexglue-sdk.git $sdk
    Invoke-Git -C $sdk config core.longpaths true
    Invoke-Git -C $sdk checkout --quiet --detach $sdkCommit
    Write-Host "SDK source: applying $($sdkPatches.Count) patches"
    foreach ($name in $sdkPatches) {
        $text = [IO.File]::ReadAllText((Join-Path $PSScriptRoot "patches/$name.patch")) -replace "`r`n", "`n"
        $tmp = New-TemporaryFile
        [IO.File]::WriteAllText($tmp, $text)
        try { Invoke-Git -C $sdk apply $tmp.FullName } finally { Remove-Item $tmp }
    }
    Invoke-Git -C $sdk add -A
    $tree = & git -C $sdk write-tree
    if ($tree -ne $expectedTree) {
        throw "The patched SDK tree is $tree, not ${expectedTree}: tools/patches changed without tools/setup.ps1."
    }
    Invoke-Git -C $sdk -c user.name=lotr-conquest-360-recomp -c user.email=setup@localhost commit --quiet -m 'lotr-conquest-360-recomp patches'
    Invoke-Git -C $sdk switch --quiet -c lotrc
}
Write-Host 'SDK source: fetching its submodules'
Invoke-Git -C $sdk submodule update --init --recursive

# Without Windows symlink support git checks out a symbolic link as a small file holding the
# target's path (libmspack's cabextract sources): replace each file link with a copy of its target.
$repos = @('.') + @(& git -C $sdk submodule foreach --quiet --recursive 'echo $displaypath')
foreach ($repo in $repos) {
    $dir = Join-Path $sdk $repo
    foreach ($entry in (& git -C $dir ls-files -s | Where-Object { $_ -like '120000 *' })) {
        $file = Join-Path $dir ($entry -split "`t", 2)[1]
        $item = Get-Item -LiteralPath $file -ErrorAction SilentlyContinue
        if (!$item -or $item.LinkType -or $item.PSIsContainer -or $item.Length -gt 1024) { continue }
        $target = Join-Path (Split-Path $file) (Get-Content -LiteralPath $file -Raw).Trim()
        if (Test-Path -LiteralPath $target -PathType Leaf) { Copy-Item -LiteralPath $target $file -Force }
    }
}

# 3. Build and install the SDK, Vulkan only. RelWithDebInfo for the game's libraries ("rd"
# postfix), Release for the code generator (bin/rexglue.exe).
if ((Test-Path (Join-Path $install 'bin\rexglue.exe')) -and (Test-Path (Join-Path $install 'bin\rexruntimerd.dll')) -and
    !$Force -and ((Get-Content $stamp -ErrorAction SilentlyContinue) -eq $expectedTree)) {
    Write-Host "SDK: built ($install)"
} else {
    Import-Module (Join-Path $vs 'Common7\Tools\Microsoft.VisualStudio.DevShell.dll')
    Enter-VsDevShell -VsInstallPath $vs -SkipAutomaticLocation -DevCmdArguments '-arch=x64 -host_arch=x64' | Out-Null
    $env:PATH = "$tools\llvm\bin;$tools\ninja;$env:PATH"
    $cmake = "$tools\cmake\cmake-3.31.8-windows-x86_64\bin\cmake.exe"
    $build = Join-Path $sdk 'out\build\win-amd64'
    Push-Location $sdk
    try {
        & $cmake --preset win-amd64 -DREXGLUE_BUILD_TESTS=OFF -DREXGLUE_USE_D3D12=OFF -DREXGLUE_USE_VULKAN=ON
        if ($LASTEXITCODE) { throw 'SDK configure failed.' }
        foreach ($config in 'RelWithDebInfo', 'Release') {
            Write-Host "SDK: building $config ($Jobs jobs)"
            & $cmake --build $build --config $config --parallel $Jobs
            if ($LASTEXITCODE) { throw "SDK build ($config) failed." }
            & $cmake --install $build --config $config --prefix $install
            if ($LASTEXITCODE) { throw "SDK install ($config) failed." }
        }
    } finally { Pop-Location }
    if (!(Test-Path (Join-Path $install 'bin\rexglue.exe'))) { throw "SDK build: $install\bin\rexglue.exe is missing." }
    Set-Content -Path $stamp -Value $expectedTree
}
Write-Host 'Setup done. Next: tools/extract.ps1 with your disc image, then tools/build.ps1 (docs/SETUP.md).'
