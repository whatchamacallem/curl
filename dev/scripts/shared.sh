# dev/scripts/shared.shz

# absolute_path - echo one path made absolute: a leading "~/" expands,
# a relative path is taken against $PWD, an absolute one is unchanged.
# Every script resolves every directory it was handed through this, so a
# report and its artifacts dir never depend on a later cd.
absolute_path() {
  case "$1" in
    "~/"*) echo "$HOME/${1#"~/"}" ;;
    /*) echo "$1" ;;
    *) echo "$PWD/$1" ;;
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

# child_capture - runs one child with its output going to $RUN_LOG, and
# records the child's exit code rather than taking it, so a caller can
# decide what a failure means. Verbose tees, so a long step's output
# arrives as it is produced. SETS the caller globals CHILD_EXIT_CODE and
# LOG_LINE_FROM, and is their canonical setter: the second is the line
# $RUN_LOG had reached before the child wrote, which failure_tail_print
# reads back. It reports through globals and never through stdout,
# because verbose's tee already owns stdout: a $(child_capture ...) would
# capture the child's own output along with the code.
child_capture() {
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

# clock_microseconds - wall clock in whole microseconds, from the
# EPOCHREALTIME builtin (its separator is the locale's, so every
# non-digit is dropped).
clock_microseconds() {
  local now="${EPOCHREALTIME}"
  echo "${now//[!0-9]/}"
}

# command_run - runs one child and, on failure, prints what it wrote and
# exits with its code. The policy a measuring run wants: the first failure
# ends the run, because every later step reads what this one was to write.
command_run() {
  log_verbose "\$ $*"
  child_capture "$@"
  if [ "$CHILD_EXIT_CODE" != 0 ]; then
    echo >&2
    failure_tail_print "$CHILD_EXIT_CODE" "$@"
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

# failure_tail_print - on stderr, what a failed child wrote: its exit
# code, the command, and the tail of its output from $LOG_LINE_FROM on.
# Arguments: the exit code, then the command and its arguments.
failure_tail_print() {
  local exit_code="$1"
  shift
  {
    echo "error: exit $exit_code from: $*"
    tail -n +"$((LOG_LINE_FROM + 1))" "$RUN_LOG" \
      | tail -n "$LOG_FAILURE_TAIL_LINES"
    echo "(last $LOG_FAILURE_TAIL_LINES lines; everything this run" \
      "printed: $RUN_LOG)"
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

# log_verbose_file - a step whose output was captured to a file rather
# than run through command_run: append the whole of it to $RUN_LOG, the
# way command_run would have, and show it too when verbose. Whole lines
# either way, because it is a file that was written a line at a time.
log_verbose_file() {
  local path="$1"
  cat "$path" >>"$RUN_LOG"
  if [ "$VERBOSE" = 1 ]; then cat "$path"; fi
}

# manifest_fault_of - the one reader deciding whether a directory is a
# finished report. Echoes why it is not, over as many lines as it takes,
# or nothing at all when it holds up. Every caller opening a report goes
# through this, so the checksum is re-verified every single time.
# Arguments: the directory, then each version string line 1 may read.
# A caller naming one string is how a diff is never read back as a diff
# input, and naming both is how either kind is accepted.
manifest_fault_of() {
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

# manifest_script_write - the assets/ script holding this report's
# manifest text as a string, for an error page to print on a file:// URL
# where nothing can be fetched. It carries every row but the checksum:
# the script is written before checksum_compute runs and is counted by
# it, so a checksum inside it could only ever be the previous run's.
manifest_script_write() {
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

# manifest_value - one LABEL= row of a report's MANIFEST.txt.
manifest_value() {
  sed -n "s/^$2=//p" "$1/MANIFEST.txt" | head -1
}

# manifest_verify - hard-error unless the directory holds up as a report
# whose line 1 is exactly one of the version strings named. The error
# prints both what was found and what was expected.
# Arguments: the directory, the role it plays in the message, then each
# version string line 1 may read.
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

# manifest_write - write a report's MANIFEST.txt, checksum row last, and
# the assets/ script an error page reads the same rows back from.
# Arguments: version string, report directory, then each LABEL=VALUE row.
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

# report_begin - the head of every run that writes a report: clear what a
# previous run left, create the directories, drop the stale manifest, open
# $RUN_LOG and lay down the two things every page links, README.md and the
# shared assets. SETS the caller global RUN_LOG, and is its canonical
# setter: every command_run after this logs into it.
# Arguments: the report directory, the run log's file name, the line that
# log opens with, and 1 to keep the report's contents or 0 to clear them.
report_begin() {
  local dir="$1" log_name="$2" opening_line="$3" keep_contents="$4"
  [ "$keep_contents" = 1 ] || report_contents_clear "$dir"
  mkdir -p "$dir" "$ARTIFACTS_DIR"
  # the caller has already read every row it wanted out of the previous
  # run's manifest, so a run that aborts from here on leaves a directory
  # no tool will open
  rm -f "$dir/MANIFEST.txt"
  RUN_LOG="$ARTIFACTS_DIR/$log_name"
  echo "$opening_line" >"$RUN_LOG"
  cp README.md "$dir/README.md"
  command_run python3 scripts/build_report.py assets \
    -o "$dir/$REPORT_ASSETS_DIR_NAME"
}

# report_contents_clear - empty a report directory that a previous run
# wrote, so nothing it no longer generates survives into the new tree and
# gets certified by checksum_compute: a dropped test's directory, or an
# asset since renamed. Its MANIFEST.txt is the proof we wrote it, which is
# why a directory holding anything else is left alone and reported rather
# than deleted -- a --report=DIR naming a populated path of the user's own
# must never be emptied.
report_contents_clear() {
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

# report_finish - the tail of every run that writes a report: the
# manifest, which is written last because it is what says the run
# finished and its checksum covers the finished tree, then the report's
# own URL.
# Arguments: the report directory, the version string, then each
# LABEL=VALUE row the manifest carries.
report_finish() {
  local dir="$1" version="$2"
  shift 2
  log_verbose "== manifest -> $dir/MANIFEST.txt =="
  manifest_write "$version" "$dir" "$@"
  printf '%-13s%s\n' manifest \
    "$(manifest_value "$dir" "$REPORT_MANIFEST_CHECKSUM_LABEL")"
  echo "file://$dir/index.html"
}

# toolchain_check - the only toolchain check the user-facing scripts
# have. Collects every missing tool before exiting, so one run names them
# all. SETS the caller global SPEEDSCOPE_RELEASE, and is its canonical
# setter: it is the resolved bundle the caller then copies pages out of.
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

# verbose_flags_of - this run's verbosity as the argument a child script
# takes, so handing it down is not a second test of $VERBOSE. It asks
# log_verbose, the one decider, to say the flag: verbose prints it and
# quiet prints nothing, which is exactly the array the caller wants.
verbose_flags_of() {
  log_verbose --verbose
}
