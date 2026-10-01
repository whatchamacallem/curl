# dev/scripts/utility.sh

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

# archive_extract - unpack one report archive into the named role's
# subdirectory of an extraction root, echoing the report directory inside.
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
  # the archive holds the one report directory archive_report_write named
  # it after, so the report is at that name and no listing decides it
  tar xJf "$archive" -C "$into" || error_exit 2 \
    "error: tar could not extract the $role archive: $archive"
  [ -d "$into/$report_name" ] || error_exit 2 \
    "error: the $role archive holds no $report_name directory: $archive"
  echo "$into/$report_name"
}

# archive_report_write - one reproducible tar.xz of a finished report,
# beside it, named <report>.txz. Written whole, then moved into place.
archive_report_write() {
  local dir="$1"
  local archive="$dir$REPORT_RAW_ARCHIVE_SUFFIX" staged
  # the previous archive is a recovery copy until this one is whole: tar
  # writes a sibling temporary name, and only a finished one is moved over
  staged="$archive.$TIMESTAMP.part"
  command_run tar --sort=name --mtime=@0 --owner=0 --group=0 \
    --numeric-owner -cJf "$staged" -C "$(dirname "$dir")" "$(basename "$dir")"
  mv -f "$staged" "$archive" || error_exit 1 \
    "error: could not move $staged onto $archive"
  log_verbose "$archive"
}

# artifacts_clean - deletes this run's artifacts subdir, and its parent once
# no sibling run keeps files there: the cache is debug only unless kept.
artifacts_clean() {
  [ -d "$ARTIFACTS_DIR" ] || return 0
  rm -r "$ARTIFACTS_DIR"
  rmdir --ignore-fail-on-non-empty "$(dirname "$ARTIFACTS_DIR")"
}

# artifacts_dir_resolve - $ARTIFACTS_DIR absolute, as --artifacts= named it,
# else a mktemp -d unless kept, else $ARTIFACTS_NAME in the dir given.
artifacts_dir_resolve() {
  # SETS ARTIFACTS_DIR. Arg: the dir a kept one defaults into, the report's
  # parent for perf2html.sh and the diff, the target dir for the batch
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

# block_lead - the blank line before a block, none before a hand-run script's
# first or after a tight item before the next. SETS VERBOSE_BLOCK_PRINTED.
block_lead() {
  # kinds: item, or other for a heading, paragraph or table. Unset, before
  # verbose_begin, the state is a parent's: something is printed above
  local kind="$1" printed="${VERBOSE_BLOCK_PRINTED-other}"
  # plain text has no blocks to keep apart: the raw levels print the lines
  # and nothing between them
  VERBOSE_BLOCK_PRINTED="$kind"
  [ "$VERBOSE" -lt "$VERBOSE_RAW_LEVEL" ] || return 0
  # only an item right after a tight one goes without: loose, the state
  # verbose_filter leaves after a table, wants the blank line whatever comes
  [ "$printed" = none ] || { [ "$kind" = item ] && [ "$printed" = item ]; } \
    || echo >&2
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

# child_capture - run one tool into $RUN_LOG, and a page file when one is
# named, teeing under --verbose. SETS CHILD_EXIT_CODE and LOG_LINE_FROM.
child_capture() {
  # args: page file or "", then the command: a tool, never one of our own
  # scripts; at level 1 its lines nest in a fence, above that they are raw
  local page_file="$1"
  shift
  local logs=("$RUN_LOG") statuses=() status
  [ -z "$page_file" ] || logs+=("$page_file")
  CHILD_EXIT_CODE=0
  printf '\n$ %s\n' "$*" >>"$RUN_LOG"
  LOG_LINE_FROM="$(wc -l <"$RUN_LOG")"
  # the `if !` is what keeps pipefail's failure from reaching PIPESTATUS's
  # reader; the tee and the filter are chosen before the child starts
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
  # tee or the filter failing tore the log or the terminal whatever the
  # child did: never a pass
  for status in "${statuses[@]:1}"; do
    [ "$status" = 0 ] || error_exit 1 \
      "error: tee or verbose_filter exited $status behind: $*"
  done
}

# child_capture_noisy - a child whose output is noise, like cmake's configure:
# raw on the terminal from the raw level up, discarded below. Returns its code.
child_capture_noisy() {
  # a return code, not CHILD_EXIT_CODE: child_capture is that global's one
  # setter, and below the raw level nothing reaches $RUN_LOG or the terminal
  if [ "$VERBOSE" -ge "$VERBOSE_RAW_LEVEL" ]; then
    child_capture "" "$@"
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

# code_span - text as --verbose shows it, $HOME/ written ~/, in one code span
# as prettier prints one: the shortest backtick run the text lacks around it.
code_span() {
  # the raw levels are plain text: the line as it stands, $HOME and all
  if [ "$VERBOSE" -ge "$VERBOSE_RAW_LEVEL" ]; then
    printf '%s\n' "$1"
    return 0
  fi
  local text="${1//"${HOME:?}"\//\~/}" run='`' gap='' edge='[^`]'
  while [[ "$text" =~ (^|$edge)"$run"($edge|$) ]]; do run+='`'; done
  # a space inside where the markdown would else eat one: a backtick at an
  # end, or spaces at both ends of text that is not all spaces
  if [[ "$text" == \`* || "$text" == *\` ||
    ("$text" == ' '*' ' && "$text" == *[!' ']*) ]]; then
    gap=' '
  fi
  printf '%s%s%s%s%s\n' "$run" "$gap" "$text" "$gap" "$run"
}

# command_item_print - the numbered item a command's output nests under,
# `$ command`. SETS VERBOSE_ITEM_INDENT, VERBOSE_COMMAND_NUMBER.
command_item_print() {
  local marker="$VERBOSE_COMMAND_NUMBER. "
  VERBOSE_ITEM_INDENT="${#marker}"
  VERBOSE_COMMAND_NUMBER=$((VERBOSE_COMMAND_NUMBER + 1))
  [ "$VERBOSE" -ge 1 ] || return 0
  block_lead item
  printf '%s%s\n' "$marker" "$(code_span "\$ $1")" >&2
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

# elapsed_format - seconds since $PERF2HTML_CLOCK_START_US, two decimals, for
# the [Ns] prefix every line of a run carries, its child scripts' included.
elapsed_format() {
  local delta=$(($(clock_microseconds) - PERF2HTML_CLOCK_START_US))
  printf '%d.%02d' "$((delta / 1000000))" "$((delta % 1000000 / 10000))"
}

# error_exit - the one way a script refuses: its lines through verbose_filter
# onto stderr, then exit with the code given first. Nothing collects a failure.
error_exit() {
  local exit_code="$1"
  shift
  printf '%s\n' "$@" | verbose_filter 0
  exit "$exit_code"
}

# failure_print_log_tail - on stderr, through verbose_filter, a failed child's
# exit code, command and output tail from $LOG_LINE_FROM on.
failure_print_log_tail() {
  local exit_code="$1" shown="$2"
  {
    echo "error: exit $exit_code from: $shown"
    tail -n +"$((LOG_LINE_FROM + 1))" "$RUN_LOG" \
      | tail -n "$LOG_FAILURE_TAIL_LINES"
    echo "(see: $RUN_LOG)"
  } | verbose_filter 0
}

# heading_print - one piece of work, a heading one level below the script's
# own title, reading `[elapsed] text`; the item numbers restart under it.
heading_print() {
  heading_write "$((PERF2HTML_HEADER_DEPTH + 1))" "$*"
}

# heading_write - a heading at the depth given, its marks dropped from the
# raw level up. SETS VERBOSE_COMMAND_NUMBER back to 1.
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

# install_command_of - one tool's official install command. Nothing
# hand-rolled and no PPA belongs here.
install_command_of() {
  case "$1" in
    cmake | ninja | ccache | valgrind | taskset | python3 | cksum | curl | \
      tar | xz | dpkg-query)
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
  printf '%s\n' "$@" | verbose_filter "$VERBOSE_ITEM_INDENT"
}

# json_quote - one string as a JSON string literal, for a generated .js.
json_quote() {
  local text="$1"
  text="${text//\\/\\\\}"
  text="${text//\"/\\\"}"
  text="${text//$'\r'/\\r}"
  text="${text//$'\n'/\\n}"
  printf '"%s"' "$text"
}

# log_verbose - one status line, a paragraph of one code span under
# --verbose. Verbose adds to quiet, so nothing else guards a printf.
log_verbose() {
  [ "$VERBOSE" -ge 1 ] || return 0
  block_lead other
  code_span "$*" >&2
}

# manifest_fault_of - the one reader deciding whether a directory is a
# finished report, echoing why it is not or nothing when it holds up.
manifest_fault_of() {
  # args: the dir, then each version string line 1 may read -- naming one
  # keeps a diff out of a diff, naming both accepts either kind
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

# manifest_recorded_of - verify a report and echo the unix time of its
# recorded= row, the one name its recordings carry. A fault exits inside.
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

# manifest_recorded_row - the recorded= row a measured report writes: the
# unix time every reader takes, then a date for a human, which nothing parses.
manifest_recorded_row() {
  echo "recorded=$TIMESTAMP $(date -d "@$TIMESTAMP" +'%F %I:%M:%S %p')"
}

# manifest_table_of - settings.manifest_table's formatting of a version and
# its LABEL=VALUE rows, the one door onto that Python function from shell.
manifest_table_of() {
  PYTHONPATH="$PERF2HTML_DIR_/scripts${PYTHONPATH:+:$PYTHONPATH}" \
    python3 -c 'import sys, settings
print(settings.manifest_table(sys.argv[1:]), end="")' "$@"
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

# manifest_write - write the shared assets, report_complete.js, the
# checksum, then MANIFEST.txt, in that order. Args: version, dir, rows.
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

# page_command_run - command_run for a child whose output is page content:
# the same bytes go to the page file named first, shown as the line given.
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

# path_display - one absolute path written relative to a base: $INVOKED_FROM
# unless one is given second. Never $PWD: the scripts cd to dev/ at startup.
path_display() {
  python3 -c 'import os, sys
print(os.path.relpath(sys.argv[1], sys.argv[2]))' "$1" "${2:-$INVOKED_FROM}"
}

# path_overlap_check - refuse two given paths, or one and dev/scripts,
# nested either way; refuse $INVOKED_FROM only nested inside a given path.
path_overlap_check() {
  # args: a path then its role, repeated; every pair is checked once, plus
  # each against dev/scripts and $INVOKED_FROM (each is a separate check)
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

# quiet_switch_set - an outside tool's own quiet switch, left empty under
# --verbose so its good news shows. SETS QUIET_SWITCH, its canonical setter.
quiet_switch_set() {
  QUIET_SWITCH=()
  case "$1" in
    prettier) [ "$VERBOSE" -ge 1 ] || QUIET_SWITCH=(--log-level warn) ;;
    ruff) [ "$VERBOSE" -ge 1 ] || QUIET_SWITCH=(--quiet) ;;
    *) error_exit 1 "error: no quiet switch is recorded for $1" ;;
  esac
}

# report_begin - the head of every run writing a report: create it, open
# $RUN_LOG, lay down README.md and the empty assets/ dir.
report_begin() {
  # SETS RUN_LOG, its canonical setter: every command_run after this logs
  # into it. Args: dir, log name, opening line
  local dir="$1" log_name="$2" opening_line="$3"
  mkdir -p "$dir" "$dir/$REPORT_ASSETS_DIR_NAME" "$ARTIFACTS_DIR"
  RUN_LOG="$ARTIFACTS_DIR/$log_name"
  echo "$opening_line" >"$RUN_LOG"
  cp README.md "$dir/README.md"
}

# report_complete_write - the assets/ script written last, holding the
# manifest table text, proving to an error page that the run finished.
report_complete_write() {
  local dir="$1" table="$2"
  local out="$dir/$REPORT_ASSETS_DIR_NAME/$ASSET_REPORT_COMPLETE_SCRIPT_NAME"
  {
    printf 'window.report_manifest_table = %s;\n' "$(json_quote "$table")"
    screenshot_label_script_print
  } >"$out"
}

# report_delete - delete a report and the archive beside it, both output
# only. No directory, or one with no MANIFEST.txt, goes only on a typed y.
report_delete() {
  local dir="$1" answer present=0
  local archive="$dir$REPORT_RAW_ARCHIVE_SUFFIX"
  path_overlap_check "$dir" report "$ARTIFACTS_DIR" "artifacts dir"
  [ ! -e "$dir" ] || present=1
  if [ "$present" = 1 ] \
    && { [ ! -d "$dir" ] || [ ! -e "$dir/MANIFEST.txt" ]; }; then
    # the file's existence alone, never its contents; no answer at all, as
    # from /dev/null, ends the prompt's line and is a no
    printf 'Delete %s? [y/N] ' "$(path_display "$dir")" >&2
    read -r answer || {
      echo >&2
      answer=
    }
    [ "$answer" = y ] || error_exit 1 \
      "error: the report is not deleted without a typed y: $dir"
  fi
  rm -rf "$dir" || error_exit 1 "error: could not delete the report: $dir"
  # the archive follows its directory's one decision and is never prompted
  # for on its own; with no directory to answer for, it is left standing
  [ "$present" = 1 ] && [ -e "$archive" ] || return 0
  rm -f "$archive" || error_exit 1 \
    "error: could not delete the report archive: $archive"
}

# report_finish - the tail of every run writing a report: the manifest last,
# saying the run finished, then the entry page. Args: dir, version, rows.
report_finish() {
  local dir="$1" version="$2"
  shift 2
  log_verbose "== manifest -> $dir/MANIFEST.txt =="
  manifest_write "$version" "$dir" "$@"
  log_verbose "manifest $(manifest_value "$dir" \
    "$REPORT_MANIFEST_CHECKSUM_LABEL")"
  log_verbose "$dir/index.html"
  # the archive holds the finished report, MANIFEST.txt and all, so it
  # extracts to a directory every reader verifies the way it verifies one
  [ "$WRITE_REPORT_ARCHIVE" = 1 ] || return 0
  heading_print "tar $(basename "$dir")$REPORT_RAW_ARCHIVE_SUFFIX"
  archive_report_write "$dir"
}

# report_path_of - one report's absolute path by the one rule, a name starting
# with / or ~/ as named, any other under $TARGET_DIR.
report_path_of() {
  local report_name="$1"
  case "$report_name" in
    /* | "~/"*) absolute_path "$report_name" ;;
    *) absolute_path "$TARGET_DIR/$report_name" ;;
  esac
}

# revision_describe - the checkout's short revision, -dirty appended while
# it holds uncommitted changes. Args: the repository directory.
revision_describe() {
  local repository="$1" revision dirty=0
  # the checkout is the curl repository, so git failing here is git's own
  # error; git diff --quiet answers 1 for a dirty tree, anything else a fault
  revision="$(git -C "$repository" rev-parse --short HEAD)"
  git -C "$repository" diff --quiet HEAD -- || dirty=$?
  if [ "$dirty" = 1 ]; then
    revision="$revision-dirty"
  elif [ "$dirty" != 0 ]; then
    error_exit 1 "error: git diff --quiet exited $dirty in $repository"
  fi
  echo "$revision"
}

# screenshot_label_script_print - the one-off call showing a "screenshot"
# URL param as a fixed bottom-left label, a capture's identification aid.
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

# shared_options_parse - the options every perf2html*.sh takes, wherever
# they stand, --help printing the calling script's usage_show and exiting.
shared_options_parse() {
  # SETS ARTIFACTS_DIR, KEEP_ARTIFACTS, REGENERATE, REMAINING_ARGUMENTS (the
  # rest, in order), TARGET_DIR (absolute), VERBOSE, WRITE_REPORT_ARCHIVE
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

# source_cache_fetch - download and unpack one source version under the
# package directory, staged so an interrupted fetch leaves nothing behind.
source_cache_fetch() {
  local package="$1" version="$2" directory="$3"
  # the orig tarball carries the upstream version only, the archive revision
  # after the last - being the packaging's and no part of the tarball's name
  local upstream="${version%-*}" pool staged tarball root
  pool="$CACHE_ARCHIVE_BASE_URL/${package:0:1}/$package"
  local url="$pool/${package}_$upstream.orig.tar.xz"
  # the package directory is replaced whole: a version that moved on leaves
  # no older tree behind, which is the invalidation the cache is given
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
  # the tarball holds its one <package>-<upstream> directory, which becomes
  # the version directory itself, so no page path carries that name twice
  root="$staged/$package-$upstream"
  [ -d "$root" ] || error_exit 1 \
    "error: $url holds no $package-$upstream directory"
  mv -f "$root" "$directory" || error_exit 1 \
    "error: could not move $root onto $directory"
  rm -rf "$staged"
  log_verbose "cached $package $version sources in $directory"
}

# source_cache_sync - make the installed external package's sources readable,
# downloading them once per version. SETS nothing; the heat map reads the dir.
source_cache_sync() {
  local installed package version directory
  installed="$(dpkg-query -W -f='${source:Package} ${source:Version}' \
    "$CACHE_EXTERNAL_PACKAGE")" || error_exit 1 \
    "error: dpkg-query knows no package $CACHE_EXTERNAL_PACKAGE"
  package="${installed%% *}"
  version="${installed##* }"
  [ -n "$package" ] && [ -n "$version" ] || error_exit 1 \
    "error: dpkg-query named no source package and version: $installed"
  directory="$(absolute_path "$CACHE_ROOT_DIR")/$package/$version"
  [ -d "$directory" ] || source_cache_fetch "$package" "$version" "$directory"
}

# table_print - one table under --verbose, padded as prettier pads one, or
# header: value lines from the raw level up. Args: columns, then every cell.
table_print() {
  [ "$VERBOSE" -ge 1 ] || return 0
  local columns="$1" cells=() widths=() rule=() cell line row column
  shift
  if [ "$#" -le "$columns" ] || [ "$(($# % columns))" != 0 ]; then
    error_exit 1 \
      "error: table_print: $# cell(s) are no header and whole rows of $columns"
  fi
  # the raw levels are plain text: one header: value line per cell, which
  # needs no padding, no rule row and no pipe to escape
  if [ "$VERBOSE" -ge "$VERBOSE_RAW_LEVEL" ]; then
    block_lead other
    for ((row = columns; row < "$#"; row++)); do
      column=$((row % columns))
      printf '%s: %s\n' "${@:column+1:1}" "${@:row+1:1}" >&2
    done
    return 0
  fi
  # a value is one code span, its pipes escaped as a table wants
  cells=("${@:1:columns}")
  for cell in "${@:columns+1}"; do
    cells+=("$(code_span "${cell//|/\\|}")")
  done
  # a column is as wide as its widest cell, three at least, and the rule row
  # below the header is dashes that wide
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

# title_print - the script's own heading, at its depth: its path and the
# arguments it was given. Args: the script's path, then its arguments.
title_print() {
  # the first line printed: verbose_begin's VERBOSE_BLOCK_PRINTED is why a
  # blank line leads it only below a parent's lines
  heading_write "$PERF2HTML_HEADER_DEPTH" "$*"
}

# toolchain_check - the scripts' only toolchain check, collecting every
# missing tool before exiting. SETS SPEEDSCOPE_RELEASE, its canonical setter.
toolchain_check() {
  local tool missing=() lines=()
  for tool in cmake ninja ccache cc valgrind perf taskset python3 \
    addr2line readelf speedscope cksum curl tar xz dpkg-query; do
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

# verbose_begin - the printer's state, once per script after args_parse. SETS
# lastpipe, the two PERF2HTML_* environment variables, the VERBOSE_* globals.
verbose_begin() {
  # a script's depth is the one it inherits plus 1, and 1 run by hand; the
  # clock is the outermost script's, which every script it runs inherits
  export PERF2HTML_HEADER_DEPTH=$((${PERF2HTML_HEADER_DEPTH:-0} + 1))
  PERF2HTML_CLOCK_START_US="${PERF2HTML_CLOCK_START_US:-$(clock_microseconds)}"
  export PERF2HTML_CLOCK_START_US
  # verbose_filter ends a pipeline and sets VERBOSE_BLOCK_PRINTED: lastpipe
  # runs that last stage in this shell, where the setting has to land
  shopt -s lastpipe
  VERBOSE_COMMAND_NUMBER=1
  VERBOSE_ITEM_INDENT=0
  # none only for a verbose run's first line: under a parent, or quiet, a
  # blank line leads the first block, as something may be printed above it
  VERBOSE_BLOCK_PRINTED=other
  if [ "$PERF2HTML_HEADER_DEPTH" = 1 ] && [ "$VERBOSE" -ge 1 ]; then
    VERBOSE_BLOCK_PRINTED=none
  fi
}

# verbose_filter - the one formatter a child's lines stream through, onto
# stderr at the indent given. SETS VERBOSE_BLOCK_PRINTED loose after a table.
verbose_filter() {
  # two or more `words: number [unit]` lines in a row are one single-row
  # table under the item; any other line sits in a ```txt fence, $HOME/ as ~/
  local separate=0 lead=0 loose status=0 raw_line
  # the raw levels format nothing: each line onto stderr as it arrives, the
  # read loop so no external command holds one back in a block buffer
  if [ "$VERBOSE" -ge "$VERBOSE_RAW_LEVEL" ]; then
    while IFS= read -r raw_line || [ -n "$raw_line" ]; do
      printf '%s\n' "$raw_line" >&2
    done
    return 0
  fi
  # at indent 0 blocks are apart, the first led by a blank line unless it is
  # the script's first; indented, they nest in the item above, tight
  if [ "$1" = 0 ]; then
    separate=1
    [ "${VERBOSE_BLOCK_PRINTED-other}" = none ] || lead=1
  fi
  # the lines go to stderr as they come; stdout is the awk's one answer, a
  # value: loose when a table led the output, so a blank line had to lead it
  loose="$(awk -v indent="$(printf '%*s' "$1" '')" -v home="${HOME:?}/" \
    -v separate="$separate" -v lead="$lead" '
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
  # a fence is as long as prettier makes one, three backticks or one past the
  # longest run inside: a line running that long closes it and opens a longer
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
  # the held run as a table: tight after a fence, but right after the item
  # line it needs a blank line, which makes the item loose, its blocks apart
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
    # a column is as wide as its header word or its value in a code span,
    # whichever is longer, the way prettier pads; the rule is dashes that wide
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
  indent != "" &&
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

# verbose_flags_of - this run's --verbose level as a child's arguments: one
# --verbose per level, one per line, for the caller's mapfile -t.
verbose_flags_of() {
  local flag_count
  for ((flag_count = 0; flag_count < VERBOSE; flag_count++)); do
    echo --verbose
  done
}
