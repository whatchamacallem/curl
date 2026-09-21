# shellcheck shell=bash
# dev/report_manifest.sh -- sourced by perf2html.sh, perf2html_diff.sh and
# scripts/reformat.sh. Not executable on its own.
#
# One MANIFEST.txt contract in one place, because all three scripts have to
# agree on it byte for byte, and with scripts/settings.py, which holds the
# three strings below and hands them to validate_report.py:
#
#   line 1        the version string, which is the ONLY thing that makes a
#                 directory a report. A diff's names perf2html_diff.sh, so
#                 a diff can never be read back as a diff input.
#   LABEL=VALUE   the header rows the overview page renders.
#   checksum=     POSIX cksum over every other file in the report.
#
# The manifest is written LAST, after every page, asset and raw archive is
# in place, so a directory holding one is a run that finished. An aborted
# run leaves none and every reader below rejects it.
#
# The checksum is order-independent and relative: the file list is
# LC_ALL=C sorted and every path fed to cksum is relative to the report
# directory, so the same tree checksums the same on any box it is copied
# to. MANIFEST.txt is excluded because it carries the result.

# settings.py, the one spelling of REPORT_MANIFEST, DIFF_MANIFEST and
# CHECKSUM_LABEL. Path is from this file, as callers source from two dirs.
MANIFEST_SETTINGS="$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")"
MANIFEST_SETTINGS="$MANIFEST_SETTINGS/scripts/settings.py"
if ! MANIFEST_SETTINGS_TEXT="$(python3 "$MANIFEST_SETTINGS" --shell)"; then
  echo "error: cannot read the manifest settings out of" \
    "$MANIFEST_SETTINGS" >&2
  echo "       (python3 is required: apt install python3)" >&2
  exit 1
fi
eval "$MANIFEST_SETTINGS_TEXT"

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

# manifest_write - write a report's MANIFEST.txt, checksum row last.
# Arguments: version string, report directory, then each LABEL=VALUE row.
manifest_write() {
  local version="$1" dir="$2"
  shift 2
  local manifest="$dir/MANIFEST.txt" checksum
  # over the finished tree, before the redirect below creates the file the
  # checksum is written into
  rm -f "$manifest"
  checksum="$(checksum_compute "$dir")"
  {
    printf '%s\n' "$version"
    [ "$#" = 0 ] || printf '%s\n' "$@"
    printf '%s=%s\n' "$CHECKSUM_LABEL" "$checksum"
  } >"$manifest"
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
  recorded="$(manifest_value "$dir" "$CHECKSUM_LABEL")"
  if [ -z "$recorded" ]; then
    echo "error: $role report has no $CHECKSUM_LABEL= row, so its files" \
      "cannot be verified: $dir" >&2
    echo "       expected: a $CHECKSUM_LABEL= row beside the version" \
      "line $want" >&2
    exit 2
  fi
  found="$(checksum_compute "$dir")"
  if [ "$found" != "$recorded" ]; then
    echo "error: $role report does not match its recorded" \
      "$CHECKSUM_LABEL: $dir" >&2
    echo "       found:    $found" >&2
    echo "       expected: $recorded" >&2
    echo "       (a file was added, removed or edited after the report" \
      "was written)" >&2
    exit 2
  fi
}
