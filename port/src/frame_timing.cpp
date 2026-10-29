// LOTRC 360 - the game's own frame rate (from graw360-recomp's frame_timing.cpp).
//
// The host presenter runs at the display's rate and repeats the last guest frame, so the log's
// presents say nothing about how fast the game itself runs. LotrcFrameMark runs just before the
// game's one call to VdSwap (sub_82705D50 at 0x82705FD4, an [[entrypoint.midasm_hook]] in the
// manifest), records the time since the previous one, and:
//  - every 10 s logs "LOTRC frames: ..." with the average fps, median, 1% low, the slowest
//    frame, and how many frames took a 60 Hz or 30 Hz vblank's time;
//  - with --lotrc_frame_log=<file>, writes one CSV row per frame (frame_time_us), the format
//    graw360-recomp's tools/perf_report.py reads.

#include <algorithm>
#include <atomic>
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <mutex>
#include <string>
#include <vector>

#include <rex/cvar.h>
#include <rex/logging.h>

#include <renderdoc/renderdoc_app.h>
#if defined(_WIN32)
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#else
#include <dlfcn.h>
#endif

REXCVAR_DEFINE_STRING(lotrc_frame_log, "", "LOTRC",
                      "Write one CSV row per game frame (frame_time_us) to this file")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);

// Unattended RenderDoc captures (tools/rdoc_capture.ps1): when the game runs under RenderDoc,
// trigger one capture at each of these times (seconds from the first frame, comma-separated).
// Without RenderDoc in the process nothing happens. F9 (bind_q4_rdoc_capture, lotrc_app.h)
// triggers one more at any moment, for a player driving the game to a bug.
REXCVAR_DEFINE_STRING(lotrc_rdoc_capture_at, "", "LOTRC",
                      "Seconds from the first game frame at which to trigger a RenderDoc capture "
                      "each (comma-separated; needs RenderDoc in the process)")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);

namespace {

using Clock = std::chrono::steady_clock;

std::mutex g_mutex;
std::atomic<bool> g_capture_requested{false};
Clock::time_point g_last{}, g_window_start{};
std::vector<uint32_t> g_window;  // frame times (us) in the current 10 s window
FILE* g_csv = nullptr;
bool g_csv_tried = false;
uint64_t g_frames = 0;

void Summarise() {
  if (g_window.empty()) return;
  std::vector<uint32_t> s = g_window;
  std::sort(s.begin(), s.end());
  double total = 0;
  for (uint32_t t : s) total += t;
  const double median = s[s.size() / 2] / 1000.0;
  const double low = s[std::min(s.size() - 1, s.size() * 99 / 100)] / 1000.0;
  size_t at60 = 0, at30 = 0;
  for (uint32_t t : s) {
    if (t >= 15500 && t < 17500) ++at60;
    if (t >= 31500 && t < 35500) ++at30;
  }
  REXLOG_INFO(
      "LOTRC frames: {:.1f} fps average over {} frames, median {:.2f} ms ({:.1f} fps), 1% low "
      "{:.1f} fps, slowest {:.1f} ms; at 60 Hz vblank {:.0f}%, at 30 Hz {:.0f}%",
      s.size() / (total / 1e6), s.size(), median, 1000.0 / median, 1000.0 / low,
      s.back() / 1000.0, 100.0 * at60 / s.size(), 100.0 * at30 / s.size());
  g_window.clear();
}

RENDERDOC_API_1_0_1* RenderDoc() {
  static RENDERDOC_API_1_0_1* api = [] {
    RENDERDOC_API_1_0_1* result = nullptr;
    pRENDERDOC_GetAPI get_api = nullptr;
#if defined(_WIN32)
    if (HMODULE module = GetModuleHandleA("renderdoc.dll")) {
      get_api = reinterpret_cast<pRENDERDOC_GetAPI>(GetProcAddress(module, "RENDERDOC_GetAPI"));
    }
#else
    if (void* module = dlopen("librenderdoc.so", RTLD_NOW | RTLD_NOLOAD)) {
      get_api = reinterpret_cast<pRENDERDOC_GetAPI>(dlsym(module, "RENDERDOC_GetAPI"));
    }
#endif
    if (!get_api || !get_api(eRENDERDOC_API_Version_1_0_1, reinterpret_cast<void**>(&result))) {
      result = nullptr;
    }
    return result;
  }();
  return api;
}

std::vector<double> CaptureTimes() {
  std::vector<double> times;
  std::string list = REXCVAR_GET(lotrc_rdoc_capture_at);
  size_t pos = 0;
  while (pos < list.size()) {
    size_t end = list.find(',', pos);
    if (end == std::string::npos) end = list.size();
    try {
      times.push_back(std::stod(list.substr(pos, end - pos)));
    } catch (...) {
    }
    pos = end + 1;
  }
  std::sort(times.begin(), times.end());
  if (!list.empty()) {
    REXLOG_INFO("LOTRC: RenderDoc capture times '{}' ({} parsed)", list, times.size());
  }
  return times;
}

void MaybeTriggerCapture(Clock::time_point now) {
  // A capture spans two game frames (StartFrameCapture at one VdSwap, EndFrameCapture two
  // later): RenderDoc's own frame boundary is the presenter's swapchain present, which holds only
  // the final blit, while the game's draws come from the renderer thread in between.
  static const std::vector<double> times = CaptureTimes();
  static size_t next = 0;
  static int frames_left = 0;
  static Clock::time_point first = now;
  RENDERDOC_API_1_0_1* api = RenderDoc();
  if (frames_left > 0 && --frames_left == 0) {
    api->EndFrameCapture(nullptr, nullptr);
    REXLOG_INFO("LOTRC: RenderDoc capture ended");
  }
  const double elapsed = std::chrono::duration<double>(now - first).count();
  if (frames_left > 0) return;
  const bool requested = g_capture_requested.exchange(false);
  if (!requested) {
    if (next >= times.size() || elapsed < times[next]) return;
    ++next;
  }
  if (api) {
    api->StartFrameCapture(nullptr, nullptr);
    frames_left = 2;
    REXLOG_INFO("LOTRC: RenderDoc capture started at {:.1f} s{}", elapsed,
                requested ? " (hotkey)" : "");
  } else {
    REXLOG_WARN("LOTRC: RenderDoc capture asked for but RenderDoc isn't in the process "
                "(tools/rdoc_capture.ps1 starts the game under it)");
  }
}

}  // namespace

// The capture hotkey: the capture starts at the next game frame.
void LotrcRequestRenderDocCapture() {
  g_capture_requested.store(true);
  REXLOG_INFO("LOTRC: RenderDoc capture requested (hotkey)");
}

void LotrcFrameMark() {
  const Clock::time_point now = Clock::now();
  std::lock_guard<std::mutex> lock(g_mutex);
  MaybeTriggerCapture(now);
  if (!g_csv_tried) {
    g_csv_tried = true;
    const std::string path = REXCVAR_GET(lotrc_frame_log);
    if (!path.empty()) {
      g_csv = std::fopen(path.c_str(), "w");
      if (g_csv) std::fputs("frame_time_us\n", g_csv);
    }
  }
  if (g_last == Clock::time_point{}) {
    g_last = g_window_start = now;
    return;
  }
  const auto us = std::chrono::duration_cast<std::chrono::microseconds>(now - g_last).count();
  g_last = now;
  const uint32_t t = static_cast<uint32_t>(std::min<int64_t>(us, 10'000'000));
  g_window.push_back(t);
  if (g_csv) {
    std::fprintf(g_csv, "%u\n", t);
    if (++g_frames % 120 == 0) std::fflush(g_csv);
  }
  if (now - g_window_start >= std::chrono::seconds(10)) {
    Summarise();
    g_window_start = now;
  }
}
