# SPDX-FileCopyrightText: © 2026 Adrian Johnston.
# SPDX-License-Identifier: MIT
# This file is licensed under the terms of the LICENSE-MIT.md file.

absolute_path() {
  local path="$1"
  case "$path" in
    "~/"*) path="$HOME/${path#"~/"}" ;;
    /*) ;;
    *) path="$INVOKED_FROM/$path" ;;
  esac
  realpath -m -s -- "$path"
}

archive_extract() {
  local archive="$1" role="$2" root="$3" into report_name
  case "$archive" in
    *"$REPORT_RAW_ARCHIVE_SUFFIX") ;;
    *) error_exit 2 \
      "error: $role is no $REPORT_RAW_ARCHIVE_SUFFIX archive: $archive" ;;
  esac
  [ -f "$archive" ] || error_exit 2 "error: no such $role archive: $archive"
  report_name="$(basename "$archive" "$REPORT_RAW_ARCHIVE_SUFFIX")"
  into="$root/$role"
  mkdir -p "$into" || error_exit 1 \
    "error: could not make the $role extraction directory at $into"
  tar xJf "$archive" -C "$into" || error_exit 2 \
    "error: tar could not extract the $role archive: $archive"
  [ -d "$into/$report_name" ] || error_exit 2 \
    "error: the $role archive holds no $report_name directory: $archive"
  echo "$into/$report_name"
}

archive_report_write() {
  local dir="$1"
  local archive="$dir$REPORT_RAW_ARCHIVE_SUFFIX" staged
  staged="$archive.$TIMESTAMP.part"
  command_run tar --sort=name --mtime=@0 --owner=0 --group=0 \
    --numeric-owner -cJf "$staged" -C "$(dirname "$dir")" "$(basename "$dir")"
  mv -f "$staged" "$archive" || error_exit 1 \
    "error: could not move $staged onto $archive"
  log_verbose "$archive"
}

artifact_path_of() {
  local kind="$1" name="$2" loops="$CALLGRIND_LOOPS" file
  local timer_root="$TIMER_ARTIFACTS_NAME_PREFIX$TIMESTAMP"
  case "$kind" in
    callgrind) file="$CALLGRIND_OUTPUT_FILE_PREFIX.$name.$loops.$TIMESTAMP" ;;
    callgrind-member)
      file="$timer_root/$CALLGRIND_OUTPUT_FILE_PREFIX.$name.$loops"
      ;;
    caller-counts)
      file="$DIFF_DELTA_FILE_PREFIX.$name.$TIMESTAMP"
      file="$file$DIFF_CALLER_COUNTS_FILE_SUFFIX"
      ;;
    delta) file="$DIFF_DELTA_FILE_PREFIX.$name.$TIMESTAMP" ;;
    diff-log) file="$DIFF_LOG_FILE_PREFIX.$TIMESTAMP.log" ;;
    extracted-profiles) file="$name.$TIMESTAMP" ;;
    header-block) file="$DIFF_HEADER_BLOCK_FILE_PREFIX.$name.$TIMESTAMP.txt" ;;
    header-rows) file="$HEADER_ROWS_NAME.$name.txt" ;;
    profile-listing)
      file="$DIFF_PROFILE_LISTING_FILE_PREFIX.$name.$TIMESTAMP.txt"
      ;;
    profile-log) file="$PROFILE_LOG_FILE_PREFIX.$TIMESTAMP.log" ;;
    regenerate-log)
      file="$REGENERATE_LOG_FILE_PREFIX.$TIMESTAMP.$(date +%s).log"
      ;;
    timer-artifacts) file="$timer_root" ;;
    timing-csv) file="$PROFILE_TIMING_FILE_PREFIX.$name.$TIMESTAMP.csv" ;;
    timing-page) file="$PROFILE_TIMING_FILE_PREFIX.$name.$TIMESTAMP.txt" ;;
    trace-binary) file="$TRACE_FILE_PREFIX.$name.$loops.$TIMESTAMP.bin" ;;
    trace-log) file="$TRACE_FILE_PREFIX.$name.$loops.$TIMESTAMP.log" ;;
    trace-speedscope)
      file="$TRACE_FILE_PREFIX.$name.$loops.$TIMESTAMP"
      file="$file$TRACE_SPEEDSCOPE_FILE_SUFFIX"
      ;;
    trace-speedscope-member)
      file="$timer_root/$TRACE_FILE_PREFIX.$name.$loops"
      file="$file$TRACE_SPEEDSCOPE_FILE_SUFFIX"
      ;;
    valgrind-log)
      file="$VALGRIND_LOG_FILE_PREFIX.$name.$loops.$TIMESTAMP.log"
      ;;
    *) error_exit 1 "error: unknown artifact kind $kind, named $name" ;;
  esac
  echo "$ARTIFACTS_DIR/$file"
}

artifacts_clean() {
  [ -d "$ARTIFACTS_DIR" ] || return 0
  rm -r "$ARTIFACTS_DIR"
  rmdir --ignore-fail-on-non-empty "$(dirname "$ARTIFACTS_DIR")"
}

artifacts_dir_resolve() {
  if [ -z "$ARTIFACTS_DIR" ]; then
    if [ "$KEEP_ARTIFACTS" = 0 ] && [ "$REGENERATE" = 0 ]; then
      ARTIFACTS_DIR="$(mktemp -d)"
      log_verbose "using --artifacts=\"$ARTIFACTS_DIR\""
    else
      ARTIFACTS_DIR="$1/$ARTIFACTS_NAME"
    fi
  fi
  ARTIFACTS_DIR="$(absolute_path "$ARTIFACTS_DIR")"
}

block_lead() {
  local kind="$1" printed="${VERBOSE_BLOCK_PRINTED-other}"
  VERBOSE_BLOCK_PRINTED="$kind"
  [ "$VERBOSE" -lt "$VERBOSE_RAW_LEVEL" ] || return 0
  [ "$printed" = none ] || { [ "$kind" = item ] && [ "$printed" = item ]; } \
    || echo >&2
}

checksum_compute() {
  local dir="$1"
  (
    cd "$dir" || exit 1
    find . -type f ! -name MANIFEST.txt -print \
      | LC_ALL=C sort \
      | LC_ALL=C tr '\n' '\0' \
      | xargs -0 -r cksum -- \
      | LC_ALL=C sort \
      | cksum
  )
}

child_capture() {
  local page_file="$1"
  shift
  local logs=("$RUN_LOG") statuses=() status
  [ -z "$page_file" ] || logs+=("$page_file")
  CHILD_EXIT_CODE=0
  printf '\n$ %s\n' "$*" >>"$RUN_LOG"
  LOG_LINE_FROM="$(wc -l <"$RUN_LOG")"
  if [ "$VERBOSE" -ge "$VERBOSE_RAW_LEVEL" ]; then
    if ! { "$@" 2>&1 | tee -a "${logs[@]}" >&2; }; then
      statuses=("${PIPESTATUS[@]}")
    fi
  elif [ "$VERBOSE" -ge 1 ]; then
    if ! { "$@" 2>&1 | tee -a "${logs[@]}" \
      | verbose_filter "$VERBOSE_ITEM_INDENT"; }; then
      statuses=("${PIPESTATUS[@]}")
    fi
  elif ! { "$@" 2>&1 | tee -a "${logs[@]}" >/dev/null; }; then
    statuses=("${PIPESTATUS[@]}")
  fi
  [ "${#statuses[@]}" != 0 ] || return 0
  CHILD_EXIT_CODE="${statuses[0]}"
  for status in "${statuses[@]:1}"; do
    [ "$status" = 0 ] || error_exit 1 \
      "error: tee or verbose_filter exited $status behind: $*"
  done
}

child_capture_noisy() {
  if [ "$VERBOSE" -ge "$VERBOSE_RAW_LEVEL" ]; then
    child_capture "" "$@"
    return "$CHILD_EXIT_CODE"
  fi
  "$@" >/dev/null 2>&1
}

clock_microseconds() {
  local now="${EPOCHREALTIME}"
  echo "${now//[!0-9]/}"
}

code_span() {
  if [ "$VERBOSE" -ge "$VERBOSE_RAW_LEVEL" ]; then
    printf '%s\n' "$1"
    return 0
  fi
  local text="${1//"${HOME:?}"\//\~/}" run='`' gap='' edge='[^`]'
  while [[ "$text" =~ (^|$edge)"$run"($edge|$) ]]; do run+='`'; done
  if [[ "$text" == \`* || "$text" == *\` ||
    ("$text" == ' '*' ' && "$text" == *[!' ']*) ]]; then
    gap=' '
  fi
  printf '%s%s%s%s%s\n' "$run" "$gap" "$text" "$gap" "$run"
}

command_item_print() {
  local marker="$VERBOSE_COMMAND_NUMBER. "
  VERBOSE_ITEM_INDENT="${#marker}"
  VERBOSE_COMMAND_NUMBER=$((VERBOSE_COMMAND_NUMBER + 1))
  [ "$VERBOSE" -ge 1 ] || return 0
  block_lead item
  printf '%s%s\n' "$marker" "$(code_span "\$ $1")" >&2
}

command_run() {
  page_command_run "" "$*" "$@"
}

duration_format() {
  local seconds=$((($(clock_microseconds) - $1) / 1000000))
  if [ "$seconds" -ge 60 ]; then
    echo "$((seconds / 60))m$((seconds % 60))s"
  else
    echo "${seconds}s"
  fi
}

elapsed_format() {
  local delta=$(($(clock_microseconds) - PERF2HTML_CLOCK_START_US))
  printf '%d.%02d' "$((delta / 1000000))" "$((delta % 1000000 / 10000))"
}

error_exit() {
  local exit_code="$1"
  shift
  [ "$VERBOSE" -lt 1 ] || block_lead other
  printf '%s\n' "$@" >&2
  exit "$exit_code"
}

failure_print_log_tail() {
  local exit_code="$1" shown="$2"
  [ "$VERBOSE" -lt 1 ] || block_lead other
  {
    echo "error: exit $exit_code from: $shown"
    tail -n +"$((LOG_LINE_FROM + 1))" "$RUN_LOG" \
      | tail -n "$LOG_FAILURE_TAIL_LINES"
    echo "(see: $RUN_LOG)"
  } >&2
}

heading_print() {
  heading_write "$((PERF2HTML_HEADER_DEPTH + 1))" "$*"
}

heading_write() {
  local depth="$1" text="$2" marks=''
  VERBOSE_COMMAND_NUMBER=1
  [ "$VERBOSE" -ge 1 ] || return 0
  if [ "$VERBOSE" -lt "$VERBOSE_RAW_LEVEL" ]; then
    printf -v marks '%*s' "$depth" ''
    marks="${marks// /#} "
  fi
  block_lead other
  printf '%s%s\n' "$marks" \
    "$(code_span "[$(elapsed_format)s] $text")" >&2
}

install_command_of() {
  case "$1" in
    cmake | ninja | ccache | valgrind | taskset | python3 | cksum | curl | \
      tar | xz | dpkg-query)
      echo "sudo apt-get install -y ${CONTAINING_PACKAGES[$1]}"
      ;;
    cc) echo "sudo apt-get install -y build-essential" ;;
    addr2line | objdump | readelf) echo "sudo apt-get install -y binutils" ;;
    perf) echo "sudo apt-get install -y linux-perf" ;;
    speedscope) echo "npm install -g speedscope" ;;
    *) error_exit 1 "error: no install command is recorded for $1" ;;
  esac
}

item_output_print() {
  [ "$VERBOSE" -ge 1 ] || return 0
  printf '%s\n' "$@" | verbose_filter "$VERBOSE_ITEM_INDENT"
}

json_quote() {
  local text="$1"
  text="${text//\\/\\\\}"
  text="${text//\"/\\\"}"
  text="${text//$'\r'/\\r}"
  text="${text//$'\n'/\\n}"
  printf '"%s"' "$text"
}

log_verbose() {
  [ "$VERBOSE" -ge 1 ] || return 0
  block_lead other
  code_span "$*" >&2
}

manifest_fault_of() {
  local dir="$1"
  shift
  local manifest="$dir/MANIFEST.txt" version expected found wanted
  local checksum_label="$REPORT_MANIFEST_CHECKSUM_LABEL"
  wanted="$(manifest_wanted_phrase "$@")"
  if [ ! -d "$dir" ]; then
    echo "no such directory: $dir, expected a report whose MANIFEST.txt" \
      "line 1 reads $wanted"
    return 0
  fi
  if [ ! -f "$manifest" ]; then
    echo "$dir has no MANIFEST.txt, expected one whose line 1 reads $wanted"
    return 0
  fi
  version="$(head -1 "$manifest")"
  local candidate matched=0
  for candidate in "$@"; do
    [ "$version" = "$candidate" ] && matched=1
  done
  if [ "$matched" = 0 ]; then
    echo "$dir has an unrecognized MANIFEST.txt: found \"$version\"," \
      "expected $wanted"
    return 0
  fi
  expected="$(manifest_value "$dir" "$checksum_label")"
  if [ -z "$expected" ]; then
    echo "$dir has no $checksum_label= row in its MANIFEST.txt, expected" \
      "one beside the version line $version"
    return 0
  fi
  found="$(checksum_compute "$dir")"
  if [ "$found" != "$expected" ]; then
    echo "$dir does not match its recorded $checksum_label: found $found," \
      "expected $expected"
  fi
}

manifest_recorded_of() {
  local dir="$1" role="$2"
  shift 2

  manifest_verify "$dir" "$role" "$@"

  local recorded
  recorded="$(manifest_value "$dir" recorded)"
  recorded="${recorded%% *}"

  [ -n "$recorded" ] || error_exit 2 \
    "error: $role report $(basename "$dir") records no recorded= row"
  echo "$recorded"
}

manifest_recorded_row() {
  echo "recorded=$TIMESTAMP $(date -d "@$TIMESTAMP" +'%F %I:%M:%S %p')"
}

manifest_table_of() {
  PYTHONPATH="$PERF2HTML_DIR_/scripts${PYTHONPATH:+:$PYTHONPATH}" \
    python3 -c 'import sys, settings
print(settings.manifest_table(sys.argv[1:]), end="")' "$@"
}

manifest_value() {
  sed -n "s/^$2=//p" "$1/MANIFEST.txt" | head -1
}

manifest_verify() {
  local dir="$1" role="$2"
  shift 2
  local fault
  fault="$(manifest_fault_of "$dir" "$@")"
  [ -z "$fault" ] || error_exit 2 "error: $role report: $fault"
}

manifest_wanted_phrase() {
  local phrase=""
  local candidate
  for candidate in "$@"; do
    [ -z "$phrase" ] || phrase="$phrase or "
    phrase="$phrase\"$candidate\""
  done
  echo "$phrase"
}

manifest_write() {
  local version="$1" dir="$2"
  shift 2
  local manifest="$dir/MANIFEST.txt" table checksum
  command_run python3 "$PERF2HTML_DIR_/scripts/build_report.py" assets \
    -o "$dir/$REPORT_ASSETS_DIR_NAME"
  table="$(manifest_table_of "$version" "$@")"
  report_complete_write "$dir" "$table"
  checksum="$(checksum_compute "$dir")"
  {
    printf '%s\n' "$version"
    [ "$#" = 0 ] || printf '%s\n' "$@"
    printf '%s=%s\n' "$REPORT_MANIFEST_CHECKSUM_LABEL" "$checksum"
  } >"$manifest"
}

page_command_run() {
  local page_file="$1" shown="$2"
  shift 2
  command_item_print "$shown"
  child_capture "$page_file" "$@"
  [ "$CHILD_EXIT_CODE" = 0 ] || {
    failure_print_log_tail "$CHILD_EXIT_CODE" "$shown"
    exit "$CHILD_EXIT_CODE"
  }
}

path_display() {
  python3 -c 'import os, sys
print(os.path.relpath(sys.argv[1], sys.argv[2]))' "$1" "${2:-$INVOKED_FROM}"
}

path_overlap_check() {
  local -a paths=() roles=()
  while [ "$#" -gt 0 ]; do
    paths+=("${1%/}/")
    roles+=("$2")
    shift 2
  done
  local scripts_dir="${PERF2HTML_DIR_%/}/scripts/"
  local invoked_from="${INVOKED_FROM%/}/"
  local i j first first_role second second_role reason
  for ((i = 0; i < ${#paths[@]}; i++)); do
    first="${paths[i]}" first_role="${roles[i]}"
    for ((j = i + 1; j < ${#paths[@]}; j++)); do
      second="${paths[j]}" second_role="${roles[j]}"
      reason="error: the $first_role $first and the $second_role $second"
      [ "${first#"$second"}" != "$first" ] \
        || [ "${second#"$first"}" != "$second" ] || continue
      error_exit 2 "$reason overlap: deleting or writing one damages the other"
    done
    reason="error: the $first_role $first and the scripts dir $scripts_dir"
    reason="$reason overlap: deleting or writing one damages the other"
    { [ "${first#"$scripts_dir"}" != "$first" ] \
      || [ "${scripts_dir#"$first"}" != "$scripts_dir" ]; } \
      && error_exit 2 "$reason"
    [ "${invoked_from#"$first"}" != "$invoked_from" ] || continue
    reason="error: the $first_role $first holds the invocation dir"
    error_exit 2 "$reason $invoked_from: deleting or writing damages it"
  done
}

quiet_switch_set() {
  QUIET_SWITCH=()
  case "$1" in
    prettier) [ "$VERBOSE" -ge 1 ] || QUIET_SWITCH=(--log-level warn) ;;
    ruff) [ "$VERBOSE" -ge 1 ] || QUIET_SWITCH=(--quiet) ;;
    *) error_exit 1 "error: no quiet switch is recorded for $1" ;;
  esac
}

report_begin() {
  local dir="$1" log_file="$2" opening_line="$3"
  mkdir -p "$dir" "$dir/$REPORT_ASSETS_DIR_NAME" "$ARTIFACTS_DIR"
  RUN_LOG="$log_file"
  echo "$opening_line" >"$RUN_LOG"
  cp README.md "$dir/README.md"
}

report_complete_write() {
  local dir="$1" table="$2"
  local out="$dir/$REPORT_ASSETS_DIR_NAME/$ASSET_REPORT_COMPLETE_SCRIPT_NAME"
  {
    printf 'window.report_manifest_table_ = %s;\n' "$(json_quote "$table")"
    screenshot_label_script_print
  } >"$out"
}

report_delete() {
  local dir="$1" answer present=0
  local archive="$dir$REPORT_RAW_ARCHIVE_SUFFIX"
  path_overlap_check "$dir" report "$ARTIFACTS_DIR" "artifacts dir"
  [ ! -e "$dir" ] || present=1
  if [ "$present" = 1 ] \
    && { [ ! -d "$dir" ] || [ ! -e "$dir/MANIFEST.txt" ]; }; then
    printf 'Delete %s? [y/N] ' "$(path_display "$dir")" >&2
    read -r answer || {
      echo >&2
      answer=
    }
    [ "$answer" = y ] || error_exit 1 \
      "error: the report is not deleted without a typed y: $dir"
  fi
  rm -rf "$dir" || error_exit 1 "error: could not delete the report: $dir"
  [ "$present" = 1 ] && [ -e "$archive" ] || return 0
  rm -f "$archive" || error_exit 1 \
    "error: could not delete the report archive: $archive"
}

report_finish() {
  local dir="$1" version="$2"
  shift 2
  log_verbose "== manifest -> $dir/MANIFEST.txt =="
  manifest_write "$version" "$dir" "$@"
  log_verbose "manifest $(manifest_value "$dir" \
    "$REPORT_MANIFEST_CHECKSUM_LABEL")"
  log_verbose "$dir/index.html"
  [ "$WRITE_REPORT_ARCHIVE" = 1 ] || return 0
  heading_print "tar $(basename "$dir")$REPORT_RAW_ARCHIVE_SUFFIX"
  archive_report_write "$dir"
}

report_path_of() {
  local report_name="$1"
  case "$report_name" in
    /* | "~/"*) absolute_path "$report_name" ;;
    *) absolute_path "$TARGET_DIR/$report_name" ;;
  esac
}

revision_describe() {
  local repository="$1" revision dirty=0
  revision="$(git -C "$repository" rev-parse --short HEAD)"
  git -C "$repository" diff --quiet HEAD -- || dirty=$?
  if [ "$dirty" = 1 ]; then
    revision="$revision-dirty"
  elif [ "$dirty" != 0 ]; then
    error_exit 1 "error: git diff --quiet exited $dirty in $repository"
  fi
  echo "$revision"
}

screenshot_label_script_print() {
  cat <<'EOF'
(function () {
  var value = new URLSearchParams(location.search).get("screenshot");
  if (value === null) return;
  var label = document.createElement("div");
  label.className = "screenshot-label-";
  label.textContent = value;
  document.body.appendChild(label);
})();
EOF
}

shared_options_parse() {
  KEEP_ARTIFACTS=0
  REGENERATE=0
  REMAINING_ARGUMENTS=()
  TARGET_DIR="$INVOKED_FROM"
  ARTIFACTS_DIR=""
  WRITE_REPORT_ARCHIVE=0
  while [ $# -gt 0 ]; do
    case "$1" in
      -h | --help)
        usage_show
        exit 0
        ;;
      --verbose)
        VERBOSE=$((VERBOSE + 1))
        shift
        ;;
      --keep-artifacts)
        KEEP_ARTIFACTS=1
        shift
        ;;
      --regenerate)
        REGENERATE=1
        KEEP_ARTIFACTS=1
        shift
        ;;
      --txz)
        WRITE_REPORT_ARCHIVE=1
        shift
        ;;
      --artifacts=*)
        ARTIFACTS_DIR="${1#--artifacts=}"
        shift
        ;;
      --target-dir=*)
        TARGET_DIR="${1#--target-dir=}"
        shift
        ;;
      *)
        REMAINING_ARGUMENTS+=("$1")
        shift
        ;;
    esac
  done
  [ "$VERBOSE" -lt "$VERBOSE_TRACE_LEVEL" ] || set -o xtrace
  TARGET_DIR="$(absolute_path "$TARGET_DIR")"
}

source_cache_fetch() {
  local package="$1" version="$2" directory="$3"
  local upstream="${version%-*}" pool staged tarball root
  pool="$CACHE_ARCHIVE_BASE_URL/${package:0:1}/$package"
  local url="$pool/${package}_$upstream.orig.tar.xz"
  local package_dir
  package_dir="$(dirname "$directory")"
  rm -rf "$package_dir"
  staged="$directory.$TIMESTAMP.part"
  mkdir -p "$staged"
  tarball="$staged/source.tar.xz"
  command_run curl --fail --location --silent --show-error \
    --output "$tarball" "$url"
  command_run tar xJf "$tarball" -C "$staged"
  rm -f "$tarball"
  root="$staged/$package-$upstream"
  [ -d "$root" ] || error_exit 1 \
    "error: $url holds no $package-$upstream directory"
  mv -f "$root" "$directory" || error_exit 1 \
    "error: could not move $root onto $directory"
  rm -rf "$staged"
  log_verbose "cached $package $version sources in $directory"
}

source_cache_fill() {
  [ -d "$SOURCE_CACHE_DIR" ] || source_cache_fetch "$SOURCE_CACHE_PACKAGE" \
    "$SOURCE_CACHE_VERSION" "$SOURCE_CACHE_DIR"
}

source_cache_sync() {
  local installed package version
  installed="$(dpkg-query -W -f='${source:Package} ${source:Version}' \
    "$CACHE_EXTERNAL_PACKAGE")" || error_exit 1 \
    "error: dpkg-query knows no package $CACHE_EXTERNAL_PACKAGE"
  package="${installed%% *}"
  version="${installed##* }"
  [ -n "$package" ] && [ -n "$version" ] || error_exit 1 \
    "error: dpkg-query named no source package and version: $installed"
  SOURCE_CACHE_PACKAGE="$package"
  SOURCE_CACHE_VERSION="$version"
  SOURCE_CACHE_DIR="$(absolute_path "$CACHE_ROOT_DIR")/$package/$version"
}

table_print() {
  [ "$VERBOSE" -ge 1 ] || return 0
  local columns="$1" cells=() widths=() rule=() cell line row column
  shift
  if [ "$#" -le "$columns" ] || [ "$(($# % columns))" != 0 ]; then
    error_exit 1 \
      "error: table_print: $# cell(s) are no header and whole rows of $columns"
  fi
  if [ "$VERBOSE" -ge "$VERBOSE_RAW_LEVEL" ]; then
    block_lead other
    for ((row = columns; row < "$#"; row++)); do
      column=$((row % columns))
      printf '%s: %s\n' "${@:column+1:1}" "${@:row+1:1}" >&2
    done
    return 0
  fi
  cells=("${@:1:columns}")
  for cell in "${@:columns+1}"; do
    cells+=("$(code_span "${cell//|/\\|}")")
  done
  for ((column = 0; column < columns; column++)); do
    widths[column]=3
    for ((row = column; row < ${#cells[@]}; row += columns)); do
      [ "${#cells[row]}" -le "${widths[column]}" ] \
        || widths[column]="${#cells[row]}"
    done
    printf -v cell '%*s' "${widths[column]}" ''
    rule+=("${cell// /-}")
  done
  cells=("${cells[@]:0:columns}" "${rule[@]}" "${cells[@]:columns}")
  block_lead other
  for ((row = 0; row < ${#cells[@]}; row += columns)); do
    line='|'
    for ((column = 0; column < columns; column++)); do
      printf -v cell '%-*s' "${widths[column]}" "${cells[row + column]}"
      line+=" $cell |"
    done
    printf '%s\n' "$line" >&2
  done
}

title_print() {
  heading_write "$PERF2HTML_HEADER_DEPTH" "$*"
}

toolchain_check() {
  local tool missing=() lines=()
  for tool in cmake ninja ccache cc valgrind perf taskset python3 \
    addr2line objdump readelf speedscope cksum curl tar xz dpkg-query; do
    command -v "$tool" >/dev/null 2>&1 || missing+=("$tool")
  done
  if [ "${#missing[@]}" != 0 ]; then
    lines=("error: ${#missing[@]} tool(s) not found on PATH:")
    for tool in "${missing[@]}"; do
      lines+=("$(printf '  %-12s -> %s' "$tool" \
        "$(install_command_of "$tool")")")
    done
    error_exit 1 "${lines[@]}"
  fi
  SPEEDSCOPE_RELEASE="$(dirname \
    "$(dirname "$(readlink -f "$(command -v speedscope)")")")/dist/release"
  local reason="error: no speedscope bundle at $SPEEDSCOPE_RELEASE/index.html"
  [ -f "$SPEEDSCOPE_RELEASE/index.html" ] || error_exit 1 \
    "$reason -> $(install_command_of speedscope)"
}

verbose_begin() {
  export PERF2HTML_HEADER_DEPTH=$((${PERF2HTML_HEADER_DEPTH:-0} + 1))
  PERF2HTML_CLOCK_START_US="${PERF2HTML_CLOCK_START_US:-$(clock_microseconds)}"
  export PERF2HTML_CLOCK_START_US
  shopt -s lastpipe
  VERBOSE_COMMAND_NUMBER=1
  VERBOSE_ITEM_INDENT=0
  VERBOSE_BLOCK_PRINTED=other
  if [ "$PERF2HTML_HEADER_DEPTH" = 1 ] && [ "$VERBOSE" -ge 1 ]; then
    VERBOSE_BLOCK_PRINTED=none
  fi
}

verbose_filter() {
  local loose status=0 raw_line
  if [ "$VERBOSE" -ge "$VERBOSE_RAW_LEVEL" ]; then
    while IFS= read -r raw_line || [ -n "$raw_line" ]; do
      printf '%s\n' "$raw_line" >&2
    done
    return 0
  fi
  loose="$(awk -v indent="$(printf '%*s' "$1" '')" -v home="${HOME:?}/" '
  function line_print(text) {
    print text > "/dev/stderr"
    fflush("/dev/stderr")
  }
  function block_open() {
    if (blocks ? separate : lead) line_print("")
    blocks++
  }
  function fence_close() {
    if (open) line_print(indent fence)
    open = 0
  }
  function text_print(text,    run, rest) {
    run = 0
    for (rest = text; match(rest, /`+/); rest = substr(rest, RSTART + RLENGTH))
      if (RLENGTH > run) run = RLENGTH
    if (!open || run >= length(fence)) {
      fence_close()
      block_open()
      for (fence = "```"; run >= length(fence);) fence = fence "`"
      line_print(indent fence "txt")
      open = 1
    }
    line_print(indent text)
  }
  function padded(text, width) { return sprintf("%-" width "s", text) }
  function held_print(    column, width, cell, dashes, head, rule, row) {
    if (held < 2) {
      if (held) text_print(held_line[1])
      held = 0
      return
    }
    fence_close()
    if (!blocks && !separate) { separate = 1; lead = 1; loose = 1 }
    block_open()
    head = indent "|"
    rule = indent "|"
    row = indent "|"
    for (column = 1; column <= held; column++) {
      cell = "`" held_value[column] "`"
      width = length(held_key[column])
      if (length(cell) > width) width = length(cell)
      dashes = padded("", width)
      gsub(/ /, "-", dashes)
      head = head " " padded(held_key[column], width) " |"
      rule = rule " " dashes " |"
      row = row " " padded(cell, width) " |"
    }
    line_print(head)
    line_print(rule)
    line_print(row)
    held = 0
  }
  { sub(/[ \t\r]+$/, "") }
  $0 == "" { next }
  { while (at = index($0, home))
      $0 = substr($0, 1, at - 1) "~/" substr($0, at + length(home)) }
  /^[A-Za-z][A-Za-z0-9\/ ]*: +-?[0-9][0-9.,]*( [A-Za-z\/]+)?$/ {
    match($0, /: +/)
    held++
    held_key[held] = substr($0, 1, RSTART - 1)
    held_value[held] = substr($0, RSTART + RLENGTH)
    held_line[held] = $0
    next
  }
  { held_print(); text_print($0) }
  END { held_print(); fence_close(); if (loose) print "loose" }
  ')" || status=$?
  [ "$loose" != loose ] || VERBOSE_BLOCK_PRINTED=loose
  return "$status"
}

verbose_flags_of() {
  local flag_count
  for ((flag_count = 0; flag_count < VERBOSE; flag_count++)); do
    echo --verbose
  done
}
