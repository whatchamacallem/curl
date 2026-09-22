# dev/scripts/shared.sh

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

# clock_microseconds - wall clock in whole microseconds, from the
# EPOCHREALTIME builtin (its separator is the locale's, so every
# non-digit is dropped).
clock_microseconds() {
  local now="${EPOCHREALTIME}"
  echo "${now//[!0-9]/}"
}

# command_run - runs one child, logs it to $RUN_LOG, and on failure
# prints the last 40 lines it wrote and exits with the child's code.
command_run() {
  local exit_code=0 from
  printf '\n$ %s\n' "$*" >>"$RUN_LOG"
  from="$(wc -l <"$RUN_LOG")"
  log_verbose "\$ $*"
  if [ "$VERBOSE" = 1 ]; then
    # tee so a step's output arrives as it is produced. The `if !` is what
    # keeps pipefail's failure from reaching PIPESTATUS's reader.
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

# log_verbose - the one function testing $VERBOSE. Verbose adds to quiet,
# so nothing else may guard a printf on it.
log_verbose() { if [ "$VERBOSE" = 1 ]; then echo "$@"; fi; }

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

# manifest_verify - hard-error unless the manifest exists, its line 1 is
# exactly "$want" and the files still checksum. Each names found/expected.
manifest_verify() {
  local dir="$1" want="$2" role="$3"
  local manifest="$dir/MANIFEST.txt" version recorded found
  local checksum_label="$REPORT_MANIFEST_CHECKSUM_LABEL"
  if [ ! -f "$manifest" ]; then
    echo "error: $role report has no MANIFEST.txt, so it is not a" \
      "finished report: $dir" >&2
    echo "       expected its first line to be: $want" >&2
    echo "       (a run that aborts writes no manifest; re-run it)" >&2
    exit 2
  fi
  version="$(head -1 "$manifest")"
  if [ "$version" != "$want" ]; then
    echo "error: $role report has an unrecognized MANIFEST.txt: $dir" >&2
    echo "       found:    $version" >&2
    echo "       expected: $want" >&2
    exit 2
  fi
  recorded="$(manifest_value "$dir" "$checksum_label")"
  if [ -z "$recorded" ]; then
    echo "error: $role report has no $checksum_label= row, so its files" \
      "cannot be verified: $dir" >&2
    echo "       expected: a $checksum_label= row beside the version" \
      "line $want" >&2
    exit 2
  fi
  found="$(checksum_compute "$dir")"
  if [ "$found" != "$recorded" ]; then
    echo "error: $role report does not match its recorded" \
      "$checksum_label: $dir" >&2
    echo "       found:    $found" >&2
    echo "       expected: $recorded" >&2
    echo "       (a file was added, removed or edited after the report" \
      "was written)" >&2
    exit 2
  fi
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
