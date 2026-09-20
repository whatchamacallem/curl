/* dev/cyg_callback.c -- enter/exit recorder for an
 * -finstrument-functions build.
 *
 * Linked into the perf executable by dev/perf2html.sh and exported
 * (-Wl,--export-dynamic), so libcurl.so binds to this copy of the hooks
 * instead of glibc's empty ones. Single-threaded, like the perf tests.
 *
 *   PERF_TRACE_OUT=FILE   write the trace here at exit; unset records
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
#define CYG_CALLBACKS_MAX_REC 16384u
#define CYG_CALLBACKS_EXIT_BIT (1ull << 63)

typedef struct {
  uint64_t fn;
  uint64_t tsc;
} cyg_callback_record_t;

typedef struct {
  cyg_callback_record_t buf[CYG_CALLBACKS_MAX_REC];
  /* where the next record goes. == end: not sampling */
  cyg_callback_record_t *next;
  /* buf + CYG_CALLBACKS_MAX_REC once set up */
  cyg_callback_record_t *end;
  /* where sampling stopped, valid while next == end */
  cyg_callback_record_t *final;
  /* cyg_callback_pause() calls not yet undone */
  unsigned holds;
  uint64_t idle, skip;
  uint64_t t0_ns, t0_tsc;
  const char *out;
} cyg_callbacks_t;

static cyg_callbacks_t s_cyg_callbacks =
    {{{0, 0}}, NULL, NULL, s_cyg_callbacks.buf, 1, 0, 0, 0, 0, NULL};

__attribute__((cold)) static uint64_t cyg_callback_now_ns(void)
{
  struct timespec ts;
  clock_gettime(CLOCK_MONOTONIC, &ts);
  return (uint64_t)ts.tv_sec * 1000000000ull + (uint64_t)ts.tv_nsec;
}

__attribute__((cold)) static void cyg_callback_pause(void)
{
  cyg_callbacks_t *cb = &s_cyg_callbacks;
  if (!cb->holds++) {
    cb->final = cb->next;
    cb->next = cb->end;
  }
}

__attribute__((cold)) static void cyg_callback_resume(void)
{
  cyg_callbacks_t *cb = &s_cyg_callbacks;
  if (!--cb->holds) {
    cb->next = cb->final;
    cb->final = cb->end;
  }
}

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

void __cyg_profile_func_enter(void *fn, void *site);
void __cyg_profile_func_exit(void *fn, void *site);

__attribute__((hot)) void __cyg_profile_func_enter(void *fn, void *site)
{
  (void)site;
  cyg_callback_record(fn, 0);
}

__attribute__((hot)) void __cyg_profile_func_exit(void *fn, void *site)
{
  (void)site;
  cyg_callback_record(fn, CYG_CALLBACKS_EXIT_BIT);
}

__attribute__((cold)) static void cyg_callback_smoketest(void)
{
  cyg_callbacks_t *cb = &s_cyg_callbacks;
  const char *bad = NULL;
  cyg_callback_record_t *fn0 = (cyg_callback_record_t *)&cb->buf;
  uint64_t tsc_a, tsc_b;

  if (cb->next != cb->end)
    bad = "sampling is already on";
  else if (cb->holds != 1)
    bad = "holds is not 1";
  else if (cb->end != cb->buf + CYG_CALLBACKS_MAX_REC)
    bad = "end does not close the buffer";

  /* an event while paused only bumps idle, it records nothing */
  if (!bad) {
    cb->skip = 0; /* cannot match ++idle below */
    __cyg_profile_func_enter(fn0, NULL);
    if (cb->idle != 1)
      bad = "a paused event did not count as idle";
    else if (cb->next != cb->end)
      bad = "a paused event turned sampling on";
  }

  /* idle reaching skip opens the window at final, i.e. at buf */
  if (!bad) {
    cb->skip = 2;
    __cyg_profile_func_enter(fn0, NULL);
    if (cb->next != cb->buf)
      bad = "reaching skip did not open the window";
  }

  /* recording stores fn and a rising tsc, and sets EXIT_BIT on exits only */
  if (!bad) {
    tsc_a = __rdtsc();
    __cyg_profile_func_enter(fn0, NULL);
    __cyg_profile_func_exit(fn0, NULL);
    tsc_b = __rdtsc();
    if (cb->next != cb->buf + 2)
      bad = "two events did not store two records";
    else if (cb->buf[0].fn != (uint64_t)fn0)
      bad = "a record did not keep its function address";
    else if (cb->buf[0].tsc & CYG_CALLBACKS_EXIT_BIT)
      bad = "an enter was flagged as an exit";
    else if (!(cb->buf[1].tsc & CYG_CALLBACKS_EXIT_BIT))
      bad = "an exit was not flagged as one";
    else if (cb->buf[0].tsc < tsc_a
             || (cb->buf[1].tsc & ~CYG_CALLBACKS_EXIT_BIT) > tsc_b
             || (cb->buf[1].tsc & ~CYG_CALLBACKS_EXIT_BIT) <= cb->buf[0].tsc)
      bad = "stamps are not rising inside the call";
  }

  /* pause/resume nest: the inner pair must not re-enable sampling */
  if (!bad) {
    cyg_callback_pause();
    cyg_callback_pause();
    cyg_callback_resume();
    if (cb->next != cb->end)
      bad = "a nested pause/resume left sampling on";
    cyg_callback_resume();
    if (cb->next != cb->buf + 2)
      bad = "the outer resume did not restore the window";
  }

  if (bad) {
    fprintf(stderr, "cyg_callback: smoketest failed: %s\n", bad);
    exit(1);
  }

  cyg_callback_pause();
  cb->next = cb->end;
  cb->final = cb->buf;
  cb->holds = 1;
  cb->idle = 0;
  cb->skip = 0;
  memset(cb->buf, 0xff, 2 * sizeof(*cb->buf));
}

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
  cyg_callback_smoketest();
  cb->skip = skip_str ? strtoull(skip_str, NULL, 10) : 0;
  cb->t0_ns = cyg_callback_now_ns();
  cb->t0_tsc = __rdtsc();
  if (cb->skip <= cb->idle) { /* nothing left to pass */
    cb->skip = cb->idle;
    cyg_callback_resume();
  }
}

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
