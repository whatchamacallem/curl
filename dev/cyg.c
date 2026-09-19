/* dev/cyg.c -- enter/exit cyg_recorder for a -finstrument-functions build.
 *
 * Linked into the perf executable by dev/perf2html.sh and exported
 * (-Wl,--export-dynamic), so libcurl.so binds to this copy of the hooks
 * instead of glibc's empty ones. Single-threaded, like the perf tests.
 *
 *   CYG_OUT=FILE   write the trace here at exit; unset = nothing is cyg_recorded
 *   CYG_SKIP=N     let the first N events pass without cyg_recording them
 *
 * While sampling, the hook is a range check, two stores and a pointer bump:
 *
 *   if(next < end) { next->fn = fn; next->tsc = rdtsc | flag; ++next; }
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

#define MAGIC 0x32475943ull
#define MAX_REC 16384u
#define EXIT_BIT (1ull << 63)

typedef struct {
  uint64_t fn;
  uint64_t tsc;
} rec_t;

static rec_t buf[MAX_REC];
static rec_t *next;        /* where the next record goes; == end: not sampling */
static rec_t *end;         /* buf + MAX_REC once set up */
static rec_t *final = buf; /* where sampling stopped, valid while next == end */
static unsigned holds = 1; /* cyg_pause() calls not yet undone */
static uint64_t idle, skip, t0_ns, t0_tsc;
static const char *out;

__attribute__((cold)) 
static uint64_t cyg_now_ns(void)
{
  struct timespec ts;
  clock_gettime(CLOCK_MONOTONIC, &ts);
  return (uint64_t)ts.tv_sec * 1000000000ull + (uint64_t)ts.tv_nsec;
}

__attribute__((cold)) 
static void cyg_pause(void)
{
  if(!holds++) {
    final = next;
    next = end;
  }
}

__attribute__((cold)) 
static void cyg_resume(void)
{
  if(!--holds) {
    next = final;
    final = end;
  }
}

__attribute__((always_inline, hot))
static inline void cyg_record(void *fn, uint64_t flag)
{
  // next == end when recording is disabled.
  if(next < end) {
    next->fn = (uint64_t)fn;
    next->tsc = __rdtsc() | flag;
    ++next;
  }
  else if(++idle == skip) {
    cyg_resume();
  }
}

void __cyg_profile_func_enter(void *fn, void *site);
void __cyg_profile_func_exit(void *fn, void *site);

__attribute__((hot))
void __cyg_profile_func_enter(void *fn, void *site)
{
  (void)site;
  cyg_record(fn, 0);
}

__attribute__((hot))
void __cyg_profile_func_exit(void *fn, void *site)
{
  (void)site;
  cyg_record(fn, EXIT_BIT);
}

__attribute__((constructor))
static void cyg_init(void)
{
  const char *skip_str = getenv("CYG_SKIP");
  out = getenv("CYG_OUT");
  if(!out)
    return;
  memset(buf, 0xff, sizeof(buf)); /* fault the pages in before timing */
  end = buf + MAX_REC;
  next = end;
  skip = skip_str ? strtoull(skip_str, NULL, 10) : 0;
  t0_ns = cyg_now_ns();
  t0_tsc = __rdtsc();
  if(skip <= idle) { /* nothing left to let pass */
    skip = idle;
    cyg_resume();
  }
}

__attribute__((destructor))
static void cyg_dump(void)
{
  uint64_t hdr[8];
  char path[4096], line[4096];
  FILE *f, *maps, *copy;
  if(!out)
    return;
  cyg_pause();
  hdr[0] = MAGIC;
  hdr[1] = (uint64_t)(final - buf);
  hdr[2] = idle + hdr[1];
  hdr[3] = skip;
  hdr[4] = t0_ns;
  hdr[5] = t0_tsc;
  hdr[7] = __rdtsc();
  hdr[6] = cyg_now_ns();
  f = fopen(out, "wb");
  if(!f)
    return;
  fwrite(hdr, sizeof(hdr), 1, f);
  fwrite(buf, sizeof(rec_t), (size_t)hdr[1], f);
  fclose(f);
  snprintf(path, sizeof(path), "%s.maps", out);
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
