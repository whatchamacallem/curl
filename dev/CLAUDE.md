# curl urlparser perf work

## Goal

Optimize `tests/perf/urlparser.c` (and, as needed, the URL API code it
exercises in `lib/urlapi.c` / `lib/uint-table.c` / `lib/idn.c` etc.) to improve
the "urlparser" perf chart tracked at:

https://curl.se/perf/index.html#urlparser

Measure with the built perf harness:

```
./build/tests/perf/perf urlparser [loops]
```

Default `loops` is 10000 if omitted. Use a smaller loop count (e.g. 1000) for
quick iteration, and a larger one for stable final numbers.

## Build

Default CMake + Ninja build, from the repo root:

```
cmake -S . -B build -G Ninja -DCURL_USE_LIBPSL=OFF
cmake --build build --parallel
cmake --build build --target perf
```

`CURL_USE_LIBPSL=OFF` is the **one intentional deviation** from a stock
default build: `libpsl-dev` headers are not installed on this machine and
`CURL_USE_LIBPSL` is `REQUIRED` when ON, which otherwise hard-fails
configure. Everything else uses CMake defaults (OpenSSL, zlib, zstd, threaded
resolver, IPv6, alt-svc, HSTS, etc. all auto-detected and on). If libpsl-dev
gets installed later, drop that flag to go fully stock.

The `perf` test binary is `EXCLUDE_FROM_ALL` in the perf CMakeLists, so it
must be built explicitly with `--target perf` — it is not part of a plain
`cmake --build build`.

## Debugging

Open this `dev/` folder (or the repo root, since `dev/.vscode` is symlinked
to the top-level `.vscode`) in VS Code and use the "perf urlparser" launch
config. It rebuilds the `perf` target first, then runs
`./build/tests/perf/perf urlparser` under gdb.

## Workflow

1. Baseline: run `./build/tests/perf/perf urlparser` a few times, note
   URLs/sec and ns/URL (some run-to-run noise is normal — prefer median of
   3-5 runs).
2. Profile if needed (`perf record`/`perf report`, or gdb, or just read the
   hot path) to find where time goes in `curl_url_set()` for
   `CURLUPART_URL`.
3. Make a focused change.
4. Rebuild (`cmake --build build --target perf`, and the main lib if you
   touched `lib/`) and re-run the benchmark.
5. Compare against baseline. Keep changes that measurably help; discard ones
   that don't or that regress correctness (`ecount` in the test output, and
   the normal `tests/` suite, must stay consistent).
6. Record what was tried and the before/after numbers as you go.

## Notes

- The test data (`urls[]` in `tests/perf/urlparser.c`) is a fixed corpus of
  ~577 real-world-ish URLs from a public dataset; it is looped and cross
  multiplied by 7 different `CURLU_*` option combinations per URL. Don't
  change the corpus or option list — that would invalidate comparisons
  against the public chart.
- `Errors:` in the output is the count of URLs that failed to parse under a
  given option combination. This is expected to be nonzero (some URLs are
  intentionally malformed test cases) — track it stays *constant* across
  your changes, since a change that "speeds up" parsing by silently
  rejecting more URLs is not a valid optimization.
- Keep correctness first: run the full test suite (`tests/runtests.pl` or
  `ctest` from `build/`, if built with `-DBUILD_TESTING=ON`) before
  considering a change final, since this perf test alone doesn't validate
  parsing correctness.
