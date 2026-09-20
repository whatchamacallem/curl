#!/usr/bin/env python3
from __future__ import annotations

import html.parser
import os
import sys
from typing import NamedTuple

# This directory: the .html page assets sit here.
_HERE = os.path.dirname(os.path.abspath(__file__))

# Tags that close themselves, so they never go on the open stack.
_VOID = frozenset(
    (
        "area",
        "base",
        "br",
        "col",
        "embed",
        "hr",
        "img",
        "input",
        "link",
        "meta",
        "param",
        "source",
        "track",
        "wbr",
    )
)


# CheckHtml - Walks every scripts/*.html and reports a tag that closes the
# wrong element or never closes at all, which no formatter here would catch.
class CheckHtml:
    # OpenTag - One element still waiting to be closed.
    class OpenTag(NamedTuple):
        # the tag's name
        name: str
        # the line it opened on
        line: int

    # TagBalance - The parser itself, counting what does not line up.
    class TagBalance(html.parser.HTMLParser):
        def __init__(self, path: str) -> None:
            super().__init__(convert_charrefs=True)
            self.path = path
            self.open_tags: list[CheckHtml.OpenTag] = []
            self.bad = 0

        def handle_starttag(
            self, tag: str, attrs: list[tuple[str, str | None]]
        ) -> None:
            if tag not in _VOID:
                self.open_tags.append(CheckHtml.OpenTag(tag, self.getpos()[0]))

        def handle_endtag(self, tag: str) -> None:
            if self.open_tags and self.open_tags[-1].name == tag:
                self.open_tags.pop()
                return
            self.bad += 1
            print(
                f"{self.path}:{self.getpos()[0]}: </{tag}> does not close"
                f" the open element",
                file=sys.stderr,
            )

    # Parse one file and report everything left unbalanced in it.
    def file_check(self, path: str) -> bool:
        with open(path, encoding="utf-8") as handle:
            parser = CheckHtml.TagBalance(os.path.basename(path))
            parser.feed(handle.read())
        for tag in parser.open_tags:
            parser.bad += 1
            print(
                f"{os.path.basename(path)}:{tag.line}:"
                f" <{tag.name}> is never closed",
                file=sys.stderr,
            )
        return parser.bad == 0

    # Check every .html beside this script, reporting all of them.
    def run(self) -> bool:
        ok = True
        for name in sorted(os.listdir(_HERE)):
            if name.endswith(".html"):
                ok = self.file_check(os.path.join(_HERE, name)) and ok
        return ok


# main - Check every page asset, and exit non-zero when any is unbalanced.
def main() -> int:
    return 0 if CheckHtml().run() else 1


if __name__ == "__main__":
    sys.exit(main())
