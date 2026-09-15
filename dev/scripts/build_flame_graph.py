#!/usr/bin/env python3
"""Turn a copy of speedscope's dist/release into a bundle that opens straight
on an embedded profile instead of the drag-and-drop landing page.

Speedscope's app only defines `window.speedscope.loadFileFromBase64` once it
sees a truthy `localProfilePath` in the URL hash -- the mechanism its own
`speedscope <file>` CLI uses, by writing a temp .js file and opening
`index.html#localProfilePath=/tmp/...js`, which the app turns into a
`<script src="file:///<absolute path>">`. That absolute path does not
survive moving the bundle. So instead the hash is set to a harmless
placeholder (any truthy value trips the gate; the injected placeholder
script fails silently) and a sibling profile.js, referenced by relative
path, waits for `window.speedscope` and calls loadFileFromBase64 with the
profile embedded as base64. The raw JSON is copied alongside for re-import
elsewhere.

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

PROFILE_JS = "profile.js"
MARK_START = "<!-- flame-graph:start -->"
MARK_END = "<!-- flame-graph:end -->"

BOOTSTRAP = """\
// Written by dev/scripts/build_flame_graph.py: the profile, and the hand-off
// to speedscope's loadFileFromBase64 once the app has defined it.
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


def patch_index(index_html: Path) -> None:
    html = index_html.read_text()
    html = re.sub(rf"\s*{re.escape(MARK_START)}.*?{re.escape(MARK_END)}\n?", "\n", html, flags=re.DOTALL)
    injection = (f"\n    {MARK_START}\n"
                 "    <script>if (!location.hash) location.hash = '#localProfilePath=profile';</script>\n"
                 f'    <script src="{PROFILE_JS}"></script>\n'
                 f"    {MARK_END}\n")
    # before the app's own bundle, so the hash is set when it mounts
    if "<script src=" in html:
        html = html.replace('<script src="', injection + '    <script src="', 1)
    else:
        html = html.replace("</body>", injection + "  </body>")
    index_html.write_text(html)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--speedscope-dir", required=True,
                    help="the copy of speedscope's dist/release to patch in place")
    ap.add_argument("--profile-json", required=True, help="the .speedscope.json to embed")
    ap.add_argument("--profile-filename", default=None,
                    help="file name speedscope shows for the profile (default: the JSON's basename)")
    args = ap.parse_args()

    out = Path(args.speedscope_dir)
    index_html = out / "index.html"
    if not index_html.exists():
        sys.exit(f"error: {index_html} not found")
    profile = Path(args.profile_json)
    raw = profile.read_bytes()
    try:
        doc = json.loads(raw)
    except json.JSONDecodeError as e:
        sys.exit(f"error: {profile} is not valid JSON: {e}")
    if "profiles" not in doc or "shared" not in doc:
        sys.exit(f"error: {profile} does not look like a speedscope profile")

    js = BOOTSTRAP.replace("{name}", json.dumps(args.profile_filename or profile.name)) \
                  .replace("{data}", json.dumps(base64.b64encode(raw).decode("ascii")))
    (out / PROFILE_JS).write_text(js)
    (out / "profile.speedscope.json").write_bytes(raw)
    patch_index(index_html)
    nframes = len(doc["shared"].get("frames", []))
    nsamples = sum(len(p.get("samples", [])) for p in doc["profiles"])
    print(f"wrote {out / PROFILE_JS} ({nframes} frames, {nsamples} stack samples, "
          f"{len(doc['profiles'])} profiles) and patched {index_html}", file=sys.stderr)


if __name__ == "__main__":
    main()
