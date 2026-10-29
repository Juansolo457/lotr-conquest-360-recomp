"""Find virtual-call forwarders the translation doesn't register as functions.

The compiler emits small forwarders for virtual calls through a pointer:
    lwz r11,0(r3); lwz r10,N(r11); mtctr r10; bctr
When one has no .pdata entry (it's a leaf) and nothing references it statically, the analyser
and tools/find_missed_functions.py miss it, and the game dies on "Call to invalid or unregistered
function" the first time it's called through a function pointer (Quake 4's first level load,
0x823F2148, docs/HANDOFF.md).

This lists the pattern's matches that are not in the generated function table and that start a
function: right after a function end (blr, bctr, an unconditional b, or zero padding) and outside
every .pdata function. Matches preceded by other instructions are the tail of a longer forwarder
already registered. Output is manifest lines.

    python -I tools/find_vcall_thunks.py private/xex/default.bin port/generated/default <pdata_funcs.txt>

pdata_funcs.txt: one function per line, "<start hex> <length hex>" (../quake4-definitive/game/xex/).
"""
import bisect
import re
import struct
import sys

BASE = 0x82000000
TEXT = (0x82150000, 0x813604)


def main():
    img = open(sys.argv[1], 'rb').read()
    init = open(f'{sys.argv[2]}/lotrc_init.cpp', encoding='utf-8').read()
    known = set(int(m, 16) for m in re.findall(r'\{ 0x([0-9A-F]{8}), sub_', init))
    funcs = []
    for line in open(sys.argv[3]):
        p = line.split()
        if len(p) >= 2:
            funcs.append((int(p[0], 16), int(p[1], 16)))
    funcs.sort()
    starts = [s for s, _ in funcs]

    def word(a):
        return struct.unpack_from('>I', img, a - BASE)[0]

    def in_pdata(a):
        i = bisect.bisect_right(starts, a) - 1
        return i >= 0 and a < funcs[i][0] + funcs[i][1]

    found = []
    lo, size = TEXT
    for a in range(lo + 4, lo + size - 12, 4):
        if not (word(a) == 0x81630000 and (word(a + 4) & 0xFFFF0000) == 0x814B0000
                and word(a + 8) == 0x7D4903A6 and word(a + 12) == 0x4E800420):
            continue
        if a in known or in_pdata(a):
            continue
        prev = word(a - 4)
        if prev in (0x4E800020, 0x4E800420, 0) or ((prev >> 26) == 18 and (prev & 3) == 0):
            found.append((a, word(a + 4) & 0xFFFF))
    print(f'# {len(found)} unregistered virtual-call forwarders')
    for a, slot in found:
        print(f'0x{a:08X} = {{}}  # vtable slot +{slot}')


if __name__ == '__main__':
    main()
