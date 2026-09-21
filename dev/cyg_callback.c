/* dev/cyg_callback.c -- enter/exit recorder for an
 * -finstrument-functions build.
 *
 * Linked into the perf executable by dev/perf2html.sh and exported
 * (-Wl,--export-dynamic), so libcurl.so binds to this copy of the hooks
 * instead of glibc's empty ones. Single-threaded, like the perf tests.
 *
 *   PERF_TRACE_OUT=FILE   write the trace here at exit. Unset records
 *                         nothing
 *   PERF_TRACE_SKIP=N     let the first N events pass without recording them
 *
 * While sampling, the hook is a range check, two stores and a pointer bump:
 *
 *   if(next < end) { next->fn = fn; next->tsc = rdtsc | flag; ++next; }
 *
 * Bit 63 of the stamp is CYG_CALLBACKS_EXIT_BIT, so the hook ORs it in without
 * masking: rdtsc counts from boot and bit 63 is ~146 years of uptime away at
 * this box's ~2GHz. Readers mask it off (trace_to_speedscope.py's ~EXIT_BIT).
 *
 * /proc/self/maps is needed to turn an address into object + offset.
 *
 */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <x86intrin.h>

#define CYG_CALLBACKS_MAGIC 0x32475943ull
#define CYG_CALLBACKS_MAX_REC 327680u
#define CYG_CALLBACKS_EXIT_BIT (1ull << 63)

/* cyg_callback_record_t - one enter or exit, as written to the file */
typedef struct {
  uint64_t fn;
  uint64_t tsc;
} cyg_callback_record_t;

/* cyg_callbacks_t - the recorder's whole state, one static instance */
typedef struct {
  /* the records, all of them static storage */
  cyg_callback_record_t buf[CYG_CALLBACKS_MAX_REC];
  /* where the next record goes. == end: not sampling */
  cyg_callback_record_t *next;
  /* buf + CYG_CALLBACKS_MAX_REC once set up */
  cyg_callback_record_t *end;
  /* where sampling stopped, valid while next == end */
  cyg_callback_record_t *final;
  /* cyg_callback_pause() calls not yet undone */
  unsigned holds;
  /* calls passed without recording, and how many to pass */
  uint64_t idle, skip;
  /* wall clock and stamp read together, to convert ticks */
  uint64_t t0_ns, t0_tsc;
  /* PERF_TRACE_OUT, NULL records nothing */
  const char *out;
} cyg_callbacks_t;

/* the one recorder. Final starts at buf so pause/resume stay paired */
static cyg_callbacks_t s_cyg_callbacks =
    {{{0, 0}}, NULL, NULL, s_cyg_callbacks.buf, 1, 0, 0, 0, 0, NULL};

/* cyg_callback_now_ns - monotonic wall clock, paired with a stamp read */
__attribute__((cold)) static uint64_t cyg_callback_now_ns(void)
{
  struct timespec ts;
  clock_gettime(CLOCK_MONOTONIC, &ts);
  return (uint64_t)ts.tv_sec * 1000000000ull + (uint64_t)ts.tv_nsec;
}

/* cyg_callback_pause - stop recording, keeping the stop point. Nests */
__attribute__((cold)) static void cyg_callback_pause(void)
{
  cyg_callbacks_t *cb = &s_cyg_callbacks;
  if (!cb->holds++) {
    cb->final = cb->next;
    cb->next = cb->end;
  }
}

/* cyg_callback_resume - undo one pause, recording again at the last hold */
__attribute__((cold)) static void cyg_callback_resume(void)
{
  cyg_callbacks_t *cb = &s_cyg_callbacks;
  if (!--cb->holds) {
    cb->next = cb->final;
    cb->final = cb->end;
  }
}

/* cyg_callback_record - the hot path. Keep it a check, two stores, a bump */
__attribute__((always_inline, hot)) static inline void
cyg_callback_record(void *fn, uint64_t flag)
{
  cyg_callbacks_t *cb = &s_cyg_callbacks;
  // next == end when recording is disabled.
  if (cb->next < cb->end) {
    cb->next->fn = (uint64_t)fn;
    cb->next->tsc = __rdtsc() | flag;
    ++cb->next;
  } else if (++cb->idle == cb->skip) {
    cyg_callback_resume();
  }
}

/* the two hooks GCC calls, declared so the definitions are not implicit */
void __cyg_profile_func_enter(void *fn, void *site);
void __cyg_profile_func_exit(void *fn, void *site);

/* __cyg_profile_func_enter - GCC's hook on entering an instrumented body */
__attribute__((hot)) void __cyg_profile_func_enter(void *fn, void *site)
{
  (void)site;
  cyg_callback_record(fn, 0);
}

/* __cyg_profile_func_exit - GCC's hook on leaving an instrumented body */
__attribute__((hot)) void __cyg_profile_func_exit(void *fn, void *site)
{
  (void)site;
  cyg_callback_record(fn, CYG_CALLBACKS_EXIT_BIT);
}

/* cyg_callback_init - set up before main, so no fault lands in a timed call */
__attribute__((constructor)) static void cyg_callback_init(void)
{
  cyg_callbacks_t *cb = &s_cyg_callbacks;
  const char *skip_str = getenv("PERF_TRACE_SKIP");
  cb->out = getenv("PERF_TRACE_OUT");
  if (!cb->out)
    return;
  /* fault the pages in before timing */
  memset(cb->buf, 0xff, sizeof(cb->buf));
  cb->end = cb->buf + CYG_CALLBACKS_MAX_REC;
  cb->next = cb->end;
  cb->skip = skip_str ? strtoull(skip_str, NULL, 10) : 0;
  cb->t0_ns = cyg_callback_now_ns();
  cb->t0_tsc = __rdtsc();
  if (cb->skip <= cb->idle) { /* nothing left to pass */
    cb->skip = cb->idle;
    cyg_callback_resume();
  }
}

/* cyg_callback_dump - write the trace and a /proc/self/maps copy at exit */
__attribute__((destructor)) static void cyg_callback_dump(void)
{
  cyg_callbacks_t *cb = &s_cyg_callbacks;
  uint64_t hdr[8];
  char path[4096], line[4096];
  FILE *f, *maps, *copy;
  if (!cb->out)
    return;
  cyg_callback_pause();
  hdr[0] = CYG_CALLBACKS_MAGIC;
  hdr[1] = (uint64_t)(cb->final - cb->buf);
  hdr[2] = cb->idle + hdr[1];
  hdr[3] = cb->skip;
  hdr[4] = cb->t0_ns;
  hdr[5] = cb->t0_tsc;
  hdr[7] = __rdtsc();
  hdr[6] = cyg_callback_now_ns();
  f = fopen(cb->out, "wb");
  if (!f)
    return;
  fwrite(hdr, sizeof(hdr), 1, f);
  fwrite(cb->buf, sizeof(cyg_callback_record_t), (size_t)hdr[1], f);
  fclose(f);
  snprintf(path, sizeof(path), "%s.maps", cb->out);
  maps = fopen("/proc/self/maps", "r");
  copy = fopen(path, "w");
  if (maps && copy) {
    while (fgets(line, sizeof(line), maps))
      fputs(line, copy);
  }
  if (maps)
    fclose(maps);
  if (copy)
    fclose(copy);
}
