"""Report on an audio dump from --lotrc_audio_dump (src/audio_dump.h): raw interleaved float32
stereo at 48 kHz, plus <file>.txt with "frame_index host_ms" every 64 frames.
  python tools/audio_report.py private/audio.f32 [--wav out.wav] [--from S] [--to S]
Per second: RMS of each channel (dBFS), peak, clipped samples, DC offset, the left/right
correlation and the share of near-silent 256-sample frames, so a 'broken' stretch shows as
clipping, silence, a one-sided mix or a DC offset. From the .txt: the submit rate per 64 frames
(187.5 frames/s when the game keeps up; lower means it starved the output). --wav writes a
16-bit WAV of the range for listening. The dump is read one second at a time, so a long capture
costs no more memory than a short one.
"""
import math
import os
import struct
import sys
import wave

RATE = 48000
FRAME = 256
SECOND_BYTES = RATE * 2 * 4  # stereo float32


def read_second(f, sec):
    """The stereo samples of second `sec` as floats (fewer than RATE pairs at the end)."""
    f.seek(sec * SECOND_BYTES)
    data = f.read(SECOND_BYTES)
    count = len(data) // 4
    return struct.unpack("<%df" % count, data[: count * 4])


def report_second(sec, chunk):
    left = chunk[0::2]
    right = chunk[1::2]
    if not left or not right:
        return

    def rms(ch):
        return 20 * math.log10(max(1e-9, math.sqrt(sum(v * v for v in ch) / len(ch))))

    peak = max(abs(v) for v in chunk)
    clip = sum(1 for v in chunk if abs(v) >= 0.999)
    dcl = sum(left) / len(left)
    dcr = sum(right) / len(right)
    cov = sum((l - dcl) * (r - dcr) for l, r in zip(left, right))
    vl = math.sqrt(sum((l - dcl) ** 2 for l in left)) or 1e-9
    vr = math.sqrt(sum((r - dcr) ** 2 for r in right)) or 1e-9
    corr = cov / (vl * vr)
    frames = max(1, len(chunk) // (FRAME * 2))
    silent = 0
    for k in range(frames):
        fr = chunk[k * FRAME * 2 : (k + 1) * FRAME * 2]
        if max(abs(v) for v in fr) < 1e-4:
            silent += 1
    print(f"{sec:4d} {rms(left):8.1f} {rms(right):8.1f} {peak:5.2f} {clip:5d} {dcl:+.4f} {dcr:+.4f} "
          f"{corr:+.2f} {100 * silent / frames:5.1f}")


def report_submit_rate(times):
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


def write_wav(f, out_wav, sec_from, sec_to):
    with wave.open(out_wav, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(RATE)
        for sec in range(sec_from, sec_to):
            chunk = read_second(f, sec)
            if not chunk:
                break
            w.writeframes(struct.pack(
                "<%dh" % len(chunk), *[int(max(-1.0, min(1.0, v)) * 32767) for v in chunk]))
    print("wrote", out_wav)


def main():
    args = sys.argv[1:]
    path = args[0]
    out_wav = None
    t_from, t_to = 0.0, None
    i = 1
    while i < len(args):
        if args[i] == "--wav":
            out_wav = args[i + 1]
            i += 2
        elif args[i] == "--from":
            t_from = float(args[i + 1])
            i += 2
        elif args[i] == "--to":
            t_to = float(args[i + 1])
            i += 2
        else:
            i += 1
    n = os.path.getsize(path) // 8  # stereo samples
    total_seconds = int(math.ceil(n / RATE))
    print(f"{path}: {n} stereo samples = {n / RATE:.1f} s")
    # The range, clamped to the dump and ordered.
    sec_from = max(0, min(int(t_from), total_seconds))
    sec_to = total_seconds if t_to is None else max(sec_from, min(int(math.ceil(t_to)), total_seconds))
    print("sec  rmsL(dB) rmsR(dB)  peak  clip  dcL     dcR     corr  silent%")
    with open(path, "rb") as f:
        for sec in range(sec_from, sec_to):
            report_second(sec, read_second(f, sec))
        if out_wav:
            write_wav(f, out_wav, sec_from, sec_to)
    times = path + ".txt"
    if os.path.exists(times):
        report_submit_rate(times)


if __name__ == "__main__":
    main()
