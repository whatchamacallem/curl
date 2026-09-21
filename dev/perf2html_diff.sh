#!/usr/bin/env bash
# dev/perf2html_diff.sh [--verbose] [--keep-raw] [--regenerate]
#     [--artifacts=DIR] [baseline-dir] [modified-dir] [report-dir]
#
# The unpacked profiles and the subtracted working files are written to a
# temporary artifacts directory. It sits beside the report by default --
# the parent directory of report-dir, holding
# perf2html_temporary_artifacts/ -- so a read-only checkout still diffs.
# --artifacts=DIR overrides that.
#
# Both inputs are refused unless their version line and recorded checksum
# hold. MANIFEST.txt is written last, once every page, asset and raw
# archive is in place, so a report holding one is a run that finished.
set -euo pipefail
# this script's resolved path. Every other path is relative to its dir
SCRIPT="$(readlink -f "$0")"
cd "$(dirname "$SCRIPT")"

# MANIFEST.txt is written by report_manifest.sh, which also supplies
# REPORT_MANIFEST and DIFF_MANIFEST, the checksum and every check that
# reads a report back.
# shellcheck source=report_manifest.sh
. ./report_manifest.sh

# extension of one test's raw-data archive
ARCHIVE_SUFFIX=.txz
# default artifacts directory name, beside the report
ARTIFACTS_NAME=perf2html_temporary_artifacts
# report subdirectory holding the one shared theme copy
ASSETS_DIR=assets

# this run's identity, reused from the manifest on --regenerate
STAMP="$(date +%s)"

# usage_show - prints the usage banner
usage_show() {
  cat <<'EOF'
perf2html_diff.sh [--verbose] [--keep-raw] [--regenerate]
    [--artifacts=DIR] [baseline-dir] [modified-dir] [report-dir]

--artifacts=DIR holds the unpacked profiles and the subtracted working
files; it defaults to perf2html_temporary_artifacts/ beside the report
directory.
EOF
}

# path_display - a path rewritten relative to the working directory
path_display() {
  python3 -c 'import os, sys
print(os.path.relpath(sys.argv[1], sys.argv[2]))' "$1" "$PWD"
}

# verbose - the one function testing $VERBOSE
verbose() { if [ "$VERBOSE" = 1 ]; then echo "$@"; fi; }

# test_run - runs a child, logs it, and exits printing the tail on failure
test_run() {
  local exit_code=0 from
  printf '\n$ %s\n' "$*" >>"$RUN_LOG"
  from="$(wc -l <"$RUN_LOG")"
  verbose "\$ $*"
  if [ "$VERBOSE" = 1 ]; then
    if ! { "$@" 2>&1 | tee -a "$RUN_LOG"; }; then
      exit_code="${PIPESTATUS[0]}"
    fi
  else
    "$@" >>"$RUN_LOG" 2>&1 || exit_code=$?
  fi
  if [ "$exit_code" != 0 ]; then
    {
      echo
      echo "error: exit $exit_code from: $*"
      tail -n +"$((from + 1))" "$RUN_LOG" | tail -n 40
      echo "(last 40 lines; everything this run printed: $RUN_LOG)"
    } >&2
    exit "$exit_code"
  fi
}

# args_parse - reads the flags and the three directories, all absolute
args_parse() {
  VERBOSE=0
  KEEP_RAW=0
  REGENERATE=0
  ARTIFACTS_DIR=""
  while [ $# -gt 0 ]; do
    case "$1" in
      -h | --help)
        usage_show
        exit 0
        ;;
      --verbose)
        VERBOSE=1
        shift
        ;;
      --keep-raw)
        KEEP_RAW=1
        shift
        ;;
      --regenerate)
        REGENERATE=1
        KEEP_RAW=1
        shift
        ;;
      --artifacts=*)
        ARTIFACTS_DIR="${1#--artifacts=}"
        shift
        ;;
      *) break ;;
    esac
  done
  BASE_DIR=perf2html_baseline_report
  MOD_DIR=perf2html_modified_report
  OUT_DIR=perf2html_diff_report
  case $# in
    0) ;;
    1) BASE_DIR="$1" ;;
    2)
      BASE_DIR="$1"
      MOD_DIR="$2"
      ;;
    3)
      BASE_DIR="$1"
      MOD_DIR="$2"
      OUT_DIR="$3"
      ;;
    *)
      usage_show >&2
      exit 2
      ;;
  esac
  local dir
  for dir in BASE_DIR MOD_DIR OUT_DIR; do
    case "${!dir}" in
      "~/"*) printf -v "$dir" '%s' "$HOME/${!dir#"~/"}" ;;
      /*) ;;
      *) printf -v "$dir" '%s' "$PWD/${!dir}" ;;
    esac
  done
  if [ -z "$ARTIFACTS_DIR" ]; then
    ARTIFACTS_DIR="$(dirname "$OUT_DIR")/$ARTIFACTS_NAME"
  fi
  case "$ARTIFACTS_DIR" in
    "~/"*) ARTIFACTS_DIR="$HOME/${ARTIFACTS_DIR#"~/"}" ;;
    /*) ;;
    *) ARTIFACTS_DIR="$PWD/$ARTIFACTS_DIR" ;;
  esac
}

# manifest_check - refuses an input whose version line is not exactly a
# perf2html.sh report's, which is how a diff is never read back as one.
manifest_check() {
  local dir="$1" role="$2" manifest="$1/MANIFEST.txt"
  if [ -f "$manifest" ] \
    && [ "$(head -1 "$manifest")" = "$DIFF_MANIFEST" ]; then
    echo "error: can't diff a diff -- the $role report was written by" \
      "perf2html_diff.sh: $dir" >&2
    echo "       found:    $DIFF_MANIFEST" >&2
    echo "       expected: $REPORT_MANIFEST" >&2
    exit 2
  fi
  manifest_verify "$dir" "$REPORT_MANIFEST" "$role"
}

# header_file_of - writes one input's LABEL=VALUE rows for the overview
header_file_of() {
  local dir="$1" role="$2"
  local out="$ARTIFACTS_DIR/header.$role.$STAMP.txt"
  {
    echo "report=$(path_display "$dir")"
    grep '=' "$dir/MANIFEST.txt" || true
  } >"$out"
  echo "$out"
}

# raw_archive_write - packs the named files into one test's raw archive
raw_archive_write() {
  local name="$1" out="$2"
  shift 2
  local stage file staged
  stage="$ARTIFACTS_DIR/stage.$name.$STAMP"
  rm -rf "$stage"
  mkdir -p "$stage" "$out/raw"
  for file in "$@"; do
    staged="$(basename "$file")"
    staged="${staged/.$STAMP/}"
    cp "$file" "$stage/$staged"
  done
  # generated output is byte-identical for one input
  test_run tar --sort=name --mtime=@0 --owner=0 --group=0 --numeric-owner \
    -cJf "$out/raw/$name$ARCHIVE_SUFFIX" -C "$stage" .
  rm -rf "$stage"
}

# profiles_extract - unpacks one report's archives once and lists them,
# synthesizing the "all" row as the union of every real test's profiles
profiles_extract() {
  local dir="$1" role="$2"
  local listing="$ARTIFACTS_DIR/profiles.$role.$STAMP.txt"
  local archive test into files every=""
  : >"$listing"
  for archive in "$dir"/raw/*"$ARCHIVE_SUFFIX" \
    "$dir"/*/raw/*"$ARCHIVE_SUFFIX"; do
    [ -f "$archive" ] || continue
    test="$(basename "$(dirname "$(dirname "$archive")")")"
    [ "$test" = "$(basename "$dir")" ] && test=.
    into="$ARTIFACTS_DIR/$role.$test.$STAMP"
    rm -rf "$into"
    mkdir -p "$into"
    test_run tar xJf "$archive" -C "$into"
    files=$(find "$into" -maxdepth 1 -type f -name 'callgrind.out.*' \
      | sort | tr '\n' ' ')
    [ -n "$files" ] || continue
    echo "$test $files" >>"$listing"
    [ "$test" = . ] || every+="$files"
  done
  [ -z "$every" ] || echo "all $every" >>"$listing"
  echo "$listing"
}

# tests_pair - the tests both reports hold, noting each one-sided name
tests_pair() {
  local base_tests cur_tests name
  base_tests="$(cut -d' ' -f1 "$BASE_LISTING" | sort -u)"
  cur_tests="$(cut -d' ' -f1 "$MODIFIED_LISTING" | sort -u)"
  if [ -z "$base_tests" ]; then
    echo "error: no */raw/*$ARCHIVE_SUFFIX archive holding" \
      "callgrind.out.* in the baseline report: $BASE_DIR" >&2
    exit 2
  fi
  if [ -z "$cur_tests" ]; then
    echo "error: no */raw/*$ARCHIVE_SUFFIX archive holding" \
      "callgrind.out.* in the modified report: $MOD_DIR" >&2
    exit 2
  fi
  for name in $(comm -23 <(echo "$base_tests") <(echo "$cur_tests")); do
    echo "note: '$name' is only in the baseline report; skipped" >&2
  done
  for name in $(comm -13 <(echo "$base_tests") <(echo "$cur_tests")); do
    echo "note: '$name' is only in the modified report; skipped" >&2
  done
  comm -12 <(echo "$base_tests") <(echo "$cur_tests")
}

# profiles_of - one test's profile files, read out of a listing
profiles_of() {
  awk -v want="$2" \
    'found { next }
     $1 == want { $1 = ""; print substr($0, 2); found = 1 }' "$1"
}

# diff_one - subtracts one test and generates its summary and heat map
diff_one() {
  local test="$1" out="$2" name="$3"
  local diff_file callers_file base_files cur_files args help_args=()
  local archive root_args=()
  [ "$MULTI" = 1 ] || root_args=(--single-test-report)
  diff_file="$ARTIFACTS_DIR/callgrind.diff.$name.$STAMP"
  callers_file="$diff_file.callers.json"
  base_files="$(profiles_of "$BASE_LISTING" "$test")"
  cur_files="$(profiles_of "$MODIFIED_LISTING" "$test")"

  verbose "== [$name]: diff -> $diff_file =="
  args=(python3 scripts/callgrind_diff.py -o "$diff_file"
    --callers-output "$callers_file")
  # shellcheck disable=SC2086
  for file in $base_files; do args+=(--baseline "$file"); done
  # shellcheck disable=SC2086
  for file in $cur_files; do args+=(--current "$file"); done
  test_run "${args[@]}"

  verbose "== [$name]: heat map -> $out/heat-map/index.html =="
  test_run python3 scripts/callgrind_to_heatmap.py "$diff_file" \
    -o "$out/heat-map/index.html" \
    --title "$name / heat map" --diff "${root_args[@]}" \
    --baseline-data "$callers_file"

  verbose "== [$name]: index -> $out/index.html =="
  rm -rf "$out/raw"
  archive="$out/raw/$(basename "$out")$ARCHIVE_SUFFIX"
  raw_archive_write "$(basename "$out")" "$out" \
    "$diff_file" "$callers_file"
  [ "$MULTI" = 1 ] && help_args=(--help-href ../README.md)
  test_run python3 scripts/build_report.py test "$diff_file" \
    -o "$out/index.html" --test "$name" --diff "${root_args[@]}" \
    --callers-data "$callers_file" --raw-data "$archive" \
    "${help_args[@]}"
  printf '%-13sdiff -> %s\n' "$name" "${out#"$PWD"/}/index.html"
}

# main - checks both inputs, diffs every shared test, stamps the report
main() {
  args_parse "$@"

  manifest_check "$BASE_DIR" baseline
  manifest_check "$MOD_DIR" modified

  [ "$KEEP_RAW" = 1 ] || rm -rf "$ARTIFACTS_DIR"
  if [ "$REGENERATE" = 1 ]; then
    # reusing a previous stamp means reading that report back, so it has
    # to hold up as one first
    manifest_verify "$OUT_DIR" "$DIFF_MANIFEST" "--regenerate input"
    local previous
    previous="$(manifest_value "$OUT_DIR" stamp)"
    if [ -n "$previous" ]; then STAMP="$previous"; fi
  fi
  mkdir -p "$OUT_DIR" "$ARTIFACTS_DIR"
  # the line above is the last reader of the previous run's manifest, so a
  # run that aborts from here on leaves a directory no tool will open
  rm -f "$OUT_DIR/MANIFEST.txt"
  RUN_LOG="$ARTIFACTS_DIR/diff.$STAMP.log"
  cp README.md "$OUT_DIR/README.md"
  test_run python3 scripts/build_report.py assets \
    -o "$OUT_DIR/$ASSETS_DIR"
  echo "dev/perf2html_diff.sh $STAMP: $BASE_DIR -> $MOD_DIR -> $OUT_DIR" \
    >"$RUN_LOG"

  local tests test_name args
  BASE_LISTING="$(profiles_extract "$BASE_DIR" baseline)"
  MODIFIED_LISTING="$(profiles_extract "$MOD_DIR" modified)"
  tests="$(tests_pair)"
  [ -n "$tests" ] || {
    echo "error: the two reports have no test in common" >&2
    exit 2
  }
  MULTI=1
  [ "$tests" = "." ] && MULTI=0

  echo "dev/perf2html_diff.sh $STAMP: $(basename "$BASE_DIR") ->" \
    "$(basename "$MOD_DIR")"
  if [ "$MULTI" = 0 ]; then
    local base_file test_name
    base_file="$(profiles_of "$BASE_LISTING" .)"
    test_name="$(basename "${base_file%% *}")"
    test_name="${test_name#callgrind.out.}"
    test_name="${test_name%%.*}"
    diff_one . "$OUT_DIR" "$test_name diff"
  else
    args=(-o "$OUT_DIR/index.html" --diff
      --header-block "baseline=$(header_file_of "$BASE_DIR" baseline)"
      --header-block "modified=$(header_file_of "$MOD_DIR" modified)")
    for test_name in $tests; do
      diff_one "$test_name" "$OUT_DIR/$test_name" "$test_name"
      args+=(--test "$test_name" --diff-profile
        "$test_name=$ARTIFACTS_DIR/callgrind.diff.$test_name.$STAMP")
    done
    verbose "== overview -> $OUT_DIR/index.html =="
    test_run python3 scripts/build_report.py overview "${args[@]}"
    printf '%-13s%s\n' overview "${OUT_DIR#"$PWD"/}/index.html"
  fi

  # last of all, once every page, asset and raw archive is in place: the
  # manifest is what says this run finished, and its checksum covers the
  # finished tree
  verbose "== manifest -> $OUT_DIR/MANIFEST.txt =="
  manifest_write "$DIFF_MANIFEST" "$OUT_DIR" \
    "baseline=$(path_display "$BASE_DIR")" \
    "modified=$(path_display "$MOD_DIR")" \
    "stamp=$STAMP"
  printf '%-13s%s\n' manifest \
    "$(manifest_value "$OUT_DIR" "$CHECKSUM_LABEL")"

  if [ "$KEEP_RAW" != 1 ]; then rm -rf "$ARTIFACTS_DIR"; fi
  echo "file://$OUT_DIR/index.html"
}

main "$@"
