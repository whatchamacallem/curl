#!/usr/bin/env bash

# This comment intentionally blank. No documentation goes here.

usage_show() {
  cat <<'EOF'
clean.sh [--help]
    Clears ./.gitignore except tmp/. Clears profiling from ccache. --help is
    the only argument.
EOF
}

set -euo pipefail

[ $# = 0 ] || { [[ $* =~ ^(-h|--help)$ ]] && usage_show && exit 0; } \
  || { echo "error: unknown option: $*" && usage_show && exit 2; } >&2

_SCRIPT="$(cd "$(dirname "$0")" && pwd)/$(basename "$0")"
cd "$(dirname "$_SCRIPT")"

. ./scripts/settings.sh

# git clean starts at the current directory, hence the cd above; tmp/ is
# the user's and stays
git clean -Xdf -e '!tmp/' -e '!tmp/**'

ccache --evict-namespace "$BUILD_CCACHE_NAMESPACE"
