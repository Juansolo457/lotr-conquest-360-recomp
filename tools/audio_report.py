"""Report on an audio dump from --lotrc_audio_dump (src/audio_dump.h): raw interleaved float32
stereo at 48 kHz, plus <file>.txt with "frame_index host_ms" every 64 frames.
  python tools/audio_report.py private/audio.f32 [--wav out.wav] [--from S] [--to S]
Per second: RMS of each channel (dBFS), peak, clipped samples, DC offset, the left/right
correlation and the share of near-silent 256-sample frames, so a 'broken' stretch shows as
clipping, silence, a one-sided mix or a DC offset. From the .txt: the submit rate per 64 frames
(187.5 frames/s when the game keeps up; lower means it starved the output). --wav writes a
16-bit WAV of the range for listening.
"""
import math
import os
import struct
import sys
import wave

RATE = 48000
FRAME = 256


def main():
    args = sys.argv[1:]
    path = args[0]
    out_wav = None
    t_from, t_to = 0.0, None
    i = 1
    while i < len(args):
        if args[i] == "--wav":
            out_wav = args[i + 1]; i += 2
        elif args[i] == "--from":
            t_from = float(args[i + 1]); i += 2
        elif args[i] == "--to":
            t_to = float(args[i + 1]); i += 2
        else:
            i += 1
    size = os.path.getsize(path)
    n = size // 8  # stereo samples
    print(f"{path}: {n} stereo samples = {n / RATE:.1f} s")
    with open(path, "rb") as f:
        data = f.read()
    vals = struct.unpack("<%df" % (n * 2), data[: n * 8])
    print("sec  rmsL(dB) rmsR(dB)  peak  clip  dcL     dcR     corr  silent%")
    for s in range(int(n / RATE)):
        if s < t_from or (t_to is not None and s >= t_to):
            continue
        a = s * RATE * 2
        chunk = vals[a : a + RATE * 2]
        left = chunk[0::2]
        right = chunk[1::2]
        rms = lambda ch: 20 * math.log10(max(1e-9, math.sqrt(sum(v * v for v in ch) / len(ch))))
        peak = max(abs(v) for v in chunk)
        clip = sum(1 for v in chunk if abs(v) >= 0.999)
        dcl = sum(left) / len(left)
        dcr = sum(right) / len(right)
        ml, mr = dcl, dcr
        cov = sum((l - ml) * (r - mr) for l, r in zip(left, right))
        vl = math.sqrt(sum((l - ml) ** 2 for l in left)) or 1e-9
        vr = math.sqrt(sum((r - mr) ** 2 for r in right)) or 1e-9
        corr = cov / (vl * vr)
        silent = 0
        frames = RATE // FRAME
        for k in range(frames):
            fr = chunk[k * FRAME * 2 : (k + 1) * FRAME * 2]
            if max(abs(v) for v in fr) < 1e-4:
                silent += 1
        print(f"{s:4d} {rms(left):8.1f} {rms(right):8.1f} {peak:5.2f} {clip:5d} {dcl:+.4f} {dcr:+.4f} {corr:+.2f} {100 * silent / frames:5.1f}")
    times = path + ".txt"
    if os.path.exists(times):
        rows = [tuple(float(x) for x in line.split()) for line in open(times) if line.strip()]
        print("submit rate per 64 frames (frames/s; 187.5 = real time):")
        prev = None
        slow = []
        for idx, ms in rows:
            if prev:
                rate = 64.0 / max(1e-3, (ms - prev[1])) * 1000.0
                if rate < 160 or rate > 215:
                    slow.append((prev[1] / 1000.0, rate))
            prev = (idx, ms)
        if slow:
            for t, rate in slow[:60]:
                print(f"  at {t:7.1f} s: {rate:6.1f}/s")
            print(f"  {len(slow)} of {len(rows)} intervals off real time")
        else:
            print("  all intervals within 160-215 frames/s")
    if out_wav:
        a = int(t_from * RATE) * 2
        b = int(t_to * RATE) * 2 if t_to is not None else n * 2
        with wave.open(out_wav, "wb") as w:
            w.setnchannels(2); w.setsampwidth(2); w.setframerate(RATE)
            w.writeframes(struct.pack("<%dh" % (b - a), *[int(max(-1.0, min(1.0, v)) * 32767) for v in vals[a:b]]))
        print("wrote", out_wav)


if __name__ == "__main__":
    main()
