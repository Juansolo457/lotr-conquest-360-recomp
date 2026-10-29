# The Lord of the Rings: Conquest 360 Recompiled

The Xbox 360 **The Lord of the Rings: Conquest** (2009, Pandemic Studios / Electronic Arts),
statically recompiled to run natively on PC and the Steam Deck, drawn with Vulkan.

> Unofficial. **No game data included.** Bring your own Xbox 360 disc. Releases, when there are
> any, are source only: you build from your own disc.

## What it is

A **static recompilation**: the game's PowerPC code is translated to x86-64 C++ ahead of time with
[ReXGlue](https://github.com/rexglue/rexglue-sdk), and a game-specific runtime stands in for the
Xbox. Not an emulator, not a decompilation. Same approach and tooling as
[graw360-recomp](https://github.com/Juansolo457/graw360-recomp),
[fear360-recomp](https://github.com/Juansolo457/fear360-recomp) and
[quake4-360-recomp](https://github.com/Juansolo457/quake4-360-recomp).

The aim: the console game, its menus, HUD and controller feel, at a steady frame rate and any
resolution. Windows first, then native Linux and the Steam Deck, both on Vulkan.

## Status

Boots to the main menu (2026-10-29): the Bink logos, the title screen and the Scaleform menus
draw correctly on the SDK's Vulkan backend. Next: the first level.

- [docs/PLAN.md](docs/PLAN.md): goals, decisions, milestones
- [docs/HANDOFF.md](docs/HANDOFF.md): current state, how things work, where things live
- [docs/FINDINGS.md](docs/FINDINGS.md): what the disc and the executable are
- [docs/SETUP.md](docs/SETUP.md): build from your own disc

## Build (Windows)

```powershell
pwsh -NoProfile -File tools/setup.ps1                                   # toolchain, Vulkan-only SDK from source
pwsh -NoProfile -File tools/extract.ps1 -Iso 'D:\path\to\your\disc.iso' # ~5.4 GB into port/assets
pwsh -NoProfile -File tools/build.ps1                                   # translate and compile
pwsh -NoProfile -File tools/launch.ps1 -Windowed                        # run
```

The supported disc is the Redump-verified "Lord of the Rings, The - Conquest (USA, Asia)
(En,Fr,Es)": `default.xex` title `45410852`, version 0.0.0.1.

## Layout

```
port/        the ReXGlue project: manifest, src/ (host code), assets/ (your disc, ignored)
tools/       setup, extract, build, launch, smoke, SDK patches (patches/), analysis tools
docs/        plan, setup, handoff, findings
third_party/ the patched ReXGlue source tools/setup.ps1 makes (ignored)
private/     your captures, logs and decrypted images (ignored)
```

## Contributing

Every change reaches `master` through a pull request: [CONTRIBUTING.md](CONTRIBUTING.md).

## Legal

- No assets, executables, generated code, keys or proprietary code are distributed. Before
  pushing, run `python -I tools/audit_repo.py`.
- Our own code is MIT ([LICENSE](LICENSE)); ReXGlue's scaffolding and our SDK patches are
  BSD-3-Clause. File by file in [NOTICE](NOTICE).
- The Lord of the Rings and the names of the characters, items, events and places therein are
  trademarks of Middle-earth Enterprises. Not affiliated with Pandemic Studios, Electronic Arts,
  Middle-earth Enterprises, New Line Cinema, Warner Bros. or Microsoft.

## Credits

- Pandemic Studios: the game
- Tom Clay and contributors: [ReXGlue](https://github.com/rexglue/rexglue-sdk); the [Xenia](https://github.com/xenia-project/xenia) team
- shaunsingh: [pgr4-native](https://github.com/shaunsingh/pgr4-native), the origin of the SDK shader patches
- Built with [Claude Code](https://claude.com/claude-code)
