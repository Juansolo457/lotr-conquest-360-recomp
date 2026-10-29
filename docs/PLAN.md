# Plan: The Lord of the Rings: Conquest (Xbox 360), statically recompiled

Written 2026-10-29 from the user's brief. State and next steps are in [HANDOFF.md](HANDOFF.md);
disc and executable facts in [FINDINGS.md](FINDINGS.md).

## Goal
The Xbox 360 build of The Lord of the Rings: Conquest running natively on **Windows and Linux**
(the Steam Deck), its PowerPC code translated to x86-64 with ReXGlue and drawn with **Vulkan**.
The console game as it was, with the console's own menus, HUD and controller feel, at a steady
frame rate and any resolution.

Order of work: **the PC (Windows) version first, the Linux build after, both on Vulkan.**

## Decisions (the user, 2026-10-29)
- **Public repository** from day one, source only (no builds with translated game code). `master`
  is locked the same way as the sister repos: every change through a pull request, the `audit`
  check, an up-to-date branch and resolved conversations, admins included. CodeRabbit reviews
  every pull request.
- **Vulkan only, no D3D12.** The SDK is built from source with `REXGLUE_USE_D3D12=OFF`
  (DOAX2's recipe) and the host loads the Xenos plugin's Vulkan backend by name.
- **No builds, codegen or game windows without the user's OK.** They test other games on this PC.
- **Use what the sister repos learned.** This repo is `../quake4-360-recomp` renamed (itself
  DOAX2's shape with GRAW's SDK patches); their HANDOFF files are the first place to look when
  something breaks.
- **The first milestone is drawn frames and the menus**, on the SDK's emulated Xenos renderer
  (Vulkan backend), the path DOAX2 ships with. Whether a native renderer (GRAW's `native/`) is
  worth it here is decided later on measurements, not up front.

## Starting points
| Source | What we take |
|---|---|
| `../quake4-360-recomp` | the repo shape: `AGENTS.md`, scripts (`tools/`), host code (`port/src`), SDK patch set, CI audit, CONTRIBUTING |
| `../doax2-360-recomp` | the Vulkan-only SDK build; the XAPI fiber hooks (`[entrypoint.rexcrt]`); `render_target_path_vulkan=fsi` for EDRAM-exact rendering; smoke/autopilot method |
| `../graw360-recomp` | `tools/patches` (the SDK patch set), Bink lessons, the Linux/Deck container build, the native renderer if it comes to that |
| `../fear360-recomp` | Deck/Linux lessons (`docs/LINUX_NATIVE.md`), performance work |

## Architecture
```
default.xex (your disc) --rexglue codegen--> port/generated/default (C++, one function per guest function)
                                                  |
port/src     host: app, crash reports, frame timing, controllers, autopilot
                                                  |
ReXGlue SDK bd833a2 + patches (tools/patches), built from source, Vulkan only:
  runtime (kernel/XAM, file system over port/assets, threads, fibers, audio, SDL3 window and pads)
  Xenos plugin, Vulkan backend: emulates the console GPU from the game's command buffers
```
The game is Pandemic's in-house engine (code name Magellan: `Mg*` classes), with Havok 5.5,
Scaleform GFx menus, Wwise audio, Bink video and Lua 5.1 scripting. See FINDINGS.md.

## Milestones
| # | Milestone | Done when |
|---|---|---|
| M0 (done 2026-10-29) | **Repo, toolchain, first translation** | Repo public and locked; Vulkan-only SDK; disc extracted; codegen clean (0 wrong switch tables, no vpkd3d128 hazards, missed-function finder at a fixed point); `lotrc.exe` links |
| M1 (done 2026-10-29) | **Drawn frames and the menus** | Boots on the Xenos plugin's Vulkan backend: logo videos, the shell (main menu) draws and a controller moves through it. Crash reporter and frame log from the first run. Reference captures |
| M2 | **A level plays** | Training or a campaign level loads and plays; saves; the HUD draws; a first pass on visual bugs against console footage |
| M3 | **Windows playable** | Campaign start to finish; resolution scale; steady pacing (frame-time logs); the user's play-test |
| M4 | **Native Linux and the Deck** | GRAW's podman/Ubuntu 22.04 build; the package in `~/recomps/LOTRConquest-360-SteamDeck/`; the user's Deck runs |
| M5 | **Performance and extras** | Measured bottlenecks (CPU per draw, GPU time); decide on a native renderer; source-only release with SETUP for Windows and Linux |

## Risks
- **XDK 2.0.7645 (late 2008)** is newer than any our recomps ran (F.E.A.R. and DOAX2 are 2006,
  GRAW 2006, pgr4-native's PGR4 2007). The kernel side is covered (all 255 imports have
  implementations, FINDINGS.md); the D3D library in the image is newer, which matters only if a
  native renderer is attempted.
- **Fibers, FP state, devkit probes:** DOAX2 needed XAPI fiber hooks, Quake 4 and GRAW an FPSCR
  guard on the audio worker. Both fixes are at hand (manifest `[entrypoint.rexcrt]`,
  `port/src/fpscr_guard.cpp`).
- **Middleware the SDK has not met:** Wwise's I/O thread and bank manager, Scaleform's renderer
  (render-to-texture, many small draws), Havok's thread pool. Each is translated code and should
  just run, but each is also a new place for a missed function entry or a thread-affinity trap.
- **Online code** (Plasma, Xbox Live, LAN): the shell reaches for `XNetStartup` and friends at
  start-up. The SDK stubs them; the menu must cope with "no connection".
