#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import glob
import json
import os
import sys
from typing import NamedTuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import theme

# The script that hands the embedded profile to speedscope once it has
# loaded -- it polls, because script order is not guaranteed.
_BOOTSTRAP = theme.theme_asset("flame_bootstrap.js")

_PAGE = theme.theme_asset("flame_graph.html")

# What the bootstrap plus its embedded profile gets written as.
_PROFILE_JS = "profile.js"


# BuildFlameGraph - Writes one flame graph page: this test's recorded
# profile, plus links to the report's one shared copy of speedscope.
class BuildFlameGraph:
    # FlameGraphArgs - Where the page goes and what it points at.
    class FlameGraphArgs(NamedTuple):
        # relative href from the page to the shared speedscope bundle
        app_href: str
        # the per-test directory the page and its profile are written to
        flame_graph_dir: str
        # the recorded profile to bake into it
        profile_json: str

    # The one file in the shared bundle matching a glob, as an href.
    def app_asset(
        self, args: BuildFlameGraph.FlameGraphArgs, pattern: str
    ) -> str:
        local = os.path.join(args.flame_graph_dir, args.app_href)
        found = sorted(glob.glob(os.path.join(local, pattern)))
        if len(found) != 1:
            sys.exit(
                f"error: {pattern} matched {len(found)} files in {local}, "
                "expected exactly 1"
            )
        return f"{args.app_href}/{os.path.basename(found[0])}"

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
            os.path.join(args.flame_graph_dir, _PROFILE_JS),
            "w",
            encoding="utf-8",
        ) as handle:
            handle.write(script)

    # Write the profile script, then the page that loads it beside the
    # shared bundle.
    def build(self, args: BuildFlameGraph.FlameGraphArgs) -> None:
        with open(args.profile_json, "rb") as handle:
            raw = handle.read()
        self.bootstrap_write(args, raw)
        self.page_write(args)
        print(
            f"wrote {os.path.join(args.flame_graph_dir, _PROFILE_JS)} "
            f"({len(raw):,} bytes of profile) and its page",
            file=sys.stderr,
        )

    # Write the page, pointing it at the shared bundle's engine and style.
    def page_write(self, args: BuildFlameGraph.FlameGraphArgs) -> None:
        html = (
            _PAGE.replace(
                "__APP_CSS__", self.app_asset(args, "speedscope-*.css")
            )
            .replace("__APP_JS__", self.app_asset(args, "speedscope-*.js"))
            .replace("__PROFILE_JS__", _PROFILE_JS)
        )
        index_html = os.path.join(args.flame_graph_dir, "index.html")
        with open(index_html, "w", encoding="utf-8") as handle:
            handle.write(html)


# main - Write the given profile's flame graph page.
def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--app-href",
        required=True,
        help="relative href from the page to the shared speedscope bundle",
    )
    parser.add_argument(
        "--flame-graph-dir",
        required=True,
        help="the per-test directory the page is written to",
    )
    parser.add_argument(
        "--profile-json", required=True, help="the .speedscope.json to embed"
    )
    namespace = parser.parse_args()
    BuildFlameGraph().build(
        BuildFlameGraph.FlameGraphArgs(
            app_href=namespace.app_href,
            flame_graph_dir=namespace.flame_graph_dir,
            profile_json=namespace.profile_json,
        )
    )


if __name__ == "__main__":
    main()
