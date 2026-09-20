from __future__ import annotations

# What callgrind_diff.py's synthesized callers diff is named, next to the
# delta it describes. Written by perf2html_diff.sh, read back by
# build_report.py and skipped by validate_report.py.
CALLERS_SUFFIX = ".callers.json"

# The one event every generator ranks, colours and divides by, recorded or
# derived. Point it at any event callgrind.py knows and every page follows.
EVENT = "CEst"
