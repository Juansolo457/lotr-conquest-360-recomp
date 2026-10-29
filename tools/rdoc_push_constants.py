# Run inside RenderDoc (qrenderdoc --python tools/rdoc_push_constants.py) with env vars:
#   RDOC_RDC = capture path, RDOC_OUT = output folder (private), RDOC_EVENT = dispatch events (comma)
# The push constants of each dispatch's compute shader, member by member, as hex: for the SDK's
# resolve and EDRAM dump shaders these are the resolve's EDRAM base, pitch, MSAA, format and
# rectangle (resolve.xesli XeResolveGetInfo decodes them), so two resolves can be compared.
import os
import traceback

import renderdoc as rd

out_dir = os.environ.get("RDOC_OUT", ".")
os.makedirs(out_dir, exist_ok=True)
log = open(os.path.join(out_dir, "push_constants.txt"), "w", encoding="utf-8")


def p(*a):
    log.write(" ".join(str(x) for x in a) + "\n")
    log.flush()


def dump(var, indent):
    if var.members:
        p(indent + var.name)
        for m in var.members:
            dump(m, indent + "  ")
    else:
        vals = var.value.u32v[:var.columns * max(1, var.rows)]
        p(indent + var.name, " ".join("%08X" % v for v in vals))


try:
    rd.InitialiseReplay(rd.GlobalEnvironment(), [])
    cap = rd.OpenCaptureFile()
    if cap.OpenFile(os.environ["RDOC_RDC"], "", None) != rd.ResultCode.Succeeded:
        raise RuntimeError("open failed")
    status, ctl = cap.OpenCapture(rd.ReplayOptions(), None)
    if status != rd.ResultCode.Succeeded:
        raise RuntimeError("replay failed %s" % status)
    for event in (int(v) for v in os.environ["RDOC_EVENT"].split(",")):
        ctl.SetFrameEvent(event, True)
        state = ctl.GetPipelineState()
        refl = state.GetShaderReflection(rd.ShaderStage.Compute)
        p("event", event, "compute shader", state.GetShader(rd.ShaderStage.Compute))
        if not refl:
            continue
        for i, block in enumerate(refl.constantBlocks):
            if block.bufferBacked:
                continue
            p("  block", block.name)
            for var in ctl.GetCBufferVariableContents(
                    state.GetComputePipelineObject(), refl.resourceId, rd.ShaderStage.Compute,
                    refl.entryPoint, i, rd.ResourceId.Null(), 0, 0):
                dump(var, "    ")
    ctl.Shutdown()
    cap.Shutdown()
except Exception:  # noqa: BLE001
    p(traceback.format_exc())
finally:
    log.close()
    os._exit(0)
