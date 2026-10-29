# Findings: the disc and the executable

Facts about the supported disc and its `default.xex`, with how each was found. Every address is
a virtual address in the decrypted image (base `0x82000000`) of the executable below.

## The disc
- **Lord of the Rings, The - Conquest (USA, Asia) (En,Fr,Es)**, Redump-verified. ISO SHA-1
  `0788080d87bd03e1d3f9e207eada27ad635b0dae`, 7,835,492,352 bytes.
- Game partition at `0xFD90000`: 107 files, 5.39 GiB (`tools/xdvdfs.py <iso> list`).
  `tools/extract.ps1` unpacks it into `port/assets`.
- Layout:
  - `default.xex`, the only executable (9.2 MB);
  - `Levels/<name>.BIN` + `.PAK` per level (82-139 MB + 8-29 MB): `shell` (the front end),
    `legal`, `Training`, `Shire`, `Weathertop`, `Rivendell`, `Moria`, `Isengard`, `Helm'sDeep`,
    `Osgiliath`, `Minas_Morgul`, `PelennorFields`, `MinasTirith`, `MinasTirith_Top`,
    `Mount_Doom`, `BlackGates`; `Levels/level_info.dat`;
  - `Shaders_Xenon.bin` (6.7 MB): the precompiled shaders;
  - `audio/sound.pck` (1.2 GB) and `audio/WWiseIDTable.bin`: Wwise;
  - `flash/*.gfx` + `.dds`: Scaleform menus, fonts, load screens, system dialogs;
  - `video/*.bik`: Bink intros/outros per level and `video/logo/` (`ea`, `newline`, `pandemic`,
    `tolkien`, `attraction` = the 193 MB attract movie);
  - `sku.bin` (1 byte), `$SystemUpdate/`.

## The executable
| | |
|---|---|
| File | `default.xex`, 9,187,328 bytes |
| SHA-256 | `1e49a80be633b78e2d84b8b8b099fc401e5e0129d0fe606a6c54b64606085403` (`tools/build.ps1` checks it) |
| Title, version | `45410852`, 0.0.0.1, disc 1 of 1, media `64353B93` |
| Built | 2008-11-26 20:42 UTC; original PE name `magellan-Release.exe`, PDB `d:\projects\magellan\final_xb360\Code\Build\xbox360_8-0\release\magellan\magellan.pdb` |
| XDK | 2.0.7645: XAPILIB, D3DX9, XGRAPHC, XBOXKRNL, XONLINE, XMP, LIBCMT, XAUD, XHV, D3D9LTCG (7645.1). The newest XDK of our recomps |
| Image | base `0x82000000`, size `0xD00000`, entry `0x8222B200`, default stack 128 KB; AES-encrypted, **basic** compression (`tools/xex_basic_decrypt.py` can decrypt it with the retail key; `xexdump` was used) |

Sections (`private/xex/default.sections.txt`, from `xexdump`):
| Section | Address | Size |
|---|---|---|
| .rdata | `0x82000600` | `0x78090` |
| .pdata | `0x82078800` | `0x2B448` (function table, ~22,000 entries) |
| BINKBSS | `0x820A3E00` | `0x2920` |
| .text | `0x820B0000` | `0x75A020` (7.4 MB of code) |
| BINK | `0x8280A200` | `0xF924` (code: Bink's own section) |
| .data | `0x82820000` | `0x49E4BC` |
| .tls | `0x82CBE600` | `0x11` |
| BINKDATA | `0x82CBE800` | `0x3D68` |
| .XBMOVIE | `0x82CC2600` | `0xC` |
| .edata | `0x82CD0000` | `0x152` |
| .idata | `0x82CE0000` | `0x4A2` |
| .XBLD | `0x82CF0000` | `0xA0` |
| .reloc | `0x82CF0200` | `0x784E8` |

Virtual-call forwarders are mostly `lwz r11,0(r3); lwz r11,N(r11); mtctr r11; bctr` (Quake 4
uses r10 for the second load), often after `this`-adjusting loads. Registered ones are pointed
at from vtables in `.rdata`; the 8 the translation leaves out have no pointer, branch or
`lis`/`addi` reference anywhere (2026-10-29, `tools/find_vcall_thunks.py`).

### Imports: all implemented
255 kernel and XAM functions (`private/xex/default.symbols.txt`), every one with an
implementation in the SDK (ReXGlue `bd833a2`): checked 2026-10-29 by matching the names
`xexdump` resolved against the SDK's `export_table.inc` files (no stubs, none missing).
Notable: `XamShowSigninUI`, `XamShowFriendsUI`, `XamShowKeyboardUI`, `XamShowGamerCardUIForXUID`,
`XamShowMarketplaceUI`, `XamShowDeviceSelectorUI`, `XamShowMessageBoxUIEx`, `XMsgStartIORequest`
(async XAM calls), `XNotifyGetNext`, the whole `NetDll_XNet*` / `NetDll_*socket*` set (Xbox
Live, LAN and EA's Plasma backend), `XGetVideoMode`, `XGetGameRegion`.

### Engine and middleware (from the decrypted image's strings)
- **Pandemic's in-house engine, code name "Magellan"**: 496 `Mg*` names (`MgSys`, `MgScript`,
  `MgCreature`, `MgGameObject`, `MgAnim`, `MgState` machines: `MgShellLoadState`,
  `MgShellRunState`, `MgClientLevelState`, `MgServerLevelRunState`, `MgCutSceneState`,
  `MgLevelCompletionState`, `MgCampaignOutroMenuState`, `MgModeSelectState`;
  `MgUIMainMenu`, `MgUIMultiplayer`, `MgUIMultiplayerGameType`; messages
  `MgGameLoadShellMessage`, `MgShellStartGameMessage`, `MgLegalCompleteMessage`, ...).
  The build string `CLIENT.PhAn.Pandemic_Magellan_Xbox360-PC-PS3_HavokComplete` names the three
  platforms the engine targets.
- **Havok 5.5.0 r1** (physics, animation, ragdolls: `hk*`, 363 strings).
- **Scaleform GFx** (the menus and HUD: `GFxLoader`, `flash/*.gfx`: `briefing`, `loadscreen`,
  `border`, `playerstats`, `audio`, `controllerconfig`, `systemdialog`, ...).
- **Wwise** (`AK::IOThread`, `AK::BankManager`, `AK::EventManager`; `audio/sound.pck`).
- **Bink** video (its own `BINK*` sections; `%s\logo\attraction.bik`), and D3DX.
- **Lua 5.1** scripting (`MgBase.lua`).
- zlib/libpng (PNG chunk messages), PIX markers.
- Paths the game forms: `game:\`, `cache:\`, `levels\%s.pak` / `%s.bin`, `levels/level_info.dat`,
  `audio\WWiseIDTable.bin`. `LoadingSaveFileXENON`: saves through XAM content.
- Multiplayer: split-screen, LAN, Xbox Live (`xb360connectionstates`), EA Plasma
  (`MgShellConnectPlasmaMessage`); expect the shell to probe the network at start-up.

### How it renders and sounds (from the runs, 2026-10-29)
- **Render targets of a level**: the scene in `k_2_10_10_10_FLOAT` (7e3 HDR) 4xMSAA at EDRAM
  base 0 with D24S8 at 720; bloom and luminance chains in `k_16_16_16_16` (fixed, base 1672)
  and `k_16_16_16_16_FLOAT` (base 0) at 640, 320, 160 and 80 wide; shadow maps as a
  `k_8_8_8_8` 560x4688 colour target and depth-only 880x2992 / 440x1496 4xMSAA targets; the HUD
  and Scaleform in `k_8_8_8_8` at 1280x720. The final frame is a `k_2_10_10_10` resolve.
- **Exposure is on the CPU**: a resolve of the luminance measurement is read back by the game
  (`readback_resolve` must be on, or every level is white). Xenia users know this game for it.
- **Screen-space effects** (shockwaves, sword trails, heat haze) sample a resolved copy of the
  scene (1280x720 `k_16_16_16_16_FLOAT`) with projected coordinates plus a distortion offset.
- **Audio**: the game registers one XAudio render driver client and mixes itself (Wwise),
  submitting 6-channel 256-sample float frames; hardware XMA contexts decode the streams
  (`XMACreateContext`). Wwise's dB-to-gain path uses the VMX `vexptefp` estimate (22 sites in
  one module), which is how the code generator's underflow bug became audible.
- The shell probes `cache:\` (no device: harmless), `game:\audio\English(US)\` (not on the
  disc; the English audio lives in `sound.pck`) and the PS3 button textures
  `flash\UI_ps3button_*` (not on the disc; harmless).

## Decrypting for analysis
```
..\quake4-definitive\build\xexdump\xexdump.exe port\assets\default.xex private\xex\default
```
writes `private/xex/default.bin` (the image at `0x82000000`), `.sections.txt` and `.symbols.txt`
(the 255 imports). `tools/xex_basic_decrypt.py` works too (basic compression) given the retail
key in `LOTRC_XEX_KEY` or `tools/xex_key.txt` (ignored); ReXGlue's code generator reads the XEX
directly and needs neither.
