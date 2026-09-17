#!/usr/bin/env python3
from __future__ import annotations

import importlib
import os
import re
import subprocess
import sys
import tempfile
from typing import NamedTuple

HERE = os.path.dirname(os.path.abspath(__file__))


class JsSource(NamedTuple):
    module: str
    attr: str


SOURCES: tuple[JsSource, ...] = (
    JsSource("build_report", "FRAME_JS"),
    JsSource("callgrind_to_heatmap", "BODY"),
)


class JsChunk(NamedTuple):
    label: str
    js: str


PLACEHOLDER_RE = re.compile(r"^\s*__[A-Z_]+__\s*$")


def js_check(label: str, src: str) -> bool:
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as fh:
        fh.write(src)
        path = fh.name
    try:
        r = subprocess.run(["node", "--check", path], capture_output=True, text=True)
    finally:
        os.unlink(path)
    if r.returncode == 0:
        return True
    print(f"{label}: {r.stderr.strip()}".replace(path, label), file=sys.stderr)
    return False


def blocks_of(label: str, src: str) -> list[JsChunk]:
    if "<script" not in src:
        return [JsChunk(label, src)]
    out: list[JsChunk] = []
    for i, js in enumerate(re.findall(r"<script[^>]*>(.*?)</script>", src, re.S)):
        if PLACEHOLDER_RE.match(js):
            continue
        out.append(JsChunk(f"{label} block {i}", js))
    return out


def check_main() -> int:
    sys.path.insert(0, HERE)
    with open(os.path.join(HERE, "theme.js"), encoding="utf-8") as f:
        ok = js_check("theme.js", f.read())
    for src in SOURCES:
        value: object = getattr(importlib.import_module(src.module), src.attr)
        if not isinstance(value, str):
            print(f"{src.module}.{src.attr}: not a string", file=sys.stderr)
            ok = False
            continue
        for chunk in blocks_of(f"{src.module}.{src.attr}", value):
            ok = js_check(chunk.label, chunk.js) and ok
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(check_main())
