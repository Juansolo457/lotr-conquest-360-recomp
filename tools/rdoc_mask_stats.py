# Run inside RenderDoc (qrenderdoc --python tools/rdoc_mask_stats.py) with env vars:
#   RDOC_RDC = capture path, RDOC_OUT = output folder (private),
#   RDOC_SIZE = texture size to look for (default 512x512), RDOC_COMPS = component count (default 1)
# For every draw whose pixel shader reads a texture of that size and component count: the event,
# the binding, the texture, and its contents at that event (how many texels are non-zero, min,
# max). Written in doax2-360-recomp for its beach shadow mask, a 512x512 k_8 resolve that came out all zeros
# when the 8bpp resolve took blue instead of alpha (docs/HANDOFF.md).
import os
import traceback

import renderdoc as rd

out_dir = os.environ.get("RDOC_OUT", ".")
rdc = os.environ["RDOC_RDC"]
w, h = (int(v) for v in os.environ.get("RDOC_SIZE", "512x512").split("x"))
comps = int(os.environ.get("RDOC_COMPS", "1"))
os.makedirs(out_dir, exist_ok=True)
log = open(os.path.join(out_dir, "mask_stats.txt"), "w", encoding="utf-8")


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
    if cap.OpenFile(rdc, "", None) != rd.ResultCode.Succeeded:
        raise RuntimeError("open failed")
    status, ctl = cap.OpenCapture(rd.ReplayOptions(), None)
    if status != rd.ResultCode.Succeeded:
        raise RuntimeError("replay failed %s" % status)
    textures = {t.resourceId: t for t in ctl.GetTextures()
                if t.width == w and t.height == h and t.format.compCount == comps}
    p("capture", rdc, "textures %dx%d with %d components: %d" % (w, h, comps, len(textures)))
    draws = 0
    for a in walk(ctl.GetRootActions()):
        if not (a.flags & rd.ActionFlags.Drawcall):
            continue
        ctl.SetFrameEvent(a.eventId, True)
        state = ctl.GetPipelineState()
        for used in state.GetReadOnlyResources(rd.ShaderStage.Pixel, True):
            rid = used.descriptor.resource
            t = textures.get(rid)
            if not t:
                continue
            draws += 1
            data = bytes(ctl.GetTextureData(rid, rd.Subresource(0, 0, 0)))
            nz = len(data) - data.count(0)
            p("event", a.eventId, "binding", used.access.index, "->", rid, t.format.Name(),
              "bytes %d, non-zero %d (%.1f%%), min %d, max %d" % (
                  len(data), nz, 100.0 * nz / max(1, len(data)), min(data), max(data)))
    p("draws reading such a texture:", draws)
    ctl.Shutdown()
    cap.Shutdown()
except Exception:  # noqa: BLE001
    p(traceback.format_exc())
finally:
    log.close()
    os._exit(0)
