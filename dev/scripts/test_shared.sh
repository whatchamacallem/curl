# dev/scripts/test_shared.sh

# tool_find - echo a tool's path, searching the pip and npm user bins too.
tool_find() {
  local name="$1" found
  for found in "$name" "$HOME/.local/bin/$name" \
    "$HOME/.npm-global/bin/$name"; do
    if command -v "$found" >/dev/null 2>&1; then
      echo "$found"
      return 0
    fi
  done
  return 1
}
