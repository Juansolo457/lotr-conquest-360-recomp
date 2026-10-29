# Run inside RenderDoc (qrenderdoc --python tools/rdoc_final_frames.py) with env vars:
#   RDOC_DIR = folder of .rdc captures, RDOC_OUT = output folder (private),
#   RDOC_SIZE = guest frame size (default 1280x720)
# For each capture: the last draw that writes a colour target at least half that size, that
# target saved as
# a PNG at that draw and its maximum value, so a folder of hotkey captures
# (tools/rdoc_capture.ps1 -Play) can be sorted into good and broken frames without opening each.
import os
import traceback

import renderdoc as rd

cap_dir = os.environ["RDOC_DIR"]
out_dir = os.environ.get("RDOC_OUT", os.path.join(cap_dir, "final"))
w, h = (int(v) for v in os.environ.get("RDOC_SIZE", "1280x720").split("x"))
os.makedirs(out_dir, exist_ok=True)
log = open(os.path.join(out_dir, "final_frames.txt"), "w", encoding="utf-8")


def p(*a):
    log.write(" ".join(str(x) for x in a) + "\n")
    log.flush()


def walk(actions):
    for a in actions:
        yield a
        if a.children:
            yield from walk(a.children)


rd.InitialiseReplay(rd.GlobalEnvironment(), [])
for name in sorted(f for f in os.listdir(cap_dir) if f.endswith(".rdc")):
    try:
        cap = rd.OpenCaptureFile()
        if cap.OpenFile(os.path.join(cap_dir, name), "", None) != rd.ResultCode.Succeeded:
            raise RuntimeError("open failed")
        status, ctl = cap.OpenCapture(rd.ReplayOptions(), None)
        if status != rd.ResultCode.Succeeded:
            raise RuntimeError("replay failed %s" % status)
        textures = {t.resourceId: t for t in ctl.GetTextures()}
        draws = [a for a in walk(ctl.GetRootActions()) if a.flags & rd.ActionFlags.Drawcall]
        found = None
        for a in reversed(draws):
            for o in a.outputs:
                t = textures.get(o)
                if t and t.width >= w // 2 and t.height >= h // 2:
                    found = (a, o)
                    break
            if found:
                break
        if not found:
            p(name, "draws", len(draws), "no %dx%d colour output" % (w, h))
        else:
            a, rid = found
            ctl.SetFrameEvent(a.eventId, True)
            s = rd.TextureSave()
            s.resourceId = rid
            s.destType = rd.FileType.PNG
            s.alpha = rd.AlphaMapping.Discard
            png = os.path.join(out_dir, name[:-4] + ".png")
            ctl.SaveTexture(s, png)
            stats = ctl.GetMinMax(rid, rd.Subresource(0, 0, 0), rd.CompType.Typeless)
            t = textures[rid]
            p(name, "draws", len(draws), "last %dx%d %s target at event" % (
                t.width, t.height, t.format.Name()), a.eventId,
              rid, "max", ["%.3f" % v for v in stats[1].floatValue[:3]],
              "->", png)
        ctl.Shutdown()
        cap.Shutdown()
    except Exception:  # noqa: BLE001
        p(name, traceback.format_exc())
log.close()
os._exit(0)
