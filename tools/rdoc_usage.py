# Run inside RenderDoc (qrenderdoc --python tools/rdoc_usage.py) with env vars:
#   RDOC_RDC = capture path, RDOC_OUT = output folder (private),
#   RDOC_RES = resource ids, comma-separated (the number in ResourceId::<n>)
# For each resource: every event that uses it (event id, usage, the action's name), so the
# writer of a frame texture and the readers of a resolve can be followed.
import os
import traceback

import renderdoc as rd

out_dir = os.environ.get("RDOC_OUT", ".")
os.makedirs(out_dir, exist_ok=True)
log = open(os.path.join(out_dir, "usage.txt"), "w", encoding="utf-8")


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
    by_event = {a.eventId: a for a in walk(ctl.GetRootActions())}
    wanted = {int(v) for v in os.environ["RDOC_RES"].split(",")}
    resources = {int(str(r.resourceId).replace("ResourceId::", "")): r.resourceId
                 for r in ctl.GetResources()}
    for n in sorted(wanted):
        rid = resources.get(n)
        p("resource", n, "found" if rid else "missing")
        if not rid:
            continue
        for u in ctl.GetUsage(rid):
            a = by_event.get(u.eventId)
            p("   event", u.eventId, u.usage, a.GetName(sfile) if a else "(not an action)")
    ctl.Shutdown()
    cap.Shutdown()
except Exception:  # noqa: BLE001
    p(traceback.format_exc())
finally:
    log.close()
    os._exit(0)
