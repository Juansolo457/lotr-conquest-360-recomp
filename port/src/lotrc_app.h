// lotrc - LOTR: Conquest (Xbox 360), ReXGlue application.
//
// Vulkan is the only render API: the SDK this links is built with REXGLUE_USE_D3D12=OFF
// (tools/setup.ps1), and the Xenos renderer plugin is loaded asking for its Vulkan backend by
// name, so a D3D12 plugin dropped beside the program can't be picked up by mistake.

#pragma once

#include <filesystem>
#include <memory>
#include <string>

#include <rex/cvar.h>
#include <rex/input/device_assignment.h>
#include <rex/input/input_system.h>
#include <rex/logging.h>
#include <rex/rex_app.h>
#include <rex/runtime.h>
#include <rex/system/gpu_plugin.h>
#include <rex/ui/imgui_dialog.h>
#include <rex/ui/keybinds.h>
#include <rex/ui/window.h>

#include "audio_dump.h"
#include "autopilot.h"
#include "crash_report.h"
#include "ui_pad.h"
#include "ui_style.h"

void LotrcRaiseTimerResolution();  // timer_resolution.cpp
void LotrcRequestRenderDocCapture();  // frame_timing.cpp

// The runtime signs in only player 1 and gives controllers player slots in connection order. A
// virtual XInput device (Logitech's, Steam Input's) can take slot 0 and leave the real pad as an
// unsigned player 2, so by default every controller and the keyboard drive player 1.
REXCVAR_DEFINE_BOOL(lotrc_shared_controllers, true, "LOTRC",
                    "Every connected controller (and the keyboard) drives player 1, the "
                    "signed-in profile; off = one controller per player slot")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);

class LotrConquestApp : public rex::ReXApp {
 public:
  using rex::ReXApp::ReXApp;

  static std::unique_ptr<rex::ui::WindowedApp> Create(rex::ui::WindowedAppContext& ctx) {
    return std::unique_ptr<LotrConquestApp>(new LotrConquestApp(ctx, "lotrc", PPCImageConfig));
  }

 protected:
  // A packaged copy (game\ = the disc's files, user\ = profile and saves beside the program)
  // runs without command-line paths.
  void OnConfigurePaths(rex::PathConfig& paths) override {
    std::error_code error;
    const auto own_dir = std::filesystem::current_path(error);
    if (paths.game_data_root.empty() && std::filesystem::is_directory(own_dir / "game", error)) {
      paths.game_data_root = own_dir / "game";
    }
    if (REXCVAR_GET(user_data_root).empty() &&
        std::filesystem::is_directory(own_dir / "user", error)) {
      paths.user_data_root = own_dir / "user";
      paths.cache_root = own_dir / "user" / "cache";
    }
  }

  void OnPreSetup(rex::RuntimeConfig& config) override {
    LotrcRaiseTimerResolution();
    lotrc::crash_report::InstallCrashReporter();

    // Without a GPU plugin the runtime ignores every Vd* call and the game never draws. Load
    // the Xenos plugin's Vulkan backend ourselves; ReXApp would ask for "any".
    if (config.gpu_plugin.empty()) config.gpu_plugin = "xenos";
    if (!config.graphics) {
      config.graphics = rex::system::LoadGpuPlugin(config.gpu_plugin, "vulkan");
      if (config.graphics) {
        // Until the native renderer (native/, docs/PLAN.md M2) draws, the plugin's emulated
        // Vulkan renderer draws: a bring-up step only, never what ships. With the native
        // renderer the plugin keeps the command ring and the presenter (--gpu_skip_draws).
        REXLOG_INFO("LOTRC: GPU plugin '{}', Vulkan backend", config.gpu_plugin);
        // The game reads its own resolves back on the CPU (its exposure control reads the
        // scene's measured luminance out of a resolve). Without the readback guest memory
        // keeps stale values, the exposure runs away and every level is white, HUD aside;
        // Xenia users hit the same and set d3d12_readback_resolve. "fast" copies each
        // resolve's result back one frame late and the levels keep the game's 30 Hz
        // (docs/HANDOFF.md, runs 4-6). The option lives in the plugin, so it is set by name
        // once the plugin is loaded; a value given on the command line, the environment or a
        // config file (--readback_resolve=none|some|full) is already applied then and is kept,
        // "none" included: the source is checked, not the value, since "none" is the SDK's
        // default.
        if (rex::cvar::GetFlagSource("readback_resolve") == rex::cvar::Source::kDefault) {
          rex::cvar::SetFlagByName("readback_resolve", "fast");
        }
        REXLOG_INFO("LOTRC: resolve readback '{}'", rex::cvar::GetFlagByName("readback_resolve"));
      } else {
        REXLOG_ERROR("LOTRC: GPU plugin '{}' has no Vulkan backend", config.gpu_plugin);
      }
    }

    lotrc::audio_dump::Install(config);  // --lotrc_audio_dump <file>: records the audio output

    if (config.input_factory) {
      config.input_factory = [base = config.input_factory](bool tool_mode) {
        auto input = base(tool_mode);
        if (auto* system = dynamic_cast<rex::input::InputSystem*>(input.get())) {
          if (REXCVAR_GET(lotrc_shared_controllers)) {
            system->SetDeviceAssignment(std::make_unique<rex::input::SharedAssignment>());
            REXLOG_INFO("LOTRC: every controller drives player 1");
          } else {
            system->SetDeviceAssignment(lotrc::autopilot::CreatePlayerSlots());
            REXLOG_INFO("LOTRC: one controller per player slot");
          }
          if (auto autopilot = lotrc::autopilot::Create()) system->AddDriver(std::move(autopilot));
        }
        return input;
      };
    }
  }

  void OnPostSetup() override {
    if (auto* w = window()) w->SetTitle("LOTR: Conquest (Xbox 360)");
    // Under RenderDoc (tools/rdoc_capture.ps1 -Play), capture the next two game frames.
    rex::ui::RegisterBind("bind_q4_rdoc_capture", "F9",
                          "Capture the next game frames in RenderDoc",
                          [] { LotrcRequestRenderDocCapture(); });
  }

  void OnConfigureFonts(ImFontAtlas* atlas) override { lotrc::ui::AddFonts(atlas); }
  void OnConfigureStyle(ImGuiStyle& imgui_style, rex::ui::Style& ui_style) override {
    (void)ui_style;
    lotrc::ui::ScaleStyle(imgui_style);
  }

  void OnCreateDialogs(rex::ui::ImGuiDrawer* drawer) override {
    pad_bridge_ = lotrc::ui::CreatePadBridge(drawer);
  }
  void OnShutdown() override { pad_bridge_.reset(); }

 private:
  std::unique_ptr<rex::ui::ImGuiDialog> pad_bridge_;
};
