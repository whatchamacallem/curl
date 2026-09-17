from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import NamedTuple, TypeAlias, TypeVar

_NAME_RE = re.compile(r"^\((\d+)\)(?: (.*))?$")

Vec: TypeAlias = list[int]


class Term(NamedTuple):
    coef: int
    raw: str


class DerivedEvent(NamedTuple):
    name: str
    terms: tuple[Term, ...]
    long: str


class IndexedTerm(NamedTuple):
    coef: int
    index_: int


class DerivedIndexed(NamedTuple):
    name: str
    terms: tuple[IndexedTerm, ...]
    long: str


class LineKey(NamedTuple):
    file: str
    line: int


class CallSiteKey(NamedTuple):
    file: str
    line: int
    callee: str


class CallerKey(NamedTuple):
    fn: str
    file: str
    line: int


@dataclass
class CallCost:
    count: int
    cost: Vec


class EventHeader(NamedTuple):
    name: str
    terms: tuple[Term, ...] | None
    long: str


class SelfCheck(NamedTuple):
    self_sum: int
    total: int
    ratio: float


class _PendingCall(NamedTuple):
    count_: int
    target: int


EVENT_LONG: dict[str, str] = {
    "Ir": "instructions executed",
    "Dr": "data reads",
    "Dw": "data writes",
    "I1mr": "L1 instruction cache misses",
    "D1mr": "L1 data cache read misses",
    "D1mw": "L1 data cache write misses",
    "ILmr": "LL (last-level) instruction cache misses",
    "DLmr": "LL (last-level) data read misses",
    "DLmw": "LL (last-level) data write misses",
    "Bc": "conditional branches executed",
    "Bcm": "conditional branches mispredicted",
    "Bi": "indirect branches executed",
    "Bim": "indirect branches mispredicted",
    "Ge": "global bus events",
    "sysCount": "system calls",
    "sysTime": "system call time",
    "sysCpuTime": "system call cpu time",
    "AcCost1": "L1 cache-block access cost",
    "SpLoss1": "L1 cache-block spatial loss",
    "AcCost2": "LL cache-block access cost",
    "SpLoss2": "LL cache-block spatial loss",
    "ILdmr": "LL instruction write-backs",
    "DLdmr": "LL data read write-backs",
    "DLdmw": "LL data write write-backs",
}

DERIVED_DEFAULTS: tuple[DerivedEvent, ...] = (
    DerivedEvent("D1m", (Term(1, "D1mr"), Term(1, "D1mw")), "L1 data cache misses (D1mr + D1mw)"),
    DerivedEvent("DLm", (Term(1, "DLmr"), Term(1, "DLmw")), "LL data cache misses (DLmr + DLmw)"),
    DerivedEvent("L1m", (Term(1, "I1mr"), Term(1, "D1mr"), Term(1, "D1mw")), "L1 misses, all (I1mr + D1mr + D1mw)"),
    DerivedEvent("LLm", (Term(1, "ILmr"), Term(1, "DLmr"), Term(1, "DLmw")), "LL misses, all (ILmr + DLmr + DLmw)"),
    DerivedEvent("Bm", (Term(1, "Bcm"), Term(1, "Bim")), "branch mispredicts, all (Bcm + Bim)"),
    DerivedEvent("CEst", (Term(1, "Ir"), Term(10, "I1mr"), Term(10, "D1mr"), Term(10, "D1mw"),
                          Term(100, "ILmr"), Term(100, "DLmr"), Term(100, "DLmw")),
                 "cycle estimate (Ir + 10 L1m + 100 LLm)"),
)


K = TypeVar("K")


def vec_add(dst: Vec, src: Vec) -> None:
    for k, v in enumerate(src):
        dst[k] += v


def vec_acc(table: dict[K, Vec], key: K, vec: Vec) -> None:
    cur = table.get(key)
    if cur is None:
        table[key] = list(vec)
    else:
        vec_add(cur, vec)


def call_acc(table: dict[K, CallCost], key: K, count: int, vec: Vec) -> None:
    cur = table.get(key)
    if cur is None:
        table[key] = CallCost(count, list(vec))
    else:
        cur.count += count
        vec_add(cur.cost, vec)


@dataclass
class Profile:
    events: list[str] = field(default_factory=list)
    event_long: dict[str, str] = field(default_factory=dict)
    derived: list[DerivedEvent] = field(default_factory=list)
    desc: list[str] = field(default_factory=list)
    positions: list[str] = field(default_factory=lambda: ["line"])
    cmd: str = ""
    summary: list[int] = field(default_factory=list)
    line_self: dict[LineKey, Vec] = field(default_factory=dict)
    line_calls: dict[LineKey, Vec] = field(default_factory=dict)
    line_callcount: defaultdict[LineKey, int] = field(default_factory=lambda: defaultdict(int))
    line_fn: dict[LineKey, str] = field(default_factory=dict)
    fn_home: dict[str, str] = field(default_factory=dict)
    fn_self: dict[str, Vec] = field(default_factory=dict)
    fn_calls: dict[str, Vec] = field(default_factory=dict)
    fn_entry: dict[str, LineKey] = field(default_factory=dict)
    callees: dict[CallSiteKey, CallCost] = field(default_factory=dict)
    callers: defaultdict[str, dict[CallerKey, CallCost]] = field(default_factory=lambda: defaultdict(dict))
    file_ob: dict[str, str] = field(default_factory=dict)

    def zeros(self) -> Vec:
        return [0] * len(self.events)

    def totals(self) -> Vec:
        if self.summary:
            return list(self.summary)
        t = self.zeros()
        for vec in self.line_self.values():
            vec_add(t, vec)
        return t

    def derived_terms(self) -> list[DerivedIndexed]:
        out: list[DerivedIndexed] = []
        for d in self.derived:
            if all(t.raw in self.events for t in d.terms):
                out.append(DerivedIndexed(
                    d.name, tuple(IndexedTerm(t.coef, self.events.index(t.raw)) for t in d.terms), d.long))
        return out

    def value(self, vec: Vec, name: str) -> int:
        if name in self.events:
            i = self.events.index(name)
            return vec[i] if i < len(vec) else 0
        for d in self.derived_terms():
            if d.name == name:
                return sum(t.coef * (vec[t.index_] if t.index_ < len(vec) else 0) for t in d.terms)
        raise KeyError(name)

    def event_names(self) -> list[str]:
        return list(self.events) + [d.name for d in self.derived_terms()]


def _parse_event_header(val: str) -> EventHeader:
    head, _, long = val.partition(":")
    name, eq, expr = head.partition("=")
    if not eq:
        return EventHeader(name.strip(), None, long.strip())
    terms: list[Term] = []
    for term in expr.split("+"):
        parts = term.replace("*", " ").split()
        if len(parts) == 1:
            terms.append(Term(1, parts[0]))
        elif len(parts) == 2:
            terms.append(Term(int(parts[0], 0), parts[1]))
    return EventHeader(name.strip(), tuple(terms), long.strip())


def profile_parse(text: str) -> Profile:
    p = Profile()
    names: dict[str, dict[str, str]] = {"fl": {}, "fn": {}, "ob": {}}

    def unc(kind: str, val: str) -> str:
        m = _NAME_RE.match(val)
        if not m:
            return val
        ident, name = m.group(1), m.group(2)
        if name is not None:
            names[kind][ident] = name
            return name
        return names[kind].get(ident, f"({ident})")

    nev = 0
    npos = 1
    line_idx = 0
    prev: list[int] = [0]
    cur_file = "???"
    cur_fn = "???"
    cur_ob = "???"
    cur_cob: str | None = None
    cur_cfile: str | None = None
    cur_cfn: str | None = None
    pending_call: _PendingCall | None = None

    def decode(tok: str, k: int) -> int:
        if tok == "*":
            return prev[k]
        if tok[0] == "+":
            return prev[k] + int(tok[1:])
        if tok[0] == "-":
            return prev[k] - int(tok[1:])
        if tok.startswith("0x") or tok.startswith("0X"):
            return int(tok, 16)
        return int(tok)

    for raw in text.split("\n"):
        if not raw or raw[0] == "#":
            continue
        c0 = raw[0]
        if c0.isdigit() or c0 in "+-*":
            toks = raw.split()
            for k in range(npos):
                prev[k] = decode(toks[k], k)
            line = prev[line_idx]
            vec = [int(t) for t in toks[npos:]]
            if len(vec) < nev:
                vec.extend([0] * (nev - len(vec)))
            key = LineKey(cur_file, line)
            if pending_call is not None:
                callee = cur_cfn or "???"
                callee_file = cur_cfile if cur_cfile is not None else cur_file
                cur_cfile = None
                vec_acc(p.line_calls, key, vec)
                p.line_callcount[key] += pending_call.count_
                p.line_fn.setdefault(key, cur_fn)
                vec_acc(p.fn_calls, cur_fn, vec)
                call_acc(p.callees, CallSiteKey(cur_file, line, callee), pending_call.count_, vec)
                call_acc(p.callers[callee], CallerKey(cur_fn, cur_file, line), pending_call.count_, vec)
                if callee not in p.fn_entry:
                    p.fn_entry[callee] = LineKey(callee_file, pending_call.target)
                p.fn_home.setdefault(callee, callee_file)
                p.file_ob.setdefault(callee_file, cur_cob or cur_ob)
                cur_cob = None
                pending_call = None
            else:
                vec_acc(p.line_self, key, vec)
                p.line_fn.setdefault(key, cur_fn)
                vec_acc(p.fn_self, cur_fn, vec)
                p.file_ob.setdefault(cur_file, cur_ob)
            continue

        eq = raw.find("=")
        colon = raw.find(":")
        if eq != -1 and (colon == -1 or eq < colon):
            key, val = raw[:eq], raw[eq + 1:]
            if key == "fl":
                cur_file = unc("fl", val)
            elif key in ("fi", "fe"):
                cur_file = unc("fl", val)
            elif key == "fn":
                cur_fn = unc("fn", val)
                p.fn_home.setdefault(cur_fn, cur_file)
                cur_cfile = None
            elif key == "ob":
                cur_ob = unc("ob", val)
            elif key == "cob":
                cur_cob = unc("ob", val)
            elif key in ("cfl", "cfi"):
                cur_cfile = unc("fl", val)
            elif key == "cfn":
                cur_cfn = unc("fn", val)
            elif key == "calls":
                parts = val.split()
                target = decode(parts[1 + line_idx], line_idx) if len(parts) > 1 + line_idx else 0
                pending_call = _PendingCall(int(parts[0]), target)
            elif key in ("jfi", "jfn"):
                unc("fl" if key == "jfi" else "fn", val)
            continue
        if colon == -1:
            continue
        key, val = raw[:colon], raw[colon + 1:].strip()
        if key == "events":
            p.events = val.split()
            nev = len(p.events)
        elif key == "event":
            hdr = _parse_event_header(val)
            if hdr.long:
                p.event_long[hdr.name] = hdr.long
            if hdr.terms is not None:
                p.derived.append(DerivedEvent(hdr.name, hdr.terms, hdr.long))
        elif key == "positions":
            p.positions = val.split()
            npos = len(p.positions)
            line_idx = p.positions.index("line") if "line" in p.positions else npos - 1
            prev = [0] * npos
        elif key == "cmd":
            p.cmd = val
        elif key == "desc":
            p.desc.append(val)
        elif key in ("summary", "totals"):
            vals = [int(v) for v in val.split()]
            if len(vals) >= len(p.summary):
                p.summary = vals

    for name in p.events:
        p.event_long.setdefault(name, EVENT_LONG.get(name, ""))
    defined = {d.name for d in p.derived}
    for d in DERIVED_DEFAULTS:
        if d.name not in defined and all(t.raw in p.events for t in d.terms):
            p.derived.append(d)
    for d in p.derived:
        p.event_long.setdefault(d.name, d.long)
    return p


def profile_self_check(p: Profile) -> SelfCheck:
    self_sum = sum(vec[0] for vec in p.line_self.values() if vec)
    total = p.summary[0] if p.summary else self_sum
    ratio = self_sum / total if total else float("nan")
    return SelfCheck(self_sum, total, ratio)


def profile_merge(profiles: Sequence[Profile]) -> Profile:
    if not profiles:
        raise ValueError("no profiles to merge")
    if len(profiles) == 1:
        return profiles[0]
    first = profiles[0]
    for q in profiles[1:]:
        if q.events != first.events:
            raise ValueError(f"cannot merge profiles with different events: {first.events} vs {q.events}")
    p = Profile(events=list(first.events), event_long=dict(first.event_long), derived=list(first.derived),
                desc=list(first.desc), positions=list(first.positions))
    cmds = [q.cmd.split() for q in profiles]
    if all(c and c[0] == cmds[0][0] for c in cmds):
        p.cmd = cmds[0][0] + " " + ", ".join(" ".join(c[1:]) for c in cmds)
    else:
        p.cmd = " + ".join(q.cmd for q in profiles)
    if all(q.summary for q in profiles):
        p.summary = [sum(q.summary[k] if k < len(q.summary) else 0 for q in profiles)
                     for k in range(max(len(q.summary) for q in profiles))]
    for q in profiles:
        for key, vec in q.line_self.items():
            vec_acc(p.line_self, key, vec)
        for key, vec in q.line_calls.items():
            vec_acc(p.line_calls, key, vec)
        for key, n in q.line_callcount.items():
            p.line_callcount[key] += n
        for key, fn in q.line_fn.items():
            p.line_fn.setdefault(key, fn)
        for fn, home in q.fn_home.items():
            p.fn_home.setdefault(fn, home)
        for fn, vec in q.fn_self.items():
            vec_acc(p.fn_self, fn, vec)
        for fn, vec in q.fn_calls.items():
            vec_acc(p.fn_calls, fn, vec)
        for fn, entry in q.fn_entry.items():
            p.fn_entry.setdefault(fn, entry)
        for site, cc in q.callees.items():
            call_acc(p.callees, site, cc.count, cc.cost)
        for callee, table in q.callers.items():
            for caller, cc in table.items():
                call_acc(p.callers[callee], caller, cc.count, cc.cost)
        for file, ob in q.file_ob.items():
            p.file_ob.setdefault(file, ob)
    return p


def profile_load(paths: Sequence[str]) -> Profile:
    profiles: list[Profile] = []
    for path in paths:
        with open(path, encoding="utf-8", errors="replace") as f:
            profiles.append(profile_parse(f.read()))
    return profile_merge(profiles)
