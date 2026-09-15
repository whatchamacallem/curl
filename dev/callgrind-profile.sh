#!/usr/bin/env bash
# Full curl urlparser profiling pipeline:
#   1. build the RelWithDebInfo tree (needed for a realistic, symbol-ful profile)
#   2. run the perf urlparser benchmark under valgrind --tool=callgrind,
#      pinned to one CPU core (see dev/PROFILING-NOTES.md for why pinning
#      matters -- unpinned runs on this machine show ~2x run-to-run noise)
#   3. convert the callgrind output to speedscope's native JSON format
#   4. assemble a self-contained, double-click-able speedscope bundle at
#      ~/Downloads/curlscope/index.html that auto-loads the profile --
#      no "open speedscope, then drag in a file" step required.
set -euo pipefail

cd "$(dirname "$0")/.."
REPO_ROOT="$(pwd)"

LOOPS="${1:-200}"
CPU="${CALLGRIND_CPU:-3}"
BUILD_DIR="build-relwithdebinfo"
OUT_DIR="dev/callgrind-out"
if ! command -v speedscope >/dev/null 2>&1; then
  echo "error: speedscope not found on PATH (npm i -g speedscope)" >&2
  exit 1
fi
# speedscope's CLI shim resolves to .../node_modules/speedscope/bin/cli.mjs;
# its bundled app lives two directories up, at dist/release.
SPEEDSCOPE_CLI="$(readlink -f "$(command -v speedscope)")"
SPEEDSCOPE_PKG_DIR="$(dirname "$(dirname "$SPEEDSCOPE_CLI")")"
SPEEDSCOPE_RELEASE="$SPEEDSCOPE_PKG_DIR/dist/release"

DEST_DIR="${CURLSCOPE_DEST:-$HOME/Downloads/curlscope}"

mkdir -p "$OUT_DIR"

echo "== 1/4: configuring + building RelWithDebInfo (optimized + debug symbols) =="
if [ ! -d "$BUILD_DIR" ]; then
  cmake -S . -B "$BUILD_DIR" -G Ninja -DCURL_USE_LIBPSL=OFF \
    -DCMAKE_BUILD_TYPE=RelWithDebInfo
fi
cmake --build "$BUILD_DIR" --parallel
cmake --build "$BUILD_DIR" --target perf

BIN="$BUILD_DIR/tests/perf/perf"
STAMP="$(date +%s)"
CG_OUT="$OUT_DIR/callgrind.out.urlparser.$LOOPS.$STAMP"

echo "== 2/4: profiling under callgrind (pinned to CPU $CPU, loops=$LOOPS) =="
echo "   note: callgrind simulates every instruction, so this run is ~30-50x"
echo "   slower than native and its own reported wall-clock is NOT a valid"
echo "   perf number -- only use ./build-relwithdebinfo/tests/perf/perf directly"
echo "   (optionally under taskset) for timing. Callgrind is for the profile only."
if command -v taskset >/dev/null 2>&1; then
  taskset -c "$CPU" valgrind --tool=callgrind \
    --callgrind-out-file="$CG_OUT" \
    "$BIN" urlparser "$LOOPS"
else
  valgrind --tool=callgrind --callgrind-out-file="$CG_OUT" "$BIN" urlparser "$LOOPS"
fi

echo "== 3/4: converting callgrind output to speedscope JSON =="
JSON_OUT="$OUT_DIR/urlparser.$LOOPS.$STAMP.speedscope.json"
python3 dev/scripts/callgrind_to_speedscope.py "$CG_OUT" \
  -o "$JSON_OUT" --event Ir \
  --name "curl urlparser (loops=$LOOPS, $STAMP)"

echo "== 4/4: assembling self-contained speedscope bundle at $DEST_DIR =="
if [ ! -d "$SPEEDSCOPE_RELEASE" ] || [ ! -f "$SPEEDSCOPE_RELEASE/index.html" ]; then
  echo "error: could not locate speedscope's dist/release directory" >&2
  echo "  (looked at: $SPEEDSCOPE_RELEASE)" >&2
  exit 1
fi

rm -rf "$DEST_DIR"
mkdir -p "$DEST_DIR"
cp -r "$SPEEDSCOPE_RELEASE"/. "$DEST_DIR"/

python3 dev/scripts/build_curlscope_bundle.py \
  --speedscope-dir "$DEST_DIR" \
  --profile-json "$JSON_OUT" \
  --profile-filename "$(basename "$JSON_OUT")"

echo
echo "Done."
echo "  Callgrind data:    $CG_OUT"
echo "  Speedscope JSON:   $JSON_OUT"
echo "  Bundle:            $DEST_DIR/index.html  (double-click to open, auto-loads the profile)"
