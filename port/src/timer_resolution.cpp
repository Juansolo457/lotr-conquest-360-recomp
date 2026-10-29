// LOTRC 360 - a finer Windows timer (from graw360-recomp's frame_timing.cpp).
//
// Windows' default timer resolution is 15.6 ms and nothing in the runtime raises it, so every
// Sleep(1) in it (the guest vblank thread, the command processor's waits, the game's own
// KeDelayExecutionThread) can sleep up to 15.6 ms, which makes vblanks late and frames uneven.
// Also asks Windows 11 to keep honouring it while the window is in the background.

#include <cstdint>

#include <rex/cvar.h>
#include <rex/logging.h>

REXCVAR_DEFINE_INT32(lotrc_timer_resolution_us, 500, "LOTRC",
                     "Windows timer resolution to request at start-up, in microseconds (0 = leave "
                     "the system default of 15.6 ms)")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);

#if defined(_WIN32)
#define WIN32_LEAN_AND_MEAN
#include <windows.h>

void LotrcRaiseTimerResolution() {
  const int32_t requested_us = REXCVAR_GET(lotrc_timer_resolution_us);
  if (requested_us <= 0) return;
  PROCESS_POWER_THROTTLING_STATE throttling{};
  throttling.Version = PROCESS_POWER_THROTTLING_CURRENT_VERSION;
  throttling.ControlMask = PROCESS_POWER_THROTTLING_IGNORE_TIMER_RESOLUTION;
  throttling.StateMask = 0;
  SetProcessInformation(GetCurrentProcess(), ProcessPowerThrottling, &throttling,
                        sizeof(throttling));
  using SetResolution = LONG(WINAPI*)(ULONG desired, BOOLEAN set, ULONG* current);
  auto set_resolution = reinterpret_cast<SetResolution>(
      GetProcAddress(GetModuleHandleW(L"ntdll.dll"), "NtSetTimerResolution"));
  ULONG current = 0;  // in 100 ns units
  if (set_resolution && set_resolution(ULONG(requested_us) * 10, TRUE, &current) >= 0) {
    REXLOG_INFO("LOTRC: timer resolution {} us (requested {} us)", current / 10, requested_us);
  } else {
    REXLOG_WARN("LOTRC: couldn't raise the timer resolution; frame pacing may be uneven");
  }
}
#else
void LotrcRaiseTimerResolution() {}
#endif
