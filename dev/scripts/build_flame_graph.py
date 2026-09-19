#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import json
import os
import sys
from typing import NamedTuple

# The script that hands the embedded profile to speedscope once it has
# loaded -- it polls, because script order is not guaranteed.
_BOOTSTRAP = """\

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

# What the bootstrap plus its embedded profile gets written as.
_PROFILE_JS = "profile.js"


# BuildFlameGraph - Bakes one recorded profile into a copy of speedscope, so
# the page opens from file:// with nothing fetched.
class BuildFlameGraph:
    # FlameGraphArgs - The two paths this tool works on.
    class FlameGraphArgs(NamedTuple):
        # a fresh copy of speedscope's release build, patched in place
        speedscope_dir: str
        # the recorded profile to bake into it
        profile_json: str

    # Write the bootstrap with the profile base64'd into it.
    def bootstrap_write(
        self, args: BuildFlameGraph.FlameGraphArgs, raw: bytes
    ) -> None:
        doc_name = json.loads(raw.decode("utf-8")).get(
            "name"
        ) or os.path.basename(args.profile_json)
        script = _BOOTSTRAP.replace("__NAME__", json.dumps(doc_name)).replace(
            "__DATA__", json.dumps(base64.b64encode(raw).decode("ascii"))
        )
        with open(
            os.path.join(args.speedscope_dir, _PROFILE_JS),
            "w",
            encoding="utf-8",
        ) as handle:
            handle.write(script)

    # Write the profile script, then point speedscope's own page at it.
    def build(self, args: BuildFlameGraph.FlameGraphArgs) -> None:
        index_html = os.path.join(args.speedscope_dir, "index.html")
        html = self.page_read(index_html)
        with open(args.profile_json, "rb") as handle:
            raw = handle.read()
        self.bootstrap_write(args, raw)
        self.page_patch(index_html, html)
        print(
            f"wrote {os.path.join(args.speedscope_dir, _PROFILE_JS)} "
            f"({len(raw):,} bytes of profile) and patched {index_html}",
            file=sys.stderr,
        )

    # Put the hash and the profile script ahead of speedscope's first script.
    def page_patch(self, index_html: str, html: str) -> None:
        injection = (
            "<script>if (!location.hash) "
            "location.hash = '#localProfilePath=profile';</script>\n"
            f'    <script src="{_PROFILE_JS}"></script>\n    '
        )
        with open(index_html, "w", encoding="utf-8") as handle:
            handle.write(
                html.replace('<script src="', injection + '<script src="', 1)
            )

    # Read speedscope's page, and refuse it if there is nothing to patch.
    def page_read(self, index_html: str) -> str:
        with open(index_html, encoding="utf-8") as handle:
            html = handle.read()
        if '<script src="' not in html:
            sys.exit(
                f"error: {index_html}: no <script src=> to patch the profile "
                "in before"
            )
        return html


# main - Bake the given profile into the given speedscope copy.
def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--speedscope-dir",
        required=True,
        help="a fresh copy of speedscope's dist/release, patched in place",
    )
    parser.add_argument(
        "--profile-json", required=True, help="the .speedscope.json to embed"
    )
    namespace = parser.parse_args()
    BuildFlameGraph().build(
        BuildFlameGraph.FlameGraphArgs(
            speedscope_dir=namespace.speedscope_dir,
            profile_json=namespace.profile_json,
        )
    )


if __name__ == "__main__":
    main()
