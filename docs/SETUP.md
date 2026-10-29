# Build from your own disc (Windows)

This project ships **source only**. No download contains the game. The game's code is
translated from your copy of the Xbox 360 disc on your own PC, and the game data comes from the
same disc. You need your own disc of **The Lord of the Rings: Conquest** for the Xbox 360, the
USA/Asia release (see step 3).

> Early days: the game builds toward its first boot; there is nothing to play yet. See
> [HANDOFF.md](HANDOFF.md) for where it stands.

The first setup takes about an hour, most of it compiling the ReXGlue SDK. After that, rebuilds
take a few minutes.

## 1. What you need

**Hardware**
- A 64-bit CPU with AVX2 and FMA: Intel Haswell (2013) or AMD Excavator (2015) and newer.
- A GPU with a current **Vulkan 1.2** driver (NVIDIA, AMD or Intel). Vulkan is the only
  renderer.
- About 20 GB of free disk space (toolchain, SDK source and build, the extracted disc).
- An Xbox controller, plugged in before you start.

**Software**
- Windows 10 or 11, 64-bit.
- [Visual Studio 2022](https://visualstudio.microsoft.com/downloads/) with the **Desktop
  development with C++** workload. The build uses its libraries; the compiler is LLVM.
- [Git for Windows](https://git-scm.com/download/win), [PowerShell 7](https://learn.microsoft.com/powershell/scripting/install/installing-powershell-on-windows)
  (`pwsh`) and [Python](https://www.python.org/downloads/) 3.10 or newer, on PATH.

## 2. Set up the toolchain and the SDK

```
pwsh -NoProfile -File tools/setup.ps1
```

It skips any step that is done already:
1. Downloads LLVM 20.1.8, CMake 3.31.8 and Ninja 1.13.1 into `.tools/`, each checked against
   its SHA-256.
2. Clones ReXGlue's source at nightly 0.10.0.24-dev.gbd833a2 into
   `third_party/rexglue-sdk-bd833a2` and applies `tools/patches` (code generator, renderer and
   shader translator changes from graw360-recomp and pgr4-native).
3. Builds the whole SDK with **Vulkan as the only graphics backend** and installs it into
   `third_party/rexglue-sdk-bd833a2/out/install/win-amd64`. The game links that, not ReXGlue's
   prebuilt package, which only has Direct3D 12 on Windows.

## 3. Extract your disc

```
pwsh -NoProfile -File tools/extract.ps1 -Iso "<your LOTR Conquest ISO>"
```

This unpacks the game partition into `port/assets` (about 5.4 GB). The build accepts only the
USA/Asia disc's `default.xex`: title `45410852`, version 0.0.0.1, SHA-256
`1e49a80be633b78e2d84b8b8b099fc401e5e0129d0fe606a6c54b64606085403`. That's the Redump dump
"Lord of the Rings, The - Conquest (USA, Asia) (En,Fr,Es)".

## 4. Build

```
pwsh -NoProfile -File tools/build.ps1
```

This translates the game's code into C++ and compiles it to
`port/out/build/win-amd64-relwithdebinfo/lotrc.exe`. That program contains code translated from
your disc: keep it to yourself.

## 5. Run

```
pwsh -NoProfile -File tools/launch.ps1 -Windowed
```

| Option | Effect |
|---|---|
| `-Scale 1..3` | internal resolution: 1 = 1280×720 (the console's, default), 2 = 2560×1440, 3 = 3840×2160 |
| `-Windowed` | a window instead of full screen |
| `-Trace` | every kernel call in the log |

Saves stay in `port/user`, logs in `port/logs`. A crash writes `crash-<time>.txt` next to the log.

## Linux and the Steam Deck

Not yet: the native Linux build comes after Windows ([PLAN.md](PLAN.md), M4).
