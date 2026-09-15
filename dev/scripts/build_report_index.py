#!/usr/bin/env python3
"""Write a bare-bones white-on-black monospace HTML page: a title, `label:
value` meta lines, links, and <pre> sections read from files or given
inline. Parts are emitted in the order the options appear on the command
line.

Usage:
  build_report_index.py -o index.html --title "curl perf profile: urlparser" \
      --meta "generated=2026-09-15 10:00" \
      --section "callgrind totals=trace/totals.txt" \
      --link "flame-graph/index.html=speedscope flame graph" \
      --link "heat-map/index.html=per-line source heat map" \
      --text "note=inline text" \
      --section "top 20 functions=trace/top20.txt"
"""
from __future__ import annotations

import argparse
import html
import os
import sys

STYLE = """\
body { background: #000; color: #fff; margin: 24px;
  font: 13px/1.4 ui-monospace, Menlo, Consolas, "Liberation Mono", monospace; }
a { color: #fff; }
a:hover { background: #fff; color: #000; text-decoration: none; }
h1, h2 { font-size: inherit; font-weight: normal; margin: 1.6em 0 .4em; }
h1 { margin-top: 0; }
h2::before { content: "== "; } h2::after { content: " =="; }
pre { margin: 0 0 .8em; white-space: pre; overflow-x: auto; }
"""


class Part(argparse.Action):
    def __call__(self, parser, ns, value, option_string=None):
        kind = option_string.lstrip("-")
        if "=" not in value:
            parser.error(f"{option_string} expects LABEL=VALUE, got {value!r}")
        label, _, val = value.partition("=")
        ns.parts.append((kind, label.strip(), val))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-o", "--output", required=True)
    ap.add_argument("--title", required=True)
    ap.add_argument("--meta", action=Part, dest="parts", metavar="LABEL=VALUE",
                    help="one `label: value` line; consecutive --meta options form one block")
    ap.add_argument("--link", action=Part, dest="parts", metavar="HREF=LABEL",
                    help="one link line; consecutive --link options form one block")
    ap.add_argument("--section", action=Part, dest="parts", metavar="HEADING=FILE",
                    help="heading plus the contents of FILE in a <pre>")
    ap.add_argument("--text", action=Part, dest="parts", metavar="HEADING=TEXT",
                    help="heading plus TEXT in a <pre>")
    ap.set_defaults(parts=[])
    args = ap.parse_args()

    body: list[str] = [f"<h1>{html.escape(args.title)}</h1>"]
    i = 0
    parts = args.parts
    while i < len(parts):
        kind = parts[i][0]
        if kind in ("meta", "link"):
            j = i
            while j < len(parts) and parts[j][0] == kind:
                j += 1
            block = parts[i:j]
            if kind == "meta":
                w = max(len(lbl) for _, lbl, _ in block)
                body.append("<pre>" + "\n".join(
                    f"{html.escape(lbl + ':'):<{w + 1}} {html.escape(val)}" for _, lbl, val in block) + "</pre>")
            else:
                w = max(len(href) for _, href, _ in block)
                body.append("<pre>" + "\n".join(
                    f'<a href="{html.escape(href, quote=True)}">{html.escape(href)}</a>{" " * (w - len(href))}  {html.escape(lbl)}'
                    for _, href, lbl in block) + "</pre>")
            i = j
            continue
        _, heading, val = parts[i]
        if kind == "section":
            try:
                with open(val, encoding="utf-8", errors="replace") as f:
                    text = f.read()
            except OSError as e:
                print(f"warning: {val}: {e}", file=sys.stderr)
                text = f"(missing: {val})"
        else:
            text = val
        body.append(f"<h2>{html.escape(heading)}</h2><pre>{html.escape(text.rstrip())}</pre>")
        i += 1

    page = ("<!doctype html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
            "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
            f"<title>{html.escape(args.title)}</title>\n<style>\n{STYLE}</style>\n</head>\n<body>\n"
            + "\n".join(body) + "\n</body>\n</html>\n")
    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(page)
    print(f"wrote {args.output} ({len(page.encode('utf-8')):,} bytes)", file=sys.stderr)


if __name__ == "__main__":
    main()
