# dev/scripts/test_utility.sh

# path_shown - one path with $HOME/ written as ~/, for a printed line.
path_shown() {
  printf '%s' "${1//"$HOME"\//"~/"}"
}

# test_archive_first_of - the first raw archive under a report, sorted,
# echoed: the one a testcase removes, so no name is spelled here.
test_archive_first_of() {
  local _archive
  _archive="$(find "$1" -mindepth 3 -maxdepth 3 -type f \
    -path '*/raw/*.txz' | LC_ALL=C sort | head -n 1)"
  [ -n "$_archive" ] \
    || test_fail test_archive_first_of "no */raw/*.txz under $1"
  echo "$_archive"
}

# test_fail - the failed testcase and why, on stderr, then stop: the
# refusal streamed just above, and the scratch dir is kept for a reader.
test_fail() {
  {
    printf '\nFAILED: %s: %s\n' "$1" "$2"
    echo "(kept: $(path_shown "$_TEST_ERROR_SCRATCH"))"
  } >&2
  exit 1
}

# test_failure_expect - run a command that must refuse with the exit
# code given. Nothing is captured: its refusal streams. Args: NAME CODE --
test_failure_expect() {
  local _name="$1" _wanted_code="$2" _code=0
  shift 2
  [ "${1:-}" = -- ] || test_fail "$_name" \
    "test_failure_expect wants -- first"
  shift
  # stdin is closed: a delete prompt a testcase reaches gets no answer, a no,
  # instead of waiting on the terminal
  "$@" </dev/null || _code=$?
  [ "$_code" = "$_wanted_code" ] \
    || test_fail "$_name" "exit $_code, expected $_wanted_code, from: $*"
  echo "ok $_name"
}

# test_report_copy - copy a report to the path given, under the scratch
# dir, and echo that path. Every testcase edits a copy, never one.
test_report_copy() {
  cp -a "$2" "$1"
  echo "$1"
}

# tool_find - echo a tool's path, searching the pip and npm user bins too.
tool_find() {
  local name="$1" found
  for found in "$name" "$HOME/.local/bin/$name" \
    "$HOME/.npm-global/bin/$name"; do
    if command -v "$found" >/dev/null 2>&1; then
      echo "$found"
      return 0
    fi
  done
  return 1
}
