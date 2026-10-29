# Run inside RenderDoc (qrenderdoc --python tools/rdoc_sized_textures.py) with env vars:
#   RDOC_RDCS = capture paths separated by ';', RDOC_OUT = output folder (private),
#   RDOC_SIZE = texture size to save (default 1280x720)
# Saves every texture of that size, as it is at the end of each capture, as PNG
# (<capture>_<resource>.png) and lists them with their format and how many draws read or write
# them. The guest's frame is a resolve into such a texture (the host render targets are EDRAM
# scratch, e.g. 800x3280), so this finds what the player saw.
import os
import traceback

import renderdoc as rd

out_dir = os.environ["RDOC_OUT"]
w, h = (int(v) for v in os.environ.get("RDOC_SIZE", "1280x720").split("x"))
os.makedirs(out_dir, exist_ok=True)
log = open(os.path.join(out_dir, "sized_textures.txt"), "w", encoding="utf-8")


def p(*a):
    log.write(" ".join(str(x) for x in a) + "\n")
    log.flush()


def walk(actions):
    for a in actions:
        yield a
        if a.children:
            yield from walk(a.children)


rd.InitialiseReplay(rd.GlobalEnvironment(), [])
for rdc in os.environ["RDOC_RDCS"].split(";"):
    name = os.path.basename(rdc)[:-4]
    try:
        cap = rd.OpenCaptureFile()
        if cap.OpenFile(rdc, "", None) != rd.ResultCode.Succeeded:
            raise RuntimeError("open failed")
        status, ctl = cap.OpenCapture(rd.ReplayOptions(), None)
        if status != rd.ResultCode.Succeeded:
            raise RuntimeError("replay failed %s" % status)
        actions = list(walk(ctl.GetRootActions()))
        ctl.SetFrameEvent(actions[-1].eventId, True)
        for t in ctl.GetTextures():
            if t.width != w or t.height != h:
                continue
            uses = ctl.GetUsage(t.resourceId)
            reads = sum(1 for u in uses if u.usage in (rd.ResourceUsage.PS_Resource,
                                                       rd.ResourceUsage.VS_Resource,
                                                       rd.ResourceUsage.CS_Resource))
            writes = len(uses) - reads
            rid = str(t.resourceId).replace("ResourceId::", "")
            png = os.path.join(out_dir, "%s_%s.png" % (name, rid))
            s = rd.TextureSave()
            s.resourceId = t.resourceId
            s.destType = rd.FileType.PNG
            s.alpha = rd.AlphaMapping.Discard
            ctl.SaveTexture(s, png)
            p(name, rid, t.format.Name(), "uses", len(uses), "reads", reads, "other", writes,
              "events %s-%s" % (uses[0].eventId, uses[-1].eventId) if uses else "")
        ctl.Shutdown()
        cap.Shutdown()
    except Exception:  # noqa: BLE001
        p(name, traceback.format_exc())
log.close()
os._exit(0)
