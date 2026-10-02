#!/bin/sh
# SPDX-FileCopyrightText: © 2026 Adrian Johnston.
# SPDX-License-Identifier: MIT
# This file is licensed under the terms of the LICENSE-MIT.md file.

set -eu

_SCRIPT_NAME_=$(basename "$0")
_PROJECT_="$(basename "$PWD")"
_DATE_="$(date +%Y-%m-%d)"
_ARCHIVE_="$_PROJECT_-$_DATE_.git.txz"

# Print help if there is more than one arg or the first arg starts with a -.
if [ "$#" -gt 1 ] || { [ "$#" -eq 1 ] && [ "${1#-}" != "$1" ]; }; then
	echo "usage_error: $0 [destination-directory]"
	echo "Will create $_ARCHIVE_ in the destination-directory if"
	echo "provided, otherwise ~/Backups/ if it exists and in ~/ otherwise. Restores all"
	echo "files if $_SCRIPT_NAME_ is the only file in the directory."
	exit 1
fi

# Check for the .git file.
if [ ! -d ".git" ]; then
	echo "error: .git not found" >&2
	exit 1
fi

# Extract archive if this script is the only non-hidden file.
if [ "$(command ls)" = "$_SCRIPT_NAME_" ]; then
	git fsck
	git restore .
	echo "Extracted all files in $_PROJECT_."

	_FS_TYPE_=$(stat -f -c "%T" . 2>/dev/null) || _FS_TYPE_=""
	if [ "$_FS_TYPE_" = "v9fs" ] || [ "$_FS_TYPE_" = "fuseblk" ] || [ "$_FS_TYPE_" = "ntfs" ]; then
		echo "Windows detected. Setting config core.fileMode false."
		git config core.fileMode false
	fi
	exit 0
fi

# Create archive.
if [ "$#" -eq 1 ]; then
	_DEST_DIR_="$1"
elif [ -d "$HOME/Backups" ]; then
	_DEST_DIR_="$HOME/Backups"
else
	_DEST_DIR_="$HOME"
fi
if [ ! -d "$_DEST_DIR_" ]; then
	echo "Destination directory not found: $_DEST_DIR_" >&2
	exit 1
fi

git fsck

git reflog expire --expire=24.hours.ago --expire-unreachable=24.hours.ago --all
git gc --prune=now --aggressive

# Save everything including local git config.
tar -cJf "$_DEST_DIR_/$_ARCHIVE_" -C ".." "$_PROJECT_/$_SCRIPT_NAME_" "$_PROJECT_/.git"

printf "Wrote: "
ls -h1s "$_DEST_DIR_/$_ARCHIVE_"
