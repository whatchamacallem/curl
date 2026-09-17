#!/usr/bin/env python3
"""Turn a copy of speedscope's dist/release into a bundle that opens
on an embedded profile instead of the drag-and-drop landing page.

Usage:
  build_flame_graph.py --speedscope-dir OUT/flame-graph --profile-json X.speedscope.json
      [--profile-filename NAME]
"""
from __future__ import annotations

import argparse
import base64
import json
import re
import sys
from pathlib import Path
from typing import NamedTuple

BOOTSTRAP = """\

(function () {
  var NAME = {name};
  var DATA = {data};
  function load() {
    if (window.speedscope && window.speedscope.loadFileFromBase64) {
      window.speedscope.loadFileFromBase64(NAME, DATA);
      return true;
    }
    return false;
  }
  if (!load()) {
    var tries = 0, timer = setInterval(function () {
      if (load() || ++tries >= 200) clearInterval(timer);
    }, 50);
  }
})();
"""
MARK_END = "<!-- flame-graph:end -->"
MARK_START = "<!-- flame-graph:start -->"
PROFILE_JS = "profile.js"
_SLOT_RE = re.compile(r"\{(name|data)\}")


class FlameArgs(NamedTuple):
    speedscope_dir: str
    profile_json: str
    profile_filename: str | None


def bootstrap_render(name: str, data_b64: str) -> str:
    slots = {"name": json.dumps(name), "data": json.dumps(data_b64)}
    return _SLOT_RE.sub(lambda match: slots[match.group(1)], BOOTSTRAP)


def index_patch(index_html: Path) -> None:
    html = index_html.read_text(encoding="utf-8")
    html = re.sub(rf"\s*{re.escape(MARK_START)}.*?{re.escape(MARK_END)}\n?", "\n", html, flags=re.DOTALL)
    injection = (f"\n    {MARK_START}\n"
                 "    <script>if (!location.hash) location.hash = '#localProfilePath=profile';</script>\n"
                 f'    <script src="{PROFILE_JS}"></script>\n'
                 f"    {MARK_END}\n")
    if "<script src=" in html:
        html = html.replace('<script src="', injection + '    <script src="', 1)
    elif "</body>" in html:
        html = html.replace("</body>", injection + "  </body>")
    else:
        sys.exit(f"error: {index_html}: no <script src=> or </body> to patch the profile into")
    index_html.write_text(html, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--speedscope-dir", required=True,
                        help="the copy of speedscope's dist/release to patch in place")
    parser.add_argument("--profile-json", required=True, help="the .speedscope.json to embed")
    parser.add_argument("--profile-filename", default=None,
                        help="file name speedscope shows for the profile (default: the JSON's basename)")
    namespace = parser.parse_args()
    args = FlameArgs(speedscope_dir=namespace.speedscope_dir, profile_json=namespace.profile_json,
                     profile_filename=namespace.profile_filename)

    output_dir = Path(args.speedscope_dir)
    index_html = output_dir / "index.html"
    if not index_html.exists():
        sys.exit(f"error: {index_html} not found")
    profile = Path(args.profile_json)
    raw = profile.read_bytes()
    try:
        doc: object = json.loads(raw)
    except json.JSONDecodeError as error:
        sys.exit(f"error: {profile} is not valid JSON: {error}")
    if not isinstance(doc, dict):
        sys.exit(f"error: {profile} does not look like a speedscope profile")
    shared, profiles = doc.get("shared"), doc.get("profiles")
    if not isinstance(shared, dict) or not isinstance(profiles, list):
        sys.exit(f"error: {profile} does not look like a speedscope profile")

    (output_dir / PROFILE_JS).write_text(
        bootstrap_render(args.profile_filename or profile.name, base64.b64encode(raw).decode("ascii")),
        encoding="utf-8")
    (output_dir / "profile.speedscope.json").write_bytes(raw)
    index_patch(index_html)
    frames = shared.get("frames")
    frame_count = len(frames) if isinstance(frames, list) else 0
    sample_count = 0
    for entry in profiles:
        samples = entry.get("samples") if isinstance(entry, dict) else None
        if isinstance(samples, list):
            sample_count += len(samples)
    print(f"wrote {output_dir / PROFILE_JS} ({frame_count} frames, {sample_count} stack samples, "
          f"{len(profiles)} profiles) and patched {index_html}", file=sys.stderr)


if __name__ == "__main__":
    main()
