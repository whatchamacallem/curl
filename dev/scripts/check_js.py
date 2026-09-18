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
PLACEHOLDER_RE = re.compile(r"^\s*__[A-Z_]+__\s*$")


class JsChunk(NamedTuple):
    label: str
    script: str


class JsSource(NamedTuple):
    module: str
    attr: str


SOURCES: tuple[JsSource, ...] = (
    JsSource("build_report", "FRAME_JS"),
    JsSource("callgrind_to_heatmap", "BODY"),
)


class CheckJs:
    def chunks(self, label: str, src: str) -> list[JsChunk]:
        if "<script" not in src:
            return [JsChunk(label, src)]
        chunks: list[JsChunk] = []
        for index, script in enumerate(re.findall(r"<script[^>]*>(.*?)</script>", src, re.S)):
            if PLACEHOLDER_RE.match(script):
                continue
            chunks.append(JsChunk(f"{label} block {index}", script))
        return chunks

    def run(self) -> bool:
        sys.path.insert(0, HERE)
        with open(os.path.join(HERE, "theme.js"), encoding="utf-8") as handle:
            ok = self.syntax_check("theme.js", handle.read())
        for source in SOURCES:
            ok = self.source_check(source) and ok
        return ok

    def source_check(self, source: JsSource) -> bool:
        value: object = getattr(importlib.import_module(source.module), source.attr)
        if not isinstance(value, str):
            print(f"{source.module}.{source.attr}: not a string", file=sys.stderr)
            return False
        ok = True
        for chunk in self.chunks(f"{source.module}.{source.attr}", value):
            ok = self.syntax_check(chunk.label, chunk.script) and ok
        return ok

    def syntax_check(self, label: str, src: str) -> bool:
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as handle:
            handle.write(src)
            path = handle.name
        try:
            result = subprocess.run(["node", "--check", path], capture_output=True, text=True)
        finally:
            os.unlink(path)
        if result.returncode == 0:
            return True
        print(f"{label}: {result.stderr.strip()}".replace(path, label), file=sys.stderr)
        return False


def main() -> int:
    return 0 if CheckJs().run() else 1


if __name__ == "__main__":
    sys.exit(main())
