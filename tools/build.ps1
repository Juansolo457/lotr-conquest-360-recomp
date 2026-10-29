# Build port/ (the ReXGlue LOTRC project) inside a VS 2022 x64 developer environment, against the
# Vulkan-only SDK tools/setup.ps1 installed. Codegen (translating default.xex to C++) runs as part
# of the build whenever lotrc_manifest.toml or the executable changed; the first run takes a while.
#   pwsh -NoProfile -File tools/build.ps1 [-Configuration RelWithDebInfo] [-Jobs 12]
[CmdletBinding()]
param(
    [ValidateSet('Release','RelWithDebInfo')][string]$Configuration = 'RelWithDebInfo',
    [ValidateRange(1,64)][int]$Jobs = 12
)
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$port = Join-Path $root 'port'
$tools = Join-Path $root '.tools'
$cmake = "$tools/cmake/cmake-3.31.8-windows-x86_64/bin/cmake.exe"
$sdkInstall = Join-Path $root 'third_party/rexglue-sdk-bd833a2/out/install/win-amd64'
if (!(Test-Path $cmake)) { throw "Toolchain missing at ${tools}: run tools/setup.ps1 (docs/SETUP.md)." }
if (!(Test-Path "$sdkInstall/bin/rexglue.exe")) { throw "The Vulkan-only SDK isn't built: run tools/setup.ps1 (docs/SETUP.md)." }
$expected = '1e49a80be633b78e2d84b8b8b099fc401e5e0129d0fe606a6c54b64606085403'
$xex = Join-Path $port 'assets/default.xex'
if (!(Test-Path $xex)) { throw 'port/assets/default.xex is missing: run tools/extract.ps1 first.' }
if ((Get-FileHash $xex -Algorithm SHA256).Hash.ToLowerInvariant() -ne $expected) {
    throw 'port/assets/default.xex is not the supported LOTR: Conquest executable (Redump USA/Asia disc, title 45410852).'
}

# vcvars64.bat breaks on quoted PATH entries; the DevShell module does not.
$vs = & "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe" -latest -version '[17.0,18.0)' -property installationPath
Import-Module (Join-Path $vs 'Common7\Tools\Microsoft.VisualStudio.DevShell.dll')
Enter-VsDevShell -VsInstallPath $vs -SkipAutomaticLocation -DevCmdArguments '-arch=x64 -host_arch=x64' | Out-Null
$env:PATH = "$tools/llvm/bin;$tools/ninja;$env:PATH"

$preset = 'win-amd64-' + $Configuration.ToLowerInvariant()
$configure = @('--preset', $preset, "-DCMAKE_PREFIX_PATH=$($sdkInstall.Replace('\', '/'))",
    '-DCMAKE_C_FLAGS=-march=x86-64-v3', '-DCMAKE_CXX_FLAGS=-march=x86-64-v3')
Push-Location $port
try {
    & $cmake @configure
    if ($LASTEXITCODE) { throw 'CMake configure failed.' }
    # Codegen first (a no-op when nothing changed), then reconfigure once if the generated
    # sources did not exist yet (the recomp target only appears once they do), then build.
    $firstTime = !(Test-Path (Join-Path $port 'generated/default/sources.cmake'))
    & $cmake --build --preset $preset --parallel $Jobs --target lotrc_codegen
    if ($LASTEXITCODE) { throw 'Code generation failed.' }
    & python -I (Join-Path $PSScriptRoot 'check_vector_aliasing.py') (Join-Path $port 'generated/default') | Out-Null
    if ($LASTEXITCODE) { throw 'The generated code has the vpkd3d128 aliasing bug: is the SDK patched? (tools/setup.ps1)' }
    if ($firstTime) {
        & $cmake @configure
        if ($LASTEXITCODE) { throw 'CMake re-configure failed.' }
    }
    & $cmake --build --preset $preset --parallel $Jobs
    if ($LASTEXITCODE) { throw 'Build failed.' }
    Write-Host "Built port/out/build/$preset/lotrc.exe"
} finally { Pop-Location }
