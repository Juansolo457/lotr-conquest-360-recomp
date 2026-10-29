// LOTRC 360 - a tee on the SDK's SDL audio output (audio_dump.h).
#define _CRT_SECURE_NO_WARNINGS
#include "audio_dump.h"

#include <chrono>
#include <cstdio>
#include <vector>

#include <rex/audio/audio_driver.h>
#include <rex/audio/conversion.h>
#include <rex/audio/downmix.h>
#include <rex/audio/sdl/sdl_audio_system.h>
#include <rex/cvar.h>
#include <rex/logging.h>

REXCVAR_DEFINE_STRING(lotrc_audio_dump, "", "LOTRC",
                      "Append the game's audio output, folded to stereo, to this file as raw "
                      "float32 PCM (2 ch, 48 kHz); <file>.txt logs the submit times")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);

using rex::X_STATUS;  // X_STATUS_SUCCESS expands to an unqualified X_STATUS cast

namespace lotrc::audio_dump {
namespace {

using Clock = std::chrono::steady_clock;

constexpr uint32_t kChannelSamples = 256;  // per frame, per channel (the SDL driver's constant)

class TeeDriver : public rex::audio::AudioDriver {
 public:
  TeeDriver(rex::memory::Memory* memory, rex::audio::AudioDriver* inner, const std::string& path)
      : AudioDriver(memory), inner_(inner), start_(Clock::now()) {
    pcm_ = std::fopen(path.c_str(), "wb");
    times_ = std::fopen((path + ".txt").c_str(), "w");
    raw6_ = std::fopen((path + ".6ch").c_str(), "wb");  // the frame as submitted: 6 x 256 BE floats
    if (!pcm_) REXLOG_ERROR("LOTRC: audio dump: can't open {}", path);
    stereo_.resize(kChannelSamples * 2);
  }
  ~TeeDriver() override {
    if (pcm_) std::fclose(pcm_);
    if (times_) std::fclose(times_);
    if (raw6_) std::fclose(raw6_);
  }

  rex::audio::AudioDriver* inner() const { return inner_; }

  void SubmitFrame(uint32_t frame_ptr) override {
    inner_->SubmitFrame(frame_ptr);
    const auto* input = memory_->TranslateVirtual<const float*>(frame_ptr);
    if (!input || !pcm_) return;
    if (raw6_) std::fwrite(input, sizeof(float), 6 * kChannelSamples, raw6_);
    rex::audio::conversion::sequential_6_BE_to_interleaved_2_LE(
        stereo_.data(), input, kChannelSamples, rex::audio::GetStereoFold(), 1.0f);
    std::fwrite(stereo_.data(), sizeof(float), stereo_.size(), pcm_);
    if (times_ && (frames_ % 64) == 0) {
      const double ms = std::chrono::duration<double, std::milli>(Clock::now() - start_).count();
      std::fprintf(times_, "%llu %.1f\n", static_cast<unsigned long long>(frames_), ms);
      std::fflush(times_);
    }
    if ((++frames_ % 1024) == 0) std::fflush(pcm_);
  }

 private:
  rex::audio::AudioDriver* inner_;
  Clock::time_point start_;
  std::FILE* pcm_ = nullptr;
  std::FILE* times_ = nullptr;
  std::FILE* raw6_ = nullptr;
  std::vector<float> stereo_;
  uint64_t frames_ = 0;
};

class TeeAudioSystem : public rex::audio::sdl::SDLAudioSystem {
 public:
  TeeAudioSystem(rex::runtime::FunctionDispatcher* dispatcher, std::string path)
      : SDLAudioSystem(dispatcher), path_(std::move(path)) {}

  rex::X_STATUS CreateDriver(size_t index, rex::thread::Semaphore* semaphore,
                        rex::audio::AudioDriver** out_driver) override {
    rex::audio::AudioDriver* inner = nullptr;
    const rex::X_STATUS status = SDLAudioSystem::CreateDriver(index, semaphore, &inner);
    if (status != X_STATUS_SUCCESS) return status;
    // One file set per client: a second client (another RegisterClient, or a Restore) would
    // otherwise truncate the first one's capture. Client 0 keeps the plain path; client n
    // writes <path>.n (and .n.txt, .n.6ch).
    std::string path = path_;
    if (index) path += "." + std::to_string(index);
    *out_driver = new TeeDriver(memory_, inner, path);
    REXLOG_INFO("LOTRC: audio dump (client {}) to {}", index, path);
    return status;
  }

  void DestroyDriver(rex::audio::AudioDriver* driver) override {
    auto* tee = dynamic_cast<TeeDriver*>(driver);
    if (!tee) {
      SDLAudioSystem::DestroyDriver(driver);
      return;
    }
    SDLAudioSystem::DestroyDriver(tee->inner());
    delete tee;
  }

 private:
  std::string path_;
};

}  // namespace

std::string Path() { return REXCVAR_GET(lotrc_audio_dump); }

void Install(rex::RuntimeConfig& config) {
  const std::string path = Path();
  if (path.empty()) return;
  config.audio_factory = [path](rex::runtime::FunctionDispatcher* dispatcher)
      -> std::unique_ptr<rex::system::IAudioSystem> {
    return std::make_unique<TeeAudioSystem>(dispatcher, path);
  };
}

}  // namespace lotrc::audio_dump
