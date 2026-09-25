#!/usr/bin/env bash

# This comment intentionally blank. No documentation goes here.

set -euo pipefail

_SCRIPT="$(readlink -f "$0")"
cd "$(dirname "$_SCRIPT")"

. ./scripts/settings.sh

# usage_show - the one line of usage, printed by -h and on a bad argument
usage_show() {
  echo "clean.sh    Deletes dev/'s ignored files but tmp/; evicts our ccache."
}

# every argument is read before anything runs: only -h/--help is one
for _ARGUMENT in "$@"; do
  case "$_ARGUMENT" in
    -h | --help)
      usage_show
      exit 0
      ;;
    *)
      echo "error: unknown option: $_ARGUMENT" >&2
      usage_show >&2
      exit 2
      ;;
  esac
done

# git clean starts at the current directory, hence the cd above; tmp/ is
# the user's and stays
git clean -Xdf -e '!tmp/' -e '!tmp/**'

ccache --evict-namespace "$BUILD_CCACHE_NAMESPACE"
