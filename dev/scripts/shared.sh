# dev/scripts/shared.sh

# absolute_path - one path, relative to $INVOKED_FROM, made canonical by
# readlink -m: no ., .., // or symlinks; nothing along it need exist yet.
absolute_path() {
  local path="$1"
  case "$path" in
    "~/"*) path="$HOME/${path#"~/"}" ;;
    /*) ;;
    *) path="$INVOKED_FROM/$path" ;;
  esac
  readlink -m -- "$path"
}

# archive_write - one reproducible tar.xz of a test's recordings, under
# $out/raw/.
archive_write() {
  local name="$1" out="$2" strip="$3"
  shift 3
  local stage file staged
  stage="$ARTIFACTS_DIR/stage.$name.$TIMESTAMP"
  rm -rf "$stage"
  mkdir -p "$stage" "$out/raw"
  for file in "$@"; do
    staged="$(basename "$file")"
    staged="${staged/.$TIMESTAMP/}"
    cp "$file" "$stage/$staged"
  done
  [ -z "$strip" ] || sed -i "s#$strip/##g" "$stage"/*
  command_run tar --sort=name --mtime=@0 --owner=0 --group=0 \
    --numeric-owner -cJf "$out/raw/$name$REPORT_RAW_ARCHIVE_SUFFIX" \
    -C "$stage" .
  rm -rf "$stage"
}

# artifacts_clean - Deletes the temp dir because it is a debug only unless told
# otherwise.
artifacts_clean() {
  [ -d "$ARTIFACTS_DIR" ] || return 0
  rm -r "$ARTIFACTS_DIR"
}

# checksum_compute - POSIX cksum of every report file but MANIFEST.txt.
# Sorted, relative paths, so readdir order and this box cannot reach it.
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

# child_capture - run one child into $RUN_LOG, and a page file when one is
# named, teeing under --verbose. SETS CHILD_EXIT_CODE and LOG_LINE_FROM.
child_capture() {
  # args: page file or "", verbose_filter mode (list for a tool, relay for
  # one of our scripts), the command. Never stdout: the tee owns it
  local page_file="$1" mode="$2"
  shift 2
  local logs=("$RUN_LOG") statuses=() status
  [ -z "$page_file" ] || logs+=("$page_file")
  CHILD_EXIT_CODE=0
  printf '\n$ %s\n' "$*" >>"$RUN_LOG"
  LOG_LINE_FROM="$(wc -l <"$RUN_LOG")"
  # the `if !` is what keeps pipefail's failure from reaching PIPESTATUS's
  # reader; the tee and the filter are chosen before the child starts
  if [ "$VERBOSE" -ge 1 ]; then
    if ! { "$@" 2>&1 | tee -a "${logs[@]}" \
      | verbose_filter "$mode" "$ITEM_INDENT"; }; then
      statuses=("${PIPESTATUS[@]}")
    fi
  elif ! { "$@" 2>&1 | tee -a "${logs[@]}" >/dev/null; }; then
    statuses=("${PIPESTATUS[@]}")
  fi
  [ "${#statuses[@]}" != 0 ] || return 0
  CHILD_EXIT_CODE="${statuses[0]}"
  # tee or the filter failing tore the log or the terminal whatever the
  # child did: never a pass
  for status in "${statuses[@]:1}"; do
    [ "$status" = 0 ] || error_exit 1 \
      "error: tee or verbose_filter exited $status behind: $*"
  done
}

# child_capture_noisy - a child whose output is noise, like cmake's configure:
# child_capture at --verbose --verbose, discarded below. Returns its code.
child_capture_noisy() {
  # a return code, not CHILD_EXIT_CODE: child_capture is that global's one
  # setter, and below level 2 nothing reaches $RUN_LOG or the terminal
  if [ "$VERBOSE" -ge 2 ]; then
    child_capture "" list "$@"
    return "$CHILD_EXIT_CODE"
  fi
  "$@" >/dev/null 2>&1
}

# clock_microseconds - wall clock in whole microseconds, from EPOCHREALTIME
# (its separator is the locale's, so every non-digit is dropped).
clock_microseconds() {
  local now="${EPOCHREALTIME}"
  echo "${now//[!0-9]/}"
}

# command_item_print - the numbered item a command's output nests under:
# `$ command`, wrapped. SETS ITEM_INDENT, and counts COMMAND_NUMBER on.
command_item_print() {
  local marker="$COMMAND_NUMBER. "
  ITEM_INDENT="${#marker}"
  COMMAND_NUMBER=$((COMMAND_NUMBER + 1))
  OUTPUT_ENDS_BLANK=0
  [ "$VERBOSE" -ge 1 ] || return 0
  printf '`$ %s`\n' "$1" | verbose_filter wrap "$marker"
}

# command_run - the one policy on child_capture: on failure print what the
# child wrote and exit with its code. No caller of it collects a failure.
command_run() {
  page_command_run "" "$*" "$@"
}

# duration_format - one span as 12s or 3m04s, from its start
# microseconds as clock_microseconds printed them.
duration_format() {
  local seconds=$((($(clock_microseconds) - $1) / 1000000))
  if [ "$seconds" -ge 60 ]; then
    echo "$((seconds / 60))m$((seconds % 60))s"
  else
    echo "${seconds}s"
  fi
}

# elapsed_format - seconds since $START_US, two decimals, for the [Ns]
# prefix a whole run's lines carry.
elapsed_format() {
  local delta=$(($(clock_microseconds) - START_US))
  printf '%d.%02d' "$((delta / 1000000))" "$((delta % 1000000 / 10000))"
}

# error_exit - the one way a script refuses: its lines in one ```sh fence on
# stderr, then exit with the code given first. Nothing collects a failure.
error_exit() {
  local exit_code="$1"
  shift
  {
    echo
    echo '```sh'
    printf '%s\n' "$@"
    echo '```'
    echo
  } | verbose_filter paths >&2
  exit "$exit_code"
}

# failure_print_log_tail - on stderr, in one ```sh fence, a failed child's
# exit code, command and output tail from $LOG_LINE_FROM on.
failure_print_log_tail() {
  local exit_code="$1" shown="$2"
  {
    echo
    echo '```sh'
    echo "error: exit $exit_code from: $shown"
    tail -n +"$((LOG_LINE_FROM + 1))" "$RUN_LOG" \
      | tail -n "$LOG_FAILURE_TAIL_LINES"
    echo "(see: $RUN_LOG)"
    echo '```'
    echo
  } | verbose_filter paths >&2
}

# failure_relay - one of our scripts failed as a child: unless --verbose
# streamed it already, reprint its output from the log, fence and all.
failure_relay() {
  if [ "$VERBOSE" -ge 1 ]; then return 0; fi
  tail -n +"$((LOG_LINE_FROM + 1))" "$RUN_LOG" | verbose_filter paths >&2
}

# heading_print - one piece of work, a heading one level below the script's
# own title, reading `[elapsed] text`; the item numbers restart under it.
heading_print() {
  heading_write "$((HEADING_DEPTH + 1))" "$*"
}

# heading_write - a heading at the depth given, printed under --verbose with
# a blank line each side. SETS COMMAND_NUMBER back to 1.
heading_write() {
  local depth="$1" text="$2" hashes
  COMMAND_NUMBER=1
  [ "$VERBOSE" -ge 1 ] || return 0
  printf -v hashes '%*s' "$depth" ''
  hashes="${hashes// /#}"
  [ "$OUTPUT_ENDS_BLANK" = 1 ] || echo
  printf '%s `[%ss] %s`\n\n' "$hashes" "$(elapsed_format)" "$text" \
    | verbose_filter paths
  OUTPUT_ENDS_BLANK=1
}

# install_command_of - one tool's official install command. Nothing
# hand-rolled and no PPA belongs here.
install_command_of() {
  case "$1" in
    cmake | ninja | ccache | valgrind | taskset | python3 | cksum)
      echo "sudo apt-get install -y ${CONTAINING_PACKAGES[$1]}"
      ;;
    cc) echo "sudo apt-get install -y build-essential" ;;
    addr2line | readelf) echo "sudo apt-get install -y binutils" ;;
    perf) echo "sudo apt-get install -y linux-perf" ;;
    speedscope) echo "npm install -g speedscope" ;;
    *) error_exit 1 "error: no install command is recorded for $1" ;;
  esac
}

# item_output_print - lines of our own as a command's nested output, under
# --verbose, through the filter a child's output takes.
item_output_print() {
  [ "$VERBOSE" -ge 1 ] || return 0
  printf '%s\n' "$@" | verbose_filter list "$ITEM_INDENT"
}

# json_quote - one string as a JSON string literal, for a generated .js.
json_quote() {
  local text="$1"
  text="${text//\\/\\\\}"
  text="${text//\"/\\\"}"
  printf '"%s"' "$text"
}

# log_verbose - one plain status line, a paragraph of its own under
# --verbose, wrapped. Verbose adds to quiet, so nothing else guards a printf.
log_verbose() {
  [ "$VERBOSE" -ge 1 ] || return 0
  [ "$OUTPUT_ENDS_BLANK" = 1 ] || echo
  printf '%s\n' "$*" | verbose_filter wrap ""
  echo
  OUTPUT_ENDS_BLANK=1
}

# manifest_fault_of - the one reader deciding whether a directory is a
# finished report, echoing why it is not or nothing when it holds up.
manifest_fault_of() {
  # args: the dir, then each version string line 1 may read -- naming one
  # keeps a diff out of a diff, naming both accepts either kind
  local dir="$1"
  shift
  local manifest="$dir/MANIFEST.txt" version recorded found wanted
  local checksum_label="$REPORT_MANIFEST_CHECKSUM_LABEL"
  wanted="$(manifest_wanted_phrase "$@")"
  if [ ! -d "$dir" ]; then
    echo "no such directory: $dir -- a report is a directory whose"
    echo "MANIFEST.txt line 1 reads $wanted"
    return 0
  fi
  if [ ! -f "$manifest" ]; then
    echo "$dir has no MANIFEST.txt, so it is not a finished report"
    echo "       expected: $wanted"
    echo "       (a run that aborts writes no manifest; re-run it)"
    return 0
  fi
  version="$(head -1 "$manifest")"
  local candidate matched=0
  for candidate in "$@"; do
    [ "$version" = "$candidate" ] && matched=1
  done
  if [ "$matched" = 0 ]; then
    echo "$dir has an unrecognized MANIFEST.txt"
    echo "       found:    $version"
    echo "       expected: $wanted"
    return 0
  fi
  recorded="$(manifest_value "$dir" "$checksum_label")"
  if [ -z "$recorded" ]; then
    echo "$dir has no $checksum_label= row, so its files cannot be"
    echo "verified"
    echo "       expected: a $checksum_label= row beside the version"
    echo "       line $version"
    return 0
  fi
  found="$(checksum_compute "$dir")"
  if [ "$found" != "$recorded" ]; then
    echo "$dir does not match its recorded $checksum_label"
    echo "       found:    $found"
    echo "       expected: $recorded"
    echo "       (a file was added, removed or edited after the report"
    echo "       was written)"
  fi
}

# manifest_script_write - the assets/ script holding the manifest text, for
# an error page on a file:// URL where nothing can be fetched.
manifest_script_write() {
  # every row but the checksum: this is written before checksum_compute
  # runs and counted by it, so a checksum here is the previous run's
  local dir="$1" version="$2"
  shift 2
  local assets="$dir/$REPORT_ASSETS_DIR_NAME" row
  local out="$assets/$ASSET_REPORT_MANIFEST_SCRIPT_NAME"
  mkdir -p "$assets"
  {
    printf 'window.report_manifest = [\n'
    for row in "$version" "$@"; do
      printf '  %s,\n' "$(json_quote "$row")"
    done
    printf '].join("\\n");\n'
  } >"$out"
}

# manifest_stamp_row - the stamp= row every report writes: the unix time a
# reader identifies recordings by, then a human date nothing parses.
manifest_stamp_row() {
  echo "stamp=$TIMESTAMP $(date -d "@$TIMESTAMP" +'%F %I:%M:%S %p')"
}

# manifest_stamp_of - verify a report and echo the unix time of its stamp=
# row, the one name its recordings carry. A fault exits inside the verify.
manifest_stamp_of() {
  local dir="$1" role="$2"
  shift 2

  manifest_verify "$dir" "$role" "$@"

  local stamp
  stamp="$(manifest_value "$dir" stamp)"
  stamp="${stamp%% *}"

  [ -n "$stamp" ] || error_exit 2 \
    "error: $role report $(basename "$dir") records no stamp= row"
  echo "$stamp"
}

# manifest_value - one LABEL= row of a report's MANIFEST.txt.
manifest_value() {
  sed -n "s/^$2=//p" "$1/MANIFEST.txt" | head -1
}

# manifest_verify - hard-error unless line 1 is exactly one version string
# named, printing both found and expected. Args: directory, role, strings.
manifest_verify() {
  local dir="$1" role="$2"
  shift 2
  local fault
  fault="$(manifest_fault_of "$dir" "$@")"
  [ -z "$fault" ] || error_exit 2 "error: $role report: $fault"
}

# manifest_wanted_phrase - the version strings an error message says were
# expected, quoted, and joined with "or" when there is more than one.
manifest_wanted_phrase() {
  local phrase=""
  local candidate
  for candidate in "$@"; do
    [ -z "$phrase" ] || phrase="$phrase or "
    phrase="$phrase\"$candidate\""
  done
  echo "$phrase"
}

# manifest_write - write MANIFEST.txt, checksum row last, and the assets/
# script an error page reads it back from. Args: version, dir, LABEL=VALUE.
manifest_write() {
  local version="$1" dir="$2"
  shift 2
  local manifest="$dir/MANIFEST.txt" checksum
  # over the finished tree, before the redirect below creates the file the
  # checksum is written into
  rm -f "$manifest"
  manifest_script_write "$dir" "$version" "$@"
  checksum="$(checksum_compute "$dir")"
  {
    printf '%s\n' "$version"
    [ "$#" = 0 ] || printf '%s\n' "$@"
    printf '%s=%s\n' "$REPORT_MANIFEST_CHECKSUM_LABEL" "$checksum"
  } >"$manifest"
}

# page_command_run - command_run for a child whose output is page content:
# the same bytes go to the page file named first, shown as the line given.
page_command_run() {
  local page_file="$1" shown="$2"
  shift 2
  command_item_print "$shown"
  child_capture "$page_file" list "$@"
  [ "$CHILD_EXIT_CODE" = 0 ] || {
    failure_print_log_tail "$CHILD_EXIT_CODE" "$shown"
    exit "$CHILD_EXIT_CODE"
  }
}

# path_display - one absolute path written relative to a base: $INVOKED_FROM
# unless one is given second. Never $PWD: the scripts cd to dev/ at startup.
path_display() {
  python3 -c 'import os, sys
print(os.path.relpath(sys.argv[1], sys.argv[2]))' "$1" "${2:-$INVOKED_FROM}"
}

# report_begin - the head of every run writing a report: clear, create,
# drop the stale manifest, open $RUN_LOG, lay down README.md and assets.
report_begin() {
  # SETS RUN_LOG, its canonical setter: every command_run after this logs
  # into it. Args: dir, log name, opening line, 1 to keep contents else 0
  local dir="$1" log_name="$2" opening_line="$3" keep_contents="$4"
  [ "$keep_contents" = 1 ] || report_contents_clear "$dir"
  mkdir -p "$dir" "$ARTIFACTS_DIR"
  # the caller has read every row it wanted from the previous manifest, so
  # a run aborting from here leaves a directory no tool will open
  rm -f "$dir/MANIFEST.txt"
  RUN_LOG="$ARTIFACTS_DIR/$log_name"
  echo "$opening_line" >"$RUN_LOG"
  cp README.md "$dir/README.md"
  command_run python3 "$PERF2HTML_DIR_/scripts/build_report.py" assets \
    -o "$dir/$REPORT_ASSETS_DIR_NAME"
}

# report_contents_clear - empty a report a previous run wrote, so a dropped
# test or renamed asset is not certified by checksum_compute.
report_contents_clear() {
  # its MANIFEST.txt is the proof we wrote it: a directory holding anything
  # else is reported, never emptied -- --report=DIR may name a user's path
  local dir="$1"
  [ -e "$dir" ] || return 0
  [ -d "$dir" ] || error_exit 2 \
    "error: the report path is not a directory: $dir"
  # an --artifacts=TMP inside the report would be deleted by the clear
  # below, taking this run's own recordings with it
  local reason
  case "$ARTIFACTS_DIR/" in
    "$dir"/*)
      reason="error: the artifacts directory is inside the report, so"
      error_exit 2 \
        "$reason clearing the report would delete it: $ARTIFACTS_DIR" \
        "       (pass an --artifacts=TMP outside $dir)"
      ;;
  esac
  if [ -f "$dir/MANIFEST.txt" ]; then
    find "$dir" -mindepth 1 -maxdepth 1 -exec rm -rf {} + \
      || error_exit 1 "error: could not empty the previous report: $dir"
    return 0
  fi
  # an empty directory is the ordinary first run, and needs no clearing
  [ -z "$(ls -A "$dir")" ] && return 0
  reason="error: $dir holds files but no MANIFEST.txt, so it is not a"
  error_exit 2 "$reason report this can overwrite" \
    "       (an aborted run leaves one: delete it yourself, or name an" \
    "       empty --report directory)"
}

# report_finish - the tail of every run writing a report: the manifest last,
# saying the run finished, then the entry page. Args: dir, version, rows.
report_finish() {
  local dir="$1" version="$2"
  shift 2
  log_verbose "== manifest -> $dir/MANIFEST.txt =="
  manifest_write "$version" "$dir" "$@"
  log_verbose "$(printf '%-13s%s' manifest \
    "$(manifest_value "$dir" "$REPORT_MANIFEST_CHECKSUM_LABEL")")"
  log_verbose "$dir/index.html"
}

# script_capture - child_capture for one of our own scripts: its output is
# already formatted, so it is relayed untouched. SETS CHILD_EXIT_CODE.
script_capture() {
  # the parent separates: the child's title starts at its first line, and
  # every script's last verbose line is a paragraph, so a blank line ends it
  if [ "$VERBOSE" -ge 1 ] && [ "$OUTPUT_ENDS_BLANK" != 1 ]; then echo; fi
  child_capture "" relay "$@"
  OUTPUT_ENDS_BLANK=1
}

# table_head_print - a table's header row and rule, under --verbose, after
# a blank line. Args: one heading per column.
table_head_print() {
  [ "$VERBOSE" -ge 1 ] || return 0
  [ "$OUTPUT_ENDS_BLANK" = 1 ] || echo
  table_row_print "$@"
  local cell row='|'
  for cell in "$@"; do row="$row --- |"; done
  echo "$row"
}

# table_row_print - one table row under --verbose, a cell per argument, an
# empty argument an empty cell.
table_row_print() {
  [ "$VERBOSE" -ge 1 ] || return 0
  local cell row='|'
  for cell in "$@"; do
    if [ -z "$cell" ]; then row="$row |"; else row="$row $cell |"; fi
  done
  printf '%s\n' "$row" | verbose_filter paths
  OUTPUT_ENDS_BLANK=0
}

# title_print - the script's own heading, at its depth: its path and the
# arguments it was given. Args: the script's path, then its arguments.
title_print() {
  # the first line printed, so no blank line leads it: a parent running
  # this script has ended its own output with one
  OUTPUT_ENDS_BLANK=1
  heading_write "$HEADING_DEPTH" "$*"
}

# toolchain_check - the scripts' only toolchain check, collecting every
# missing tool before exiting. SETS SPEEDSCOPE_RELEASE, its canonical setter.
toolchain_check() {
  local tool missing=() lines=()
  for tool in cmake ninja ccache cc valgrind perf taskset python3 \
    addr2line readelf speedscope cksum; do
    command -v "$tool" >/dev/null 2>&1 || missing+=("$tool")
  done
  if [ "${#missing[@]}" != 0 ]; then
    lines=("error: ${#missing[@]} tool(s) not found on PATH:")
    for tool in "${missing[@]}"; do
      lines+=("$(printf '  %-12s -> %s' "$tool" \
        "$(install_command_of "$tool")")")
    done
    case " ${missing[*]} " in
      *" perf "*)
        lines+=("  note: linux-tools-generic is built against an Ubuntu"
          "        kernel WSL does not run. linux-perf is the"
          "        kernel-independent build.")
        ;;
    esac
    error_exit 1 "${lines[@]}"
  fi
  SPEEDSCOPE_RELEASE="$(dirname \
    "$(dirname "$(readlink -f "$(command -v speedscope)")")")/dist/release"
  [ -f "$SPEEDSCOPE_RELEASE/index.html" ] || error_exit 1 \
    "error: no speedscope bundle at $SPEEDSCOPE_RELEASE" \
    "       (reinstall it: npm install -g speedscope)"
}

# verbose_begin - the printer's state, once per script after args_parse. SETS
# START_US, HEADING_DEPTH, COMMAND_NUMBER, ITEM_INDENT, OUTPUT_ENDS_BLANK.
verbose_begin() {
  # PERF2HTML_HEADER_DEPTH is the one environment variable: read as this
  # script's heading depth, exported one deeper for the scripts it runs
  START_US="$(clock_microseconds)"
  HEADING_DEPTH="${PERF2HTML_HEADER_DEPTH:-1}"
  export PERF2HTML_HEADER_DEPTH=$((HEADING_DEPTH + 1))
  COMMAND_NUMBER=1
  ITEM_INDENT=0
  OUTPUT_ENDS_BLANK=0
}

# verbose_filter - the one formatter every printed line streams through,
# by mode: paths, wrap PREFIX, list INDENT, row LABEL, or relay (untouched).
verbose_filter() {
  # list: $HOME/ is ~/, blank lines go, a run of two or more `words: number
  # [unit]` lines is one single-row table, anything else a numbered item
  local mode="$1" argument="${2:-}"
  if [ "$mode" = relay ]; then
    cat
    return 0
  fi
  awk -v mode="$mode" -v argument="$argument" -v home="$HOME/" \
    -v width="$VERBOSE_LINE_WIDTH_CHARS" '
function shown(text,    at, out) {
  out = ""
  while ((at = index(text, home)) > 0) {
    out = out substr(text, 1, at - 1) "~/"
    text = substr(text, at + length(home))
  }
  return out text
}
function spaces(count,    text) {
  text = ""
  while (count-- > 0) text = text " "
  return text
}
function line_flush(line) {
  print line
  fflush()
}
function wrap(text, first, rest,    words, count, i, line, filled) {
  count = split(text, words, / /)
  line = first
  filled = 0
  for (i = 1; i <= count; i++) {
    if (filled && length(line) + 1 + length(words[i]) > width) {
      line_flush(line)
      line = rest words[i]
    } else if (filled) {
      line = line " " words[i]
    } else {
      line = line words[i]
    }
    filled = 1
  }
  line_flush(line)
}
function item_print(text,    marker) {
  if (after_table) {
    line_flush("")
    after_table = 0
  }
  number++
  marker = indent number ". "
  wrap(text, marker, spaces(length(marker)))
}
function group_flush(    i, line) {
  if (held == 0) return
  if (held == 1) {
    held = 0
    item_print(held_line[1])
    return
  }
  line_flush("")
  line = indent "|"
  for (i = 1; i <= held; i++) line = line " " key[i] " |"
  line_flush(line)
  line = indent "|"
  for (i = 1; i <= held; i++) line = line " --- |"
  line_flush(line)
  line = indent "|"
  for (i = 1; i <= held; i++) line = line " " value[i] " |"
  line_flush(line)
  after_table = 1
  held = 0
}
BEGIN {
  if (mode == "list") indent = spaces(argument)
  if (mode == "wrap") rest = spaces(length(argument))
}
{
  sub(/[ \t\r]+$/, "")
  line = shown($0)
  if (mode == "paths") {
    line_flush(line)
    next
  }
  if (mode == "wrap") {
    wrap(line, argument, rest)
    next
  }
  if (line == "") next
  if (mode == "row") {
    gsub(/\|/, "\\|", line)
    line_flush("| | " argument " | | `" line "` |")
    next
  }
  if (line ~ /^[A-Za-z][A-Za-z0-9\/ ]*: +-?[0-9][0-9.,]*( [A-Za-z\/]+)?$/) {
    match(line, /: +/)
    held++
    key[held] = substr(line, 1, RSTART - 1)
    value[held] = substr(line, RSTART + RLENGTH)
    held_line[held] = line
    next
  }
  group_flush()
  item_print(line)
}
END { group_flush() }
'
}

# verbose_flags_of - this run's --verbose level as a child's arguments: one
# --verbose per level, one per line, for the caller's mapfile -t.
verbose_flags_of() {
  local flag_count
  for ((flag_count = 0; flag_count < VERBOSE; flag_count++)); do
    echo --verbose
  done
}
