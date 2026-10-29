"""Find virtual-call forwarders the translation doesn't register as functions.

The compiler emits small forwarders for virtual calls through a pointer:
    lwz rX,0(r3); lwz rY,N(rX); mtctr rY; bctr
(Quake 4: r11/r10; LOTR mostly r11/r11), often after a few instructions that adjust `this`
(`lwz r3,N(r3)`, `lis`/`lwz` of a global). When one has no .pdata entry (it's a leaf) and
nothing references it statically, the analyser and tools/find_missed_functions.py miss it, and
the game dies on "Call to invalid or unregistered function" the first time it's called through
a function pointer (Quake 4's first level load, 0x823F2148, its docs/HANDOFF.md).

For every match outside the generated function table and the .pdata functions, this walks back
to the instruction after the previous function end (blr, bctr, an unconditional b, zero padding)
and keeps that entry only if it is not registered, not in .pdata and not a label in the
generated code. A label means a registered function branches there: the null-check wrappers
whose second half follows a `blr`, loop heads after a `b` (doa4-360-recomp's false positives).
Each kept entry is listed as a manifest line with its static references: a pointer to it in the
image, a branch to it, or a lis/addi pair that builds it. An entry with none can't be reached.

    python -I tools/find_vcall_thunks.py private/xex/default.bin port/generated/default private/xex/pdata_funcs.txt [sections.txt]

pdata_funcs.txt: one function per line, "<start hex> <length hex in bytes>", from the image's
.pdata (8-byte big-endian entries: start, then flags with the length in words at bits 8-29).
The scan covers every section marked "code" in the xexdump section list (default: the image's
name with .sections.txt, private/xex/default.sections.txt): LOTR's .text is 0x820B0000 +
0x75A020 and BINK 0x8280A200 + 0xF924. The range used to be hard-coded to Quake 4's .text
(0x82150000 + 0x813604), which here skipped the first 640 KB of code and read past its end.
"""
import bisect
import glob
import os
import re
import struct
import sys

BASE = 0x82000000
MAX_PREFIX = 16  # instructions walked back from a match to its entry


def code_ranges(path):
    ranges = []
    for line in open(path, encoding='utf-8'):
        p = line.split()
        if len(p) >= 4 and p[-1] == 'code':
            ranges.append((int(p[-3], 16), int(p[-2], 16)))
    if not ranges:
        sys.exit(f'{path}: no code sections')
    return ranges


def s16(v):
    return v - 0x10000 if v & 0x8000 else v


def main():
    img = open(sys.argv[1], 'rb').read()
    init = open(f'{sys.argv[2]}/lotrc_init.cpp', encoding='utf-8').read()
    known = set(int(m, 16) for m in re.findall(r'\{ 0x([0-9A-F]{8}), sub_', init))
    labels = set()
    for path in glob.glob(f'{sys.argv[2]}/lotrc_recomp.*.cpp'):
        text = open(path, encoding='utf-8').read()
        labels.update(int(m, 16) for m in re.findall(r'^loc_([0-9A-F]{8}):', text, re.M))
    funcs = []
    for line in open(sys.argv[3]):
        p = line.split()
        if len(p) >= 2:
            funcs.append((int(p[0], 16), int(p[1], 16)))
    funcs.sort()
    starts = [s for s, _ in funcs]
    sections = sys.argv[4] if len(sys.argv) > 4 else os.path.splitext(sys.argv[1])[0] + '.sections.txt'
    code = code_ranges(sections)

    def word(a):
        return struct.unpack_from('>I', img, a - BASE)[0]

    def in_pdata(a):
        i = bisect.bisect_right(starts, a) - 1
        return i >= 0 and a < funcs[i][0] + funcs[i][1]

    def ends_function(x):
        return x in (0x4E800020, 0x4E800420, 0) or ((x >> 26) == 18 and (x & 1) == 0)

    def is_forwarder(a):
        x, y = word(a), word(a + 4)
        if x >> 26 != 32 or (x >> 16) & 31 != 3 or x & 0xFFFF:
            return False
        rx = (x >> 21) & 31
        if y >> 26 != 32 or (y >> 16) & 31 != rx:
            return False
        return word(a + 8) == 0x7C0903A6 | ((y >> 21) & 31) << 21 and word(a + 12) == 0x4E800420

    entries = {}
    for lo, size in code:
        for a in range(lo + 4, lo + size - 12, 4):
            if not is_forwarder(a) or a in known or in_pdata(a):
                continue
            e = a
            for _ in range(MAX_PREFIX):
                if e in known or e in labels or in_pdata(e) or ends_function(word(e - 4)):
                    break
                e -= 4
            if ends_function(word(e - 4)) and not (e in known or e in labels or in_pdata(e)):
                entries.setdefault(e, a)

    refs = {e: [] for e in entries}
    for off in range(0, len(img) - 3, 4):
        v = struct.unpack_from('>I', img, off)[0]
        if v in refs:
            refs[v].append(f'pointer at 0x{BASE + off:08X}')
    for lo, size in code:
        for a in range(lo, lo + size, 4):
            x = word(a)
            op = x >> 26
            if op == 18 and not x & 2:
                li = x & 0x3FFFFFC
                t = a + (li - 0x4000000 if li & 0x2000000 else li)
            elif op == 16 and not x & 2:
                t = a + s16(x & 0xFFFC)
            elif op == 15 and (x >> 16) & 31 == 0:
                rd = (x >> 21) & 31
                for b in range(a + 4, min(a + 64, lo + size), 4):
                    y = word(b)
                    if y >> 26 in (14, 32) and (y >> 16) & 31 == rd:
                        t = ((x & 0xFFFF) << 16) + s16(y & 0xFFFF) & 0xFFFFFFFF
                        if t in refs:
                            refs[t].append(f'lis/addi at 0x{a:08X}')
                continue
            else:
                continue
            if t in refs:
                refs[t].append(f'branch at 0x{a:08X}')

    print(f'# {len(entries)} unregistered virtual-call forwarder entries, '
          f'{sum(1 for e in entries if refs[e])} with a static reference')
    for e, a in sorted(entries.items()):
        why = ', '.join(refs[e]) if refs[e] else 'no static reference'
        print(f'0x{e:08X} = {{}}  # vtable slot +{word(a + 4) & 0xFFFF} at 0x{a:08X}; {why}')


if __name__ == '__main__':
    main()
