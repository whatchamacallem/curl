#!/usr/bin/env python3
# SPDX-FileCopyrightText: © 2026 Adrian Johnston.
# SPDX-License-Identifier: MIT
# This file is licensed under the terms of the LICENSE-MIT.md file.

from __future__ import annotations

import argparse, base64, json, os, sys
from typing import NamedTuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import settings, theme

_ASSET_DEBUG_SCRIPT_NAME: str = ""
_ASSET_FLAME_GRAPH_SCRIPT_NAME: str = ""
_ASSET_SETTINGS_SCRIPT_NAME: str = ""
_ASSET_TEMPLATE_FLAME_GRAPH_PAGE_NAME: str = ""
_ASSET_THEME_SCRIPT_NAME: str = ""
_ASSET_UI_STRINGS_SCRIPT_NAME: str = ""
_FLAME_GRAPH_APP_DIR_NAME: str = ""
_FLAME_GRAPH_PROFILE_DIR_NAME: str = ""
_FLAME_GRAPH_PROFILE_GLOBAL_NAME: str = ""
_FLAME_GRAPH_VIEW_ENTRY: tuple[str, str] = ("", "")
_REPORT_ASSETS_DIR_NAME: str = ""
settings.load_into(__name__)

_FLAME_GRAPH_PAGE_PATH = _FLAME_GRAPH_VIEW_ENTRY[1]
_FLAME_GRAPH_PAGE_DEPTH = _FLAME_GRAPH_PAGE_PATH.count("/")

_PAGE = theme.asset_text_read(_ASSET_TEMPLATE_FLAME_GRAPH_PAGE_NAME)


class BuildFlameGraph:
    class PageArgs(NamedTuple):
        app_css: str
        app_js: str
        report_dir: str

    class ProfileArgs(NamedTuple):
        profile_json: str
        report_dir: str
        test: str

    def page_write(self, args: BuildFlameGraph.PageArgs) -> None:
        assets_href = theme.href(
            _FLAME_GRAPH_PAGE_DEPTH, _REPORT_ASSETS_DIR_NAME
        )
        app_href = theme.href(
            _FLAME_GRAPH_PAGE_DEPTH, _FLAME_GRAPH_APP_DIR_NAME
        )
        scripts = theme.script_tags(
            assets_href,
            (_ASSET_UI_STRINGS_SCRIPT_NAME, _ASSET_SETTINGS_SCRIPT_NAME),
        )
        held_scripts = theme.held_script_tags(
            theme.script_tags(
                assets_href,
                (
                    _ASSET_DEBUG_SCRIPT_NAME,
                    _ASSET_THEME_SCRIPT_NAME,
                    _ASSET_FLAME_GRAPH_SCRIPT_NAME,
                ),
            )
            + theme.script_tags(app_href, (args.app_js,))
        )
        html = theme.template_fill(
            _PAGE,
            {
                "__APP_CSS__": f"{app_href}/{args.app_css}",
                "__HELD_SCRIPTS__": held_scripts,
                "__SCRIPTS__": scripts,
            },
        )
        path = os.path.join(args.report_dir, _FLAME_GRAPH_PAGE_PATH)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(html)
        print(f"wrote {path}", file=sys.stderr)

    def profile_write(self, args: BuildFlameGraph.ProfileArgs) -> None:
        with open(args.profile_json, "rb") as handle:
            raw = handle.read()
        test_profile = {
            "name": json.loads(raw.decode("utf-8"))["name"],
            "base64": base64.b64encode(raw).decode("ascii"),
        }
        profiles_global = f"window.{_FLAME_GRAPH_PROFILE_GLOBAL_NAME}"
        profile_dir = os.path.join(
            args.report_dir,
            os.path.dirname(_FLAME_GRAPH_PAGE_PATH),
            _FLAME_GRAPH_PROFILE_DIR_NAME,
        )
        os.makedirs(profile_dir, exist_ok=True)
        path = os.path.join(profile_dir, f"{args.test}.js")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(
                f"{profiles_global} = {profiles_global} || {{}};\n"
                f"{profiles_global}[{json.dumps(args.test)}] ="
                f" {json.dumps(test_profile)};\n"
            )
        print(f"wrote {path} ({len(raw):,} bytes of profile)", file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="cmd", required=True)

    profile_parser = subparsers.add_parser(
        "profile", help="one test's profile script"
    )
    profile_parser.add_argument(
        "--profile-json", required=True, help="the .speedscope.json to embed"
    )
    profile_parser.add_argument(
        "--report-dir",
        required=True,
        help="the report directory the script is written in",
    )
    profile_parser.add_argument(
        "--test",
        required=True,
        help="the test the profile is filed under and its script named after",
    )

    page_parser = subparsers.add_parser(
        "page", help="the one flame graph page"
    )
    page_parser.add_argument(
        "--app-css",
        required=True,
        help="the shared bundle's stylesheet, a bare file name",
    )
    page_parser.add_argument(
        "--app-js",
        required=True,
        help="the shared bundle's engine, a bare file name",
    )
    page_parser.add_argument(
        "--report-dir",
        required=True,
        help="the report directory the page is written in",
    )

    namespace = parser.parse_args()
    flame_graph = BuildFlameGraph()
    if namespace.cmd == "page":
        flame_graph.page_write(
            BuildFlameGraph.PageArgs(
                app_css=namespace.app_css,
                app_js=namespace.app_js,
                report_dir=namespace.report_dir,
            )
        )
    else:
        flame_graph.profile_write(
            BuildFlameGraph.ProfileArgs(
                profile_json=namespace.profile_json,
                report_dir=namespace.report_dir,
                test=namespace.test,
            )
        )


if __name__ == "__main__":
    main()
