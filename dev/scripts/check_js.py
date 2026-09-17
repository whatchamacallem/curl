#!/usr/bin/env python3
"""`node --check` every JS the generators embed in a Python string.

JS inside a Python triple-quoted string is invisible to every other check
here: a `\\n` that should have been `\\\\n`, a stray brace, an f-string brace
that ate a JS one -- all of it survives until the generated page silently
fails to run. This imports each generator and syntax-checks the JS it would
emit, plus the standalone theme.js the pages inline verbatim.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))

# Generator attributes holding JS to check: (module, attribute). A value that
# looks like HTML is scanned for <script> blocks instead of checked whole.
SOURCES = [
    ("build_report", "FRAME_JS"),
    ("callgrind_to_heatmap", "BODY"),
]

# Placeholders the generators substitute at build time; a block that is only a
# placeholder is checked via its own source file, not here.
PLACEHOLDER_RE = re.compile(r"^\s*__[A-Z_]+__\s*$")


def js_check(label: str, src: str) -> bool:
    """Syntax-check one chunk of JS. True when it parses."""
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as fh:
        fh.write(src)
        path = fh.name
    try:
        r = subprocess.run(["node", "--check", path], capture_output=True, text=True)
    finally:
        os.unlink(path)
    if r.returncode == 0:
        return True
    # node points at the temp file; name the real source instead.
    print(f"{label}: {r.stderr.strip()}".replace(path, label), file=sys.stderr)
    return False


def blocks_of(label: str, src: str) -> list[tuple[str, str]]:
    """The JS chunks in one source value, as (label, js) pairs."""
    if "<script" not in src:
        return [(label, src)]
    out = []
    for i, js in enumerate(re.findall(r"<script[^>]*>(.*?)</script>", src, re.S)):
        if PLACEHOLDER_RE.match(js):
            continue
        out.append((f"{label} block {i}", js))
    return out


def check_main() -> int:
    sys.path.insert(0, HERE)
    ok = True
    ok &= js_check("theme.js", open(os.path.join(HERE, "theme.js")).read())
    for mod_name, attr in SOURCES:
        mod = __import__(mod_name)
        for label, js in blocks_of(f"{mod_name}.{attr}", getattr(mod, attr)):
            ok &= js_check(label, js)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(check_main())
