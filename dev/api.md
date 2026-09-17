# dev/ internal API surfaces — removal checklist

`*` = tried to remove, could not (still invoked or imported); what is left of it
is noted. Unmarked = removed.

Scope: only surfaces one `dev/` script touches on another — shell → Python CLI
invocations, and Python → Python imports. Not a facilities catalog and not an
environment-variable reference (there are none left; the knobs are constants at
the top of each script). "Touched" = actually invoked by `lint.sh`,
`perf2html.sh`, `perf2html_diff.sh`, or by one `dev/scripts/*.py` importing
another.

## Shell driver → Python CLI

### `perf2html.sh` → `dev/scripts/*.py`

- \* `callgrind_to_speedscope.py CALLGRIND_FILES... -o JSON --event EVENT [--event EVENT ...] --name NAME`
  now `callgrind_to_speedscope.py FILE -o JSON`: one file; `--event` is the `EVENTS`
  constant (`Ir D1mr+D1mw DLmr+DLmw I1mr Bcm Bim`); `--name` is the file's basename.
- \* `build_flame_graph.py --speedscope-dir OUT/flame-graph --profile-json JSON`
  unchanged (`--profile-filename` and the `profile.speedscope.json` copy gone).
- \* `callgrind_to_heatmap.py CALLGRIND_FILES... -o OUT/heat-map/index.html --title "NAME / heat map"`
  now one FILE; `--event`/`--repo-root`/`--tree`/`--all-sources` gone
  (`DEFAULT_EVENT`/`TREE` constants, `callgrind.REPO_ROOT`).
- \* `build_report.py timing -o OUT/perf-tool/index.html --test NAME --output-file OUT/perf-tool/output.txt --meta LABEL=VALUE [...]`
  unchanged (`--meta` repeated: `binary=`, `pinned to=`, `build=`).
- \* `build_report.py test CALLGRIND_FILES... -o OUT/index.html --test NAME --top TOP [--log FILE ...] [--raw-data FILE ...] [--no-log] [--help-href ../README.md]`
  now `build_report.py test FILE -o OUT/index.html --test NAME --raw-data FILE --log FILE`;
  `--top` (constant 50), `--event` (constant Ir), `--no-log`, `--help-href`, `--repo-root` gone.
- `build_report.py overview -o OUTDIR/index.html --meta LABEL=VALUE [...] --test all --test NAME [--test NAME ...]`
  removed with the `all`/multi-test mode.
- \* `validate_report.py OUTDIR` — last step, always.

### `perf2html_diff.sh` → `dev/scripts/*.py`

- \* `callgrind_diff.py -o DIFF_FILE --repo-root REPO_ROOT --baseline FILE [--baseline FILE ...] --current FILE [--current FILE ...]`
  now `callgrind_diff.py BASELINE MODIFIED -o DIFF_FILE` (one file per side).
- \* `callgrind_to_heatmap.py DIFF_FILE -o OUT/heat-map/index.html --title "NAME / heat map" --diff`
  unchanged.
- \* `build_report.py test DIFF_FILE -o OUT/index.html --test NAME --top TOP --diff --event EVENT --raw-data OUT/raw/FILE --meta baseline=... --meta current=... [--help-href ../README.md]`
  now `--test NAME --diff --raw-data FILE --meta baseline=... --meta modified=...`.
- `build_report.py overview -o OUTDIR/index.html --diff --event EVENT --meta LABEL=VALUE [...] --test NAME [--test NAME ...]`
  removed.
- \* `validate_report.py OUTDIR` — now `validate_report.py OUTDIR --diff`.

### `lint.sh` → `dev/scripts/*.py`

- \* `check_js.py` — no args.
- \* `pyright --project dev` — the `npx` fallbacks are gone.

## Python → Python imports

`build_report.py`, `callgrind_to_heatmap.py`, `callgrind_to_speedscope.py`,
`callgrind_diff.py` and now `validate_report.py` import the shared parser
`callgrind`; `build_report.py` and `callgrind_to_heatmap.py` additionally import
`callgrind_diff` and `theme`. `check_js.py` imports `build_report` and
`callgrind_to_heatmap` by module name via `importlib`, reading one attribute off
each. Nothing else imports another `dev/scripts` module.

### `callgrind` (`callgrind.py`)

Functions:
- \* `profile_load(paths: Sequence[str]) -> Profile` — now `profile_load(path: str)`, one file;
  does the self-check itself and exits on a bad ratio.
- `profile_self_check(profile: Profile) -> SelfCheck` — folded into `profile_load`.
- \* `costs_add(dst: Costs, src: Costs) -> None`
- \* `costs_accumulate(table: dict[Key, Costs], key: Key, costs: Costs) -> None`
- \* (new) `REPO_ROOT`, `path_norm(path: str) -> PathInfo(display, local, group)`, `Group` —
  replaced every `--repo-root` flag and the private path helpers of three generators.

Types/constants:
- \* `Costs: TypeAlias = list[int]`
- \* `SourceLine(file: str, line: int)` — NamedTuple
- \* `Profile` — same fields/methods as before minus `descriptions`/`derived`
  (`desc:`/`event:` header lines are no longer parsed; callgrind never wrote an `event:` line).
- \* `ResolvedDerivedEvent`, `ResolvedTerm`
- \* `DERIVED_DEFAULTS: tuple[DerivedEvent, ...]`

### `callgrind_diff` (`callgrind_diff.py`) — consumed by `build_report`, `callgrind_to_heatmap`

Functions:
- \* `profile_magnitudes(profile: callgrind.Profile) -> Costs`
- `profile_baseline_total(profile: callgrind.Profile, event: str) -> int` — removed with the overview.

(`profile_diff`, `profile_write`, `costs_sub` are internal; `profile_read` is gone.)

### `theme` (`theme.py`) — consumed by `build_report`, `callgrind_to_heatmap`

Functions:
- \* `heat_style(heat: float, alpha: AlphaRange = ..., signed: bool = False) -> str` — now
  `heat_style(heat, signed=False)`; `alpha`/`AlphaRange` gone.
- \* `heat_t(share: float, max_share: float) -> float`
- \* `num_human(number: float) -> str`
- \* `num_pct(percent: float) -> str`
- \* `num_signed(number: float) -> str`
- \* `num_signed_pct(percent: float) -> str`
- \* `num_time(seconds: float) -> str`
- \* `html_escape(value: object) -> str`
- \* `page_document(title: str, body: str, extra_css: str = "", extra_js: str = "", body_class: str = "") -> str` — `extra_css` gone.
- \* `table_render(key: str, columns: Sequence[Column], rows: Sequence[Sequence[CellOrText]], fill: bool = False, header: bool = True, lines: bool = False) -> str` — `lines` gone (nothing styled it).
- \* `theme_css() -> str`
- \* `theme_js() -> str`
- \* `theme_runtime() -> ThemeRuntime`

Types imported directly (`from theme import ...`) by `build_report.py`:
- \* `Cell(text: str = "", html: str | None = None, style: str = "", cls: str = "", title: str = "")`
- \* `CellOrText: TypeAlias = Cell | str`
- \* `Column(label: str, title: str = "", numeric: bool = False, width: int | None = None, clip: int | None = None, cls: str = "", grow: bool = False)` — `cls` gone.
- \* `html_escape`
- \* `ThemeRuntime` (TypedDict: `heat: list[str]`, `bg: str`, `fgLight: str`, `fgDark: str`)

### `check_js.py` → `build_report`, `callgrind_to_heatmap`

- \* `build_report.FRAME_JS`
- \* `callgrind_to_heatmap.BODY`
