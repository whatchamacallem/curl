#!/usr/bin/env python3
from __future__ import annotations

import argparse, base64, json, os, sys
from typing import NamedTuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import settings, theme

# All constants needed from settings.py have to be loaded here before anything
# else.
_ASSET_SETTINGS_SCRIPT_NAME: str = ""
_ASSET_TEMPLATE_FLAME_GRAPH_BOOTSTRAP_NAME: str = ""
_ASSET_TEMPLATE_FLAME_GRAPH_PAGE_NAME: str = ""
_ASSET_UI_STRINGS_SCRIPT_NAME: str = ""
_FLAME_GRAPH_PROFILE_SCRIPT_NAME: str = ""
_REPORT_ASSETS_DIR_NAME: str = ""
settings.load_into(__name__)

# Hands the embedded profile to speedscope. It polls, because speedscope
# starts up well after its own script tag has run.
_BOOTSTRAP = theme.asset_text_read(_ASSET_TEMPLATE_FLAME_GRAPH_BOOTSTRAP_NAME)

# How far a flame graph page sits below the report root, fixing its href to
# the shared assets. Always <test>/flame-graph/: a diff has no flame graph.
_FLAME_GRAPH_PAGE_DEPTH = 2

# The page itself: a link and two script tags, the markers substituted.
_PAGE = theme.asset_text_read(_ASSET_TEMPLATE_FLAME_GRAPH_PAGE_NAME)


# BuildFlameGraph - Writes one flame graph page: this test's recorded
# profile, plus links to the report's one shared copy of speedscope.
class BuildFlameGraph:
    # FlameGraphArgs - Where the page goes and what it points at.
    class FlameGraphArgs(NamedTuple):
        # the shared bundle's stylesheet, a bare file name
        app_css: str
        # relative href from the page to the shared speedscope bundle
        app_href: str
        # the shared bundle's engine, a bare file name
        app_js: str
        # the per-test directory the page and its profile are written to
        flame_graph_dir: str
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
            os.path.join(
                args.flame_graph_dir, _FLAME_GRAPH_PROFILE_SCRIPT_NAME
            ),
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
        written = os.path.join(
            args.flame_graph_dir, _FLAME_GRAPH_PROFILE_SCRIPT_NAME
        )
        print(
            f"wrote {written} ({len(raw):,} bytes of profile) and its page",
            file=sys.stderr,
        )

    # Write the page, pointing it at the shared bundle's engine and style.
    def page_write(self, args: BuildFlameGraph.FlameGraphArgs) -> None:
        assets_href = theme.shared_href(
            _FLAME_GRAPH_PAGE_DEPTH, _REPORT_ASSETS_DIR_NAME
        )
        # overlay first, so a speedscope that never starts shows the failure;
        # then settings and vocabulary, the bootstrap's bounds and failure id
        scripts = theme.script_tags(
            assets_href, theme.page_preamble_scripts()
        ) + theme.script_tags(
            assets_href,
            (_ASSET_SETTINGS_SCRIPT_NAME, _ASSET_UI_STRINGS_SCRIPT_NAME),
        )
        # __SCRIPTS__ goes in last, so nothing substituted before it can be
        # read back out of the text the scripts bring with them
        html = (
            _PAGE.replace("__APP_CSS__", f"{args.app_href}/{args.app_css}")
            .replace("__APP_JS__", f"{args.app_href}/{args.app_js}")
            .replace("__PROFILE_JS__", _FLAME_GRAPH_PROFILE_SCRIPT_NAME)
            .replace("__SCRIPTS__", scripts)
        )
        index_html = os.path.join(args.flame_graph_dir, "index.html")
        with open(index_html, "w", encoding="utf-8") as handle:
            handle.write(html)


# main - Write the given profile's flame graph page.
def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--app-css",
        required=True,
        help="the shared bundle's stylesheet, a bare file name",
    )
    parser.add_argument(
        "--app-href",
        required=True,
        help="relative href from the page to the shared speedscope bundle",
    )
    parser.add_argument(
        "--app-js",
        required=True,
        help="the shared bundle's engine, a bare file name",
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
            app_css=namespace.app_css,
            app_href=namespace.app_href,
            app_js=namespace.app_js,
            flame_graph_dir=namespace.flame_graph_dir,
            profile_json=namespace.profile_json,
        )
    )


if __name__ == "__main__":
    main()
