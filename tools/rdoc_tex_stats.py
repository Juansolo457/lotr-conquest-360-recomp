# Run inside RenderDoc (qrenderdoc --python tools/rdoc_tex_stats.py) with env vars:
#   RDOC_RDC = capture, RDOC_OUT = output folder (private), RDOC_RES = resource id number,
#   RDOC_EVENT = event(s) to replay to, comma-separated (optional; default the last).
# For a 16-bit float texture (R16G16B16A16_FLOAT): per-channel min, max, mean and percentiles
# of mip 0 at each event, and a PNG tone-mapped with the 99th percentile as white, for HDR
# targets that save all white through TextureSave.
import os
import struct
import sys
import traceback

import renderdoc as rd

res = int(os.environ["RDOC_RES"])
out_dir = os.environ["RDOC_OUT"]
os.makedirs(out_dir, exist_ok=True)
log = open(os.path.join(out_dir, "texstats_%d.txt" % res), "w", encoding="utf-8")


def p(*a):
    log.write(" ".join(str(x) for x in a) + "\n")
    log.flush()


def walk(actions):
    for a in actions:
        yield a
        if a.children:
            yield from walk(a.children)


failed = False
try:
    rd.InitialiseReplay(rd.GlobalEnvironment(), [])
    cap = rd.OpenCaptureFile()
    if cap.OpenFile(os.environ["RDOC_RDC"], "", None) != rd.ResultCode.Succeeded:
        raise RuntimeError("open failed")
    status, ctl = cap.OpenCapture(rd.ReplayOptions(), None)
    if status != rd.ResultCode.Succeeded:
        raise RuntimeError("replay failed %s" % status)
    last = max(a.eventId for a in walk(ctl.GetRootActions()))
    events = [int(v) for v in os.environ.get("RDOC_EVENT", "").split(",") if v.strip()] or [last]
    tex = next(t for t in ctl.GetTextures() if int(t.resourceId) == res)
    for event in events:
        ctl.SetFrameEvent(event, True)
        p("texture", tex.resourceId, "%dx%d" % (tex.width, tex.height), tex.format.Name(),
          "at event", event)
        data = bytes(ctl.GetTextureData(tex.resourceId, rd.Subresource(0, 0, 0)))
        n = tex.format.compCount
        if tex.format.compByteWidth == 2 and tex.format.compType == rd.CompType.Float:
            vals = struct.unpack("<%de" % (len(data) // 2), data)
        elif tex.format.compByteWidth == 1:
            vals = [v / 255.0 for v in data]
        else:
            p("   unsupported format", tex.format.Name())
            failed = True
            continue
        white = 1.0
        for c in range(n):
            ch = sorted(vals[c::n])
            m = len(ch)
            pct = lambda q: ch[min(m - 1, int(q * m))]
            p("   channel", c, "min %.4f max %.4f mean %.4f p50 %.4f p90 %.4f p99 %.4f" % (
                ch[0], ch[-1], sum(ch) / m, pct(0.5), pct(0.9), pct(0.99)))
            if c < 3:
                white = max(white, pct(0.99))
        s = rd.TextureSave()
        s.resourceId = tex.resourceId
        s.destType = rd.FileType.PNG
        s.alpha = rd.AlphaMapping.Discard
        s.comp.blackPoint = 0.0
        s.comp.whitePoint = float(white)
        path = os.path.join(out_dir, "texstats_%d_ev%d.png" % (res, event))
        status = ctl.SaveTexture(s, path)
        if status != rd.ResultCode.Succeeded:
            p("   save failed:", status, path)
            failed = True
        else:
            p("   saved", path, "white %.4f" % white)
    ctl.Shutdown()
    cap.Shutdown()
except Exception:  # noqa: BLE001
    p(traceback.format_exc())
    failed = True
finally:
    log.close()
    os._exit(1 if failed else 0)
