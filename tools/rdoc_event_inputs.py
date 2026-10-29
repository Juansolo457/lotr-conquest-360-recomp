# Run inside RenderDoc (qrenderdoc --python tools/rdoc_event_inputs.py) with env vars:
#   RDOC_RDC = capture path, RDOC_OUT = output folder (private), RDOC_EVENT = event id
# At that event: the draw's name, the shaders, every resource the pixel and vertex stages read
# (binding, resource, size, format), each read-only texture saved as a PNG (and an R32 one also
# as raw float statistics), and the colour/depth outputs. For finding what a draw sampled.
import os
import struct
import traceback

import renderdoc as rd

out_dir = os.environ.get("RDOC_OUT", ".")
rdc = os.environ["RDOC_RDC"]
event = int(os.environ["RDOC_EVENT"])
os.makedirs(out_dir, exist_ok=True)
log = open(os.path.join(out_dir, "event_%d.txt" % event), "w", encoding="utf-8")


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
    sfile = ctl.GetStructuredFile()
    textures = {t.resourceId: t for t in ctl.GetTextures()}
    names = {r.resourceId: r.name for r in ctl.GetResources()}
    action = next((a for a in walk(ctl.GetRootActions()) if a.eventId == event), None)
    p("event", event, action.GetName(sfile) if action else "?", "indices",
      action.numIndices if action else "?")
    ctl.SetFrameEvent(event, True)
    state = ctl.GetPipelineState()
    for stage in (rd.ShaderStage.Vertex, rd.ShaderStage.Pixel):
        refl = state.GetShaderReflection(stage)
        p("stage", stage, "shader", state.GetShader(stage), "entry",
          refl.entryPoint if refl else "-")
        for used in state.GetReadOnlyResources(stage, True):
            rid = used.descriptor.resource
            t = textures.get(rid)
            desc = "%dx%d %s" % (t.width, t.height, t.format.Name()) if t else "(not a texture)"
            p("   read-only binding", used.access.index, "array", used.access.arrayElement,
              "->", rid, names.get(rid, ""), desc)
            if t and stage == rd.ShaderStage.Pixel:
                s = rd.TextureSave()
                s.resourceId = rid
                s.destType = rd.FileType.PNG
                s.alpha = rd.AlphaMapping.Discard
                try:
                    ctl.SaveTexture(s, os.path.join(out_dir, "ev%d_ps_b%d_%s.png" % (
                        event, used.access.index, str(rid).replace("ResourceId::", ""))))
                except Exception as e:  # noqa: BLE001
                    p("      save failed", e)
                if t.format.compCount == 1 and t.format.compByteWidth == 4:
                    data = ctl.GetTextureData(rid, rd.Subresource(0, 0, 0))
                    vals = struct.unpack("<%df" % (len(data) // 4), data)
                    nz = [v for v in vals if v != 0.0]
                    p("      R32 stats: count %d, zeros %d, min %g, max %g" % (
                        len(vals), len(vals) - len(nz), min(vals), max(vals)))
    for o in state.GetOutputTargets():
        if o.resource != rd.ResourceId.Null():
            t = textures.get(o.resource)
            p("output", o.resource, "%dx%d %s" % (t.width, t.height, t.format.Name()) if t else "")
    d = state.GetDepthTarget()
    if d.resource != rd.ResourceId.Null():
        t = textures.get(d.resource)
        p("depth", d.resource, "%dx%d %s" % (t.width, t.height, t.format.Name()) if t else "")
    ctl.Shutdown()
    cap.Shutdown()
except Exception:  # noqa: BLE001
    p(traceback.format_exc())
finally:
    log.close()
    os._exit(0)
