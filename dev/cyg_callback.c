/* dev/cyg_callback.c -- enter/exit recorder for a -finstrument-functions build.
 *
 * Linked into the perf executable by dev/perf2html.sh and exported
 * (-Wl,--export-dynamic), so libcurl.so binds to this copy of the hooks
 * instead of glibc's empty ones. Single-threaded, like the perf tests.
 *
 *   PERF_TRACE_OUT=FILE   write the trace here at exit; unset = nothing is recorded
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

static cyg_callback_record_t s_cyg_callbacks_buf[CYG_CALLBACKS_MAX_REC];
/* where the next record goes. == s_cyg_callbacks_end: not sampling */
static cyg_callback_record_t *s_cyg_callbacks_next;
/* s_cyg_callbacks_buf + CYG_CALLBACKS_MAX_REC once set up */
static cyg_callback_record_t *s_cyg_callbacks_end;
/* where sampling stopped, valid while next == end */
static cyg_callback_record_t *s_cyg_callbacks_final = s_cyg_callbacks_buf;
/* cyg_callback_pause() calls not yet undone */
static unsigned s_cyg_callbacks_holds = 1;
static uint64_t s_cyg_callbacks_idle, s_cyg_callbacks_skip;
static uint64_t s_cyg_callbacks_t0_ns, s_cyg_callbacks_t0_tsc;
static const char *s_cyg_callbacks_out;

__attribute__((cold))
static uint64_t cyg_callback_now_ns(void)
{
  struct timespec ts;
  clock_gettime(CLOCK_MONOTONIC, &ts);
  return (uint64_t)ts.tv_sec * 1000000000ull + (uint64_t)ts.tv_nsec;
}

__attribute__((cold))
static void cyg_callback_pause(void)
{
  if(!s_cyg_callbacks_holds++) {
    s_cyg_callbacks_final = s_cyg_callbacks_next;
    s_cyg_callbacks_next = s_cyg_callbacks_end;
  }
}

__attribute__((cold))
static void cyg_callback_resume(void)
{
  if(!--s_cyg_callbacks_holds) {
    s_cyg_callbacks_next = s_cyg_callbacks_final;
    s_cyg_callbacks_final = s_cyg_callbacks_end;
  }
}

__attribute__((always_inline, hot))
static inline void cyg_callback_record(void *fn, uint64_t flag)
{
  // next == end when recording is disabled.
  if(s_cyg_callbacks_next < s_cyg_callbacks_end) {
    s_cyg_callbacks_next->fn = (uint64_t)fn;
    s_cyg_callbacks_next->tsc = __rdtsc() | flag;
    ++s_cyg_callbacks_next;
  }
  else if(++s_cyg_callbacks_idle == s_cyg_callbacks_skip) {
    cyg_callback_resume();
  }
}

void __cyg_profile_func_enter(void *fn, void *site);
void __cyg_profile_func_exit(void *fn, void *site);

__attribute__((hot))
void __cyg_profile_func_enter(void *fn, void *site)
{
  (void)site;
  cyg_callback_record(fn, 0);
}

__attribute__((hot))
void __cyg_profile_func_exit(void *fn, void *site)
{
  (void)site;
  cyg_callback_record(fn, CYG_CALLBACKS_EXIT_BIT);
}

__attribute__((cold))
static void cyg_callback_smoketest(void)
{
  const char *bad = NULL;
  cyg_callback_record_t *fn0 = (cyg_callback_record_t *)&s_cyg_callbacks_buf;
  uint64_t tsc_a, tsc_b;

  if(s_cyg_callbacks_next != s_cyg_callbacks_end)
    bad = "sampling is already on";
  else if(s_cyg_callbacks_holds != 1)
    bad = "holds is not 1";
  else if(s_cyg_callbacks_end != s_cyg_callbacks_buf + CYG_CALLBACKS_MAX_REC)
    bad = "end does not close the buffer";

  /* an event while paused only bumps idle, it records nothing */
  if(!bad) {
    s_cyg_callbacks_skip = 0; /* cannot match ++idle below */
    __cyg_profile_func_enter(fn0, NULL);
    if(s_cyg_callbacks_idle != 1)
      bad = "a paused event did not count as idle";
    else if(s_cyg_callbacks_next != s_cyg_callbacks_end)
      bad = "a paused event turned sampling on";
  }

  /* idle reaching skip opens the window at final, i.e. at buf */
  if(!bad) {
    s_cyg_callbacks_skip = 2;
    __cyg_profile_func_enter(fn0, NULL);
    if(s_cyg_callbacks_next != s_cyg_callbacks_buf)
      bad = "reaching skip did not open the window";
  }

  /* recording stores fn and a rising tsc, and sets EXIT_BIT on exits only */
  if(!bad) {
    tsc_a = __rdtsc();
    __cyg_profile_func_enter(fn0, NULL);
    __cyg_profile_func_exit(fn0, NULL);
    tsc_b = __rdtsc();
    if(s_cyg_callbacks_next != s_cyg_callbacks_buf + 2)
      bad = "two events did not store two records";
    else if(s_cyg_callbacks_buf[0].fn != (uint64_t)fn0)
      bad = "a record did not keep its function address";
    else if(s_cyg_callbacks_buf[0].tsc & CYG_CALLBACKS_EXIT_BIT)
      bad = "an enter was flagged as an exit";
    else if(!(s_cyg_callbacks_buf[1].tsc & CYG_CALLBACKS_EXIT_BIT))
      bad = "an exit was not flagged as one";
    else if(s_cyg_callbacks_buf[0].tsc < tsc_a ||
            (s_cyg_callbacks_buf[1].tsc & ~CYG_CALLBACKS_EXIT_BIT) > tsc_b ||
            (s_cyg_callbacks_buf[1].tsc & ~CYG_CALLBACKS_EXIT_BIT) <=
              s_cyg_callbacks_buf[0].tsc)
      bad = "stamps are not rising inside the call";
  }

  /* pause/resume nest: the inner pair must not re-enable sampling */
  if(!bad) {
    cyg_callback_pause();
    cyg_callback_pause();
    cyg_callback_resume();
    if(s_cyg_callbacks_next != s_cyg_callbacks_end)
      bad = "a nested pause/resume left sampling on";
    cyg_callback_resume();
    if(s_cyg_callbacks_next != s_cyg_callbacks_buf + 2)
      bad = "the outer resume did not restore the window";
  }

  if(bad) {
    fprintf(stderr, "cyg_callback: smoketest failed: %s\n", bad);
    exit(1);
  }

  cyg_callback_pause();
  s_cyg_callbacks_next = s_cyg_callbacks_end;
  s_cyg_callbacks_final = s_cyg_callbacks_buf;
  s_cyg_callbacks_holds = 1;
  s_cyg_callbacks_idle = 0;
  s_cyg_callbacks_skip = 0;
  memset(s_cyg_callbacks_buf, 0xff, 2 * sizeof(*s_cyg_callbacks_buf));
}

__attribute__((constructor))
static void cyg_callback_init(void)
{
  const char *skip_str = getenv("PERF_TRACE_SKIP");
  s_cyg_callbacks_out = getenv("PERF_TRACE_OUT");
  if(!s_cyg_callbacks_out)
    return;
  /* fault the pages in before timing */
  memset(s_cyg_callbacks_buf, 0xff, sizeof(s_cyg_callbacks_buf));
  s_cyg_callbacks_end = s_cyg_callbacks_buf + CYG_CALLBACKS_MAX_REC;
  s_cyg_callbacks_next = s_cyg_callbacks_end;
  cyg_callback_smoketest();
  s_cyg_callbacks_skip = skip_str ? strtoull(skip_str, NULL, 10) : 0;
  s_cyg_callbacks_t0_ns = cyg_callback_now_ns();
  s_cyg_callbacks_t0_tsc = __rdtsc();
  if(s_cyg_callbacks_skip <= s_cyg_callbacks_idle) { /* nothing left to pass */
    s_cyg_callbacks_skip = s_cyg_callbacks_idle;
    cyg_callback_resume();
  }
}

__attribute__((destructor))
static void cyg_callback_dump(void)
{
  uint64_t hdr[8];
  char path[4096], line[4096];
  FILE *f, *maps, *copy;
  if(!s_cyg_callbacks_out)
    return;
  cyg_callback_pause();
  hdr[0] = CYG_CALLBACKS_MAGIC;
  hdr[1] = (uint64_t)(s_cyg_callbacks_final - s_cyg_callbacks_buf);
  hdr[2] = s_cyg_callbacks_idle + hdr[1];
  hdr[3] = s_cyg_callbacks_skip;
  hdr[4] = s_cyg_callbacks_t0_ns;
  hdr[5] = s_cyg_callbacks_t0_tsc;
  hdr[7] = __rdtsc();
  hdr[6] = cyg_callback_now_ns();
  f = fopen(s_cyg_callbacks_out, "wb");
  if(!f)
    return;
  fwrite(hdr, sizeof(hdr), 1, f);
  fwrite(s_cyg_callbacks_buf, sizeof(cyg_callback_record_t), (size_t)hdr[1], f);
  fclose(f);
  snprintf(path, sizeof(path), "%s.maps", s_cyg_callbacks_out);
  maps = fopen("/proc/self/maps", "r");
  copy = fopen(path, "w");
  if(maps && copy) {
    while(fgets(line, sizeof(line), maps))
      fputs(line, copy);
  }
  if(maps)
    fclose(maps);
  if(copy)
    fclose(copy);
}
