"""List the hottest source lines of one file from a callgrind_annotate output.

Usage: hotlines.py <annotated.txt> <source-file-as-shown-in-header> [N]
"""
import re
import sys

path, srcfile = sys.argv[1], sys.argv[2]
n = int(sys.argv[3]) if len(sys.argv) > 3 else 20

cost_re = re.compile(r"^ *([0-9,]+) \( *([0-9.]+)%\)  (.*)$")
dot_re = re.compile(r"^ *\.  {2,}(.*)$")
marker_re = re.compile(r"^-- line (\d+) -+$")

rows = []
in_section = False
lineno = None
with open(path) as f:
    for raw in f:
        line = raw.rstrip("\n")
        if line.startswith("-- User-annotated source: ") or line.startswith("-- Auto-annotated source: "):
            in_section = line.endswith(srcfile)
            lineno = None
            continue
        if not in_section:
            continue
        m = marker_re.match(line)
        if m:
            lineno = int(m.group(1))
            continue
        if lineno is None:
            continue
        m = cost_re.match(line)
        if m:
            src = m.group(3)
            if src.startswith("=> "):
                # inclusive cost of a call made from the previous source line; not a source line
                continue
            ir = int(m.group(1).replace(",", ""))
            rows.append((ir, float(m.group(2)), lineno, src.rstrip()))
            lineno += 1
            continue
        if dot_re.match(line) or line.strip() == ".":
            lineno += 1
            continue
        # anything else (blank, headers) doesn't advance the counter

rows.sort(key=lambda r: -r[0])
print(f"{'Ir':>14} {'%':>7}  {'line':>5}  source")
for ir, pct, ln, src in rows[:n]:
    print(f"{ir:>14,} {pct:>6.2f}%  {ln:>5}  {src.strip()}")
