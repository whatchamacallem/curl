#!/usr/bin/env python3
# SPDX-FileCopyrightText: © 2026 Adrian Johnston.
# SPDX-License-Identifier: MIT
# This file is licensed under the terms of the LICENSE-MIT.md file.

from __future__ import annotations

import argparse, html.entities, os, re, sys
from typing import NamedTuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import callgrind


class SourceScan:
    class CommentSpan(NamedTuple):
        first_line: int
        last_line: int

    class CommentSyntax(NamedTuple):
        line_marks: tuple[str, ...]
        block_marks: tuple[tuple[str, str], ...]

    class EscapeRule(NamedTuple):
        description: str
        pattern: str
        extensions: tuple[str, ...]

    class SourceFault(NamedTuple):
        path: str
        line_number: int
        message: str

    def __init__(self) -> None:
        self.faults: list[SourceScan.SourceFault] = []
        self.escape_patterns = [
            (rule, re.compile(rule.pattern)) for rule in _ESCAPE_RULES
        ]

    def banned_tag_re(self) -> re.Pattern[str]:
        names = "|".join(_SOURCE_SCAN_BANNED_TAG_NAMES)
        return re.compile(r"</?(" + names + r")(?=[\s/>]|$)", re.IGNORECASE)

    def comment_check(
        self,
        path: str,
        comments: list[SourceScan.CommentSpan],
        header_end: int,
    ) -> None:
        for comment in comments:
            if comment.first_line < header_end:
                continue
            length = comment.last_line - comment.first_line + 1
            if length > _COMMENT_BLOCK_MAX_LINES:
                self.faults.append(
                    SourceScan.SourceFault(
                        path,
                        comment.first_line,
                        f"a comment block of {length} lines, over the limit"
                        f" of {_COMMENT_BLOCK_MAX_LINES}",
                    )
                )

    def comment_cut_re(self) -> re.Pattern[str]:
        marks = sorted(_SOURCE_SCAN_COMMENT_MARKUP, key=len, reverse=True)
        markup = "|".join(re.escape(mark) for mark in marks)
        return re.compile(r"```[\s\S]*?```|`[^`\n]*`|" + markup)

    def comment_re_of(
        self, syntax: SourceScan.CommentSyntax
    ) -> re.Pattern[str]:
        alternatives: list[str] = []
        for opening_mark, closing_mark in syntax.block_marks:
            opening = re.escape(opening_mark)
            closing = re.escape(closing_mark)
            alternatives.append(
                rf"^[ \t]*{opening}(?:(?!{closing})[\s\S])*{closing}[ \t]*$"
            )
        for line_mark in syntax.line_marks:
            line_pattern = rf"[ \t]*{re.escape(line_mark)}[^\n]*"
            alternatives.append(rf"^{line_pattern}(?:\n{line_pattern})*")
        return re.compile("|".join(alternatives), re.MULTILINE)

    def comment_syntax_of(self, path: str) -> SourceScan.CommentSyntax:
        for extensions, syntax in _COMMENT_SYNTAX_BY_EXTENSION:
            if path.endswith(extensions):
                return syntax
        sys.exit(
            f"error: {path}: no comment syntax is known for this kind of"
            " file; add its extension to _COMMENT_SYNTAX_BY_EXTENSION"
        )

    def comments_of(
        self, text: str, syntax: SourceScan.CommentSyntax
    ) -> list[SourceScan.CommentSpan]:
        return [
            SourceScan.CommentSpan(
                text.count("\n", 0, match.start()) + 1,
                text.count("\n", 0, match.end()) + 1,
            )
            for match in self.comment_re_of(syntax).finditer(text)
        ]

    def escape_check(self, path: str, lines: list[str]) -> None:
        for rule, pattern in self.escape_patterns:
            if rule.extensions and not path.endswith(rule.extensions):
                continue
            for line_number, line in enumerate(lines, start=1):
                match = pattern.search(line)
                if match:
                    self.faults.append(
                        SourceScan.SourceFault(
                            path,
                            line_number,
                            f"writes {rule.description}"
                            f" {match.group(1)!r}: {line.strip()}",
                        )
                    )

    def exit_code(self, file_count: int, verbose: bool) -> int:
        if not self.faults:
            if verbose:
                print(
                    f"{file_count} file(s): no comment block over"
                    f" {_COMMENT_BLOCK_MAX_LINES} lines, no stray non-ASCII,"
                    " no unicode escape, no banned tag, no comment outside"
                    " ENGLISH_PUNCT"
                )
            return 0
        for fault in sorted(self.faults):
            relative = os.path.relpath(fault.path, callgrind.REPO_ROOT)
            print(
                f"{relative}:{fault.line_number}: {fault.message}",
                file=sys.stderr,
            )
        return 1

    def file_scan(
        self,
        path: str,
        non_ascii: re.Pattern[str],
        banned_tag: re.Pattern[str],
        comment_cut: re.Pattern[str],
        outside_punctuation: re.Pattern[str],
    ) -> None:
        syntax = self.comment_syntax_of(path)
        text = self.file_text_of(path)
        lines = text.split("\n")
        comments = self.comments_of(text, syntax)
        header_end = self.header_ends_at(lines, comments)
        self.unicode_check(path, lines, non_ascii)
        self.escape_check(path, lines)
        self.tag_check(path, lines, banned_tag)
        self.comment_check(path, comments, header_end)
        self.punctuation_check(
            path, lines, comments, header_end, comment_cut, outside_punctuation
        )

    def file_text_of(self, path: str) -> str:
        try:
            with open(path, "rb") as handle:
                raw_bytes = handle.read()
        except OSError as error:
            sys.exit(f"error: cannot read {path}: {error}")
        try:
            return raw_bytes.decode("utf-8")
        except UnicodeDecodeError as error:
            line_number = raw_bytes.count(b"\n", 0, error.start) + 1
            sys.exit(f"error: {path}:{line_number}: not UTF-8, {error.reason}")

    def files_scan(self, paths: list[str]) -> None:
        non_ascii = self.non_ascii_re()
        banned_tag = self.banned_tag_re()
        comment_cut = self.comment_cut_re()
        outside_punctuation = self.outside_punctuation_re()
        for path in paths:
            self.file_scan(
                path, non_ascii, banned_tag, comment_cut, outside_punctuation
            )

    def header_ends_at(
        self, lines: list[str], comments: list[SourceScan.CommentSpan]
    ) -> int:
        header_end = 1
        for comment in comments:
            if header_end == 2 and lines[0].startswith("#!"):
                while not lines[header_end - 1].strip():
                    header_end += 1
            if comment.first_line != header_end:
                break
            header_end = comment.last_line + 1
        return header_end

    def non_ascii_re(self) -> re.Pattern[str]:
        allowed = "".join(_SOURCE_SCAN_ALLOWED_NON_ASCII_CHARS)
        return re.compile(r"[^\t\n\r -~" + allowed + r"]")

    def outside_punctuation_re(self) -> re.Pattern[str]:
        return re.compile(r"[^A-Za-z0-9\s" + re.escape(ENGLISH_PUNCT) + r"]")

    def punctuation_check(
        self,
        path: str,
        lines: list[str],
        comments: list[SourceScan.CommentSpan],
        header_end: int,
        comment_cut: re.Pattern[str],
        outside_punctuation: re.Pattern[str],
    ) -> None:
        for comment in comments:
            if comment.first_line < header_end:
                continue
            text = "\n".join(lines[comment.first_line - 1 : comment.last_line])
            text = comment_cut.sub(
                lambda cut: "\n" * cut.group().count("\n"), text
            )
            for offset, line in enumerate(text.split("\n")):
                match = outside_punctuation.search(line)
                if match:
                    self.faults.append(
                        SourceScan.SourceFault(
                            path,
                            comment.first_line + offset,
                            f"comment holds {match.group()!r} outside"
                            " ENGLISH_PUNCT",
                        )
                    )

    def tag_check(
        self, path: str, lines: list[str], banned_tag: re.Pattern[str]
    ) -> None:
        for line_number, line in enumerate(lines, start=1):
            match = banned_tag.search(line)
            if match:
                self.faults.append(
                    SourceScan.SourceFault(
                        path,
                        line_number,
                        f"writes the banned tag {match.group(1)!r}, which"
                        " styles text beyond colour; use a span or div"
                        " with a colour class: "
                        f"{line.strip()}",
                    )
                )

    def unicode_check(
        self, path: str, lines: list[str], non_ascii: re.Pattern[str]
    ) -> None:
        for line_number, line in enumerate(lines, start=1):
            match = non_ascii.search(line)
            if match:
                self.faults.append(
                    SourceScan.SourceFault(
                        path,
                        line_number,
                        "contains a character outside printable ASCII"
                        f" {match.group()!r}:"
                        f" {line.strip()}",
                    )
                )


_COMMENT_BLOCK_MAX_LINES = 1

_COMMENT_SYNTAX_BY_EXTENSION = (
    ((".py", ".sh"), SourceScan.CommentSyntax(("#",), ())),
    ((".c", ".h", ".js"), SourceScan.CommentSyntax(("//",), (("/*", "*/"),))),
    ((".css",), SourceScan.CommentSyntax((), (("/*", "*/"),))),
    (
        (".html",),
        SourceScan.CommentSyntax(("//",), (("<!--", "-->"), ("/*", "*/"))),
    ),
    ((".md",), SourceScan.CommentSyntax((), (("<!--", "-->"),))),
)

ENGLISH_PUNCT = """.,"'?:!()/"""

_ESCAPE_NAMED_ENTITY_PATTERN = "|".join(
    re.escape(name)
    for name, glyph in sorted(html.entities.html5.items())
    if name.endswith(";") and not glyph.isascii()
)

_ESCAPE_PREFIX_PATTERN = r"(?<!\\)(?:\\\\)*"

_ESCAPE_RULES = (
    SourceScan.EscapeRule(
        "the unicode escape",
        _ESCAPE_PREFIX_PATTERN + r"(\\[uU][0-9A-Fa-f{])",
        (),
    ),
    SourceScan.EscapeRule(
        "the hex escape", _ESCAPE_PREFIX_PATTERN + r"(\\x[0-9A-Fa-f])", ()
    ),
    SourceScan.EscapeRule(
        "the named escape", _ESCAPE_PREFIX_PATTERN + r"(\\N\{)", ()
    ),
    SourceScan.EscapeRule(
        "the octal escape", _ESCAPE_PREFIX_PATTERN + r"(\\[0-7]{3})", ()
    ),
    SourceScan.EscapeRule(
        "the stylesheet escape",
        _ESCAPE_PREFIX_PATTERN + r"(\\[0-9A-Fa-f]{1,6})",
        (".css",),
    ),
    SourceScan.EscapeRule(
        "the named entity",
        r"(&(?:" + _ESCAPE_NAMED_ENTITY_PATTERN + r"))",
        (".css", ".html", ".js", ".md", ".py", ".sh"),
    ),
    SourceScan.EscapeRule(
        "the numeric entity", r"(&#(?:[0-9]+|[xX][0-9A-Fa-f]+);)", ()
    ),
    SourceScan.EscapeRule(
        "the character constructor",
        r"(String\s*\.\s*from(?:CharCode|CodePoint)"
        r"|(?<![\w.])(?:(?:globalThis|self|window)\s*\.\s*)?"
        r"(?:unescape|atob)(?=\()"
        r"|(?<!\w)ch[r](?=\()"
        r"|bytes\.fromhex"
        r"|unicode[_]escape)",
        (),
    ),
)

_SOURCE_SCAN_ALLOWED_NON_ASCII_CHARS = (
    "©",
    "≈",
    "∞",
    "▲",
    "⯅",
    "⯇",
    "⯈",
    "⯆",
    "▼",
    "…",
    "█",
    "░",
    "▒",
    "▓",
)

_SOURCE_SCAN_BANNED_TAG_NAMES = (
    "abbr",
    "address",
    "b",
    "big",
    "blockquote",
    "center",
    "cite",
    "code",
    "del",
    "dfn",
    "em",
    "font",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "hr",
    "i",
    "ins",
    "kbd",
    "mark",
    "p",
    "q",
    "s",
    "samp",
    "small",
    "strike",
    "strong",
    "sub",
    "sup",
    "tt",
    "u",
    "var",
)

_SOURCE_SCAN_COMMENT_MARKUP = (
    "<!--",
    "-->",
    "/*",
    "*/",
    "///",
    "//",
    "#",
    "*",
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "paths",
        nargs="+",
        help="the files to scan, as the caller expands its whitelist",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="print the ok line; a quiet run prints nothing on success",
    )
    namespace = parser.parse_args()
    scanner = SourceScan()
    scanner.files_scan(namespace.paths)
    return scanner.exit_code(len(namespace.paths), namespace.verbose)


if __name__ == "__main__":
    sys.exit(main())
