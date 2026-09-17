#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from typing import NamedTuple, NotRequired, TypedDict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import callgrind as cg
from callgrind import Vec

MAX_STACK_DEPTH = 200


class Frame(TypedDict):
    name: str
    file: NotRequired[str]


class Shared(TypedDict):
    frames: list[Frame]


class SampledProfile(TypedDict):
    type: str
    name: str
    unit: str
    startValue: int
    endValue: float
    samples: list[list[int]]
    weights: list[float]


SpeedscopeDoc = TypedDict("SpeedscopeDoc", {
    "$schema": str, "shared": Shared, "profiles": list[SampledProfile], "name": str, "exporter": str})


class BuiltProfile(NamedTuple):
    profile: SampledProfile
    total: float


class SpeedscopeArgs(NamedTuple):
    callgrind_file: list[str]
    output: str
    event: list[str] | None
    name: str | None
    repo_root: str


def path_display(repo_root: str, path: str) -> str:
    if not path or path == "???":
        return path
    root = os.path.abspath(repo_root).rstrip("/") + "/"
    norm = os.path.normpath(path) if os.path.isabs(path) else path
    return norm[len(root):] if norm.startswith(root) else norm


class _Work(NamedTuple):
    v: int
    it: Iterator[int]


@dataclass
class Graph:
    nev: int
    names: list[str]
    files: list[str]
    index: dict[str, int]
    self_cost: dict[int, Vec]
    edges: defaultdict[int, dict[int, Vec]]
    cycles: list[str] = field(default_factory=list)

    def collapse_cycles(self) -> list[str]:
        n = len(self.names)
        index, low, on = [-1] * n, [0] * n, [False] * n
        stack: list[int] = []
        comps: list[list[int]] = []
        counter = 0
        for v0 in range(n):
            if index[v0] != -1:
                continue
            index[v0] = low[v0] = counter
            counter += 1
            stack.append(v0)
            on[v0] = True
            work = [_Work(v0, iter(self.edges.get(v0, {})))]
            while work:
                v, it = work[-1]
                pushed = False
                for w in it:
                    if index[w] == -1:
                        index[w] = low[w] = counter
                        counter += 1
                        stack.append(w)
                        on[w] = True
                        work.append(_Work(w, iter(self.edges.get(w, {}))))
                        pushed = True
                        break
                    if on[w]:
                        low[v] = min(low[v], index[w])
                if pushed:
                    continue
                work.pop()
                if work:
                    low[work[-1].v] = min(low[work[-1].v], low[v])
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
        self_cost: dict[int, Vec] = {}
        for i, vec in self.self_cost.items():
            cg.vec_acc(self_cost, new[rep[i]], vec)
        edges: defaultdict[int, dict[int, Vec]] = defaultdict(dict)
        for a, out in self.edges.items():
            for b, vec in out.items():
                if rep[a] != rep[b]:
                    cg.vec_acc(edges[new[rep[a]]], new[rep[b]], vec)
        self.self_cost, self.edges = self_cost, edges
        return list(merged.values())

    def roots(self) -> list[int]:
        callees = {c for out in self.edges.values() for c in out}
        roots = [i for i in range(len(self.names)) if i not in callees]
        return roots or list(range(len(self.names)))


def graph_from_profile(p: cg.Profile, repo_root: str = ".") -> Graph:
    names = set(p.fn_self) | set(p.fn_calls) | set(p.callers) | set(p.fn_home)
    for sites in p.callers.values():
        for caller in sites:
            names.add(caller.fn)
    sorted_names = sorted(names)
    index = {n: i for i, n in enumerate(sorted_names)}
    g = Graph(nev=len(p.events), names=sorted_names,
              files=[path_display(repo_root, p.fn_home.get(n, "")) for n in sorted_names], index=index,
              self_cost={index[n]: list(vec) for n, vec in p.fn_self.items()}, edges=defaultdict(dict))
    for callee, sites in p.callers.items():
        for caller, cc in sites.items():
            if caller.fn != callee:
                cg.vec_acc(g.edges[index[caller.fn]], index[callee], cc.cost)
    g.cycles = g.collapse_cycles()
    return g


def expr_resolve(p: cg.Profile, expr: str) -> list[int] | None:
    idxs: list[int] = []
    for name in (t.strip() for t in expr.split("+")):
        if name not in p.events:
            return None
        idxs.append(p.events.index(name))
    return idxs


def expr_label(p: cg.Profile, expr: str) -> str:
    names = [t.strip() for t in expr.split("+")]
    long = ""
    if len(names) == 1:
        long = p.event_long.get(names[0], "")
    else:
        for d in cg.DERIVED_DEFAULTS:
            if all(t.coef == 1 for t in d.terms) and sorted(t.raw for t in d.terms) == sorted(names):
                long = d.long
                break
        long = long or " + ".join(p.event_long.get(n) or n for n in names)
    return f"{expr} — {long}" if long else expr


def graph_build_profile(g: Graph, idxs: Sequence[int], name: str) -> BuiltProfile:

    def value(vec: Vec) -> int:
        return sum(vec[i] for i in idxs if i < len(vec))

    def self_of(frame: int) -> int:
        vec = g.self_cost.get(frame)
        return value(vec) if vec else 0

    incoming: defaultdict[int, float] = defaultdict(float)
    for out in g.edges.values():
        for callee, vec in out.items():
            incoming[callee] += value(vec)

    samples: list[list[int]] = []
    weights: list[float] = []

    def walk(frame: int, stack: list[int], visiting: frozenset[int], scale: float) -> None:
        if len(stack) >= MAX_STACK_DEPTH or frame in visiting:
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
    return BuiltProfile({"type": "sampled", "name": name, "unit": "none", "startValue": 0, "endValue": total,
                         "samples": samples, "weights": weights}, total)


def document_build(p: cg.Profile, exprs: Sequence[str], base_name: str, repo_root: str = ".") -> SpeedscopeDoc:
    g = graph_from_profile(p, repo_root)
    if g.cycles:
        print(f"collapsed {len(g.cycles)} cycle(s) into one frame each: {'; '.join(g.cycles)}", file=sys.stderr)
    frames: list[Frame] = []
    for n, f in zip(g.names, g.files):
        frame: Frame = {"name": n}
        if f and f != "???":
            frame["file"] = f
        frames.append(frame)
    profiles: list[SampledProfile] = []
    for expr in exprs:
        idxs = expr_resolve(p, expr)
        if idxs is None:
            print(f"skipping --event {expr!r}: not all of its events are in this file "
                  f"(events: {' '.join(p.events)})", file=sys.stderr)
            continue
        raw_total = sum(sum(v[i] for i in idxs if i < len(v)) for v in g.self_cost.values())
        if raw_total <= 0:
            print(f"skipping --event {expr!r}: total is zero", file=sys.stderr)
            continue
        label = expr_label(p, expr)
        built = graph_build_profile(g, idxs, label)
        print(f"{label}: {len(built.profile['samples'])} stack samples; raw self total {raw_total:,}, "
              f"emitted {built.total:,.0f}, ratio {built.total / raw_total:.4f} (must be ~1.0)", file=sys.stderr)
        profiles.append(built.profile)
    if not profiles:
        sys.exit("error: none of the requested --event expressions is usable")
    return {"$schema": "https://www.speedscope.app/file-format-schema.json",
            "shared": {"frames": frames}, "profiles": profiles, "name": base_name,
            "exporter": "callgrind_to_speedscope.py (curl dev/scripts)"}


def speedscope_main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("callgrind_file", nargs="+", help="callgrind output file(s); several are merged into one profile")
    ap.add_argument("-o", "--output", required=True, help="output .speedscope.json path")
    ap.add_argument("--event", action="append", default=None, metavar="EXPR",
                    help="event to weight by; repeatable, each becomes one profile; 'A+B' sums "
                         "events, e.g. D1mr+D1mw (default: Ir)")
    ap.add_argument("--name", default=None, help="document name (default: input file basename)")
    ap.add_argument("--repo-root", default=".", help="repository root the profile's paths are relative to")
    ns = ap.parse_args()
    args = SpeedscopeArgs(callgrind_file=ns.callgrind_file, output=ns.output, event=ns.event, name=ns.name,
                          repo_root=ns.repo_root)

    p = cg.profile_load(args.callgrind_file)
    if not p.events:
        sys.exit("error: no 'events:' line -- not a callgrind file?")
    check = cg.profile_self_check(p)
    print(f"events: {' '.join(p.events)}; ratio (must be 1.0000): {check.ratio:.4f}", file=sys.stderr)
    if check.total and abs(check.ratio - 1.0) > 1e-6:
        sys.exit("error: per-line self cost does not add up to callgrind's summary")

    doc = document_build(p, args.event or ["Ir"], args.name or os.path.basename(args.callgrind_file[0]), args.repo_root)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(doc, f)
    print(f"wrote {args.output} ({len(doc['shared']['frames'])} frames)", file=sys.stderr)


if __name__ == "__main__":
    speedscope_main()
