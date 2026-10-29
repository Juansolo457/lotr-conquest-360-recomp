# Run inside RenderDoc (qrenderdoc --python tools/rdoc_draw_state.py) with env vars:
#   RDOC_RDC = capture path, RDOC_OUT = output folder (private), RDOC_EVENT = event ids (comma)
# At each draw (or dispatch: its shader and bound resources): the pixel shader's output signature (which colour outputs and depth it writes),
# the colour attachments and blend write masks, depth test/write state, and the shader's SPIR-V
# disassembly to <out>/ps_<event>.txt. For telling why a draw writes no colour.
import os
import traceback

import renderdoc as rd

out_dir = os.environ.get("RDOC_OUT", ".")
os.makedirs(out_dir, exist_ok=True)
log = open(os.path.join(out_dir, "draw_state.txt"), "w", encoding="utf-8")


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
    def walk(actions):
        for a in actions:
            yield a
            if a.children:
                yield from walk(a.children)

    flags = {a.eventId: a.flags for a in walk(ctl.GetRootActions())}
    for event in (int(v) for v in os.environ["RDOC_EVENT"].split(",")):
        ctl.SetFrameEvent(event, True)
        state = ctl.GetPipelineState()
        cs = state.GetShaderReflection(rd.ShaderStage.Compute)
        if flags.get(event, 0) & rd.ActionFlags.Dispatch:
            p("event", event, "dispatch, compute shader", state.GetShader(rd.ShaderStage.Compute),
              "entry", cs.entryPoint if cs else "-")
            for u in state.GetReadOnlyResources(rd.ShaderStage.Compute, True):
                p("   reads binding", u.access.index, u.descriptor.resource)
            for u in state.GetReadWriteResources(rd.ShaderStage.Compute, True):
                p("   writes binding", u.access.index, u.descriptor.resource)
            if cs:
                targets = ctl.GetDisassemblyTargets(True)
                text = ctl.DisassembleShader(state.GetComputePipelineObject(), cs, targets[0])
                with open(os.path.join(out_dir, "cs_%d.txt" % event), "w",
                          encoding="utf-8") as f:
                    f.write(text)
            continue
        refl = state.GetShaderReflection(rd.ShaderStage.Pixel)
        p("event", event, "pixel shader", state.GetShader(rd.ShaderStage.Pixel))
        if refl:
            for sig in refl.outputSignature:
                p("   output", sig.varName, "semantic", sig.systemValue, "index", sig.regIndex,
                  "components", sig.compCount)
            targets = ctl.GetDisassemblyTargets(True)
            text = ctl.DisassembleShader(state.GetGraphicsPipelineObject(), refl, targets[0])
            with open(os.path.join(out_dir, "ps_%d.txt" % event), "w", encoding="utf-8") as f:
                f.write(text)
        else:
            p("   no pixel shader")
        for i, o in enumerate(state.GetOutputTargets()):
            p("   colour attachment", i, o.resource)
        for i, b in enumerate(state.GetColorBlends()):
            p("   blend", i, "enabled", b.enabled, "write mask", b.writeMask)
        vk = ctl.GetVulkanPipelineState()
        for v in vk.viewportScissor.viewportScissors:
            p("   viewport", "%g,%g %gx%g" % (v.vp.x, v.vp.y, v.vp.width, v.vp.height),
              "scissor", "%d,%d %dx%d" % (v.scissor.x, v.scissor.y, v.scissor.width,
                                          v.scissor.height))
        ds = vk.depthStencil
        p("   depth test", ds.depthTestEnable, "write", ds.depthWriteEnable, "func",
          ds.depthFunction, "stencil", ds.stencilTestEnable)
    ctl.Shutdown()
    cap.Shutdown()
except Exception:  # noqa: BLE001
    p(traceback.format_exc())
finally:
    log.close()
    os._exit(0)
