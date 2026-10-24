#!/usr/bin/env python3
# SPDX-FileCopyrightText: © 2026 Adrian Johnston.
# SPDX-License-Identifier: MIT
# This file is licensed under the terms of the LICENSE-MIT.md file.

from __future__ import annotations

import argparse, base64, json, os, sys
from typing import NamedTuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import artifacts, settings, theme

_ASSET_TEMPLATE_FLAME_GRAPH_PAGE_NAME: str = ""
_FLAME_GRAPH_APP_DIR_NAME: str = ""
_FLAME_GRAPH_PROFILE_DIR_NAME: str = ""
_FLAME_GRAPH_PROFILE_GLOBAL_NAME: str = ""
_FLAME_GRAPH_VIEW_ENTRY: tuple[str, str] = ("", "")
_SETTINGS_HELD_SCRIPT_TEMPLATE_ID: str = ""
settings.load_into(__name__)

_FLAME_GRAPH_PAGE_PATH = _FLAME_GRAPH_VIEW_ENTRY[1]
_FLAME_GRAPH_PAGE_DEPTH = _FLAME_GRAPH_PAGE_PATH.count("/")

_PAGE = theme.asset_text_read(_ASSET_TEMPLATE_FLAME_GRAPH_PAGE_NAME)


class BuildFlameGraph:
    class PageArgs(NamedTuple):
        app_css: str
        app_js: str
        report: str

    class ProfilesArgs(NamedTuple):
        artifacts: str
        report: str

    def page_write(self, args: BuildFlameGraph.PageArgs) -> None:
        app_href = theme.href(
            _FLAME_GRAPH_PAGE_DEPTH, _FLAME_GRAPH_APP_DIR_NAME
        )
        html = theme.template_fill(
            _PAGE,
            {
                "__APP_CSS__": f"{app_href}/{args.app_css}",
                "__APP_SCRIPT__": f"{app_href}/{args.app_js}",
                "__HELD_SCRIPT_TEMPLATE_ID__": theme.render_html_escape(
                    _SETTINGS_HELD_SCRIPT_TEMPLATE_ID
                ),
            },
        )
        path = os.path.join(args.report, _FLAME_GRAPH_PAGE_PATH)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(html)
        print(f"wrote {path}", file=sys.stderr)

    # Writes one test's profile script, its speedscope profile embedded.
    def profile_write(
        self, report_dir: str, artifacts_dir: str, test_name: str
    ) -> None:
        with artifacts.artifact_open(
            artifacts_dir, "trace-speedscope", test_name, "rb"
        ) as handle:
            raw = handle.read()
        test_profile = {
            "name": json.loads(raw.decode("utf-8"))["name"],
            "base64": base64.b64encode(raw).decode("ascii"),
        }
        profiles_global = f"window.{_FLAME_GRAPH_PROFILE_GLOBAL_NAME}"
        profile_dir = os.path.join(
            report_dir,
            os.path.dirname(_FLAME_GRAPH_PAGE_PATH),
            _FLAME_GRAPH_PROFILE_DIR_NAME,
        )
        os.makedirs(profile_dir, exist_ok=True)
        path = os.path.join(profile_dir, f"{test_name}.js")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(
                f"{profiles_global} = {profiles_global} || {{}};\n"
                f"{profiles_global}[{json.dumps(test_name)}] ="
                f" {json.dumps(test_profile)};\n"
            )
        print(f"wrote {path} ({len(raw):,} bytes of profile)", file=sys.stderr)

    # Writes every listed test's profile script.
    def profiles_write(self, args: BuildFlameGraph.ProfilesArgs) -> None:
        artifacts_dir = artifacts.report_artifacts_dir(
            args.artifacts, args.report
        )
        for test_name in artifacts.test_list_read(artifacts_dir):
            self.profile_write(args.report, artifacts_dir, test_name)


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="cmd", required=True)

    profiles_parser = subparsers.add_parser(
        "profiles", help="every listed test's profile script"
    )
    profiles_parser.add_argument(
        "--artifacts",
        required=True,
        metavar="DIR",
        help="the profiler artifacts directory, holding the report's own,"
        " whose test list names every profile embedded",
    )
    profiles_parser.add_argument(
        "--report",
        required=True,
        metavar="DIR",
        help="the report directory the scripts are written in",
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
        "--report",
        required=True,
        metavar="DIR",
        help="the report directory the page is written in",
    )

    namespace = parser.parse_args()
    flame_graph = BuildFlameGraph()
    if namespace.cmd == "page":
        flame_graph.page_write(
            BuildFlameGraph.PageArgs(
                app_css=namespace.app_css,
                app_js=namespace.app_js,
                report=namespace.report,
            )
        )
    else:
        flame_graph.profiles_write(
            BuildFlameGraph.ProfilesArgs(
                artifacts=namespace.artifacts, report=namespace.report
            )
        )


if __name__ == "__main__":
    main()
