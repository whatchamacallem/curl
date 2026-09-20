#!/bin/sh

set -eu

# Nuke the files in .gitignore.
git clean -Xdf

ccache --clear --zero-stats
