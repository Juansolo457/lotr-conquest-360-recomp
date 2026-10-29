# Handoff: The Lord of the Rings: Conquest 360 (2026-10-29)

Read [PLAN.md](PLAN.md) for the goals, decisions and milestones, and [FINDINGS.md](FINDINGS.md)
for the disc and executable facts. This file is the state, the build/run detail and where
things live. Update it at the end of every session; the next model starts here, not from chat
history.

## Where it stands
**M0 in progress: the repository is bootstrapped; codegen and the first build await the user's
OK.** (2026-10-29)

Done 2026-10-29, before any build:
- The repository from `../quake4-360-recomp` (tracked files only), every Quake 4 name renamed
  (`lotrc`, `LotrConquestApp`, `lotrc_*` options, `Lotrc*` hooks, `LOTRC_XEX_KEY`). A fresh
  `port/lotrc_manifest.toml` with no function hints yet. `port/src` is Quake 4's host code
  unchanged in behaviour: Vulkan-only plugin load, crash reporter, frame timing, shared
  controllers, autopilot, the FPSCR guard (not hooked until a boot needs it).
- `default.xex` and `sku.bin` extracted into `port/assets` (hash checked, FINDINGS.md); the
  full disc extraction is still to run (`tools/extract.ps1`, 5.4 GB).
- The decrypted image in `private/xex/` (`xexdump`), and recon from it (FINDINGS.md): all 255
  imports implemented in the SDK; engine and middleware identified.
- `tools/audit_repo.py` extended with this game's formats (`.pak`, `.pck`, `.gfx`, `.dds`,
  `.dat`); its tests pass.

## Next steps
1. **Codegen and the first build (needs the user's OK):** `tools/build.ps1`. Expect codegen
   warnings naming `b` targets outside any function (manifest round 1, as Quake 4's), then run
   the three checks (`check_switch_tables.py`, `check_vector_aliasing.py`,
   `find_missed_functions.py`) and add round 2 wholesale, dropping candidates that split
   functions.
2. **First boot (M1):** `tools/smoke.ps1 -Seconds 60 -CaptureEvery 5`. Expect, from the sister
   projects: XAPI fibers (DOAX2's `[entrypoint.rexcrt]` block), FP exceptions on the audio
   worker (hook `LotrcGuardFpscr`), network probes failing harmlessly, `XamShowSigninUI` and the
   device selector answered by `--headless`, Bink logos (EA, New Line, Pandemic, Tolkien), then
   `Levels/shell.BIN` (the front end). If the frame has a wrong band or tint, try
   `--render_target_path_vulkan=fsi` (DOAX2's red band was the fbo path's EDRAM handling).
3. **Autopilot through the menus** (`tools/autopilot/`), captures of the main menu, then a level.

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
