# Run inside RenderDoc (qrenderdoc --python tools/rdoc_target_draws.py) with env vars:
#   RDOC_RDC = capture, RDOC_OUT = output folder (private), RDOC_RES = render target id number,
#   RDOC_READ = texture id number (optional) whose writes and reads to list too.
# Lists every action that writes the render target with its viewport and scissor, and the
# usage of the second texture (which events write and read it).
import os
import traceback

import renderdoc as rd

out_dir = os.environ.get("RDOC_OUT", ".")
os.makedirs(out_dir, exist_ok=True)
res = int(os.environ["RDOC_RES"])
log = open(os.path.join(out_dir, "draws_%d.txt" % res), "w", encoding="utf-8")


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
    sfile = ctl.GetStructuredFile()
    rid = next(t.resourceId for t in ctl.GetTextures() if int(t.resourceId) == res)
    for u in ctl.GetUsage(rid):
        a = next((x for x in walk(ctl.GetRootActions()) if x.eventId == u.eventId), None)
        if u.usage not in (rd.ResourceUsage.ColorTarget, rd.ResourceUsage.Clear, rd.ResourceUsage.CopyDst,
                           rd.ResourceUsage.CopySrc, rd.ResourceUsage.PS_Resource,
                           rd.ResourceUsage.CS_Resource, rd.ResourceUsage.CS_RWResource):
            continue
        line = "ev %d %s %s" % (u.eventId, u.usage, a.GetName(sfile)[:50] if a else "")
        if u.usage == rd.ResourceUsage.ColorTarget and a:
            ctl.SetFrameEvent(u.eventId, False)
            st = ctl.GetPipelineState()
            vp = st.GetViewport(0)
            sc = st.GetScissor(0)
            line += " | viewport %g,%g %gx%g | scissor %d,%d %dx%d | indices %d" % (
                vp.x, vp.y, vp.width, vp.height, sc.x, sc.y, sc.width, sc.height, a.numIndices)
        p(line)
    read = os.environ.get("RDOC_READ")
    if read:
        rid2 = next(t.resourceId for t in ctl.GetTextures() if int(t.resourceId) == int(read))
        p("usage of", rid2)
        for u in ctl.GetUsage(rid2):
            a = next((x for x in walk(ctl.GetRootActions()) if x.eventId == u.eventId), None)
            p("  ev %d %s %s" % (u.eventId, u.usage, a.GetName(sfile)[:60] if a else ""))
    ctl.Shutdown()
    cap.Shutdown()
except Exception:  # noqa: BLE001
    p(traceback.format_exc())
finally:
    log.close()
    os._exit(0)
