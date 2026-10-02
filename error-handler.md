# error handler plan

Four changes, in dependency order. Nothing here is implemented yet.

## 1 The ui-key throw protocol

An exception message becomes a whitespace-delimited array. Token 0 is what
might be a ui string key; tokens 1..n are its positional args. The thrower
resolves nothing; the error handler resolves, and may fail without
breaking. Localization becomes possible without becoming a dependency: a
page with no `ui_strings.js` still prints the raw array, which names the
key and every arg explicitly.

### 1.1 `format_or_raw` replaces `text_or_fallback`

`error_overlay.js`'s `text_or_fallback(string_id)` becomes
`format_or_raw(message)`, taking the whole exception message:

1. Split `message` on whitespace. Token 0 is the candidate key.
1. If `window.ui_strings` is absent, or `text_of` is not a function,
   return `message` unchanged.
1. Look the key up through the existing swallowing `try`. On a miss,
   return `message` unchanged.
1. On a hit, use the found string as a format string over the remaining
   tokens and return `<key>:  <formatted>`.

Every failure path returns the raw message verbatim. There is no throw and
no second exception; an error page that cannot format still prints
everything the reader needs.

### 1.2 Positional markers, sequential

Format strings take `{0}`, `{1}`, `{2}` - indices into the array of args
that followed the key. This replaces the named `{counter}`, `{file}`,
`{function}`, `{view}`, `{seconds}` markers those five strings carry
today.

**A missing arg does not throw and does not partially format.** If a
format string references an index the arg array does not hold, the whole
attempt is abandoned and the raw message is printed instead:
`eg_ui_str 45 85`. That is the diagnostic - the reader sees the key, sees
which args arrived, and can tell what was missing. A half-substituted
sentence would hide it.

### 1.3 `text_fill` and the two consumers

`text_fill(string_id, replacements)` in `ui_strings.js` fills named
markers and is called from ~10 sites in `heatmap.js` that are not error
paths (`str_scale_entry`, `str_popup_*`, `str_heading_*`). Those keep
named markers and keep `text_fill`. Only the `str_error_*` strings the
handler formats move to positional.

So `ui_strings.js` gains a positional formatter beside `text_fill`,
rather than replacing it. Name it for what it does over an array.

### 1.4 Throw sites become key-first

Five sites build a resolved sentence today and stop doing so:

- `heatmap.js:1786` - `str_error_hash_counter_unknown` + counter
- `heatmap.js:1813` - `str_error_hash_function_unknown` + function
- `heatmap.js:1820` - `str_error_hash_file_unknown` + file
- `frame.js:78` - `str_error_hash_view_unknown` + view key
- `flame_bootstrap.js:22` - `str_error_flame_graph_never_started` +
  seconds

Each passes `"<key> <arg>"` to `hash_fault_show` / `overlay_show`.
`flame_bootstrap.js` already throws the bare key on its fallback branch;
that branch becomes the only form and its `text_fill` branch goes, which
also drops its `window.ui_strings` dependency entirely.

`heatmap.js`'s `hash_fault_show` keeps its shape - it still wraps the
message in `new Error` and still passes a source label. Only what the
caller hands it changes.

### 1.5 Non-key throws are unaffected

`settings_handler.js:13` throws `"no such setting: " + name`. Token 0 is
`no`, which is not a key, so the lookup misses and the raw message prints
naturally. Every browser-thrown `TypeError` behaves the same way. This is
the point of the protocol, not an edge case.

### 1.6 The ui string args

Rewriting the five strings to positional markers means each one's args are
now ordered, not named. Where a string takes one arg this is trivial. None
of the five takes more than one today, so no ordering question arises yet
- but the format is sequential from `{0}` and stays that way.

## 2 Error page rebuild - `error_overlay.js`

One `<pre>` holding a valid Markdown document. As few dependencies as
possible: the args passed to the handler, and nothing else.

### 2.1 Document shape

```
# perf2html error

<formatted or raw message>

## address

<truncated address>

## callstack

<markdown table>

## manifest

<markdown table>
```

`# perf2html error` is the title. `address`, `callstack` and `manifest`
are `##` rows. No explanation paragraph, no source-label sentence - that
sentence is what `str_error_page_explanation` and the source labels exist
for, and section 5 covers what happens to them.

### 2.2 Callstack as a table

The `at route_render (file://wsl.loc...` lines following the message
become a Markdown table with whitespace padded so the columns line up as
plain text. Columns: frame name, location. A stack line that does not
parse goes through as a single-cell row rather than being dropped.

`str_error_callstack_unavailable` covers an empty stack.

### 2.3 Manifest as a table

`window.report_manifest` is LABEL=VALUE rows. Split each on the first `=`
and render a two-column Markdown table, whitespace-padded the same way.
`str_error_manifest_unavailable` covers the global being absent.

### 2.4 Path truncation is a privacy requirement

Every `file://` path printed - the address and every stack frame location
- is truncated to start at the report root, so the copy button cannot
leak a home directory. This is not cosmetic. The report root is
recoverable from `location.href`; the truncation happens on the strings
the page prints, before they reach the `<pre>`.

### 2.5 Styling

White text on a charcoal background, medium ember red links, no
underline, done inline in the handler. `OVERLAY_STYLE_TEXT` and
`style_install()` go, and with them every `var(--bg, #14171c)` theme
reference. The handler stops having a theme relationship at all - today's
fallbacks are why it renders correctly on an unthemed page, and inline
styles make that unconditional.

## 3 Bottom controls

Three unadorned word links, matching the existing `copy`:

- `copy` - copies the `<pre>` text verbatim, truncated paths included.
- `reload` - reloads the page that threw, returning to the app. The
  overlay touches neither `history` nor the URL, so the bad address is
  still in the bar and a reload relaunches it.
- `restart` - sends the top document to the report root `index.html`,
  the overview page.

## 4 Manifest stamp

### 4.1 Write the human date after the unix time

`stamp=<unix> <date '+%F %I:%M:%S %p'>`, so the row reads
`stamp=556777 2026-09-23 11:56:04 AM`. Written in `perf2html.sh:470` and
`perf2html_diff.sh:290`. One spelling - a shared helper in `shared.sh`,
not the same `date` invocation typed into two files.

### 4.2 Teach the stamp readers to take the first token only

The tail is for humans and could be locale-specific, so no reader parses
it. Three call sites read `stamp`:

- `perf2html.sh:132` - `stamp_reuse`, whose `$TIMESTAMP` rebuilds
  artifact filenames for `--regenerate`. Breaking this breaks
  `--regenerate`.
- `perf2html_diff.sh:255` - `_previous`.
- `validate_report.py` - via `manifest_value`, for the labels
  `_LAYOUT_*.manifest_labels` name.

**The first-token rule belongs at the stamp readers, not inside
`shared.sh`'s `manifest_value`.** That function serves every label, and
`cpu=` and `build=` hold values with spaces in them - truncating there
would corrupt both. Same for `validate_report.py`'s `manifest_value`,
which reads the checksum row.

So: a stamp-specific accessor in each language that calls the general
`manifest_value` and takes its first whitespace-delimited token. Four
scanners taught, none of them by narrowing a shared reader.

### 4.3 What must still pass

- `validate_report.py`'s `manifest_check` matches `^stamp=.+$` per label,
  which a longer value still satisfies.
- `build_report.py`'s `manifest_read_file` splits on `=` and renders the
  row into the header table; the longer value renders as-is.
- The `checksum=` row is unaffected - it is written last and covers
  files, not manifest rows.

## 5 Contract updates

- `ui_strings.js` keeps its `str_error_*` entries. They are what the
  handler looks up now, not what the thrower embeds. The five that the
  handler formats move to positional markers.
- `str_error_page_explanation`, `str_error_source_address`,
  `str_error_source_exception` and `str_error_source_rejection` lose their
  place on the page under section 2.1. Decide whether the source label
  survives as a line in the Markdown document or the entries are dropped.
- `DECLAUDE.md` 6.4 asserts `text_or_fallback` by name, "its `str_error_*`
  entries live only in `ui_strings.js`", and "the source label leads the
  explanation sentence". All three change. Same-change update, per rule
  1.1.
- `dev/README.md` - check for error-page and `stamp=` wording. If it
  disagrees with the new model, ask; never silently edit it to match.
- `screenshots.py`'s `_VIEWS` and `validate_report.py` - check for
  assertions about the old error-page structure.

## 6 Verification

- 79 columns on every touched line. Markdown table rows and template
  literals are out of every formatter's reach - split by hand.
- ASCII plus the allow-list. Tables use ASCII pipes and hyphens only.
- Comment blocks at most 2 lines.
- One run of `dev/scripts/reformat.sh`.
