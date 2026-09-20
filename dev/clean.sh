#!/bin/sh

set -eu

# Nukes the files in .gitignore.
git clean -Xdf

# Nukes ccache.
ccache --clear --zero-stats
