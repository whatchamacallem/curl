#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import json
import os
import sys
from typing import NamedTuple

BOOTSTRAP = """\

(function () {
  var NAME = __NAME__;
  var DATA = __DATA__;
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
PROFILE_JS = "profile.js"


class FlameArgs(NamedTuple):
    speedscope_dir: str
    profile_json: str


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--speedscope-dir", required=True,
                        help="a fresh copy of speedscope's dist/release, patched in place")
    parser.add_argument("--profile-json", required=True, help="the .speedscope.json to embed")
    namespace = parser.parse_args()
    args = FlameArgs(speedscope_dir=namespace.speedscope_dir, profile_json=namespace.profile_json)

    index_html = os.path.join(args.speedscope_dir, "index.html")
    with open(index_html, encoding="utf-8") as handle:
        html = handle.read()
    if '<script src="' not in html:
        sys.exit(f"error: {index_html}: no <script src=> to patch the profile in before")
    with open(args.profile_json, "rb") as handle:
        raw = handle.read()
    doc_name = json.loads(raw.decode("utf-8")).get("name") or os.path.basename(args.profile_json)
    script = BOOTSTRAP.replace("__NAME__", json.dumps(doc_name)) \
        .replace("__DATA__", json.dumps(base64.b64encode(raw).decode("ascii")))
    with open(os.path.join(args.speedscope_dir, PROFILE_JS), "w", encoding="utf-8") as handle:
        handle.write(script)
    injection = ("<script>if (!location.hash) location.hash = '#localProfilePath=profile';</script>\n"
                 f'    <script src="{PROFILE_JS}"></script>\n    ')
    with open(index_html, "w", encoding="utf-8") as handle:
        handle.write(html.replace('<script src="', injection + '<script src="', 1))
    print(f"wrote {os.path.join(args.speedscope_dir, PROFILE_JS)} ({len(raw):,} bytes of profile) "
          f"and patched {index_html}", file=sys.stderr)


if __name__ == "__main__":
    main()
