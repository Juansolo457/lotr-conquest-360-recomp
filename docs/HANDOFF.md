# Handoff: The Lord of the Rings: Conquest 360 (2026-10-29)

Read [PLAN.md](PLAN.md) for the goals, decisions and milestones, and [FINDINGS.md](FINDINGS.md)
for the disc and executable facts. This file is the state, the build/run detail and where
things live. Update it at the end of every session; the next model starts here, not from chat
history.

## Where it stands
**M2 in progress (2026-10-29): the Training level plays through with correct rendering and
sound.** Two bugs fixed today: every 3D scene washed out to white (the game's exposure control
reads a resolve back on the CPU: `readback_resolve=fast` is now the host's default) and the
level's ambience blown out to a full-scale square wave for a minute (the code generator's 2^x
estimate wrapped below 2^-127: `tools/patches/rexglue-bd833a2-vexptefp-underflow.patch`).
Open: the screen-space distortion effects draw as streaked rectangles. M1 (boot, logos,
title, main menu) was done earlier the same day.

### Runs 7-11 (2026-10-29): Training plays; the blown-out audio and its fix
`tools/autopilot/training.txt` (run, look, attack, block, jump in a loop from +140 s) plays the
whole Training level for 7 minutes without a crash: combat, fire attacks, the pause tutorials,
the HUD and radar, the capture point, the archer switch (`private/captures/lotrc-training-*`,
contact sheets `training-sheet-*.png`). Rendering is right everywhere except the screen-space
distortion effects (below).

**The user heard the level's ambient bed blown out for the first minute or two of a level, then
gone.** `--lotrc_audio_dump <file>` (`src/audio_dump.*`, a tee on the SDL audio system; reports
with `tools/audio_report.py` and `tools/audio_6ch_report.py`) showed every sample of the
centre channel (and at times a side channel) at exactly +-2^31 (float(INT_MAX) / float(INT_MIN))
from the level's loading screen until ~50 s into play, a square wave whose sign carried the
ambience. The cause is the code generator's `vexptefp` (2^x estimate, Wwise's dB-to-gain
conversion, 22 uses in one module): it built the result's exponent as `(floor(x) + 127) << 23`,
which wraps for x < -127 (2^-130 came out as -8.5e37, 2^-1000 as +1.7e7) instead of flushing
to zero, so a voice fading from "silent" got an astronomical gain, the mixer's saturating
convert clamped it to +-INT_MAX and the frame went out unscaled. Fix: clamp x to [-127, 128]
before the exponent math, NaN kept (`tools/patches/rexglue-bd833a2-vexptefp-underflow.patch`,
a code generator patch, so a new `rexglue.exe` and a full regeneration). Verified: the
recording with the fix has no sample outside +-1.01 on any channel and the user heard the
level's audio correct. The other recomps (GRAW, DOAX2, F.E.A.R., Quake 4) share this SDK
tree through the junction: their `tools/setup.ps1` expect the old tree hash until they take
the same patch (a one-line change each; the fix can only help them).

### Runs 4-6 (2026-10-29): into Training; the white-out and its fix
`tools/autopilot/level.txt` (menu.txt's path, then A every 3 s so the Singleplayer sub-menus take
their first entry) reaches the campaign map at ~+95 s and the **Training level** at ~+135 s:
the world map, a loading screen, then a third-person view of a Gondor soldier on a walled
mountain path with the tutorial prompt "Move LS to run forward". No crash, no new kernel noise,
steady 30 presents/s in the level. Render targets the level creates: the scene in
`k_2_10_10_10_FLOAT` (7e3) 4xMSAA at EDRAM 0 with D24S8 at 720, bloom/luminance chains in
`k_16_16_16_16` (fixed) at 1672 and `k_16_16_16_16_FLOAT` at 0, shadow maps (`k_8_8_8_8`
560x4688, depth-only 880x2992 and 440x1496 4xMSAA).
- **Run 4** (`smoke-20261029-030557.log`, captures `lotrc-level-20261029-030557/`): the HUD
  and the prompt bar draw correctly but the whole 3D scene is blown out to near white, only the
  darkest texels showing (stone walls, the soldier's outline); a torch at the top left draws as a
  hard yellow/red/black blot.
- **Run 5** (`smoke-20261029-031157.log`, `--render_target_path_vulkan=fsi`, captures
  `lotrc-fsi-20261029-031157/`): byte-for-byte the same picture. So not the host render-target
  path's EDRAM handling (DOAX2's red band was); FSI stays off.
- **Run 6** (`smoke-20261029-031433.log`, `--readback_resolve=fast`, captures
  `lotrc-readback-20261029-031433/`): **correct.** Sky, rock, chain mail, the ground's specular,
  the torch flame, shadows, all as on the console. The lead came from Xenia: its users fix this
  game's "bright screen" with `d3d12_readback_resolve = true`. Reading: the game resolves a
  luminance measurement to a texture and reads it on the CPU for its exposure (auto-exposure
  key / average luminance); without the readback the guest memory never changes, the average
  stays at its initial tiny value and the exposure runs away. Cost: none measurable, 30
  presents/s in the level with and without (the SDK's `fast` mode copies each resolve one frame
  late; `full` would stall every frame). `LotrConquestApp::OnPreSetup` sets `readback_resolve`
  to `fast` unless the command line gave a value (`--readback_resolve=none` shows the bug
  again); the log says `LOTRC: resolve readback 'fast'`.
- **Open: the screen-space distortion effects** (the Block Breaker shockwave, sword-trail
  haze, the fire sweep's heat haze) draw as large rectangles showing a stretched, streaked
  copy of the scene (`lotrc-training-20261029-031853/lotrc-20261029-032258.png`, `-032438`,
  `-032228`): the streaks look like clamped texture coordinates (the top row of the scene copy
  repeated vertically). RenderDoc (`private/rdoc/20261029-033626/`, `tools/rdoc_capture.ps1`
  with the new `LotrcFrameMark` hook at the game's VdSwap call) shows the pass: after the
  bloom chain, draws into the 1280x2048 R16G16B16A16_FLOAT scene target read the resolved scene
  copy (a 1280x720 R16G16B16A16_FLOAT texture, correct contents) plus a 4096x1024 BC1 atlas or
  a 256x128 particle texture, events 5230/5262/5266 in `lotrc_capture_2.rdc`; the capture
  frames had no effect active, so the bad coordinates were not caught yet. Next: capture a
  frame with the fire sweep on screen (`-Times` around the script's Y press) and compare the
  refraction draw's interpolators/constants against the pixel shader (`out/ps_5230.txt`:
  the scene UV is `r3.xyzy * c0.zwxy`, then `+ distortion * c0`). Also still unexplained: the
  hard yellow/red/black torch blot of run 4 and the black ragged blob of run 6's first frame.

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
  `game:\audio\English(US)\` opened 8 times and missing on the disc (the English audio lives in
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
0. **The distortion effects** (above): a RenderDoc capture with the effect on screen, then
   the coordinate math. The torch blot and the black blob may be the same bug.
1. **Play through Training (M2):** `tools/autopilot/training.txt` (run, look, attack, block,
   jump in a loop from +140 s) with `-Seconds 430 -CaptureEvery 5`; look at every capture for
   rendering bugs (particles, water, shadows, the HUD's radar, post effects), then the first
   campaign level (Helm's Deep) the same way.
2. **Cheaper readback:** `fast` copies every resolve back each frame. If a level is ever
   CPU-bound on it, an SDK patch could limit the readback to small resolves (the luminance one
   is a few texels) with a size cap option.
3. **Reference captures** of the menu and the first level for later renderer comparisons.
4. **Measure**: the game paces at 30 Hz; find the vblank wait before deciding how 60 would work.
5. **CodeRabbit** is active (it reviewed pull request #1): keep its threads answered.

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
  `../quake4-360-recomp/third_party/rexglue-sdk-bd833a2`: the same SDK commit with GRAW's
  patch set plus this project's `vexptefp-underflow` (expected tree `12884d9`, committed in
  that checkout on 2026-10-29 as "lotr-conquest-360-recomp patch: vexptefp underflow"), built
  Vulkan-only. `tools/setup.ps1` accepts that checkout (it checks the tree and the install
  stamp `lotrc-sdk-tree`). Quake 4's `setup.ps1` still expects tree `54ab593`: it needs the
  same patch line and hash before it is run again there. Anyone else runs `setup.ps1` and
  gets their own copy.
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
| `tools/rdoc_capture.ps1 -Times 212,215` | a scripted run under RenderDoc: a capture of two game frames at each time (`LotrcFrameMark` hook); the times go through `REX_LOTRC_RDOC_CAPTURE_AT` |
| `tools/rdoc_*.py` | run with `qrenderdoc --python` (RenderDoc 1.46 in `../graw360-recomp/private/tools/renderdoc/`), settings in `RDOC_*` variables (each file's header); `rdoc_tex_stats.py` for HDR targets (min/max/percentiles, auto white point; the PNGs carry alpha 0, flatten them before viewing) |
| `--lotrc_audio_dump <file>` + `tools/audio_report.py`, `tools/audio_6ch_report.py` | the audio output as raw float PCM (stereo fold and the raw 6-channel frames) with per-second levels, clipping, submit-rate gaps |

## Where things live
| | |
|---|---|
| `port/lotrc_manifest.toml` | project and entrypoint config; function hints in rounds, each with a comment saying where it came from |
| `port/src/lotrc_app.h`, `main.cpp` | host app: Vulkan-only plugin load, crash reporter, shared controllers, autopilot driver |
| `port/src/crash_report.*` | `logs/crash-<time>.txt` with the guest stack (`sub_<address>` with the generated file and line) and a minidump |
| `port/src/frame_timing.cpp`, `timer_resolution.cpp` | frame log, 0.5 ms timer resolution |
| `port/src/fpscr_guard.cpp` | `LotrcGuardFpscr`, ready to hook if the audio worker raises FP exceptions |
| `port/src/autopilot.*` | scripted virtual controller (`--lotrc_autopilot <script>`); scripts in `tools/autopilot/`: `menu.txt` (main menu), `level.txt` (into Training), `training.txt` (plays it) |
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
- **`third_party/rexglue-sdk-bd833a2` is a junction**: a relative `..\..` from inside it lands
  in `../quake4-360-recomp`, not here (a patch file written that way ended up in Quake 4's
  `tools/patches`). Use absolute paths for anything that crosses it.
- SDL's "disk" audio driver isn't in the SDK's SDL build (`SDL_AUDIO_DRIVER=disk` makes
  `SDL_InitSubSystem` fail and the runtime then crashes on a null driver): record with
  `--lotrc_audio_dump` instead.
- Under RenderDoc the game slows and later `-Times` may never fire (two of five did); the
  exposure also swings dark while the readback stalls, which is not a rendering bug.
- The SDK's RenderDoc auto-load and `/dev/shm` leak bit F.E.A.R. and GRAW on Linux: their fixes
  (GRAW's `linux-*` patches) join `tools/patches` with the Linux build (M4).
