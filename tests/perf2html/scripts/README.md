# perf2html scripts

The [HTML Report Generators](#html-report-generators) are all you need to
profile and generate reports.

- [HTML Report Generators](#html-report-generators)

The rest of these sections are provided as a guide for interested developers.

These are the data formats.

- [URL Components](#url-components)
- [Browser Preferences](#browser-preferences)
- [Report Contents](#report-contents)
- [Raw Data Archive Contents](#raw-data-archive-contents)

The remaining sections describe the source code implementing the `perf2html`
report generators. Start by running the tests and checking the results.

- [Callers Page](#callers-page)
- [Callgrind Parsing](#callgrind-parsing)
- [Error Overlay](#error-overlay)
- [Flame Graph](#flame-graph)
- [Heat Map](#heat-map)
- [Menu Strip](#menu-strip)
- [Overview Page](#overview-page)
- [Settings Files](#settings-files)
- [Test Harness](#test-harness)
- [Theme Library](#theme-library)
- [Tool Configuration](#tool-configuration)

## HTML Report Generators

| File                    | Purpose                                           |
| ----------------------- | ------------------------------------------------- |
| `../perf2html.sh`       | Builds RelWithDebInfo, profiles every test under  |
|                         | callgrind, perf stat and a function trace, then   |
|                         | writes one report.                                |
| `../perf2html_batch.sh` | Writes a baseline report, a modified report built |
|                         | with the cmake flags given, then the diff of the  |
|                         | two.                                              |
| `../perf2html_diff.sh`  | Subtracts a baseline report from a modified       |
|                         | report and writes a diff report, measuring        |
|                         | nothing.                                          |

## URL Components

- `debug`: Query key, value `1`, that unfreezes the settings so the settings
  view can apply a setting.
- `file`: Hash key, heat map view only, that names the source file to open.
- `function`: Hash key, heat map view only, that names the function to open and
  excludes `file` and `line`.
- `line`: Hash key, heat map view only, that names the line within `file` to
  scroll to.
- `localProfilePath`: Hash key, flame graph view only, that is speedscope's own
  key naming the profile to load.
- `screenshot`: Query key whose value is shown as a label on the page.
- `screenshot-menu`: Query key, a menu entry number, that opens or focuses that
  entry after each menu render.
- `screenshot-mode`: Query key, `1` dark or `0` light, that sets the mode a
  screenshot is shot in.
- `setting`: Hash key, settings view only, that names the setting scrolled to
  the top.
- `setting-val`: Hash key, settings view only, that carries the base64 JSON of
  the new value for `setting`, applied on load.
- `test`: Hash key that names the test shown, `all` being the merged test.
- `view`: Hash key, one of `callers`, `heat-map`, `flame-graph` or `settings`,
  that names the page framed, required whenever `test` is present.

## Browser Preferences

Reports keep user preferences in in the browser's `localStorage`, shared by
every report opened from the same origin. Each value is JSON, `null` meaning
the user never chose one and the default in `settings.py` applies.

If the `perf2html.version` does not match `STORAGE_VERSION` then all
preferences are reset at startup.

- `callers.rows`: The callers row count, one of `TABLE_ROW_COUNT_CHOICES`.
- `heatmap.rows`: The heat map row count, one of `TABLE_ROW_COUNT_CHOICES`.
- `heatmap.scale`: The heat map scale, `<curve>/<scope>`, shown if offered.
- `heatmap.sort`: The heat map sort order, `heat` or `name`.
- `log.display_length`: The load log line count the settings view shows.
- `perf2html.version`: The `STORAGE_VERSION` the other keys were written under.
- `speedscope-color-scheme`: Speedscope's scheme, plain text `DARK` or `LIGHT`.
- `view.calls_column`: Whether the calls columns are shown, `true` or `false`.
- `view.counter_columns`: The counter columns shown, never the ranking counter.
- `view.dark_mode`: The dark mode chosen, `enabled` or `disabled`.
- `view.scale`: The design scale multiple chosen, shown at the nearest stop.

## Report Contents

Reading a report requires opening `index.html`. The rest of the report is of no
interest to users, except perhaps automated processing of `MANIFEST.txt`.

Otherwise, if you are an interested developer, these are the rest of the files
in the directory. A diff report lacks the `flame-graph/`, `flame-graph-app/`
and raw data archive files.

- `scripts/*.js`: Files copied whole or modified, from the scripts/ dir.
- `callers/<test>.html`: A test's callers page holding its JSON callers model.
- `flame-graph-app/SourceCodePro-Regular.ttf-*.woff2`: The speedscope font.
- `flame-graph-app/speedscope-*.css`: The speedscope app's stylesheet.
- `flame-graph-app/speedscope-*.js`: The speedscope app.
- `flame-graph/index.html`: The flame graph page loading the speedscope app.
- `flame-graph/profiles/<test>.js`: A test's speedscope profile, no `all`.
- `heat-map/data/<test>.js`: A test's heat map model.
- `heat-map/index.html`: The one heat map page for every test.
- `index.html`: The overview, the top page with the menu, home panel and frame.
- `MANIFEST.txt`: The version line, then the `LABEL=VALUE` rows, written last.
- `README.md`: A copy of the user contract.
- `settings/index.html`: The settings view page.
- `sources/<path>.js`: A source file's text, the path's non-alphanumerics `_`.
- `timer-artifacts-c.txz`: The raw data archive, recorded at `<time_t>`.

## Raw Data Archive Contents

- `0_file_data.<time_t>.json`: Source directory file listing with mode flags.
- `<test>.callgrind.<time_t>.out`: A test's callgrind file, the repo root cut.

In `0_file_data.<time_t>.json` each filename is associated with the following:

- `repo` : A project file with source.
- `git` : A non-contributing project file with no source.
- `sys` : A system file with source.
- `err` : A file that `callgrind` could not find or was deleted.

## Callers Page

| File           | Purpose                                              |
| -------------- | ---------------------------------------------------- |
| `callers.html` | Templates the callers page of one test, holding the  |
|                | JSON callers model that `callers.js` draws.          |
| `callers.js`   | Draws the callers heading and function table, then   |
|                | activates the page as a view that scrolls to the top |
|                | when the address is followed again.                  |

## Callgrind Parsing

| File                   | Purpose                                            |
| ---------------------- | -------------------------------------------------- |
| `callgrind.py`         | Parses callgrind files into the one profile model  |
|                        | with costs, derived counters and display paths.    |
| `callgrind_diff.py`    | Subtracts the baseline profile from the modified   |
|                        | profile and writes the delta and the callers JSON. |
| `callgrind_symbols.py` | Names the functions that callgrind left as         |
|                        | addresses in one recording.                        |

## Error Overlay

| File               | Purpose                                               |
| ------------------ | ----------------------------------------------------- |
| `debug.js`         | Templates the report's debug script, the manifest     |
|                    | table the error report shows, then the debug tip.     |
| `error_overlay.js` | Catches the first error a page throws, relays it up   |
|                    | the frames and replaces the top page with a plain     |
|                    | error report.                                         |
| `utility.js`       | Reports a failed load of a link, script or image, and |
|                    | keeps the log.                                        |

## Flame Graph

| File                     | Purpose                                         |
| ------------------------ | ----------------------------------------------- |
| `build_flame_graph.py`   | Writes the flame graph page and one base64      |
|                          | profile script per test for the speedscope app. |
| `flame_graph.html`       | Templates the flame graph page that loads the   |
|                          | speedscope app and the report scripts.          |
| `flame_graph.js`         | Waits for speedscope to start, then opens the   |
|                          | profile of the addressed test.                  |
| `trace_to_speedscope.py` | Converts a function trace log into a speedscope |
|                          | profile of the busiest run.                     |

## Heat Map

| File                      | Purpose                                      |
| ------------------------- | -------------------------------------------- |
| `callgrind_to_heatmap.py` | Writes the heat map data and sources of each |
|                           | test, the paths document a diff derives and  |
|                           | the one heat map page.                       |
| `heat_map.css`            | Styles the heat map tree, source table,      |
|                           | information box, ticker tape and minimap.    |
| `heat_map.html`           | Templates the heat map page with its tree    |
|                           | pane, main box, minimap and text bars.       |
| `heat_map.js`             | Draws the heat map tree, home table, source  |
|                           | view and info boxes for every test.          |
| `heat_map_main.html`      | Templates the heat map home, a heading over  |
|                           | the table of the kind its pulldown picks.    |

## Menu Strip

| File             | Purpose                                                 |
| ---------------- | ------------------------------------------------------- |
| `menu.js`        | Holds the menu controller, which draws the strip, takes |
|                  | keys and starts every navigation.                       |
| `preferences.js` | Holds the preferences the menu edits and a view draws   |
|                  | with, their choices and their counter labels.           |

## Overview Page

| File              | Purpose                                                |
| ----------------- | ------------------------------------------------------ |
| `build_report.py` | Writes the overview page with its menu and the callers |
|                   | page of each test.                                     |
| `frame.js`        | Holds the model of the top page, which checks the      |
|                   | address and loads each view into the frame.            |
| `overview.html`   | Templates the top page with the menu, the home panel   |
|                   | and the view frame.                                    |
| `overview.js`     | Fills the home panel's headings and raw data link,     |
|                   | then draws its tables from the rows the page holds.    |

## Settings Files

| File                 | Purpose                                              |
| -------------------- | ---------------------------------------------------- |
| `settings.js`        | Templates the settings every page reads, the top     |
|                      | page installing them, a framed page taking them      |
|                      | relayed, then writes every root value a stylesheet   |
|                      | reads.                                               |
| `settings.py`        | Holds every PY and JS setting with the reader and    |
|                      | writer that load and ship them.                      |
| `settings.sh`        | Holds every shell setting, read by the shell scripts |
|                      | and by `settings.py`.                                |
| `settings_page.html` | Templates the settings view                          |
| `settings_page.js`   | Draws every setting in an editable JSON box.         |
| `ui_strings.js`      | Holds every user interface string, looked up by      |
|                      | name.                                                |

## Test Harness

| File                        | Purpose                                      |
| --------------------------- | -------------------------------------------- |
| `test_all.sh`               | Runs `test_expected_behavior.sh` with kept   |
|                             | artifacts, then `test_error_handling.sh`.    |
| `test_error_handling.sh`    | Proves the cached and regenerated runs, then |
|                             | checks the exit code of each failure mode.   |
| `test_expected_behavior.sh` | Formats, lints and scans the sources, runs   |
|                             | the batch, then checks the reports and takes |
|                             | screenshots.                                 |
| `test_report.py`            | Checks the pages, manifest, checksum, heat   |
|                             | map, flame graph and timer artifacts of one  |
|                             | report.                                      |
| `test_screenshot.py`        | Shoots the golden bookmarks of one report in |
|                             | Chrome and writes `test_index.html`.         |
| `test_source_scan.py`       | Faults long comment blocks, comment          |
|                             | punctuation, glyphs and escapes in the given |
|                             | sources.                                     |
| `test_template.html`        | Templates the index of report links over a   |
|                             | grid of framed report pages that             |
|                             | `test_screenshot.py` fills in.               |
| `test_utility.sh`           | Holds the functions shared by the test       |
|                             | scripts.                                     |
| `test_whitelist.txt`        | Lists the file globs that the format, lint   |
|                             | and scan stages touch.                       |

## Theme Library

| File             | Purpose                                                |
| ---------------- | ------------------------------------------------------ |
| `dark_mode.css`  | Overrides every light mode color rule with a dark mode |
|                  | role unless dark mode is disabled.                     |
| `light_mode.css` | Holds every light mode color rule, linked before the   |
|                  | dark mode sheet.                                       |
| `theme.css`      | Lays out every page as a grid of its regions, then     |
|                  | styles the strips, tables and text scrollbars.         |
| `theme.js`       | Holds the shared page library for addresses, strips,   |
|                  | tables, numbers, scrollbars and layout.                |
| `theme.py`       | Writes table rows and numbers, fills the page          |
|                  | templates, and writes the shared scripts.              |

## Tool Configuration

| File                 | Purpose                                           |
| -------------------- | ------------------------------------------------- |
| `.prettierrc.json`   | Sets the prettier line width, prose wrap and line |
|                      | endings for the formatting checks.                |
| `pyrightconfig.json` | Configures the pyright type check of the Python   |
|                      | scripts.                                          |
| `ruff.toml`          | Configures the ruff formatter and linter for the  |
|                      | Python scripts.                                   |
| `utility.sh`         | Holds every function shared by the shipping shell |
|                      | scripts.                                          |
