<!--
Copyright (C) Daniel Stenberg, <daniel@haxx.se>, et al.

SPDX-License-Identifier: curl
-->

# AVXX: vectorized routines in libcurl (working plan, branch `dev-vec`)

This file is a working plan for the `dev-vec` branch only. It is not part of
the upstream submission and is removed from the branch before any pull
request is opened. Everything it describes is written so that the resulting
diff looks like it was always part of curl: same option scheme as the other
experimental features, same file layout, same test and doc obligations.

Baseline measured on this branch (master `f4caaa2`, GCC 13.3, `-O2
-march=x86-64-v3`, 636 byte input, 1000000 loops):

    ./tests/perf/perf urldecode 1000000
    Time/loop: 362.63 ns

That number includes one `curlx_malloc()` and one `curl_free()` per loop.

## 1. What curl requires from an experimental feature

Taken from `docs/EXPERIMENTAL.md`, `configure.ac`, `CMakeLists.txt` and the
way `USE_SSLS_EXPORT`, `USE_APPLE_FAST_UDP` and `USE_PROXY_HTTP3` are wired.
Every item below is a hard requirement. A missing item is a review reject.

1. Off by default. Must be enabled explicitly at configure time with both
   build systems: `--enable-<name>` for autotools and `-D<OPTION>=ON` for
   CMake.
2. One `USE_<NAME>` define in `curl_config.h`, produced by both
   `configure.ac` (`AC_DEFINE`) and `lib/curl_config-cmake.h.in`
   (`#cmakedefine`).
3. `configure` appends the name to `$experimental` so the final
   `AC_MSG_WARN([... is enabled but marked EXPERIMENTAL ...])` fires, and
   the configure summary block gets a line (`curl_<name>_msg`).
4. CMake: `option(... "(experimental)" OFF)`, a `curl_add_if()` line so the
   feature shows in `Features:` at configure time, and the option documented
   in `docs/INSTALL-CMAKE.md` in alphabetical position.
5. `lib/version.c`: a `FEATURE("<Name>", NULL, 0)` entry in alphabetical
   order with no public `CURL_VERSION_*` bit (experimental features never
   get one; see `SSLS-EXPORT`, `HTTPSRR`, `HTTPSIG`).
6. Feature string documented in `docs/libcurl/curl_version_info.md` with
   `*features* mask bit: non-existent` and `(experimental, added in X.Y.Z)`,
   and in `docs/cmdline-opts/version.md`.
7. A section in `docs/EXPERIMENTAL.md` with explicit graduation
   requirements.
8. Test cases. A build with the feature on must pass the full `runtests.pl`
   suite with zero tests disabled. New code gets a dedicated unit test with
   its own `tests/data/testNNNN` file.
9. Code passes `scripts/checksrc.pl` (`make checksrc`), builds warning free
   with `PICKY_COMPILER` on GCC, clang and MSVC, and is clean under
   `-fsanitize=address,undefined`, valgrind and clang-tidy. No over-reads
   past the input buffer, ever.
10. C89 syntax in `lib/`: `/* */` comments only, declarations at block
    start, no VLAs, 79 column limit, two space indent, no tabs.
11. Separate commits per area with the curl subject style
    `<area>: <lower case summary>` (examples: `build: add USE_SIMD option`,
    `escape: vectorize percent decoding`, `tests: add unit test for
    urldecode SIMD paths`, `docs: document SIMD experimental feature`).
    `RELEASE-NOTES` is maintained by the maintainer and is not touched.
12. No new public symbol, so `docs/libcurl/symbols-in-versions` and the
    ABI stay untouched. If that ever changes the feature is no longer
    eligible as experimental without a wider discussion.

## 2. Feature naming

| Item                       | Value                                      |
|----------------------------|--------------------------------------------|
| configure option           | `--enable-simd` / `--disable-simd`         |
| CMake option               | `USE_SIMD` (default `OFF`)                 |
| config define              | `USE_SIMD`                                 |
| feature string (`curl -V`) | `SIMD`                                     |
| configure summary line     | `SIMD:             ${curl_simd_msg}`       |
| `$experimental` token      | `SIMD`                                     |
| m4 macro                   | `CURL_CHECK_OPTION_SIMD` in `m4/curl-confopts.m4` |

The user facing name is "SIMD" and not "AVX" because the option gates every
vector implementation, not one instruction set. The instruction set is
chosen by the compiler flags the user already passes (`-mavx2`,
`-march=x86-64-v4`, `/arch:AVX2`, `/arch:AVX512`). curl does not add
`-m` flags on its own and this plan keeps that rule: the build system only
turns the feature on and verifies that `<immintrin.h>` compiles.

Translation unit level selection, in the order tested:

```c
#ifdef USE_SIMD
#if defined(__AVX512BW__) && defined(__AVX512VL__)
#define CURL_SIMD_AVX_512 1
#elif defined(__AVX2__)
#define CURL_SIMD_AVX2 1
#endif
#endif
```

`__AVX2__`, `__AVX512BW__` and `__AVX512VL__` are predefined by GCC, clang,
ICX and MSVC under the matching `-m`/`/arch:` flag, so no configure probe is
needed for the instruction set. BW and VL are required together because the
byte compares and masked 256 bit loads used below need both. `USE_SIMD`
without either macro produces the C version, so `--enable-simd` on a build
without vector flags is harmless and still reports `SIMD` in `curl -V`
(that is the experimental contract: the option was requested).

## 3. Case study: `Curl_urldecode()` in `lib/escape.c`

### 3.1 Why this function

`tests/perf/urldecode.c` feeds a 636 byte string that is 190 `%XX` triplets
and 66 literal bytes. The scalar loop in `Curl_urldecode()`
(`lib/escape.c:157`) does one of two things per iteration:

- literal run: `memchr()` to the next `%`, an optional control character
  scan, then `memcpy()`.
- escape: two `hextable[]` lookups, one `or`, one shift, one byte store.

The literal run is already vectorized by libc `memchr()`/`memcpy()`. The
escape path is one byte of output per loop iteration with a table lookup
chain, a data dependent branch on the `%` test and a second branch on the
validation. For escape heavy input (every non-ASCII URL path, every form
body, the perf test) that is the bottleneck. It is also self contained: no
`struct Curl_easy`, no allocation inside the loop, fixed input format. That
makes it the right first subject.

### 3.2 Scope of the vectorization

Only the escape run is vectorized. The literal run keeps `memchr()` and
`memcpy()`. Reasoning: libc already vectorizes those, a `%` scan merged with
the control character check would save one pass over literal data but the
measurable win is in the triplet path, and keeping one path scalar keeps
the diff small for review.

Decoding a run of consecutive triplets is a fixed layout problem:

    input:  % h h % h h % h h % h h ...   (3 bytes per output byte)
    output: b     b     b     b     ...

With a 32 byte load there are 10 full triplets in the first 30 bytes. With
a 64 byte load there are 21 triplets in 63 bytes. There is no compaction
step: the output positions are fixed, so plain `pshufb`/`vpermb` gathers
suffice and the AVX2 version does not need `vpcompressb` (AVX512_VBMI2),
which keeps the AVX2 code on every AVX2 CPU.

### 3.3 The three inline versions

One helper with one name and three bodies, so `Curl_urldecode()` is
identical for all builds and the unit test can run the same cases against
each body.

```c
/*
 * urldecode_run() decodes a run of consecutive "%XX" triplets at the start
 * of 'in'. It consumes as many triplets as fit in one vector step: zero if
 * the first bytes are not a complete, valid run of triplets, or if 'inlen'
 * is shorter than one full step.
 *
 * Returns the number of input bytes consumed, always a multiple of three.
 * The decoded bytes are stored to 'out'. If any decoded byte is below
 * 'reject_limit', 'rejected' is set to TRUE; the caller then fails the
 * whole decode exactly like the scalar path does.
 *
 * Never reads past in[inlen - 1].
 */
static CURL_INLINE size_t urldecode_run(const char *in, size_t inlen,
                                        uint8_t *out, uint8_t reject_limit,
                                        bool *rejected);
```

Rules shared by all three bodies:

- The step size is a file local constant: `URLDECODE_RUN_TRIPLETS` is 10
  for AVX2, 21 for AVX-512 and 10 for C. It is `UNITTEST` visible so the
  unit test knows the lane boundaries to probe.
- `inlen < 3 * URLDECODE_RUN_TRIPLETS` returns 0 immediately. That is what
  makes the over-read rule hold with unmasked loads. The scalar loop handles
  the tail, as it already does.
- A run is accepted only if every triplet in the step is well formed. A
  partially valid step returns 0 and the scalar loop takes over from the
  same position, so decoding stays byte exact with master. This is the
  simplest correct rule; refining it to "consume the valid prefix" is a
  later optimization and only if the perf numbers justify it.

**C body.** A plain loop over `URLDECODE_RUN_TRIPLETS` triplets using the
existing `hextable[]`, with the same accept/reject rule. This is not
expected to be faster than the current code; its purpose is to make the
control flow of `Curl_urldecode()` identical in every build so that the
non-SIMD CI jobs exercise the exact same call sites and the unit test is
meaningful on every platform. The C body is the reference the two vector
bodies must match bit for bit.

**AVX2 body** (`CURL_SIMD_AVX2`), 32 byte load, 30 bytes used:

1. `v = _mm256_loadu_si256(in)` (legal: `inlen >= 32` was checked).
2. Percent check: shuffle the 10 bytes at offsets 0,3,...,27 into the low
   lanes of one register, `_mm256_cmpeq_epi8` with a broadcast `'%'`,
   `_mm256_movemask_epi8` must have the low 10 bits set. Because
   `vpshufb` works within 128 bit lanes, the shuffle control uses one
   `_mm256_permute2x128_si256` or `_mm256_permute4x64_epi64` first to bring
   bytes 16..29 into the lane where they are needed. This is the one
   genuinely AVX2 specific detail and gets a comment in the code.
3. Gather high nibble characters (offsets 1,4,...,28) and low nibble
   characters (offsets 2,5,...,29) the same way into two registers `hi`
   and `lo`.
4. Classify each digit character `c` with unsigned range tests, done as
   `_mm256_subs_epu8`/`_mm256_cmpeq_epi8` or `_mm256_max_epu8` compare
   idioms since AVX2 has no unsigned compare:
   - `d = c - '0'`, digit if `d <= 9`
   - `a = (c | 0x20) - 'a'`, letter if `a <= 5`, value `a + 10`
   - anything else is invalid; the step returns 0.
5. `value = (hi << 4) | lo` via `_mm256_slli_epi16` plus an `and` mask of
   `0xf0` and `_mm256_or_si256`.
6. Reject check: `_mm256_cmpeq_epi8(_mm256_max_epu8(value, limit), value)`
   gives "value >= limit"; any zero lane among the 10 sets `*rejected`.
   `reject_limit == 0` (REJECT_NADA) short-circuits before the compare.
7. Store: the 10 result bytes are in the low lanes, written with one
   `_mm_storel_epi64` (8 bytes) plus a 2 byte scalar store, or
   `_mm_maskmoveu_si128` with a 10 byte mask. Both are fine; the 8+2 store
   avoids the non-temporal hint of `maskmoveu`.
8. Return 30.

**AVX-512 body** (`CURL_SIMD_AVX_512`), 64 byte load, 63 bytes used:

Same steps with 512 bit registers. `vpermb` (`_mm512_permutexvar_epi8`)
needs AVX512_VBMI, which is not implied by BW+VL (Skylake-SP lacks it), so
the gathers use `_mm512_shuffle_epi8` plus lane permutes like the AVX2
version, or the code requires `__AVX512VBMI__` as well. Decision for the
prototype: require only BW+VL, do the two stage shuffle, and note VBMI as a
graduation era refinement. Mask registers replace `movemask`:
`_mm512_cmpeq_epi8_mask` returns `__mmask64` directly and the digit range
tests use `_mm512_cmple_epu8_mask`, which does exist for unsigned, so the
classify step is shorter than in AVX2. The 21 result bytes are stored with
`_mm256_mask_storeu_epi8` and a 21 bit mask (needs BW+VL, which is already
required). Return 63.

Two facts to keep in mind for this body:

- valgrind does not support AVX-512 instructions. A `USE_SIMD` build with
  `-mavx512bw` cannot run under the valgrind CI jobs; those jobs stay on
  the AVX2 or C body. ASan and UBSan work fine.
- Mixing 512 bit instructions into a library that is otherwise 256 bit
  wide can lower the core frequency on some Intel parts. That is a
  graduation question (measurement on real workloads), not a correctness
  one, and is listed as such in `docs/EXPERIMENTAL.md`.

### 3.4 Call site change in `Curl_urldecode()`

Inside `while(alloc)`, before the existing `if(*string == '%')` test:

```c
    if(*string == '%') {
      size_t used = urldecode_run(string, alloc, (uint8_t *)ns,
                                  reject_limit, &rejected);
      if(rejected)
        goto error;
      if(used) {
        ns += used / 3;
        string += used;
        alloc -= used;
        continue;
      }
      /* existing single triplet code follows unchanged */
```

Nothing else in the function changes. The function signature, the
`urlreject` semantics, `olen`, the error path and the allocation size are
untouched, so `curl_easy_unescape()`, the URL API and every existing test
see identical output.

### 3.5 Where the code lives

All of it stays in `lib/escape.c`. It is file local, so `static` and the
`singleuse.pl` check are satisfied, and `UNITTEST` (which expands to
`static` except in unit test builds) exposes `urldecode_run()` and the step
constant to the test bundle the same way other internal helpers are
exposed. No new file in `lib/`, so `lib/Makefile.inc` is untouched. The
`#include <immintrin.h>` goes in `escape.c` under `#ifdef USE_SIMD` after
`curl_setup.h`, never in a header, so the rest of the library is not
affected. If a second translation unit is vectorized later, the selection
macros move to `lib/curl_setup.h` next to the other compiler capability
blocks (around line 728, where `__GNUC__`/`__clang__` features are
probed). Not before.

## 4. Build system changes

### 4.1 autotools

`m4/curl-confopts.m4`: add `CURL_CHECK_OPTION_SIMD` by copying
`CURL_CHECK_OPTION_SSLS_EXPORT` (line 548 area). It sets `want_simd` to
`yes`/`no` and `curl_simd_msg` to `no      (--enable-simd)` by default.

`configure.ac`:

- call `CURL_CHECK_OPTION_SIMD` next to `CURL_CHECK_OPTION_SSLS_EXPORT`
  (line 56).
- a block after the SSLS-EXPORT block (line 5099 area):

```
dnl *************************************************************
dnl check whether experimental SIMD routines are enabled
dnl
if test "$want_simd" = "yes"; then
  AC_MSG_CHECKING([whether SIMD intrinsics are usable])
  AC_COMPILE_IFELSE([
    AC_LANG_PROGRAM([[
#include <immintrin.h>
    ]],[[
      __m128i v = _mm_setzero_si128();
      (void)v;
    ]])
  ],[
    AC_MSG_RESULT([yes])
    AC_DEFINE(USE_SIMD, 1, [if SIMD routines are enabled])
    curl_simd_msg="enabled (--disable-simd)"
    experimental="$experimental SIMD"
  ],[
    AC_MSG_ERROR([--enable-simd requires <immintrin.h>])
  ])
fi
```

  The probe only checks `<immintrin.h>` and SSE2, which every x86-64
  compiler has. It fails hard on non-x86 targets, which is the intended
  behavior for an opt-in option (same pattern as `--enable-proxy-http3`
  erroring without ngtcp2).
- `SIMD:             ${curl_simd_msg}` in the summary block at line 5607
  area, after `SSLS-EXPORT`.

### 4.2 CMake

`CMakeLists.txt`, after the `USE_SSLS_EXPORT` block (line 1093):

```cmake
option(USE_SIMD "Enable SIMD-accelerated routines (experimental)" OFF)
if(USE_SIMD)
  check_c_source_compiles("
    #include <immintrin.h>
    int main(void) { __m128i v = _mm_setzero_si128(); (void)v; return 0; }"
    HAVE_IMMINTRIN_H)
  if(NOT HAVE_IMMINTRIN_H)
    message(FATAL_ERROR "USE_SIMD requires <immintrin.h>")
  endif()
  message(STATUS "SIMD routines enabled (experimental)")
endif()
```

`curl_add_if("SIMD" USE_SIMD)` next to the `SSLS-EXPORT` line (2052).

`lib/curl_config-cmake.h.in`: `#cmakedefine USE_SIMD 1` next to
`USE_SSLS_EXPORT` (line 660).

`docs/INSTALL-CMAKE.md`: one line in the alphabetical option list near
`USE_SSLS_EXPORT` (line 259):

```
- `USE_SIMD`:                               Enable SIMD-accelerated routines (experimental). Default: `OFF`
```

`lib/config-win32.h` is left alone: hand written Windows makefile builds do
not get the feature, which matches how `USE_SSLS_EXPORT` is handled there.

## 5. Tests

### 5.1 Existing coverage that must stay green

- test 1396 (`tests/libtest/lib1396.c`): `curl_easy_unescape()` edge
  cases, including truncated and invalid triplets.
- test 1537 (`tests/libtest/lib1537.c`): full 0..255 round trip.
- the URL API tests (1560 and friends) decode via `Curl_urldecode()` with
  `REJECT_CTRL`/`REJECT_ZERO`.
- `tests/perf/urldecode.c`: the performance probe.

### 5.2 New unit test

`tests/unit/unit1688.c` (next free number after 1687; adjust if master
moved) plus `tests/data/test1688` in the same shape as `test1620`
(keywords `unittest`, `URL`; `<features>unittest</features>`; name `unit
tests for urldecode vector paths`). Register in `tests/unit/Makefile.inc`.
The test calls `urldecode_run()` and `Curl_urldecode()` directly through
the unit test bundle and checks:

1. Exactly `URLDECODE_RUN_TRIPLETS` triplets consumed on a buffer of that
   many valid triplets; output bytes compared with `memcmp()` against the
   expected values. Upper and lower case hex, all 256 values across runs.
2. Return 0 when `inlen` is one byte short of a full step, and the scalar
   path still decodes the whole input correctly (end to end through
   `Curl_urldecode()`).
3. For each lane `i` in `0..URLDECODE_RUN_TRIPLETS-1`: a non `%` at
   triplet `i`, a non hex high digit at `i`, a non hex low digit at `i`.
   Each must return 0 and the end to end result must equal master's output
   (literal `%` kept, as in test 1396).
4. Reject semantics for each lane: `REJECT_ZERO` with `%00` at lane `i`
   fails, `REJECT_CTRL` with `%1F` at lane `i` fails and `%20` passes,
   `REJECT_NADA` passes everything.
5. A buffer whose valid run ends exactly at a step boundary, one that ends
   one triplet past it, and one that is literal data interleaved with
   single triplets (no run at all), to prove the fallback is seamless.
6. Over-read guard: the inputs are allocated with `curlx_malloc()` at
   their exact length so ASan and valgrind catch any load past the end.

The same source compiles for all three bodies; the CI matrix supplies the
instruction set. Results must be identical.

### 5.3 CI

`.github/workflows/linux.yml`, two matrix entries copied from the
`openssl -O3 libssh valgrind` ones:

- `openssl SIMD avx2 valgrind`: `CFLAGS: -O2 -mavx2`, `generate:
  -DENABLE_DEBUG=ON -DUSE_SIMD=ON`. Runs the full suite under valgrind.
- `openssl SIMD avx512`: `CFLAGS: -O2 -mavx512bw -mavx512vl`, `generate:
  -DENABLE_DEBUG=ON -DUSE_SIMD=ON -DCURL_WERROR=ON`, ASan instead of
  valgrind. GitHub hosted Linux runners are not guaranteed to have
  AVX-512, so this job builds, runs `runtests.pl` only if
  `grep -q avx512bw /proc/cpuinfo`, and otherwise reports the skip. The
  first `-Wstringop-overflow` warning already seen with `-march=x86-64-v4`
  in `lib/curlx/inet_pton.c:178` must be understood and fixed or silenced
  with a source change before `CURL_WERROR=ON` can be used here. It is a
  pre-existing issue unrelated to this feature and goes in its own
  commit.
- one `USE_SIMD=ON` build with no `-m` flags (C body) in an existing job,
  to keep the C body compiled and tested in every run.

`.github/workflows/windows.yml`: one MSVC entry with `/arch:AVX2` and
`-DUSE_SIMD=ON` for the `__AVX2__` plus `<immintrin.h>` combination on
MSVC. clang-tidy and `codeql.yml` pick up the new code through the
existing `USE_SIMD=ON` additions.

## 6. Documentation

- `docs/EXPERIMENTAL.md`: new section `## SIMD-accelerated routines` with
  graduation requirements:
  - runtime CPU dispatch so distribution builds benefit without
    `-march` flags (the compile time selection in section 2 is a
    prototype limitation, not a design)
  - measurements showing a gain on real inputs, not only
    `tests/perf/urldecode`, with the AVX-512 frequency effect quantified
  - no test cases disabled, identical output across the C, AVX2 and
    AVX-512 bodies verified by the unit test on every CI run
  - at least one more routine converted, to prove the scheme generalizes
- `docs/libcurl/curl_version_info.md`: `## SIMD` entry, mask bit
  non-existent, `(experimental, added in 8.23.0)`.
- `docs/cmdline-opts/version.md`: `## SIMD` entry: "This build uses
  SIMD-accelerated routines (experimental)."
- `docs/INSTALL-CMAKE.md`: option line (section 4.2).
- `tests/perf/README.md`: unchanged; `urldecode` already documented.

## 7. Work order on `dev-vec`

Each step is one commit. Build and run `make checksrc`, `make test-ci` (or
`runtests.pl -a -p` with the relevant test numbers) after each.

1. `build: add USE_SIMD experimental option` (section 4, section 6 docs
   for the option, `version.c` feature entry, EXPERIMENTAL.md section).
   Builds with the option on and off, `curl -V` shows `SIMD`.
2. `escape: add urldecode_run() with the C body and call it`. No
   intrinsics yet. All existing tests pass. Perf number recorded; it must
   not regress by more than noise.
3. `tests: add unit test 1688 for urldecode_run()`. Passes against the C
   body.
4. `escape: add AVX2 body for urldecode_run()`. Unit test and full suite
   pass under valgrind with `-mavx2`. Perf number recorded.
5. `escape: add AVX-512 body for urldecode_run()`. Same under ASan with
   `-mavx512bw -mavx512vl`. Perf number recorded.
6. `curlx: fix -Wstringop-overflow in inet_pton.c with 512 bit
   vectors` (independent, lands first or separately).
7. `CI: add SIMD jobs`.

Perf numbers for the three bodies are recorded in this file under a
"Results" heading as they come in, so the eventual pull request text can
quote them.

## 8. Things that will get the patch rejected

Listed because each one is easy to do by accident in this kind of code.

- `//` comments, `inline` without `CURL_INLINE`, `__attribute__` without
  the existing macros, `_Alignas`, `alignas`, VLAs, mixed declarations
  and code. The intrinsic types (`__m256i`) are fine; everything around
  them must be C89.
- `static inline` in a header, or any intrinsics header included from a
  header. Keep it in the `.c` file.
- Unmasked vector loads near the end of the input. The `inlen` check is
  the only thing preventing an over-read, and valgrind runs every test.
- Touching `RELEASE-NOTES`, bumping version numbers, or editing generated
  files.
- A `CURL_VERSION_SIMD` bit in `include/curl/curl.h`. Experimental
  features do not get public bits.
- `-mavx2` or `-march` added by `configure.ac` or `CMakeLists.txt`. The
  user chooses the target; the build system only enables the feature.
- Any change in decoded output compared to master for any input. The
  three bodies and the scalar path must be indistinguishable from the
  outside.
- Spelling: `docs/` is checked by `codespell`, `typos` and `pyspelling`.
  Unknown technical words (`AVX2`, `pshufb`) go in
  `.github/scripts/spellcheck.words` only if the spellcheck job complains.
