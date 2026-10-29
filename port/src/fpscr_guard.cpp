// LOTR: Conquest 360 - keep floating-point exceptions masked when the game writes the FPSCR.
// From graw360-recomp (port/src/fpscr_guard.cpp), where the same bug killed GRAW's campaign.
//
// ReXGlue keeps each context's host MXCSR in a cached value (ctx.fpscr.csr) and writes the whole
// value to the CPU whenever the translated code changes the flush mode (enableFlushMode /
// disableFlushMode around vector code) or the rounding mode (mtfsf -> storeFromGuest). Guest
// threads seed it with InitHost(): every exception masked. The audio worker's context, which
// runs the game's mixer callback, is not seeded, so its cached value is 0 and the mixer's first
// vector op writes MXCSR with every FP exception unmasked.
//
// Quake 4's and GRAW's first boots died that way (C000008F on the audio worker). Kept here
// ready: if a boot dies with an FP exception on the audio thread, hook LotrcGuardFpscr at the
// callback's entry and before each mtfsf ([[entrypoint.midasm_hook]] in lotrc_manifest.toml,
// as in ../quake4-360-recomp). It seeds the context the way InitHost does: the current MXCSR
// with every exception masked.

#include <rex/ppc/context.h>
#include <rex/system/thread_state.h>

void LotrcGuardFpscr() {
  PPCContext* ctx = rex::runtime::current_ppc_context();
  if (!ctx) return;
  ctx->fpscr.InitHost();
}
