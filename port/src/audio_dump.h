// LOTRC 360 - a tee on the SDK's SDL audio output, for audio bugs that need a recording.
//
// --lotrc_audio_dump <file> wraps the SDL audio system: every frame the game submits (6
// channels x 256 float samples at 48 kHz, big-endian, sequential by channel) still goes to SDL,
// and the same frame folded to stereo the way the SDL driver folds it for a 2-channel endpoint
// is appended to <file> as raw interleaved 32-bit float PCM, 2 channels, 48 kHz (no header: the
// process is usually killed by the smoke script). <file>.txt gets one line per 64 frames with
// the frame index and the host time in ms, so starvation gaps (frames the game didn't submit)
// show as a frame rate below 187.5/s. <file>.6ch is every frame as submitted (6 x 256
// big-endian floats, channel-sequential: FL FR FC LFE BL BR), for per-channel analysis.
//   python tools/audio_report.py private/audio.f32 [private/audio.f32.txt]
#pragma once

#include <functional>
#include <memory>
#include <string>

#include <rex/runtime.h>

namespace lotrc::audio_dump {

// The path from --lotrc_audio_dump, empty when off.
std::string Path();

// Wraps config.audio_factory so the dump sees every submitted frame. No-op when Path() is empty.
void Install(rex::RuntimeConfig& config);

}  // namespace lotrc::audio_dump
