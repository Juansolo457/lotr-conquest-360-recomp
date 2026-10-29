# Run inside RenderDoc (qrenderdoc --python tools/rdoc_actions.py) with env vars:
#   RDOC_RDC = capture path, RDOC_OUT = output folder (private),
#   RDOC_FROM, RDOC_TO = event range
# Every action in the range: event, name, colour outputs (with size and format) and depth target,
# and for draws the textures the pixel shader reads. For following a pass chain step by step.
import os
import traceback

import renderdoc as rd

out_dir = os.environ.get("RDOC_OUT", ".")
os.makedirs(out_dir, exist_ok=True)
lo, hi = int(os.environ["RDOC_FROM"]), int(os.environ["RDOC_TO"])
log = open(os.path.join(out_dir, "actions_%d_%d.txt" % (lo, hi)), "w", encoding="utf-8")


def p(*a):
    log.write(" ".join(str(x) for x in a) + "\n")
    log.flush()


def walk(actions):
    for a in actions:
        yield a
        if a.children:
            yield from walk(a.children)


def short(rid):
    return str(rid).replace("ResourceId::", "")


try:
    rd.InitialiseReplay(rd.GlobalEnvironment(), [])
    cap = rd.OpenCaptureFile()
    if cap.OpenFile(os.environ["RDOC_RDC"], "", None) != rd.ResultCode.Succeeded:
        raise RuntimeError("open failed")
    status, ctl = cap.OpenCapture(rd.ReplayOptions(), None)
    if status != rd.ResultCode.Succeeded:
        raise RuntimeError("replay failed %s" % status)
    sfile = ctl.GetStructuredFile()
    textures = {t.resourceId: t for t in ctl.GetTextures()}

    def desc(rid):
        t = textures.get(rid)
        return "%s(%dx%d %s)" % (short(rid), t.width, t.height, t.format.Name()) if t else short(rid)

    for a in walk(ctl.GetRootActions()):
        if not lo <= a.eventId <= hi or a.children:
            continue
        line = ["event", a.eventId, a.GetName(sfile)]
        outs = [o for o in a.outputs if o != rd.ResourceId.Null()]
        if outs:
            line += ["out"] + [desc(o) for o in outs]
        if a.depthOut != rd.ResourceId.Null():
            line += ["depth", desc(a.depthOut)]
        if a.flags & rd.ActionFlags.Drawcall:
            line += ["indices", a.numIndices]
            ctl.SetFrameEvent(a.eventId, False)
            state = ctl.GetPipelineState()
            reads = [desc(u.descriptor.resource)
                     for u in state.GetReadOnlyResources(rd.ShaderStage.Pixel, True)
                     if u.descriptor.resource in textures]
            if reads:
                line += ["reads"] + reads
        p(*line)
    ctl.Shutdown()
    cap.Shutdown()
except Exception:  # noqa: BLE001
    p(traceback.format_exc())
finally:
    log.close()
    os._exit(0)
