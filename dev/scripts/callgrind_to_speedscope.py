#!/usr/bin/env python3
"""Convert a callgrind profile into speedscope's JSON file format
(https://www.speedscope.app/file-format-schema.json).

Callgrind's body is a *call graph* (functions with self cost, plus
caller->callee edges each carrying an inclusive cost), not a stack-trace
log. A function can have many distinct callers (malloc, memcpy, ...), so
there is no single "the" stack for its cost. To render it as a flame graph
we first collapse every cycle (mutual recursion, and the loops that appear
when callgrind.py merges same-named symbols) into one frame, then walk the
resulting DAG from its root(s) and, at each edge, hand the callee's cost to
that caller in proportion to the edge's share of the callee's incoming
inclusive cost -- the same idea as KCachegrind's cycle detection and callee
map. A depth limit remains as the guarantee of termination; cost cut off
there is folded into the current stack so nothing is silently dropped.

Parsing is callgrind.py's (shared with the heat map and the report);
its self-check ratio must be 1.0000 or nothing is written. A second ratio,
emitted weight / raw self cost, checks the walk and is printed per profile.

Usage:
  callgrind_to_speedscope.py callgrind.out.X -o out.speedscope.json
      [--event Ir] [--event D1mr+D1mw ...] [--name "..."]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import callgrind as cg  # noqa: E402

MAX_STACK_DEPTH = 200


class Graph:
    """Frames (one per function name) with self cost and summed caller->callee
    edges, lifted from a parsed Profile."""

    def __init__(self, p: cg.Profile) -> None:
        names = set(p.fn_self) | set(p.fn_calls) | set(p.callers) | set(p.fn_home)
        for sites in p.callers.values():
            for cfn, _, _ in sites:
                names.add(cfn)
        self.nev = len(p.events)
        self.names = sorted(names)
        self.index = {n: i for i, n in enumerate(self.names)}
        self.files = [p.fn_home.get(n, "") for n in self.names]
        self.self_cost = {self.index[n]: list(vec) for n, vec in p.fn_self.items()}
        # caller index -> {callee index: summed inclusive cost over all call sites}
        self.edges: dict[int, dict[int, list[int]]] = defaultdict(dict)
        for callee, sites in p.callers.items():
            for (cfn, _, _), (_, vec) in sites.items():
                if cfn != callee:  # direct recursion: the self cost already covers every level
                    self._add(self.edges[self.index[cfn]], self.index[callee], vec)
        self.cycles = self._collapse_cycles()

    def _add(self, table: dict[int, list[int]], key: int, vec: list[int]) -> None:
        acc = table.setdefault(key, [0] * self.nev)
        for k, v in enumerate(vec):
            acc[k] += v

    def _collapse_cycles(self) -> list[str]:
        """Merge every strongly connected component into one frame, so the
        graph is a DAG and each callee's incoming edges are exactly the
        calls into it from outside.

        A cycle's back edge carries inclusive cost that is already inside
        the edge that entered the cycle; counting it as a second caller
        would hand that share to a path the walk then cuts off as recursion.
        Cycles come from genuine mutual recursion and from callgrind.py's
        merging of same-named functions: `_start -> (below main) ->
        __libc_start_main -> (below main) -> main` is a loop once both
        `(below main)` symbols are one frame. Same approach as KCachegrind's
        cycle detection. Returns the merged frames' names."""
        n = len(self.names)
        index, low, on = [-1] * n, [0] * n, [False] * n
        stack: list[int] = []
        comps: list[list[int]] = []
        counter = 0
        for v0 in range(n):  # Tarjan, iterative
            if index[v0] != -1:
                continue
            index[v0] = low[v0] = counter
            counter += 1
            stack.append(v0)
            on[v0] = True
            work = [(v0, iter(self.edges.get(v0, {})))]
            while work:
                v, it = work[-1]
                pushed = False
                for w in it:
                    if index[w] == -1:
                        index[w] = low[w] = counter
                        counter += 1
                        stack.append(w)
                        on[w] = True
                        work.append((w, iter(self.edges.get(w, {}))))
                        pushed = True
                        break
                    if on[w]:
                        low[v] = min(low[v], index[w])
                if pushed:
                    continue
                work.pop()
                if work:
                    low[work[-1][0]] = min(low[work[-1][0]], low[v])
                if low[v] == index[v]:
                    comp: list[int] = []
                    while True:
                        w = stack.pop()
                        on[w] = False
                        comp.append(w)
                        if w == v:
                            break
                    comps.append(comp)
        rep = list(range(n))
        merged: dict[int, str] = {}
        for comp in comps:
            if len(comp) < 2:
                continue
            comp.sort(key=lambda i: -(self.self_cost[i][0] if i in self.self_cost and self.self_cost[i] else 0))
            for i in comp:
                rep[i] = comp[0]
            members = [self.names[i] for i in comp]
            merged[comp[0]] = " + ".join(members[:3]) + (f" + {len(members) - 3} more" if len(members) > 3 else "")
        if not merged:
            return []
        keep = sorted(set(rep))
        new = {old: k for k, old in enumerate(keep)}
        self.names = [merged.get(i, self.names[i]) for i in keep]
        self.files = [self.files[i] for i in keep]
        self.index = {n: i for i, n in enumerate(self.names)}
        self_cost: dict[int, list[int]] = {}
        for i, vec in self.self_cost.items():
            self._add(self_cost, new[rep[i]], vec)
        edges: dict[int, dict[int, list[int]]] = defaultdict(dict)
        for a, out in self.edges.items():
            for b, vec in out.items():
                if rep[a] != rep[b]:
                    self._add(edges[new[rep[a]]], new[rep[b]], vec)
        self.self_cost, self.edges = self_cost, edges
        return list(merged.values())

    def roots(self) -> list[int]:
        """Frames that are never a callee; every frame if there are none."""
        callees = {c for out in self.edges.values() for c in out}
        roots = [i for i in range(len(self.names)) if i not in callees]
        return roots or list(range(len(self.names)))


def resolve_expr(p: cg.Profile, expr: str) -> list[int] | None:
    """'D1mr+D1mw' -> the raw event columns it sums; None if one is missing."""
    idxs = []
    for name in (t.strip() for t in expr.split("+")):
        if name not in p.events:
            return None
        idxs.append(p.events.index(name))
    return idxs


def expr_label(p: cg.Profile, expr: str) -> str:
    """'D1mr+D1mw — L1 data cache misses (D1mr + D1mw)'."""
    names = [t.strip() for t in expr.split("+")]
    long = ""
    if len(names) == 1:
        long = p.event_long.get(names[0], "")
    else:
        for _, terms, dlong in cg.DERIVED_DEFAULTS:
            if all(c == 1 for c, _ in terms) and sorted(r for _, r in terms) == sorted(names):
                long = dlong
                break
        long = long or " + ".join(p.event_long.get(n) or n for n in names)
    return f"{expr} — {long}" if long else expr


def build_profile(g: Graph, idxs: list[int], name: str) -> tuple[dict, float]:
    """One speedscope 'sampled' profile weighted by the sum of the given
    event columns. Returns (profile, sum of emitted weights)."""

    def value(vec: list[int]) -> int:
        return sum(vec[i] for i in idxs if i < len(vec))

    def self_of(frame: int) -> int:
        vec = g.self_cost.get(frame)
        return value(vec) if vec else 0

    incoming: dict[int, float] = defaultdict(float)
    for out in g.edges.values():
        for callee, vec in out.items():
            incoming[callee] += value(vec)

    samples: list[list[int]] = []
    weights: list[float] = []

    def walk(frame: int, stack: list[int], visiting: frozenset[int], scale: float) -> None:
        if len(stack) >= MAX_STACK_DEPTH or frame in visiting:
            # cannot happen on the collapsed DAG; kept as the guarantee of
            # termination, folding the cost into the current stack
            sc = self_of(frame) * scale
            if sc > 0:
                samples.append(list(stack))
                weights.append(sc)
            return
        here = stack + [frame]
        sc = self_of(frame) * scale
        if sc > 0:
            samples.append(here)
            weights.append(sc)
        out = g.edges.get(frame)
        if not out:
            return
        visiting = visiting | {frame}
        for callee, vec in out.items():
            ec = value(vec)
            total_in = incoming.get(callee, 0)
            if ec > 0 and total_in > 0:
                walk(callee, here, visiting, scale * ec / total_in)

    for r in g.roots():
        walk(r, [], frozenset(), 1.0)
    total = sum(weights)
    return {"type": "sampled", "name": name, "unit": "none", "startValue": 0, "endValue": total,
            "samples": samples, "weights": weights}, total


def build_document(p: cg.Profile, exprs: list[str], base_name: str) -> dict:
    """One speedscope document with one profile per event expression
    (speedscope shows a picker when there is more than one). Expressions
    whose events are absent, or whose total is zero, are skipped."""
    g = Graph(p)
    if g.cycles:
        print(f"collapsed {len(g.cycles)} cycle(s) into one frame each: {'; '.join(g.cycles)}", file=sys.stderr)
    frames = [{"name": n, **({"file": f} if f and f != "???" else {})} for n, f in zip(g.names, g.files)]
    profiles = []
    for expr in exprs:
        idxs = resolve_expr(p, expr)
        if idxs is None:
            print(f"skipping --event {expr!r}: not all of its events are in this file "
                  f"(events: {' '.join(p.events)})", file=sys.stderr)
            continue
        raw_total = sum(sum(v[i] for i in idxs if i < len(v)) for v in g.self_cost.values())
        if raw_total <= 0:
            print(f"skipping --event {expr!r}: total is zero", file=sys.stderr)
            continue
        label = expr_label(p, expr)
        profile, total = build_profile(g, idxs, label)
        print(f"{label}: {len(profile['samples'])} stack samples; raw self total {raw_total:,}, "
              f"emitted {total:,.0f}, ratio {total / raw_total:.4f} (must be ~1.0)", file=sys.stderr)
        profiles.append(profile)
    if not profiles:
        sys.exit("error: none of the requested --event expressions is usable")
    return {"$schema": "https://www.speedscope.app/file-format-schema.json",
            "shared": {"frames": frames}, "profiles": profiles, "name": base_name,
            "exporter": "callgrind_to_speedscope.py (curl dev/scripts)"}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("callgrind_file", nargs="+", help="callgrind output file(s); several are merged into one profile")
    ap.add_argument("-o", "--output", required=True, help="output .speedscope.json path")
    ap.add_argument("--event", action="append", default=None, metavar="EXPR",
                    help="event to weight by; repeatable, each becomes one profile; 'A+B' sums "
                         "events, e.g. D1mr+D1mw (default: Ir)")
    ap.add_argument("--name", default=None, help="document name (default: input file basename)")
    args = ap.parse_args()

    p = cg.load(args.callgrind_file)
    if not p.events:
        sys.exit("error: no 'events:' line -- not a callgrind file?")
    self_sum, total, ratio = cg.self_check(p)
    print(f"events: {' '.join(p.events)}; ratio (must be 1.0000): {ratio:.4f}", file=sys.stderr)
    if total and abs(ratio - 1.0) > 1e-6:
        sys.exit("error: per-line self cost does not add up to callgrind's summary")

    doc = build_document(p, args.event or ["Ir"], args.name or os.path.basename(args.callgrind_file[0]))
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(doc, f)
    print(f"wrote {args.output} ({len(doc['shared']['frames'])} frames)", file=sys.stderr)


if __name__ == "__main__":
    main()
