#!/usr/bin/env python3
# dev/scripts/comment_block_scan.py [dir ...] -- the comment length check.
#
# A comment block is consecutive whole-line comments. Three or more of them
# in a row is an error: a comment says what a thing is in one line, or two
# where one will not carry it, and anything longer belongs in README.md or
# DECLAUDE.md rather than above the code.
#
# A file's opening header is exempt. It runs from line 1 to the first line
# of code, and it is where a format reference, a grammar the other language
# parses against, or a table of what runs over what is written down.
#
# Immune everywhere else, because none of them is a comment: usage text, a
# .md file, and a string literal. Only a line whose first character begins a
# comment is counted, so a trailing comment and a "#" inside a string are
# both invisible to this.
from __future__ import annotations

import argparse, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import callgrind, settings

_ARTIFACTS_NAME: str = ""
settings.load_into(__name__)


# CommentBlockScan - Every comment block in a tree, and which ran too long.
class CommentBlockScan:
    # CommentRun - one block of whole-line comments, as found.
    class CommentRun:
        # the file it sits in
        path: str
        # the line the block opens on, 1-based
        first_line: int
        # how many lines of comment it runs for
        length: int

        def __init__(self, path: str, first_line: int, length: int) -> None:
            self.path = path
            self.first_line = first_line
            self.length = length

    def __init__(self) -> None:
        # every block found over the limit, printed together at the end
        self.faults: list[CommentBlockScan.CommentRun] = []

    # Whether a stripped line opens a whole-line comment in this language.
    def comment_line_is(self, line: str, marks: tuple[str, ...]) -> bool:
        return any(line.startswith(mark) for mark in marks)

    # Which comment markers a file's extension uses, or none when the
    # extension is not one this scans.
    def comment_marks_of(self, path: str) -> tuple[str, ...]:
        for extensions, marks in _COMMENT_MARKS_BY_EXTENSION:
            if path.endswith(extensions):
                return marks
        return ()

    # Print every fault and give the exit code the caller returns.
    def exit_code(self) -> int:
        if not self.faults:
            print(f"no comment block over {_COMMENT_BLOCK_MAX_LINES} lines")
            return 0
        for fault in sorted(
            self.faults, key=lambda run: (run.path, run.first_line)
        ):
            relative = os.path.relpath(fault.path, callgrind.REPO_ROOT)
            print(
                f"{relative}:{fault.first_line}: a comment block of"
                f" {fault.length} lines, over the limit of"
                f" {_COMMENT_BLOCK_MAX_LINES}. Say it in"
                f" {_COMMENT_BLOCK_MAX_LINES} lines or move the rest into"
                " README.md or DECLAUDE.md",
                file=sys.stderr,
            )
        print(
            f"{len(self.faults)} comment block(s) over"
            f" {_COMMENT_BLOCK_MAX_LINES} lines",
            file=sys.stderr,
        )
        return 1

    # Where a file's header ends: the first line that is neither a comment,
    # a blank, nor a shebang. Everything above it is exempt.
    def header_ends_at(self, lines: list[str], marks: tuple[str, ...]) -> int:
        for number, line in enumerate(lines, start=1):
            stripped = line.strip()
            if not stripped or stripped.startswith(_SHEBANG_MARK):
                continue
            if not self.comment_line_is(stripped, marks):
                return number
        return len(lines) + 1

    # Walk one file, recording every block over the limit below its header.
    # A blank line is not a comment, so it splits one block into two.
    def file_scan(self, path: str) -> None:
        marks = self.comment_marks_of(path)
        if not marks:
            return
        try:
            with open(path, encoding="utf-8", errors="replace") as handle:
                lines = handle.read().split("\n")
        except OSError:
            return
        header_end = self.header_ends_at(lines, marks)
        length = 0
        first_line = 0
        for number, line in enumerate(lines, start=1):
            if number < header_end:
                continue
            if self.comment_line_is(line.strip(), marks):
                if not length:
                    first_line = number
                length += 1
                continue
            self.run_record(path, first_line, length)
            length = 0
        self.run_record(path, first_line, length)

    # Keep one finished block when it ran past the limit.
    def run_record(self, path: str, first_line: int, length: int) -> None:
        if length > _COMMENT_BLOCK_MAX_LINES:
            self.faults.append(
                CommentBlockScan.CommentRun(path, first_line, length)
            )

    # Scan every source file under each directory given, or a file named
    # directly, which walking would silently find nothing in.
    def tree_scan(self, roots: list[str]) -> None:
        for root_dir in roots:
            if os.path.isfile(root_dir):
                self.file_scan(root_dir)
                continue
            for root, dirs, names in os.walk(root_dir):
                dirs[:] = [
                    name
                    for name in dirs
                    if name not in _SCAN_SKIPPED_DIRS
                    and not name.endswith(_SCAN_SKIPPED_DIR_SUFFIXES)
                    and not name.startswith(".")
                ]
                for name in names:
                    self.file_scan(os.path.join(root, name))


# How many consecutive comment lines a block may run to. Two names a thing
# and says why; a third is a paragraph, which belongs in README.md.
_COMMENT_BLOCK_MAX_LINES = 2

# Which extensions this scans and what opens a comment in each. A .c block
# runs "/*" then " *", so both count. A config file is not source.
_COMMENT_MARKS_BY_EXTENSION = (
    ((".py", ".sh"), ("#",)),
    ((".c", ".h"), ("/*", "*/", "*", "//")),
    ((".js", ".css"), ("/*", "*/", "*", "//")),
)

# Generated output, caches and recordings, none of which is source. A report
# and a build tree are recognised by name, as the ASCII scan does it.
_SCAN_SKIPPED_DIRS = ("__pycache__", _ARTIFACTS_NAME)
_SCAN_SKIPPED_DIR_SUFFIXES = ("_report",)

# A "#!" line is part of the header, not a comment block of its own.
_SHEBANG_MARK = "#!"


# main - Scan the trees named, or dev/ when none is.
def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "roots",
        nargs="*",
        help="directories to scan, or dev/ when none is given",
    )
    namespace = parser.parse_args()
    roots = namespace.roots or [os.path.join(callgrind.REPO_ROOT, "dev")]
    scanner = CommentBlockScan()
    scanner.tree_scan(roots)
    return scanner.exit_code()


if __name__ == "__main__":
    sys.exit(main())
