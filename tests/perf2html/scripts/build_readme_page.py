#!/usr/bin/env python3
# SPDX-FileCopyrightText: © 2026 Adrian Johnston.
# SPDX-License-Identifier: MIT
# This file is licensed under the terms of the LICENSE-MIT.md file.

from __future__ import annotations

import argparse, os, re, subprocess, sys
from typing import NamedTuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import settings, theme

_ASSET_TEMPLATE_README_PAGE_NAME: str = ""
_README_PAGE_BODY_MARKER: str = ""
_README_PAGE_CONVERTER_EXTENSION_ARGUMENTS: tuple[str, ...] = ()
_README_PAGE_HEADING_ANCHOR_DROPPED_PATTERN: str = ""
_README_PAGE_HEADING_PATTERN: str = ""
_README_PAGE_HEADING_TEXT_DROPPED_PATTERN: str = ""
_README_PAGE_ROOT_VALUES_MARKER: str = ""
_STYLE_README_PAGE_VALUE_ENTRIES: dict[str, str] = {}
settings.load_into(__name__)


class BuildReadmePage:
    class PageArgs(NamedTuple):
        converter: str
        markdown: str
        out: str
        verbose: bool

    # Returns the page body the converter writes, its stderr passing through.
    def body_convert(self, args: BuildReadmePage.PageArgs) -> str:
        command = [
            args.converter,
            *_README_PAGE_CONVERTER_EXTENSION_ARGUMENTS,
            args.markdown,
        ]
        completed = subprocess.run(
            command, check=False, stdout=subprocess.PIPE, text=True
        )
        if completed.returncode != 0:
            command_text = " ".join(command)
            print(
                f"error: exit {completed.returncode} from: {command_text}",
                file=sys.stderr,
            )
            sys.exit(completed.returncode)
        return completed.stdout

    # Gives each heading the anchor GitHub gives it, a repeat numbered.
    def headings_anchor(self, body_markup: str) -> str:
        anchor_counts: dict[str, int] = {}

        def heading_anchored(heading_found: re.Match[str]) -> str:
            heading_markup = heading_found[2]
            heading_text = re.sub(
                _README_PAGE_HEADING_TEXT_DROPPED_PATTERN, "", heading_markup
            )
            heading_anchor = re.sub(
                _README_PAGE_HEADING_ANCHOR_DROPPED_PATTERN,
                "",
                heading_text.lower(),
            ).replace(" ", "-")
            repeat_count = anchor_counts.get(heading_anchor, 0)
            anchor_counts[heading_anchor] = repeat_count + 1
            if repeat_count:
                heading_anchor = f"{heading_anchor}-{repeat_count}"
            return theme.render_element(
                f"h{heading_found[1]}", {"id": heading_anchor}, heading_markup
            )

        return re.sub(
            _README_PAGE_HEADING_PATTERN, heading_anchored, body_markup
        )

    # Returns whether the page is newer than every file it is built from.
    def is_current(self, args: BuildReadmePage.PageArgs) -> bool:
        input_times = [
            os.path.getmtime(input_path)
            for input_path in (
                args.markdown,
                args.converter,
                os.path.abspath(__file__),
                os.path.join(
                    theme.Theme.DIRECTORY, _ASSET_TEMPLATE_README_PAGE_NAME
                ),
                settings.__file__,
                theme.__file__,
            )
        ]
        return os.path.isfile(args.out) and all(
            input_time < os.path.getmtime(args.out)
            for input_time in input_times
        )

    # Writes the page unless current, the old page gone before a rebuild.
    def write(self, args: BuildReadmePage.PageArgs) -> None:
        if self.is_current(args):
            if args.verbose:
                print(f"{args.out}: newer than every file it is built from")
            return
        if os.path.isfile(args.out):
            os.remove(args.out)
        root_values = "; ".join(
            f"--{name}: {value}"
            for name, value in _STYLE_README_PAGE_VALUE_ENTRIES.items()
        )
        page_markup = theme.template_fill(
            theme.asset_text_read(_ASSET_TEMPLATE_README_PAGE_NAME),
            {
                _README_PAGE_ROOT_VALUES_MARKER: theme.render_html_escape(
                    root_values
                ),
                _README_PAGE_BODY_MARKER: self.headings_anchor(
                    self.body_convert(args)
                ),
            },
        )
        os.makedirs(os.path.dirname(args.out), exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as page_file:
            page_file.write(page_markup)
        if args.verbose:
            print(f"{args.out}: built from {args.markdown}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--converter",
        required=True,
        help="the path of the cmark-gfm command that writes the page body",
    )
    parser.add_argument(
        "--markdown", required=True, help="the README the page shows"
    )
    parser.add_argument("--out", required=True, help="the page written")
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="print the ok line; a quiet run prints nothing on success",
    )
    namespace = parser.parse_args()
    BuildReadmePage().write(
        BuildReadmePage.PageArgs(
            converter=namespace.converter,
            markdown=namespace.markdown,
            out=namespace.out,
            verbose=namespace.verbose,
        )
    )


if __name__ == "__main__":
    main()
