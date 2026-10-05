#!/usr/bin/env python3
# SPDX-FileCopyrightText: © 2026 Adrian Johnston.
# SPDX-License-Identifier: MIT
# This file is licensed under the terms of the LICENSE-MIT.md file.

from __future__ import annotations

import argparse, os, re, subprocess, sys
from typing import NamedTuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import callgrind

_OBJDUMP_FUNCTION_SYMBOL_RE = re.compile(r"^([0-9a-f]+) .{6}F .*\s(\S+)$")
_OBJDUMP_LABEL_RE = re.compile(r"^([0-9a-f]+) <(.+)>:$")
_OBJDUMP_TEXT_SECTION_NAME = ".text"

_VALGRIND_LOAD_ADDRESS_RE = re.compile(
    r"^--\d+--\s+svma (0x[0-9a-f]+), avma (0x[0-9a-f]+)$"
)
_VALGRIND_READING_SYMBOLS_RE = re.compile(r"^--\d+-- Reading syms from (.+)$")


class CodeSection(NamedTuple):
    name: str
    start: int
    size: int


class LoadedObject(NamedTuple):
    path: str
    bias: int


class CallgrindSymbols:
    class SymbolsArgs(NamedTuple):
        valgrind_log: str
        callgrind_file: str

    def __init__(self) -> None:
        self.labels_by_path: dict[str, dict[int, str]] = {}
        self.sections_by_path: dict[str, list[CodeSection]] = {}

    def build(self, args: CallgrindSymbols.SymbolsArgs) -> None:
        loaded_objects = self.loaded_objects_read(args.valgrind_log)
        with open(args.callgrind_file, encoding="utf-8") as handle:
            recorded_text = handle.read()
        resolved_text = callgrind.address_names_resolve(
            recorded_text,
            lambda object_path, name: self.name_of(
                args, loaded_objects, object_path, name
            ),
        )
        with open(args.callgrind_file, "w", encoding="utf-8") as handle:
            handle.write(resolved_text)

    # Reads the code sections of an object, once.
    def code_sections(self, path: str) -> list[CodeSection]:
        if path not in self.sections_by_path:
            sections: list[CodeSection] = []
            for line in self.listing_of(["-h", "-w"], path).splitlines():
                line_fields = line.split(maxsplit=7)
                if (
                    len(line_fields) == 8
                    and line_fields[0].isdigit()
                    and "CODE" in line_fields[7]
                ):
                    sections.append(
                        CodeSection(
                            line_fields[1],
                            int(line_fields[3], 16),
                            int(line_fields[2], 16),
                        )
                    )
            self.sections_by_path[path] = sections
        return self.sections_by_path[path]

    def listing_of(self, options: list[str], path: str) -> str:
        return subprocess.run(
            ["objdump", *options, path],
            check=True,
            capture_output=True,
            text=True,
        ).stdout

    def loaded_objects_read(self, path: str) -> list[LoadedObject]:
        loaded_objects: list[LoadedObject] = []
        reading_path: str | None = None
        with open(path, encoding="utf-8") as handle:
            for line in handle.read().splitlines():
                match = _VALGRIND_READING_SYMBOLS_RE.match(line)
                if match:
                    reading_path = match.group(1)
                    continue
                match = _VALGRIND_LOAD_ADDRESS_RE.match(line)
                if match and reading_path is not None:
                    loaded_objects.append(
                        LoadedObject(
                            reading_path,
                            int(match.group(2), 16) - int(match.group(1), 16),
                        )
                    )
                    reading_path = None
        if not loaded_objects:
            sys.exit(
                f"error: no load address in {path}: valgrind needs"
                " --trace-redir=yes"
            )
        return loaded_objects

    # Names an address in its object, or keeps callgrind's name there.
    def name_of(
        self,
        args: CallgrindSymbols.SymbolsArgs,
        loaded_objects: list[LoadedObject],
        object_path: str | None,
        name: str,
    ) -> str | None:
        name_address = int(name, 16)
        if object_path is not None:
            return self.object_labels(object_path).get(name_address)
        owner_objects = [
            loaded
            for loaded in loaded_objects
            if any(
                section.start
                <= name_address - loaded.bias
                < section.start + section.size
                for section in self.code_sections(loaded.path)
            )
        ]
        if len(owner_objects) != 1:
            sys.exit(
                f"error: {args.callgrind_file}: function {name} lies in"
                f" {len(owner_objects)} objects {args.valgrind_log} loads,"
                " expected 1"
            )
        object_offset = name_address - owner_objects[0].bias
        label_name = self.object_labels(owner_objects[0].path).get(
            object_offset
        )
        if label_name is None:
            sys.exit(
                f"error: {args.callgrind_file}: function {name} lies at"
                f" {object_offset:#x} in {owner_objects[0].path}, where no"
                " symbol starts"
            )
        return label_name

    # Reads every function symbol and every label outside the text section.
    def object_labels(self, path: str) -> dict[int, str]:
        if path not in self.labels_by_path:
            label_names: dict[int, str] = {}
            for line in self.listing_of(["-t"], path).splitlines():
                match = _OBJDUMP_FUNCTION_SYMBOL_RE.match(line)
                if match:
                    label_names.setdefault(
                        int(match.group(1), 16), match.group(2)
                    )
            section_options = [
                option
                for section in self.code_sections(path)
                if section.name != _OBJDUMP_TEXT_SECTION_NAME
                for option in ("-j", section.name)
            ]
            if section_options:
                disassembly_text = self.listing_of(
                    ["-d", "--no-show-raw-insn", *section_options], path
                )
                for line in disassembly_text.splitlines():
                    match = _OBJDUMP_LABEL_RE.match(line)
                    if match:
                        label_names.setdefault(
                            int(match.group(1), 16), match.group(2)
                        )
            self.labels_by_path[path] = label_names
        return self.labels_by_path[path]


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Names each function callgrind left as an address, from the"
            " objects and load addresses the valgrind log names, and"
            " rewrites the callgrind file in place."
        )
    )
    parser.add_argument(
        "--valgrind-log",
        required=True,
        metavar="FILE",
        help="the log of the valgrind run, written with --trace-redir=yes",
    )
    parser.add_argument(
        "--callgrind-file",
        required=True,
        metavar="FILE",
        help="the callgrind file that run wrote",
    )
    namespace = parser.parse_args()
    CallgrindSymbols().build(
        CallgrindSymbols.SymbolsArgs(
            valgrind_log=namespace.valgrind_log,
            callgrind_file=namespace.callgrind_file,
        )
    )


if __name__ == "__main__":
    main()
