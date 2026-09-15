#!/usr/bin/env python3
"""Fixed-width text summary of a callgrind profile: the totals block (refs,
misses, miss rates, branch mispredicts, simulated cache geometry) and the
top-N functions by self cost with their call count and callers by call
count. Meant to be dropped into a <pre> block by build_report_index.py, or
read in a terminal.

Usage:
  callgrind_summary.py callgrind.out.X [--part all|totals|functions]
      [--event Ir] [--top 20] [--callers 6] [--repo-root .] [-o file]
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import callgrind as cg  # noqa: E402

EXTRA_EVENTS = ["D1m", "DLm", "Bcm"]  # shown per function when the profile has them


def make_disp(p: cg.Profile, repo_root: str):
    root = os.path.abspath(repo_root).rstrip("/") + "/"

    def disp(path: str) -> str:
        if path == "???" or not path:
            return ""
        norm = os.path.normpath(path) if os.path.isabs(path) else path
        if norm.startswith(root):
            return norm[len(root):]
        if os.path.isabs(norm) and not os.path.isfile(norm):
            return os.path.basename(norm)
        return norm

    def where(fn: str) -> str:
        ef, el = p.fn_entry.get(fn, (p.fn_home.get(fn, "???"), 0))
        f = disp(ef)
        if not f:
            ob = os.path.basename(p.file_ob.get(ef, "") or "")
            return f"[{ob}]" if ob else ""
        return f"{f}:{el}" if el else f

    return where


def functions_report(p: cg.Profile, event: str, top: int, ncallers: int, repo_root: str) -> str:
    where = make_disp(p, repo_root)
    total = p.value(p.totals(), event) or 1
    extras = [e for e in EXTRA_EVENTS if e in p.event_names() and p.value(p.totals(), e) > 0]

    rows = []
    for fn, vec in p.fn_self.items():
        s = p.value(vec, event)
        if s > 0:
            rows.append((s, fn))
    rows.sort(key=lambda t: (-t[0], t[1]))
    rows = rows[:top]

    def ncalls(fn: str) -> int:
        return sum(c for c, _ in p.callers.get(fn, {}).values())

    w_self = max((len(f"{s:,}") for s, _ in rows), default=1)
    w_x = {e: max([len(f"{p.value(p.fn_self[fn], e):,}") for _, fn in rows] + [len(e)]) for e in extras}
    w_calls = max([len(f"{ncalls(fn):,}") + 1 for _, fn in rows] + [5])
    w_rank = len(str(len(rows)))

    out = [f"top {len(rows)} functions by self {event} (of {total:,} total)",
           f"calls = times the function was entered; callers listed by call count, share of those calls in parentheses",
           ""]
    hdr = f"{'#':>{w_rank}}  {'self%':>7}  {event:>{w_self}}"
    for e in extras:
        hdr += f"  {e:>{w_x[e]}}"
    hdr += f"  {'calls':>{w_calls}}  function"
    out.append(hdr)
    out.append("-" * len(hdr))
    for i, (s, fn) in enumerate(rows, 1):
        line = f"{i:>{w_rank}}  {100.0 * s / total:6.2f}%  {s:>{w_self},}"
        for e in extras:
            line += f"  {p.value(p.fn_self[fn], e):>{w_x[e]},}"
        n = ncalls(fn)
        line += f"  {(f'{n:,}x' if n else '-'):>{w_calls}}  {fn}"
        loc = where(fn)
        if loc:
            line += f"  {loc}"
        out.append(line)
        callers = sorted(p.callers.get(fn, {}).items(), key=lambda kv: (-kv[1][0], kv[0][0]))
        indent = " " * (w_rank + 2)
        if not callers:
            out.append(f"{indent}callers: none (root)")
        else:
            wc = max(len(f"{c:,}") for _, (c, _) in callers[:ncallers])
            for (cfn, cfile, cline), (count, vec) in callers[:ncallers]:
                share = 100.0 * count / n if n else 0.0
                out.append(f"{indent}{count:>{wc},}x ({share:5.1f}%)  {cfn}  {_site(repo_root, cfile, cline)}")
            if len(callers) > ncallers:
                rest = sum(c for _, (c, _) in callers[ncallers:])
                out.append(f"{indent}{'':>{wc}}  … +{len(callers) - ncallers} more callers ({rest:,}x)")
        out.append("")
    return "\n".join(out) + "\n"


def _site(repo_root: str, cfile: str, cline: int) -> str:
    root = os.path.abspath(repo_root).rstrip("/") + "/"
    if cfile == "???" or not cfile:
        return ""
    norm = os.path.normpath(cfile) if os.path.isabs(cfile) else cfile
    if norm.startswith(root):
        norm = norm[len(root):]
    elif os.path.isabs(norm) and not os.path.isfile(norm):
        norm = os.path.basename(norm)
    return f"{norm}:{cline}" if cline else norm


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("callgrind_file")
    ap.add_argument("--part", choices=["all", "totals", "functions"], default="all")
    ap.add_argument("--event", default="Ir", help="event that ranks the functions (default: Ir)")
    ap.add_argument("--top", type=int, default=20)
    ap.add_argument("--callers", type=int, default=6, help="callers listed per function (default: 6)")
    ap.add_argument("--repo-root", default=".")
    ap.add_argument("-o", "--output", default=None, help="write here instead of stdout")
    args = ap.parse_args()

    with open(args.callgrind_file, encoding="utf-8", errors="replace") as f:
        p = cg.parse_callgrind(f.read())
    if not p.events:
        sys.exit("error: no 'events:' line -- not a callgrind file?")
    if args.event not in p.event_names():
        sys.exit(f"error: event {args.event!r} not in this profile ({' '.join(p.event_names())})")
    self_sum, total, ratio = cg.self_check(p)
    print(f"ratio (must be 1.0000): {ratio:.4f}", file=sys.stderr)
    if total and abs(ratio - 1.0) > 1e-6:
        sys.exit("error: per-line self cost does not add up to callgrind's summary")

    parts = []
    if args.part in ("all", "totals"):
        parts.append(cg.totals_report(p))
    if args.part in ("all", "functions"):
        parts.append(functions_report(p, args.event, args.top, args.callers, args.repo_root))
    text = "\n".join(parts)
    if args.output:
        os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(text)
    else:
        sys.stdout.write(text)


if __name__ == "__main__":
    main()
