# Handoff: The Lord of the Rings: Conquest 360 (2026-10-29)

Read [PLAN.md](PLAN.md) for the goals, decisions and milestones, and [FINDINGS.md](FINDINGS.md)
for the disc and executable facts. This file is the state, the build/run detail and where
things live. Update it at the end of every session; the next model starts here, not from chat
history.

## Where it stands
**M1 done: the game boots on the Xenos plugin's Vulkan backend, plays its Bink logos, draws the
title screen and the main menu, and an autopilot Start press gets there (2026-10-29).** Next: M2,
a level.

### Run 3 (2026-10-29, `tools/autopilot/menu.txt`; log `port/logs/smoke-20261029-002656.log`)
Captures in `private/captures/lotrc-menu1-20261029-002656/`, one every 5 s.
- Start at 30-40 s skipped the logos; `XamShowDeviceSelectorUI` at +40 s (the storage prompt,
  answered by the pad through `ui_pad.cpp`); the shell's "Saving... This game saves data
  automatically" notice over the main menu at +45 s; the **main menu** (Multiplayer,
  Singleplayer, Options, Marketplace, "B Back / A Select") clean at +70 s, with the attract
  backdrop (a Bink loop) behind it.
- The script's A presses took Multiplayer, which shows "You must be signed into an Xbox LIVE
  enabled gamer profile" (expected: no Live) and loops on A. Next run: Down, then A into
  Singleplayer.
- No crash, no new kernel errors.

### Run 2 (2026-10-29, no input, 90 s; log `smoke-20261029-002439.log`)
Captures in `private/captures/lotrc-boot2-20261029-002439/`.
- Bink logos (the Pandemic ink animation at +6-11 s, the EA and New Line logos after), then
  the **title screen** ("Press START button", (c) 2009 Electronic Arts) from ~+50 s, with its
  animated battle backdrop. Everything drawn correctly on the fbo render-target path; no band
  or tint (DOAX2's #menu-red didn't show), so FSI isn't needed so far.
- **30 presents a second** the whole run, from +1 s: the game paces itself at 30 Hz.
- Kernel noise, none fatal: `cache:\` has no device (StfsCreateDevice stub);
  `game:udio\English(US)\` opened 8 times and missing on the disc (the English audio lives in
  `audio/sound.pck`; a localisation probe); `ObReferenceObject`, `IoDismountVolume`,
  `NetDll_XNetUnregisterKey` stubs; two "allocation to devkit memory area" warnings.
- Not seen: fibers (no `rexcrt` hooks needed so far), FP exceptions on the audio worker (the
  FPSCR guard is still unhooked), `XamShowSigninUI`.

### Run 1 (2026-10-29, first boot; log `smoke-20261029-002216.log`)
Vulkan on the RTX 4090, presents from +1.9 s, audio driver registered at +3 s, then "Call to
invalid or unregistered function at 0x82469EE8": a 5-instruction vtable method
(`mr r10,r3; lwz r11,4(r10); addi r3,r11,1; stw; blr`) with no `.pdata` entry, referenced from a
method table at 0x82026F1C. It was in the missed-function finder's list: manifest round 3.

### Build and codegen rounds (2026-10-29)
Six builds (`private/build-1..6.log`), each a few minutes (codegen ~15 s, 145 objects):
1. codegen refused three `b` targets outside any function: three leaf thunks (round 1);
2. built the translation but four "use of undeclared label loc_8256A1xx" compile errors, and
   two "Unresolved conditional branch to 0x824BA828" warnings;
3. explicit `.pdata` sizes for the three functions around the labels changed nothing (the
   output was byte-identical), which pointed away from function bounds;
4. `tools/check_switch_tables.py` found the cause: two **byte-indexed jump tables**
   (`lbzx` from a byte table, target = base + 4*byte) that the analyser sized at 512 and 147
   cases where the image's tables hold 11 and 47 bytes before the next table; the phantom
   cases pointed into the following functions and pulled their blocks in. Two
   `[[entrypoint.switch_tables]]` overrides (round 2), plus `0x824BA800 = { size = 0x54 }` for
   a leaf the analyser cut at its first `blr`. `lotrc.exe` linked (48 MB);
5. round 3, the finder's 122 candidates: 88 "Unresolved conditional branch" warnings, all
   inside two `.pdata` functions that two candidates split;
6. those two dropped (eight other candidates also sit inside `.pdata` functions but warn
   nothing, kept as Quake 4 kept its landing pads): clean.
Checks after the final codegen: 282 switches, 0 wrong; no vpkd3d128 hazards in 73,671 vector
instructions; `find_vcall_thunks.py` 0 forwarders; the finder's remaining candidates are the
two dropped ones.

The SDK DLLs beside the program are the Vulkan-only install's (hashes checked).

## Next steps
1. **Into a level (M2):** `tools/autopilot/menu.txt` with Down before A, then through
   Singleplayer (campaign / Training) and the loading screen; `-Seconds 300 -CaptureEvery 5`.
   Expect the first real 3D rendering problems here, and maybe fibers or FP exceptions once
   Havok and the level threads start.
2. **Reference captures** of the menu and the first level for later renderer comparisons.
3. **Measure**: the game paces at 30 Hz; find the vblank wait before deciding how 60 would work.
4. **CodeRabbit:** confirm it reviews pull request #1; if it doesn't, the repository has to be
   added to the CodeRabbit GitHub App's repository list (the user's GitHub settings).

## How it is built and run
```
pwsh -NoProfile -File tools/setup.ps1                     # once: toolchain + Vulkan-only SDK (~1 h)
pwsh -NoProfile -File tools/extract.ps1 -Iso 'E:\360-recomps\Lord of the Rings, The - Conquest (USA, Asia) (En,Fr,Es).iso'
pwsh -NoProfile -File tools/build.ps1 [-Jobs 12]          # codegen when needed, then compile
pwsh -NoProfile -File tools/smoke.ps1 -Seconds 60         # boot check; its window shows on the user's screen
pwsh -NoProfile -File tools/launch.ps1 -Windowed          # a window on the user's screen: ask first
```
- **On this PC** `.tools/` is a junction to `../n3-360-recomp/reference/N3-Recomp/.tools` (LLVM
  20.1.8, CMake 3.31.8, Ninja 1.13.1) and `third_party/rexglue-sdk-bd833a2` is a junction to
  `../quake4-360-recomp/third_party/rexglue-sdk-bd833a2`: the same SDK commit, the same patch
  set (expected tree `54ab593`), already built Vulkan-only. `tools/setup.ps1` accepts that
  checkout (it checks the tree and the install stamp `lotrc-sdk-tree`, copied from Quake 4's).
  Anyone else runs `setup.ps1` and gets their own copy.
- `build.ps1` enters a VS 2022 DevShell, checks the XEX hash, runs `lotrc_codegen`, reconfigures
  once on the first run, then builds `port/out/build/win-amd64-relwithdebinfo/lotrc.exe`.

## Analysis tools (all read-only on the game's files)
| | |
|---|---|
| `tools/xdvdfs.py <iso> list \| extract <dir> [names]` | XDVDFS reader; `tools/extract.ps1` wraps it |
| `tools/xexinfo.py <xex>` | XEX2 headers: title, build time, entry, image size, encryption, XDK libraries |
| `..\quake4-definitive\build\xexdump\xexdump.exe <xex> private\xex\default` | the decrypted image (`default.bin`), sections and the import names |
| `tools/xex_basic_decrypt.py <xex> <out.bin>` | the same without xexdump, given the retail key (`LOTRC_XEX_KEY`) |
| `tools/check_switch_tables.py <image.bin> port/generated/default [--toml out.toml]` | replays every generated `switch` against the image; rerun after every codegen |
| `tools/find_missed_functions.py <image.bin> port/generated/default` | function entries the analyser missed, as manifest lines |
| `tools/check_vector_aliasing.py port/generated/default` | the vpkd3d128 hazard; `build.ps1` runs it |
| `tools/find_vcall_thunks.py <image.bin> port/generated/default <pdata_funcs.txt>` | virtual-call forwarders with no function-table entry or static reference |
| `tools/scan_d3d.py port/generated/default` | functions that build PM4 packets (only if a native renderer is attempted) |
| `tools/rdoc_*.py`, `tools/rdoc_capture.ps1` | RenderDoc capture and inspection scripts (from the sister projects) |

## Where things live
| | |
|---|---|
| `port/lotrc_manifest.toml` | project and entrypoint config; function hints in rounds, each with a comment saying where it came from |
| `port/src/lotrc_app.h`, `main.cpp` | host app: Vulkan-only plugin load, crash reporter, shared controllers, autopilot driver |
| `port/src/crash_report.*` | `logs/crash-<time>.txt` with the guest stack (`sub_<address>` with the generated file and line) and a minidump |
| `port/src/frame_timing.cpp`, `timer_resolution.cpp` | frame log, 0.5 ms timer resolution |
| `port/src/fpscr_guard.cpp` | `LotrcGuardFpscr`, ready to hook if the audio worker raises FP exceptions |
| `port/src/autopilot.*` | scripted virtual controller (`--lotrc_autopilot <script>`); scripts go in `tools/autopilot/` |
| `port/assets/` | the extracted disc (ignored) |
| `private/xex/` | `default.bin`, sections, symbols (ignored) |
| `tools/patches/` | the SDK patches (BSD-3-Clause, see NOTICE); `setup.ps1` lists their order |

## Known traps (from the sister projects)
- **GitHub drops long clones on this connection** (Quake 4's setup: FFmpeg 26 minutes, SDL
  reset). Point uninitialised submodules at `../graw360-recomp/third_party/rexglue-sdk-bd833a2/<path>`
  and run `git -c protocol.file.allow=always submodule update --init --recursive`.
- **Plugin options need `--name=value`** (`--resolution_scale=3`): the plugin is loaded after
  the command line is parsed and only that form is replayed.
- **Fibers:** translated code can't switch stacks; DOAX2's `[entrypoint.rexcrt]` binds the
  game's `ConvertThreadToFiber`/`CreateFiber`/`SwitchToFiber`/... to the SDK's host fibers.
  Symptom: a fault right after a fiber switch with another fiber's registers.
- **FP exceptions on the audio worker** (`C000008F`, MXCSR `0x8060`): `fpscr_guard.cpp`.
- **"Call to invalid or unregistered function"** at a leaf with no `.pdata` entry: a manifest
  line; a virtual-call forwarder means `find_vcall_thunks.py`.
- A hook that reads guest memory must check the page is committed.
- A Logitech or Steam virtual XInput device can take controller slot 0;
  `lotrc_shared_controllers` (on by default) makes every pad drive player 1.
- `--resolution 720p` tells the guest it is on a 720p display; the launch and smoke scripts
  pass it. `tools/smoke.ps1` passes `--headless`, but the window still appears.
- Long heredocs with backslashes get mangled by the Bash tool on this PC: write scripts to a
  file first. Windows paths for Python arguments.
- The SDK's RenderDoc auto-load and `/dev/shm` leak bit F.E.A.R. and GRAW on Linux: their fixes
  (GRAW's `linux-*` patches) join `tools/patches` with the Linux build (M4).
