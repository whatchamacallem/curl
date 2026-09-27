#!/usr/bin/env bash

# This comment intentionally blank. No documentation goes here.

set -euo pipefail

# usage_show - the one usage text, printed by -h and on a bad argument
usage_show() {
  cat <<'EOF'
clean.sh [--help]
    Clears .gitignore except tmp/. Clears profiling from ccache . --help is
    the only argument.
EOF
}

[ $# = 0 ] || { [[ $* =~ ^(-h|--help)$ ]] && usage_show && exit 0; } \
  || { echo "error: unknown option: $*" && usage_show && exit 2; } >&2

_SCRIPT="$(readlink -f "$0")"
cd "$(dirname "$_SCRIPT")"

. ./scripts/settings.sh

# git clean starts at the current directory, hence the cd above; tmp/ is
# the user's and stays
git clean -Xdf -e '!tmp/' -e '!tmp/**'

ccache --evict-namespace "$BUILD_CCACHE_NAMESPACE"
