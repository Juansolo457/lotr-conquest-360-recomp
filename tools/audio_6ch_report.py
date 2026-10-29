"""Per-channel report on the raw frames from --lotrc_audio_dump (<file>.6ch: every frame the game
submitted, 6 x 256 big-endian floats, channel-sequential FL FR FC LFE BL BR, 48 kHz).
  python tools/audio_6ch_report.py private/audio.f32.6ch [--from S] [--to S] [--every N]
Per second and channel: RMS (dBFS), the largest magnitude before any clamp (so a runaway gain
shows as 1e+10 and a decode fault as values outside +-1 that are still bounded), NaN/inf counts.
"""
import math
import struct
import sys

RATE = 48000
FRAME = 256
# A second is 187.5 frames: each second reads from its boundary to the next one (187 or 188).
NAMES = ["FL", "FR", "FC", "LFE", "BL", "BR"]


def main():
    args = sys.argv[1:]
    path = args[0]
    t_from, t_to, every = 0.0, None, 1
    i = 1
    while i < len(args):
        if args[i] == "--from":
            t_from = float(args[i + 1]); i += 2
        elif args[i] == "--to":
            t_to = float(args[i + 1]); i += 2
        elif args[i] == "--every":
            every = int(args[i + 1]); i += 2
        else:
            i += 1
    frame_bytes = 6 * FRAME * 4
    with open(path, "rb") as f:
        f.seek(0, 2)
        n_frames = f.tell() // frame_bytes
        print(f"{path}: {n_frames} frames = {n_frames * FRAME / RATE:.1f} s")
        print("sec   " + "  ".join(f"{n:>5}rms {n:>6}max" for n in NAMES) + "  nan/inf")
        sec = 0
        while True:
            start = int(sec * RATE / FRAME)
            if start >= n_frames:
                break
            if sec >= t_from and (t_to is None or sec < t_to) and (sec - int(t_from)) % every == 0:
                f.seek(start * frame_bytes)
                count = min(int((sec + 1) * RATE / FRAME), n_frames) - start
                data = f.read(count * frame_bytes)
                vals = struct.unpack(">%df" % (count * 6 * FRAME), data)
                sums = [0.0] * 6
                maxes = [0.0] * 6
                bad = 0
                for k in range(count):
                    base = k * 6 * FRAME
                    for c in range(6):
                        ch = vals[base + c * FRAME : base + (c + 1) * FRAME]
                        for v in ch:
                            if math.isnan(v) or math.isinf(v):
                                bad += 1
                                continue
                            sums[c] += v * v
                            if abs(v) > maxes[c]:
                                maxes[c] = abs(v)
                total = count * FRAME
                cells = []
                for c in range(6):
                    rms = 20 * math.log10(max(1e-9, math.sqrt(sums[c] / total)))
                    cells.append(f"{rms:8.1f} {maxes[c]:9.3g}")
                print(f"{sec:4d} " + " ".join(cells) + f"  {bad}")
            sec += 1


if __name__ == "__main__":
    main()
