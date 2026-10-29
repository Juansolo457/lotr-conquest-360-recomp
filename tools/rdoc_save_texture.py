# Run inside RenderDoc (qrenderdoc --python tools/rdoc_save_texture.py) with env vars:
#   RDOC_RDC = capture, RDOC_OUT = output folder (private), RDOC_RES = resource id number,
#   RDOC_EVENT = event(s) to replay to, comma-separated (optional; default the last).
# Saves the texture as a PNG at that event and logs the mean and the share of non-zero values of
# each channel, for telling which channel a pass wrote.
import os
import traceback

import renderdoc as rd

out_dir = os.environ.get("RDOC_OUT", ".")
os.makedirs(out_dir, exist_ok=True)
res = int(os.environ["RDOC_RES"])
log = open(os.path.join(out_dir, "texture_%d.txt" % res), "w", encoding="utf-8")


def p(*a):
    log.write(" ".join(str(x) for x in a) + "\n")
    log.flush()


def walk(actions):
    for a in actions:
        yield a
        if a.children:
            yield from walk(a.children)


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
        s = rd.TextureSave()
        s.resourceId = tex.resourceId
        s.destType = rd.FileType.PNG
        s.alpha = rd.AlphaMapping.Preserve
        ctl.SaveTexture(s, os.path.join(out_dir, "tex_%d_ev%d.png" % (res, event)))
        data = ctl.GetTextureData(tex.resourceId, rd.Subresource(0, 0, 0))
        if tex.format.compByteWidth == 1:
            n = tex.format.compCount
            for c in range(n):
                vals = data[c::n]
                p("   channel", c, "mean %.1f" % (sum(vals) / len(vals)), "non-zero %.1f%%" % (
                    100.0 * sum(1 for v in vals if v) / len(vals)))
    ctl.Shutdown()
    cap.Shutdown()
except Exception:  # noqa: BLE001
    p(traceback.format_exc())
finally:
    log.close()
    os._exit(0)
