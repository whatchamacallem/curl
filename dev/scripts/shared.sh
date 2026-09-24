# dev/scripts/shared.shz

# absolute_path - Every script resolves paths relative to $INVOKED_FROM.
absolute_path() {
  case "$1" in
    "~/"*) echo "$HOME/${1#"~/"}" ;;
    /*) echo "$1" ;;
    *) echo "$INVOKED_FROM/$1" ;;
  esac
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

# child_capture - run one child into $RUN_LOG, verbose teeing. SETS
# CHILD_EXIT_CODE and LOG_LINE_FROM, their canonical setter.
child_capture() {
  # never stdout: verbose's tee owns it, so $(child_capture) would capture
  # the child's own output along with the code
  CHILD_EXIT_CODE=0
  printf '\n$ %s\n' "$*" >>"$RUN_LOG"
  LOG_LINE_FROM="$(wc -l <"$RUN_LOG")"
  if [ "$VERBOSE" = 1 ]; then
    # the `if !` is what keeps pipefail's failure from reaching
    # PIPESTATUS's reader
    if ! { "$@" 2>&1 | tee -a "$RUN_LOG"; }; then
      CHILD_EXIT_CODE="${PIPESTATUS[0]}"
    fi
  else
    "$@" >>"$RUN_LOG" 2>&1 || CHILD_EXIT_CODE=$?
  fi
}

# clock_microseconds - wall clock in whole microseconds, from EPOCHREALTIME
# (its separator is the locale's, so every non-digit is dropped).
clock_microseconds() {
  local now="${EPOCHREALTIME}"
  echo "${now//[!0-9]/}"
}

# command_run - the one policy on child_capture: on failure print what the
# child wrote and exit with its code. No caller of it collects a failure.
command_run() {
  log_verbose "\$ $*"
  child_capture "$@"
  if [ "$CHILD_EXIT_CODE" != 0 ]; then
    echo >&2
    failure_print_log_tail "$CHILD_EXIT_CODE" "$@"
    exit "$CHILD_EXIT_CODE"
  fi
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

# failure_print_log_tail - on stderr, a failed child's exit code, command, and
# output tail from $LOG_LINE_FROM on. Args: exit code, command, arguments.
failure_print_log_tail() {
  local exit_code="$1"
  shift
  {
    echo "error: exit $exit_code from: $*"
    tail -n +"$((LOG_LINE_FROM + 1))" "$RUN_LOG" \
      | tail -n "$LOG_FAILURE_TAIL_LINES"
    echo "(see: $RUN_LOG)"
  } >&2
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
    *) echo "(no official install command is recorded for this tool)" ;;
  esac
}

# json_quote - one string as a JSON string literal, for a generated .js.
json_quote() {
  local text="$1"
  text="${text//\\/\\\\}"
  text="${text//\"/\\\"}"
  printf '"%s"' "$text"
}

# log_verbose - the one function deciding whether a line is printed.
# Verbose adds to quiet, so nothing else may guard a printf on it.
log_verbose() { if [ "$VERBOSE" = 1 ]; then echo "$@"; fi; }

# log_verbose_file - a step's captured output file: append the whole of it
# to $RUN_LOG as command_run would, and show it too when verbose.
log_verbose_file() {
  local path="$1"
  cat "$path" >>"$RUN_LOG"
  if [ "$VERBOSE" = 1 ]; then cat "$path"; fi
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

  [ -n "$stamp" ] || {
    echo "error: $role report $(basename "$dir") records no stamp= row" >&2
    exit 2
  }
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
  if [ -n "$fault" ]; then
    echo "error: $role report: $fault" >&2
    exit 2
  fi
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
  command_run python3 scripts/build_report.py assets \
    -o "$dir/$REPORT_ASSETS_DIR_NAME"
}

# report_contents_clear - empty a report a previous run wrote, so a dropped
# test or renamed asset is not certified by checksum_compute.
report_contents_clear() {
  # its MANIFEST.txt is the proof we wrote it: a directory holding anything
  # else is reported, never emptied -- --report=DIR may name a user's path
  local dir="$1"
  [ -e "$dir" ] || return 0
  if [ ! -d "$dir" ]; then
    echo "error: the report path is not a directory: $dir" >&2
    exit 2
  fi
  # an --artifacts=TMP inside the report would be deleted by the clear
  # below, taking this run's own recordings with it
  case "$ARTIFACTS_DIR/" in
    "$dir"/*)
      echo "error: the artifacts directory is inside the report, so" \
        "clearing the report would delete it: $ARTIFACTS_DIR" >&2
      echo "       (pass an --artifacts=TMP outside $dir)" >&2
      exit 2
      ;;
  esac
  if [ -f "$dir/MANIFEST.txt" ]; then
    find "$dir" -mindepth 1 -maxdepth 1 -exec rm -rf {} + || {
      echo "error: could not empty the previous report: $dir" >&2
      exit 1
    }
    return 0
  fi
  # an empty directory is the ordinary first run, and needs no clearing
  [ -z "$(ls -A "$dir")" ] || {
    echo "error: $dir holds files but no MANIFEST.txt, so it is not a" \
      "report this can overwrite" >&2
    echo "       (an aborted run leaves one: delete it yourself, or" \
      "name an empty --report directory)" >&2
    exit 2
  }
}

# report_finish - the tail of every run writing a report: the manifest last,
# saying the run finished, then the URL. Args: dir, version, LABEL=VALUE rows.
report_finish() {
  local dir="$1" version="$2"
  shift 2
  log_verbose "== manifest -> $dir/MANIFEST.txt =="
  manifest_write "$version" "$dir" "$@"
  printf '%-13s%s\n' manifest \
    "$(manifest_value "$dir" "$REPORT_MANIFEST_CHECKSUM_LABEL")"
  echo "file://$dir/index.html"
}

# toolchain_check - the scripts' only toolchain check, collecting every
# missing tool before exiting. SETS SPEEDSCOPE_RELEASE, its canonical setter.
toolchain_check() {
  local tool missing=()
  for tool in cmake ninja ccache cc valgrind perf taskset python3 \
    addr2line readelf speedscope cksum; do
    command -v "$tool" >/dev/null 2>&1 || missing+=("$tool")
  done
  if [ "${#missing[@]}" != 0 ]; then
    {
      echo "error: ${#missing[@]} tool(s) not found on PATH:"
      for tool in "${missing[@]}"; do
        printf '  %-12s -> %s\n' "$tool" "$(install_command_of "$tool")"
      done
      case " ${missing[*]} " in
        *" perf "*)
          echo "  note: linux-tools-generic is built against an Ubuntu"
          echo "        kernel WSL does not run. linux-perf is the"
          echo "        kernel-independent build."
          ;;
      esac
    } >&2
    exit 1
  fi
  SPEEDSCOPE_RELEASE="$(dirname \
    "$(dirname "$(readlink -f "$(command -v speedscope)")")")/dist/release"
  [ -f "$SPEEDSCOPE_RELEASE/index.html" ] || {
    echo "error: no speedscope bundle at $SPEEDSCOPE_RELEASE" >&2
    echo "       (reinstall it: npm install -g speedscope)" >&2
    exit 1
  }
}

# verbose_flags_of - this run's verbosity as a child's argument, so handing
# it down is not a second test of $VERBOSE: log_verbose says the flag.
verbose_flags_of() {
  log_verbose --verbose
}
