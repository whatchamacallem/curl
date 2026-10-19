# SPDX-FileCopyrightText: © 2026 Adrian Johnston.
# SPDX-License-Identifier: MIT
# This file is licensed under the terms of the LICENSE-MIT.md file.

from __future__ import annotations

import os, sys, typing

import settings

_ARTIFACT_FILE_PURPOSES: dict[str, str] = {}
_ARTIFACT_RUN_FILE_FORMATS: dict[str, str] = {}
_ARTIFACT_TEST_FILE_FORMATS: dict[str, str] = {}
_REPORT_ARTIFACTS_DIR_FORMAT: str = ""
_REPORT_RAW_ARCHIVE_SUFFIX: str = ""
_TIMER_ARTIFACTS_ROOT_FORMAT: str = ""
settings.load_into(__name__)


# Opens a contract file, exiting 2 with the name and purpose of a missing one.
def artifact_open(
    directory: str, kind: str, test_name: str = "", mode: str = "r"
) -> typing.IO[typing.Any]:
    path = artifact_path(directory, kind, test_name)
    try:
        return open(path, mode, encoding=None if "b" in mode else "utf-8")
    except FileNotFoundError:
        test_text = f" of {test_name}" if test_name else ""
        print(
            f"error: {directory} is missing {os.path.basename(path)},"
            f" {_ARTIFACT_FILE_PURPOSES[kind]}{test_text}",
            file=sys.stderr,
        )
        sys.exit(2)


# Returns the path a kind's format makes of a directory and any test name.
def artifact_path(directory: str, kind: str, test_name: str = "") -> str:
    if test_name and kind in _ARTIFACT_TEST_FILE_FORMATS:
        return _ARTIFACT_TEST_FILE_FORMATS[kind] % (directory, test_name)
    if not test_name and kind in _ARTIFACT_RUN_FILE_FORMATS:
        return _ARTIFACT_RUN_FILE_FORMATS[kind] % (directory,)
    raise ValueError(
        f"no artifact kind {kind!r} takes the test name {test_name!r}"
    )


# Returns the report's raw data archive, named for the run's recorded time.
def raw_data_archive_path(report_dir: str, recorded: str) -> str:
    root = _TIMER_ARTIFACTS_ROOT_FORMAT % (report_dir, recorded)
    return root + _REPORT_RAW_ARCHIVE_SUFFIX


# Returns the first word of the recorded row of the run's header rows.
def recorded_time_read(directory: str) -> str:
    with artifact_open(directory, "header-rows") as handle:
        rows = handle.read().splitlines()
    for row in rows:
        label, _, value = row.partition("=")
        if label == "recorded":
            recorded = value.partition(" ")[0]
            if recorded:
                return recorded
            break
    path = artifact_path(directory, "header-rows")
    print(
        f"error: {path} holds no recorded= row with a time first",
        file=sys.stderr,
    )
    sys.exit(2)


# Returns a report's own artifacts directory inside the artifacts directory.
def report_artifacts_dir(artifacts_dir: str, report_dir: str) -> str:
    return _REPORT_ARTIFACTS_DIR_FORMAT % (
        artifacts_dir,
        os.path.basename(report_dir),
    )


# Returns the run's test names, refusing an empty or unsorted list.
def test_list_read(directory: str) -> list[str]:
    with artifact_open(directory, "test-list") as handle:
        test_names = handle.read().splitlines()
    path = artifact_path(directory, "test-list")
    purpose = _ARTIFACT_FILE_PURPOSES["test-list"]
    if not test_names:
        print(f"error: {path} is empty, expected {purpose}", file=sys.stderr)
        sys.exit(2)
    if test_names != sorted(test_names):
        print(
            f"error: {path} is not LC_ALL=C sorted, expected {purpose}",
            file=sys.stderr,
        )
        sys.exit(2)
    return test_names
