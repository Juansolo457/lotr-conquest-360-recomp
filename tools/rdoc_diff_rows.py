# Run inside RenderDoc (qrenderdoc --python tools/rdoc_diff_rows.py) with env vars:
#   RDOC_RDC = capture path, RDOC_OUT = output folder (private), RDOC_RES = resource id number,
#   RDOC_BEFORE, RDOC_AFTER = the two events to compare
# Reads the texture's raw data at both events and logs which rows changed (as ranges, with the
# changed pixel count) and the value range before and after: what area a draw wrote. Rows are
# host pixels; with 80x16-pixel EDRAM tiles at 1x, row // 16 is the tile row.
import os
import traceback

import renderdoc as rd

out_dir = os.environ.get("RDOC_OUT", ".")
os.makedirs(out_dir, exist_ok=True)
res = int(os.environ["RDOC_RES"])
before, after = int(os.environ["RDOC_BEFORE"]), int(os.environ["RDOC_AFTER"])
log = open(os.path.join(out_dir, "diff_%d_%d_%d.txt" % (res, before, after)), "w",
           encoding="utf-8")


def p(*a):
    log.write(" ".join(str(x) for x in a) + "\n")
    log.flush()


try:
    rd.InitialiseReplay(rd.GlobalEnvironment(), [])
    cap = rd.OpenCaptureFile()
    if cap.OpenFile(os.environ["RDOC_RDC"], "", None) != rd.ResultCode.Succeeded:
        raise RuntimeError("open failed")
    status, ctl = cap.OpenCapture(rd.ReplayOptions(), None)
    if status != rd.ResultCode.Succeeded:
        raise RuntimeError("replay failed %s" % status)
    tex = next(t for t in ctl.GetTextures() if int(t.resourceId) == res)
    data = []
    for event in (before, after):
        ctl.SetFrameEvent(event, True)
        data.append(bytes(ctl.GetTextureData(tex.resourceId, rd.Subresource(0, 0, 0))))
    a, b = data
    bpp = len(a) // (tex.width * tex.height)
    p("texture", res, "%dx%d" % (tex.width, tex.height), tex.format.Name(), "bytes", len(a),
      "bytes per pixel", bpp)
    row_bytes = tex.width * bpp
    start = None
    run_changed = 0
    for y in range(tex.height + 1):
        changed = 0
        if y < tex.height:
            ra, rb = a[y * row_bytes:(y + 1) * row_bytes], b[y * row_bytes:(y + 1) * row_bytes]
            if ra != rb:
                changed = sum(1 for x in range(tex.width)
                              if ra[x * bpp:(x + 1) * bpp] != rb[x * bpp:(x + 1) * bpp])
        if changed and start is None:
            start, run_changed = y, 0
        if changed:
            run_changed += changed
        if not changed and start is not None:
            p("rows %d-%d changed (tile rows %d-%d), %d pixels" % (
                start, y - 1, start // 16, (y - 1) // 16, run_changed))
            start = None
    nonzero_before = sum(1 for i in range(0, len(a), bpp) if any(a[i:i + bpp]))
    nonzero_after = sum(1 for i in range(0, len(b), bpp) if any(b[i:i + bpp]))
    p("non-zero pixels before", nonzero_before, "after", nonzero_after)
    ctl.Shutdown()
    cap.Shutdown()
except Exception:  # noqa: BLE001
    p(traceback.format_exc())
finally:
    log.close()
    os._exit(0)
