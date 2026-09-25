#!/bin/sh

set -eu

# Otherwise git clean starts at the current directory.
_SCRIPT="$(readlink -f "$0")"
cd "$(dirname "$_SCRIPT")"

# Nuke the files in .gitignore except docs/.
git clean -Xdf -e '!docs/' -e '!docs/**'

ccache --clear --zero-stats
