#!/usr/bin/env python3
# enforcer.sh uses this to enforce comment length and ascii-only.
from __future__ import annotations

import argparse, os, re, sys
from typing import NamedTuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import callgrind


# SourceScan - Every comment block over the limit and every non-ASCII
# character outside the allowed set, in the files named.
class SourceScan:
    # CommentSyntax - How one kind of file writes a comment.
    class CommentSyntax(NamedTuple):
        # what opens a comment that runs to the end of its line
        line_marks: tuple[str, ...]
        # each block comment's opening and closing mark, which may span lines
        block_marks: tuple[tuple[str, str], ...]

    # SourceFault - One line of one file that broke a rule, and how.
    class SourceFault(NamedTuple):
        # the file it sits in
        path: str
        # the line it is on, or a comment block opens on, 1-based
        line_number: int
        # what is wrong there, for the message
        message: str

    def __init__(self) -> None:
        # every fault found, printed together once every file is read
        self.faults: list[SourceScan.SourceFault] = []

    # Record every comment block below a file's header that runs past the
    # limit. A blank line outside a block comment splits one block into two.
    def comment_check(
        self, path: str, lines: list[str], syntax: SourceScan.CommentSyntax
    ) -> None:
        comment_lines = self.comment_lines_of(lines, syntax)
        header_end = self.header_ends_at(lines, comment_lines)
        length = 0
        first_line = 0
        for number, is_comment in enumerate(comment_lines, start=1):
            if number < header_end:
                continue
            if is_comment:
                if not length:
                    first_line = number
                length += 1
                continue
            self.run_record(path, first_line, length)
            length = 0
        self.run_record(path, first_line, length)

    # Whether each line is a whole-line comment: one opening first on the
    # line, or any line of a block comment still open from above it.
    def comment_lines_of(
        self, lines: list[str], syntax: SourceScan.CommentSyntax
    ) -> list[bool]:
        comment_lines: list[bool] = []
        open_block_end = ""
        for line in lines:
            stripped = line.strip()
            if open_block_end:
                comment_lines.append(True)
                if open_block_end in stripped:
                    open_block_end = ""
                continue
            comment_lines.append(stripped.startswith(syntax.line_marks))
            for opening_mark, closing_mark in syntax.block_marks:
                if stripped.startswith(opening_mark):
                    comment_lines[-1] = True
                    if closing_mark not in stripped[len(opening_mark) :]:
                        open_block_end = closing_mark
                    break
        return comment_lines

    # The comment syntax of a file's kind. A kind with none written down
    # cannot be measured, so it stops the scan rather than passing unread.
    def comment_syntax_of(self, path: str) -> SourceScan.CommentSyntax:
        for extensions, syntax in _COMMENT_SYNTAX_BY_EXTENSION:
            if path.endswith(extensions):
                return syntax
        sys.exit(
            f"error: {path}: no comment syntax is known for this kind of"
            " file; add its extension to _COMMENT_SYNTAX_BY_EXTENSION"
        )

    # Print every fault, or the one ok line, and give the exit code.
    def exit_code(self, file_count: int) -> int:
        if not self.faults:
            print(
                f"{file_count} file(s): no comment block over"
                f" {_COMMENT_BLOCK_MAX_LINES} lines, no stray non-ASCII"
            )
            return 0
        for fault in sorted(self.faults):
            relative = os.path.relpath(fault.path, callgrind.REPO_ROOT)
            print(
                f"{relative}:{fault.line_number}: {fault.message}",
                file=sys.stderr,
            )
        return 1

    # Read one file once and run both checks over it. A file this cannot
    # read or decode was never checked, so that stops the scan.
    def file_scan(self, path: str, non_ascii: re.Pattern[str]) -> None:
        syntax = self.comment_syntax_of(path)
        try:
            with open(path, "rb") as handle:
                raw_bytes = handle.read()
        except OSError as error:
            sys.exit(f"error: cannot read {path}: {error}")
        try:
            text = raw_bytes.decode("utf-8")
        except UnicodeDecodeError as error:
            line_number = raw_bytes.count(b"\n", 0, error.start) + 1
            sys.exit(f"error: {path}:{line_number}: not UTF-8, {error.reason}")
        lines = text.split("\n")
        self.unicode_check(path, lines, non_ascii)
        self.comment_check(path, lines, syntax)

    # Scan each file named, and only those: enforcer.sh expands the list
    # from its whitelist, so no directory is walked here.
    def files_scan(self, paths: list[str]) -> None:
        non_ascii = self.non_ascii_re()
        for path in paths:
            self.file_scan(path, non_ascii)

    # Where a file's header ends: the first line that is neither a comment
    # nor blank. Everything above it, a "#!" line included, is exempt.
    def header_ends_at(
        self, lines: list[str], comment_lines: list[bool]
    ) -> int:
        for number, (line, is_comment) in enumerate(
            zip(lines, comment_lines, strict=True), start=1
        ):
            if line.strip() and not is_comment:
                return number
        return len(lines) + 1

    # Anything outside plain ASCII that the allow list does not permit.
    def non_ascii_re(self) -> re.Pattern[str]:
        allowed = "".join(_SOURCE_SCAN_ALLOWED_NON_ASCII_CHARS)
        return re.compile(r"[^\x00-\x7F" + allowed + r"]")

    # Keep one finished comment block when it ran past the limit.
    def run_record(self, path: str, first_line: int, length: int) -> None:
        if length > _COMMENT_BLOCK_MAX_LINES:
            self.faults.append(
                SourceScan.SourceFault(
                    path,
                    first_line,
                    f"a comment block of {length} lines, over the limit of"
                    f" {_COMMENT_BLOCK_MAX_LINES}. Say it in"
                    f" {_COMMENT_BLOCK_MAX_LINES} lines or move the rest"
                    " into README.md or DECLAUDE.md",
                )
            )

    # Record every line holding a character the allow list does not permit.
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
                        f"contains a non-ASCII character {match.group()!r}:"
                        f" {line.strip()}",
                    )
                )


# How many consecutive comment lines a block may run to. Two names a thing
# and says why; a third is a paragraph, which belongs in README.md.
_COMMENT_BLOCK_MAX_LINES = 2

# How each whitelisted kind writes a comment. A page template holds script
# and style too, so it takes their marks beside its own.
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

# The diff vocabulary, spelled the same everywhere a reader sees it. These
# are the only non-ASCII characters a whitelisted file may contain.
_SOURCE_SCAN_ALLOWED_NON_ASCII_CHARS = (
    # almost equal to
    "≈",
    # infinity
    "∞",
    # up-pointing triangle
    "▲",
    # right-pointing triangle, the heat map's collapsed caret
    "▶",
    # down-pointing triangle
    "▼",
    # horizontal ellipsis
    "…",
)


# main - Scan exactly the files named. enforcer.sh names every whitelisted
# one, so nothing here decides which files are source.
def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "paths",
        nargs="+",
        help="the files to scan, as enforcer.sh expands its whitelist",
    )
    namespace = parser.parse_args()
    scanner = SourceScan()
    scanner.files_scan(namespace.paths)
    return scanner.exit_code(len(namespace.paths))


if __name__ == "__main__":
    sys.exit(main())
