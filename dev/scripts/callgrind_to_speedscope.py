#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import defaultdict
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
import json
import os
import sys
from typing import NamedTuple, NotRequired, TypedDict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import callgrind
from callgrind import Costs

EVENTS = ("Ir", "D1mr+D1mw", "DLmr+DLmw", "I1mr", "Bcm", "Bim")
MAX_STACK_DEPTH = 200


class BuiltProfile(NamedTuple):
    profile: SampledProfile
    total: float


class Frame(TypedDict):
    name: str
    file: NotRequired[str]


@dataclass
class Graph:
    event_count: int
    names: list[str]
    files: list[str]
    index: dict[str, int]
    self_cost: dict[int, Costs]
    edges: defaultdict[int, dict[int, Costs]]
    cycles: list[str] = field(default_factory=list)

    def collapse_cycles(self) -> list[str]:
        node_count = len(self.names)
        discovery, low_link, on_stack = [-1] * node_count, [0] * node_count, [False] * node_count
        stack: list[int] = []
        components: list[list[int]] = []
        counter = 0
        for root in range(node_count):
            if discovery[root] != -1:
                continue
            discovery[root] = low_link[root] = counter
            counter += 1
            stack.append(root)
            on_stack[root] = True
            work = [_WalkFrame(root, iter(self.edges.get(root, {})))]
            while work:
                node, neighbors = work[-1]
                pushed = False
                for neighbor in neighbors:
                    if discovery[neighbor] == -1:
                        discovery[neighbor] = low_link[neighbor] = counter
                        counter += 1
                        stack.append(neighbor)
                        on_stack[neighbor] = True
                        work.append(_WalkFrame(neighbor, iter(self.edges.get(neighbor, {}))))
                        pushed = True
                        break
                    if on_stack[neighbor]:
                        low_link[node] = min(low_link[node], discovery[neighbor])
                if pushed:
                    continue
                work.pop()
                if work:
                    low_link[work[-1].node] = min(low_link[work[-1].node], low_link[node])
                if low_link[node] == discovery[node]:
                    component: list[int] = []
                    while True:
                        popped = stack.pop()
                        on_stack[popped] = False
                        component.append(popped)
                        if popped == node:
                            break
                    components.append(component)
        representative = list(range(node_count))
        merged: dict[int, str] = {}
        for component in components:
            if len(component) < 2:
                continue
            component.sort(key=lambda i: -(self.self_cost[i][0] if i in self.self_cost and self.self_cost[i] else 0))
            for i in component:
                representative[i] = component[0]
            members = [self.names[i] for i in component]
            merged[component[0]] = " + ".join(members[:3]) \
                + (f" + {len(members) - 3} more" if len(members) > 3 else "")
        if not merged:
            return []
        keep = sorted(set(representative))
        renumber = {old: new for new, old in enumerate(keep)}
        self.names = [merged.get(i, self.names[i]) for i in keep]
        self.files = [self.files[i] for i in keep]
        self.index = {name: i for i, name in enumerate(self.names)}
        self_cost: dict[int, Costs] = {}
        for i, costs in self.self_cost.items():
            callgrind.costs_accumulate(self_cost, renumber[representative[i]], costs)
        edges: defaultdict[int, dict[int, Costs]] = defaultdict(dict)
        for source, targets in self.edges.items():
            for target, costs in targets.items():
                if representative[source] != representative[target]:
                    callgrind.costs_accumulate(edges[renumber[representative[source]]],
                                               renumber[representative[target]], costs)
        self.self_cost, self.edges = self_cost, edges
        return list(merged.values())

    def roots(self) -> list[int]:
        callees = {callee for targets in self.edges.values() for callee in targets}
        roots = [i for i in range(len(self.names)) if i not in callees]
        return roots or list(range(len(self.names)))


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


class SpeedscopeArgs(NamedTuple):
    callgrind_file: list[str]
    output: str
    name: str | None


SpeedscopeDoc = TypedDict("SpeedscopeDoc", {
    "$schema": str, "shared": Shared, "profiles": list[SampledProfile], "name": str, "exporter": str})


class _WalkFrame(NamedTuple):
    node: int
    neighbors: Iterator[int]


def document_build(profile: callgrind.Profile, name: str) -> SpeedscopeDoc:
    graph = graph_from_profile(profile)
    if graph.cycles:
        print(f"collapsed {len(graph.cycles)} cycle(s) into one frame each: {'; '.join(graph.cycles)}", file=sys.stderr)
    frames: list[Frame] = []
    for frame_name, file in zip(graph.names, graph.files):
        frame: Frame = {"name": frame_name}
        if file:
            frame["file"] = file
        frames.append(frame)
    profiles: list[SampledProfile] = []
    for expr in EVENTS:
        indexes = expr_resolve(profile, expr)
        if indexes is None:
            print(f"skipping {expr!r}: not all of its events are in this file "
                  f"(events: {' '.join(profile.events)})", file=sys.stderr)
            continue
        raw_total = sum(sum(costs[i] for i in indexes if i < len(costs)) for costs in graph.self_cost.values())
        if raw_total <= 0:
            print(f"skipping {expr!r}: total is zero", file=sys.stderr)
            continue
        label = expr_label(profile, expr)
        built = graph_build_profile(graph, indexes, label)
        print(f"{label}: {len(built.profile['samples'])} stack samples; raw self total {raw_total:,}, "
              f"emitted {built.total:,.0f}, ratio {built.total / raw_total:.4f} (must be ~1.0)", file=sys.stderr)
        profiles.append(built.profile)
    if not profiles:
        sys.exit("error: none of the event expressions is usable")
    return {"$schema": "https://www.speedscope.app/file-format-schema.json",
            "shared": {"frames": frames}, "profiles": profiles, "name": name,
            "exporter": "callgrind_to_speedscope.py (curl dev/scripts)"}


def expr_label(profile: callgrind.Profile, expr: str) -> str:
    names = [term.strip() for term in expr.split("+")]
    long = ""
    if len(names) == 1:
        long = profile.event_long.get(names[0], "")
    else:
        for derived_event in callgrind.DERIVED_DEFAULTS:
            if all(term.coefficient == 1 for term in derived_event.terms) \
                    and sorted(term.event_name for term in derived_event.terms) == sorted(names):
                long = derived_event.long
                break
        long = long or " + ".join(profile.event_long.get(name) or name for name in names)
    return f"{expr} — {long}" if long else expr


def expr_resolve(profile: callgrind.Profile, expr: str) -> list[int] | None:
    indexes: list[int] = []
    for name in (term.strip() for term in expr.split("+")):
        if name not in profile.events:
            return None
        indexes.append(profile.events.index(name))
    return indexes


def frame_file(home: str) -> str:
    return callgrind.path_norm(home).display if home and home != "???" else ""


def graph_build_profile(graph: Graph, indexes: Sequence[int], name: str) -> BuiltProfile:

    def value(costs: Costs) -> int:
        return sum(costs[i] for i in indexes if i < len(costs))

    def self_of(node: int) -> int:
        costs = graph.self_cost.get(node)
        return value(costs) if costs else 0

    incoming: defaultdict[int, float] = defaultdict(float)
    for targets in graph.edges.values():
        for callee, costs in targets.items():
            incoming[callee] += value(costs)

    samples: list[list[int]] = []
    weights: list[float] = []

    def walk(node: int, stack: list[int], visiting: frozenset[int], scale: float) -> None:
        if len(stack) >= MAX_STACK_DEPTH or node in visiting:
            scaled = self_of(node) * scale
            if scaled > 0:
                samples.append(list(stack))
                weights.append(scaled)
            return
        here = stack + [node]
        scaled = self_of(node) * scale
        if scaled > 0:
            samples.append(here)
            weights.append(scaled)
        targets = graph.edges.get(node)
        if not targets:
            return
        visiting = visiting | {node}
        for callee, costs in targets.items():
            edge_cost = value(costs)
            total_in = incoming.get(callee, 0)
            if edge_cost > 0 and total_in > 0:
                walk(callee, here, visiting, scale * edge_cost / total_in)

    for root in graph.roots():
        walk(root, [], frozenset(), 1.0)
    total = sum(weights)
    return BuiltProfile({"type": "sampled", "name": name, "unit": "none", "startValue": 0, "endValue": total,
                         "samples": samples, "weights": weights}, total)


def graph_from_profile(profile: callgrind.Profile) -> Graph:
    sorted_names = sorted(profile.function_home)
    index = {name: i for i, name in enumerate(sorted_names)}
    graph = Graph(event_count=len(profile.events), names=sorted_names,
                  files=[frame_file(profile.function_home[name]) for name in sorted_names],
                  index=index, self_cost={index[name]: list(costs) for name, costs in profile.function_self.items()},
                  edges=defaultdict(dict))
    for callee, sites in profile.callers.items():
        for caller, tally in sites.items():
            if caller.function != callee:
                callgrind.costs_accumulate(graph.edges[index[caller.function]], index[callee], tally.costs)
    graph.cycles = graph.collapse_cycles()
    return graph


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("callgrind_file", nargs="+",
                        help="callgrind output file(s); several are merged into one profile")
    parser.add_argument("-o", "--output", required=True, help="output .speedscope.json path")
    parser.add_argument("--name", default=None, help="document name (default: the file's basename)")
    namespace = parser.parse_args()
    args = SpeedscopeArgs(callgrind_file=namespace.callgrind_file, output=namespace.output, name=namespace.name)

    profile = callgrind.profile_load(args.callgrind_file)
    doc = document_build(profile, args.name or os.path.basename(args.callgrind_file[0]))
    with open(args.output, "w", encoding="utf-8") as handle:
        json.dump(doc, handle)
    print(f"wrote {args.output} ({len(doc['shared']['frames'])} frames)", file=sys.stderr)


if __name__ == "__main__":
    main()
