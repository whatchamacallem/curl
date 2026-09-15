#!/usr/bin/env python3
"""
Convert a Callgrind profile data file (valgrind --tool=callgrind output) into
speedscope's native JSON file format (https://www.speedscope.app/file-format-schema.json).

Implements the format described in the Callgrind Format Specification
(/usr/share/doc/valgrind/html/cl-format.html on Debian/Ubuntu systems with
valgrind installed). Only single-part files with the default "line" position
type are supported, which is what `valgrind --tool=callgrind` produces for a
normal run.

Callgrind's body is a *call graph* (functions with self cost, plus
caller->callee edges each carrying an own inclusive cost), not a stack trace
log. A function can have many distinct callers (e.g. malloc, memcpy), so
there is no single "the" stack for its cost. To render this as a
speedscope-style flamegraph, we walk the graph from its root(s) and, at each
edge, distribute the callee's total self+descendant cost across its callers
in proportion to each edge's own inclusive-cost share -- this is the same
idea KCachegrind's "callee map" uses. Recursion (direct or mutual) is cut off
after a fixed depth to guarantee termination; the cut-off cost is folded into
the frame where recursion was detected so no cost is silently dropped.
"""
import argparse
import json
import os
import re
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import callgrind as cg  # noqa: E402  (event long names / derived-event labels only)

MAX_STACK_DEPTH = 200


class Frame:
    __slots__ = ("name", "file", "index")

    def __init__(self, name, file, index):
        self.name = name
        self.file = file
        self.index = index


class Parser:
    def __init__(self):
        # Function identity in Callgrind is scoped to its own "fn"/"cfn"
        # compressed ID namespace -- NOT to (file, name). The same function
        # can be reopened later in the file with just "fn=(ID)" while a
        # completely different "fl=" is currently active (e.g. after
        # visiting callees whose own source file changed cur_file), and
        # that reopened block must resolve back to the SAME Frame, not a
        # new one. So frames are keyed by (spec_namespace, compressed_id)
        # when an ID is present, falling back to (file, name) only for the
        # rare position spec with no compression id at all.
        self.frames_by_id = {}    # ("fn", compressed_id) -> Frame
        self.frames_by_name = {}  # (file, name) -> Frame, for uncompressed refs
        self.frame_list = []
        self.events = []
        self.event_index = {}
        self.event_long = {}      # from "event: Name : Long name" header lines
        self.self_cost = {}       # frame_index -> [cost,...] (own self cost only)
        # edges[caller_frame_index] -> list of (callee_frame_index, cost_vec)
        # cost_vec is the SUM of inclusive costs of all calls at this call
        # site (multiple call sites to the same callee within one caller are
        # merged, matching how callgrind_annotate treats them).
        self.edges = defaultdict(list)
        self.positions_has_instr = False
        self.positions_has_line = True

    def get_frame_by_id(self, fn_id, name, file):
        """fn_id is the compressed ID string shared by fn= and cfn= (both are
        the 'function name' position spec, sharing one ID namespace per the
        format's Name Compression rules). name may be None if this is a bare
        'fn=(ID)' back-reference with no new name given."""
        f = self.frames_by_id.get(fn_id)
        if f is None:
            f = Frame(name or "???", file, len(self.frame_list))
            self.frames_by_id[fn_id] = f
            self.frame_list.append(f)
        elif name and f.name == "???":
            f.name = name
        if file and (f.file is None or f.file == "???"):
            f.file = file
        return f

    def get_frame_by_name(self, file, name):
        key = (file, name)
        f = self.frames_by_name.get(key)
        if f is None:
            f = Frame(name, file, len(self.frame_list))
            self.frames_by_name[key] = f
            self.frame_list.append(f)
        return f

    def zero_costs(self):
        return [0] * len(self.events)

    def add_self_cost(self, frame_index, costs):
        cur = self.self_cost.get(frame_index)
        if cur is None:
            cur = self.zero_costs()
            self.self_cost[frame_index] = cur
        for i, c in enumerate(costs):
            if i < len(cur):
                cur[i] += c

    def add_edge(self, caller_index, callee_index, costs):
        for callee_i, vec in self.edges[caller_index]:
            if callee_i == callee_index:
                for i, c in enumerate(costs):
                    if i < len(vec):
                        vec[i] += c
                return
        self.edges[caller_index].append((callee_index, list(costs)))

    def parse(self, text):
        lines = text.split("\n")
        i = 0
        n = len(lines)

        # fn= and cfn= are both the "function name" position spec and share
        # one compressed-ID namespace (same for fl/fi/fe/cfi/cfl all being
        # "file name" specs), per the format's Name Compression section.
        id_tables = {
            "ob": {}, "fl": {}, "fi": {}, "fe": {},
            "fn": {}, "cob": {}, "cfi": {}, "cfl": {}, "cfn": {},
        }
        id_tables["cfn"] = id_tables["fn"]
        id_tables["cfi"] = id_tables["fl"]
        id_tables["cfl"] = id_tables["fl"]
        id_tables["fi"] = id_tables["fl"]
        id_tables["fe"] = id_tables["fl"]

        cur_file = None
        cur_fn_frame = None
        cur_call_file = None
        cur_call_fn = None
        cur_call_id = None

        last_subpos = {"line": 0, "instr": 0}

        def parse_subpos(tok, kind):
            if tok == "*":
                return last_subpos[kind]
            if tok[0] == "+":
                last_subpos[kind] += int(tok[1:], 0)
                return last_subpos[kind]
            if tok[0] == "-":
                last_subpos[kind] -= int(tok[1:], 0)
                return last_subpos[kind]
            val = int(tok, 0)
            last_subpos[kind] = val
            return val

        def resolve_name(spec, rest):
            """Returns (compressed_id_or_None, name)."""
            rest = rest.strip()
            table = id_tables[spec]
            m = re.match(r"^\((\d+)\)\s*(.*)$", rest)
            if m:
                cid, name = m.group(1), m.group(2).strip()
                if name:
                    table[cid] = name
                    return cid, name
                return cid, table.get(cid, "???")
            return None, (rest if rest else "???")

        def consume_cost_line(stripped, target_costs_adder):
            toks = stripped.split()
            if not toks:
                return
            npos = (1 if self.positions_has_instr else 0) + \
                   (1 if self.positions_has_line else 0)
            if npos == 0:
                npos = 1
            pos_toks = toks[:npos]
            cost_toks = toks[npos:]
            idx = 0
            if self.positions_has_instr and idx < len(pos_toks):
                parse_subpos(pos_toks[idx], "instr")
                idx += 1
            if self.positions_has_line and idx < len(pos_toks):
                parse_subpos(pos_toks[idx], "line")

            costs = self.zero_costs()
            for k, tok in enumerate(cost_toks):
                if k >= len(costs):
                    break
                try:
                    costs[k] = int(tok)
                except ValueError:
                    costs[k] = 0
            target_costs_adder(costs)

        while i < n:
            line = lines[i]
            i += 1
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue

            if ":" in stripped and not stripped[0].isdigit() and \
               not stripped.startswith(("+", "-", "*", "0x")):
                key, _, val = stripped.partition(":")
                key = key.strip()
                val = val.strip()
                if key == "events":
                    self.events = val.split()
                    self.event_index = {e: idx for idx, e in enumerate(self.events)}
                    continue
                if key == "positions":
                    parts = val.split()
                    self.positions_has_instr = "instr" in parts
                    self.positions_has_line = ("line" in parts) or (not parts)
                    continue
                if key == "event":
                    ename, _, elong = cg._parse_event_header(val)
                    if elong:
                        self.event_long[ename] = elong
                    continue
                if key in ("version", "creator", "pid", "thread", "part",
                           "cmd", "desc", "summary", "totals"):
                    continue

            m = re.match(r"^(ob|fl|fi|fe|fn|cob|cfi|cfl|cfn)=(.*)$", stripped)
            if m:
                spec, rest = m.group(1), m.group(2)
                cid, name = resolve_name(spec, rest)
                if spec == "fl":
                    cur_file = name
                elif spec in ("fi", "fe"):
                    cur_file = name
                elif spec == "fn":
                    if cid is not None:
                        cur_fn_frame = self.get_frame_by_id(cid, name, cur_file)
                    else:
                        cur_fn_frame = self.get_frame_by_name(cur_file, name)
                elif spec in ("cfi", "cfl"):
                    cur_call_file = name
                elif spec == "cfn":
                    cur_call_id = cid
                    cur_call_fn = name
                continue

            m = re.match(r"^calls=(\S+)\s+(.*)$", stripped)
            if m:
                callee_file = cur_call_file if cur_call_file is not None else cur_file
                if cur_call_id is not None:
                    callee_frame = self.get_frame_by_id(cur_call_id, cur_call_fn,
                                                         callee_file)
                else:
                    callee_frame = self.get_frame_by_name(callee_file, cur_call_fn)

                while i < n and not lines[i].strip():
                    i += 1
                if i < n:
                    nxt_stripped = lines[i].strip()
                    if nxt_stripped and (nxt_stripped[0].isdigit() or
                                          nxt_stripped[0] in "+-*"):
                        i += 1
                        caller_idx = cur_fn_frame.index
                        callee_idx = callee_frame.index
                        consume_cost_line(
                            nxt_stripped,
                            lambda costs, ci=caller_idx, ce=callee_idx:
                                self.add_edge(ci, ce, costs))
                cur_call_file = None
                cur_call_fn = None
                cur_call_id = None
                continue

            if stripped.startswith("jump=") or stripped.startswith("jcnd="):
                continue

            frame_idx = cur_fn_frame.index
            consume_cost_line(
                stripped,
                lambda costs, fi=frame_idx: self.add_self_cost(fi, costs))

        return self


def compute_roots(parser: Parser):
    """Frames that are never a callee of anyone -> natural roots.
    If none exist (shouldn't happen for a real profile), fall back to every
    frame that has self cost or outgoing edges."""
    callees = set()
    for edge_list in parser.edges.values():
        for callee_idx, _ in edge_list:
            callees.add(callee_idx)
    all_frames = set(range(len(parser.frame_list)))
    roots = sorted(all_frames - callees)
    if not roots:
        roots = sorted(all_frames)
    return roots


def resolve_expr(parser: Parser, expr: str):
    """'D1mr+D1mw' -> the cost-vector column indexes it sums, or None when
    any named event is not in this file."""
    idxs = []
    for name in (t.strip() for t in expr.split("+")):
        if name not in parser.event_index:
            return None
        idxs.append(parser.event_index[name])
    return idxs


def expr_label(parser: Parser, expr: str) -> str:
    """Human label for a profile: the expression plus a long name (from the
    file's own `event:` lines, or callgrind.py's tables)."""
    names = [t.strip() for t in expr.split("+")]

    def long_of(n):
        return parser.event_long.get(n) or cg.EVENT_LONG.get(n, "")

    long = ""
    if len(names) == 1:
        long = long_of(names[0])
    else:
        for _, terms, dlong in cg.DERIVED_DEFAULTS:
            if all(c == 1 for c, _ in terms) and sorted(r for _, r in terms) == sorted(names):
                long = dlong
                break
        if not long:
            long = " + ".join(long_of(n) or n for n in names)
    return f"{expr} — {long}" if long else expr


def build_profile(parser: Parser, idxs, profile_name: str):
    """One speedscope 'sampled' profile weighted by the sum of the given
    event columns. Returns (profile, sum of emitted weights)."""

    def value(vec):
        return sum(vec[i] for i in idxs if i < len(vec))

    def self_cost_of(frame_idx):
        c = parser.self_cost.get(frame_idx)
        return value(c) if c else 0

    # Sum of inclusive costs over all of each callee's incoming edges, so a
    # callee with several callers is split across them proportionally.
    incoming = defaultdict(float)
    for caller_edges in parser.edges.values():
        for c_idx, c_vec in caller_edges:
            incoming[c_idx] += value(c_vec)

    samples = []
    weights = []

    # visiting set for cycle detection along the *current* stack path only
    def walk(frame_idx, stack, visiting, scale):
        if len(stack) >= MAX_STACK_DEPTH or frame_idx in visiting:
            # Recursion / runaway depth: fold remaining cost into the
            # current frame itself rather than dropping it, scaled the same
            # way as everything else on this path.
            sc = self_cost_of(frame_idx) * scale
            if sc > 0:
                samples.append(list(stack))
                weights.append(sc)
            return

        new_stack = stack + [frame_idx]

        sc = self_cost_of(frame_idx) * scale
        if sc > 0:
            samples.append(list(new_stack))
            weights.append(sc)

        out_edges = parser.edges.get(frame_idx)
        if not out_edges:
            return

        visiting = visiting | {frame_idx}
        for callee_idx, vec in out_edges:
            ec = value(vec)
            if ec <= 0:
                continue
            # Share of this callee's total activity attributable to THIS
            # call site: this edge's inclusive cost as a fraction of the
            # sum of inclusive costs over all of the callee's incoming
            # edges (i.e. proportional attribution across multiple
            # callers).
            total_incoming = incoming.get(callee_idx, 0)
            if total_incoming <= 0:
                continue
            edge_scale = scale * (ec / total_incoming)
            walk(callee_idx, new_stack, visiting, edge_scale)

    roots = compute_roots(parser)
    for r in roots:
        walk(r, [], frozenset(), 1.0)

    total = sum(weights)

    # weights may be non-integer due to proportional splitting; speedscope
    # accepts floats for weights.
    profile = {
        "type": "sampled",
        "name": profile_name,
        "unit": "none",
        "startValue": 0,
        "endValue": total,
        "samples": samples,
        "weights": weights,
    }
    return profile, total


def build_speedscope_json(parser: Parser, exprs, base_name: str):
    """One speedscope document holding one profile per event expression
    (speedscope shows a profile picker when there is more than one).
    Expressions whose events are absent from the file, or whose total is
    zero, are skipped with a note on stderr."""
    if not parser.events:
        raise SystemExit("No 'events:' line found in callgrind file")

    shared_frames = []
    for f in parser.frame_list:
        entry = {"name": f.name or "???"}
        if f.file and f.file != "???":
            entry["file"] = f.file
        shared_frames.append(entry)

    profiles = []
    for expr in exprs:
        idxs = resolve_expr(parser, expr)
        if idxs is None:
            print(f"skipping --event {expr!r}: not all of its events are in this "
                  f"file (events: {' '.join(parser.events)})", file=sys.stderr)
            continue
        true_self_total = sum(sum(c[i] for i in idxs if i < len(c))
                              for c in parser.self_cost.values())
        if true_self_total <= 0:
            print(f"skipping --event {expr!r}: total is zero", file=sys.stderr)
            continue
        label = expr_label(parser, expr)
        profile, total = build_profile(parser, idxs, label)
        ratio = total / true_self_total
        print(f"{label}: {len(profile['samples'])} stack samples; "
              f"raw self total {true_self_total}, emitted {total:.0f}, "
              f"ratio {ratio:.4f} (must be ~1.0)", file=sys.stderr)
        profiles.append(profile)
    if not profiles:
        raise SystemExit("error: none of the requested --event expressions is usable")

    doc = {
        "$schema": "https://www.speedscope.app/file-format-schema.json",
        "shared": {"frames": shared_frames},
        "profiles": profiles,
        "name": base_name,
        "exporter": "callgrind_to_speedscope.py (curl dev/scripts)",
    }
    return doc


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("callgrind_file")
    ap.add_argument("-o", "--output", required=True,
                     help="output .speedscope.json path")
    ap.add_argument("--event", action="append", default=None, metavar="EXPR",
                     help="event to use as the cost weight; repeatable, each "
                          "becomes one profile in the file (speedscope shows a "
                          "picker); 'A+B' sums events, e.g. D1mr+D1mw "
                          "(default: Ir)")
    ap.add_argument("--name", default=None,
                     help="document name (default: input file basename)")
    args = ap.parse_args()

    with open(args.callgrind_file, "r", errors="replace") as f:
        text = f.read()

    parser = Parser().parse(text)
    if not parser.events:
        sys.exit("error: could not find 'events:' line -- not a callgrind file?")

    name = args.name or args.callgrind_file.rsplit("/", 1)[-1]
    print(f"Parsed {len(parser.frame_list)} frames; events: {' '.join(parser.events)}",
          file=sys.stderr)
    doc = build_speedscope_json(parser, args.event or ["Ir"], name)

    with open(args.output, "w") as f:
        json.dump(doc, f)

    print(f"Wrote {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()
