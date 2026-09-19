#!/usr/bin/env python3
from __future__ import annotations

import importlib
import os
import re
import subprocess
import sys
import tempfile
from typing import NamedTuple

# This directory: theme.js sits here, and so do the generators we import.
_HERE = os.path.dirname(os.path.abspath(__file__))

# A <script> body that is only a __NAME__ marker, filled in at generate time.
_PLACEHOLDER_RE = re.compile(r"^\s*__[A-Z_]+__\s*$")


# CheckJs - Runs node --check over theme.js and every JS chunk embedded in a
# Python string, so a missed backslash is caught before a page ships.
class CheckJs:
    # EmbeddedScript - One piece of JavaScript to check, and what to call it
    # when it fails.
    class EmbeddedScript(NamedTuple):
        # what to print when node rejects it
        label: str
        # the JavaScript itself
        script: str

    # ScriptHolder - One module-level string that JavaScript lives inside.
    class ScriptHolder(NamedTuple):
        # the generator to import, e.g. build_report
        module: str
        # the string constant in it, looked up by this exact name
        attr: str

    # Split one string into checkable chunks: a whole document splits on its
    # <script> tags, anything else is already one chunk.
    def chunks(self, label: str, src: str) -> list[CheckJs.EmbeddedScript]:
        if "<script" not in src:
            return [CheckJs.EmbeddedScript(label, src)]
        chunks: list[CheckJs.EmbeddedScript] = []
        for index, script in enumerate(
            re.findall(r"<script[^>]*>(.*?)</script>", src, re.S)
        ):
            if _PLACEHOLDER_RE.match(script):
                continue
            chunks.append(
                CheckJs.EmbeddedScript(f"{label} block {index}", script)
            )
        return chunks

    # Check theme.js and every holder, reporting every failure, not just the
    # first.
    def run(self) -> bool:
        sys.path.insert(0, _HERE)
        with open(os.path.join(_HERE, "theme.js"), encoding="utf-8") as handle:
            ok = self.syntax_check("theme.js", handle.read())
        for holder in _HOLDERS:
            ok = self.holder_check(holder) and ok
        return ok

    # Import one generator, pull its JavaScript string out by name and check
    # every chunk of it.
    def holder_check(self, holder: CheckJs.ScriptHolder) -> bool:
        value: object = getattr(
            importlib.import_module(holder.module), holder.attr
        )
        if not isinstance(value, str):
            print(
                f"{holder.module}.{holder.attr}: not a string", file=sys.stderr
            )
            return False
        ok = True
        for chunk in self.chunks(f"{holder.module}.{holder.attr}", value):
            ok = self.syntax_check(chunk.label, chunk.script) and ok
        return ok

    # Hand one chunk to node --check, via a temporary file it can open.
    def syntax_check(self, label: str, src: str) -> bool:
        with tempfile.NamedTemporaryFile(
            "w", suffix=".js", delete=False, encoding="utf-8"
        ) as handle:
            handle.write(src)
            path = handle.name
        try:
            result = subprocess.run(
                ["node", "--check", path], capture_output=True, text=True
            )
        finally:
            os.unlink(path)
        if result.returncode == 0:
            return True
        print(
            f"{label}: {result.stderr.strip()}".replace(path, label),
            file=sys.stderr,
        )
        return False


# Every generator string that holds JavaScript. Add a pair here when a
# generator grows new embedded JS -- these names are resolved as written.
_HOLDERS: tuple[CheckJs.ScriptHolder, ...] = (
    CheckJs.ScriptHolder("build_report", "FRAME_JS"),
    CheckJs.ScriptHolder("callgrind_to_heatmap", "BODY"),
)


# main - Check every script, and exit non-zero when any of them is bad.
def main() -> int:
    return 0 if CheckJs().run() else 1


if __name__ == "__main__":
    sys.exit(main())
