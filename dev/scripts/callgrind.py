"""Shared callgrind data-file parser for the dev/scripts profile tooling.

Per-line attribution mirrors callgrind_annotate exactly:
  * cost lines are charged to the *current* file, which `fl=` sets for a
    function and `fi=`/`fe=` switch for inlined code, and to the current
    line, decoded from callgrind's absolute/`+n`/`-n`/`*` subpositions;
  * the cost line that follows a `calls=` record is the *inclusive* cost of
    that call, charged to the call-site line separately (never as self cost);
  * `calls=` target positions are decoded relative to the last cost line but
    do not advance it.
"""
from __future__ import annotations

import re
from collections import defaultdict

_NAME_RE = re.compile(r"^\((\d+)\)(?: (.*))?$")

# Long names for the events callgrind can emit (it writes only the short
# names into the file); an `event:` header line in the file overrides these.
EVENT_LONG = {
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

# Derived events (name, [(coefficient, raw event)...], long name) that are
# added when all of their inputs are present in the file and the file itself
# did not define an inherited event of that name. CEst is KCachegrind's
# cycle estimation and is the one number that mixes instructions with
# cache misses.
DERIVED_DEFAULTS = [
    ("D1m", [(1, "D1mr"), (1, "D1mw")], "L1 data cache misses (D1mr + D1mw)"),
    ("DLm", [(1, "DLmr"), (1, "DLmw")], "LL data cache misses (DLmr + DLmw)"),
    ("L1m", [(1, "I1mr"), (1, "D1mr"), (1, "D1mw")], "L1 misses, all (I1mr + D1mr + D1mw)"),
    ("LLm", [(1, "ILmr"), (1, "DLmr"), (1, "DLmw")], "LL misses, all (ILmr + DLmr + DLmw)"),
    ("Bm", [(1, "Bcm"), (1, "Bim")], "branch mispredicts, all (Bcm + Bim)"),
    ("CEst", [(1, "Ir"), (10, "I1mr"), (10, "D1mr"), (10, "D1mw"),
              (100, "ILmr"), (100, "DLmr"), (100, "DLmw")],
     "cycle estimate (Ir + 10 L1m + 100 LLm)"),
]


class Profile:
    def __init__(self) -> None:
        self.events: list[str] = []            # raw event names, cost-line column order
        self.event_long: dict[str, str] = {}    # short name -> long name
        # (name, [(coef, raw event name)...], long name), from `event:` lines
        # in the file or DERIVED_DEFAULTS
        self.derived: list[tuple[str, list[tuple[int, str]], str]] = []
        self.desc: list[str] = []               # `desc:` header lines (cache geometry etc.)
        self.positions: list[str] = ["line"]
        self.cmd = ""
        self.summary: list[int] = []
        # (file, line) -> cost vector
        self.line_self: dict[tuple[str, int], list[int]] = {}
        self.line_calls: dict[tuple[str, int], list[int]] = {}
        self.line_callcount: dict[tuple[str, int], int] = defaultdict(int)
        # (file, line) -> function name (first function that charged it)
        self.line_fn: dict[tuple[str, int], str] = {}
        # fn name -> home file (file active at its first fn= record)
        self.fn_home: dict[str, str] = {}
        self.fn_self: dict[str, list[int]] = {}
        self.fn_calls: dict[str, list[int]] = {}
        # callee fn -> (file, line) of its first executed line (calls= target)
        self.fn_entry: dict[str, tuple[str, int]] = {}
        # (caller file, caller line, callee fn) -> [count, cost vector]
        self.callees: dict[tuple[str, int, str], list] = {}
        # callee fn -> {(caller fn, caller file, caller line): [count, cost vector]}
        self.callers: dict[str, dict[tuple[str, str, int], list]] = defaultdict(dict)
        # file -> object it was seen in (for grouping files without source)
        self.file_ob: dict[str, str] = {}

    # -- vector helpers ----------------------------------------------------
    def zeros(self) -> list[int]:
        return [0] * len(self.events)

    def _acc(self, table: dict, key, vec: list[int]) -> None:
        cur = table.get(key)
        if cur is None:
            table[key] = list(vec)
        else:
            for k, v in enumerate(vec):
                cur[k] += v

    def _acc_call(self, table: dict, key, count: int, vec: list[int]) -> None:
        cur = table.get(key)
        if cur is None:
            table[key] = [count, list(vec)]
        else:
            cur[0] += count
            c = cur[1]
            for k, v in enumerate(vec):
                c[k] += v

    # -- totals ------------------------------------------------------------
    def totals(self) -> list[int]:
        """The summary vector from the file, or the sum of self-cost lines."""
        if self.summary:
            return list(self.summary)
        t = self.zeros()
        for vec in self.line_self.values():
            for k, v in enumerate(vec):
                t[k] += v
        return t

    def index(self, name: str) -> int:
        return self.events.index(name)

    def has(self, *names: str) -> bool:
        return all(n in self.events for n in names)

    def derived_terms(self) -> list[tuple[str, list[tuple[int, int]], str]]:
        """Derived events with raw names resolved to column indexes; only
        those whose inputs all exist in this file."""
        out = []
        for name, terms, long in self.derived:
            if all(raw in self.events for _, raw in terms):
                out.append((name, [(c, self.events.index(raw)) for c, raw in terms], long))
        return out

    def value(self, vec: list[int], name: str) -> int:
        """Value of a raw or derived event in a cost vector."""
        if name in self.events:
            i = self.events.index(name)
            return vec[i] if i < len(vec) else 0
        for dname, terms, _ in self.derived_terms():
            if dname == name:
                return sum(c * (vec[i] if i < len(vec) else 0) for c, i in terms)
        raise KeyError(name)

    def event_names(self) -> list[str]:
        """Raw events followed by the derived events available in this file."""
        return list(self.events) + [n for n, _, _ in self.derived_terms()]


def _parse_event_header(val: str) -> tuple[str, list[tuple[int, str]] | None, str]:
    """`event: Name [= expr] [: long name]` -> (name, terms or None, long)."""
    name, eq, rest = val.partition("=")
    if not eq:
        name, _, long = val.partition(":")
        return name.strip(), None, long.strip()
    expr, _, long = rest.partition(":")
    terms: list[tuple[int, str]] = []
    for term in expr.split("+"):
        parts = term.replace("*", " ").split()
        if len(parts) == 1:
            terms.append((1, parts[0]))
        elif len(parts) == 2:
            terms.append((int(parts[0], 0), parts[1]))
    return name.strip(), terms, long.strip()


def parse_callgrind(text: str) -> Profile:
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
    prev = [0]
    cur_file = "???"
    cur_fn = "???"
    cur_ob = "???"
    cur_cob: str | None = None
    cur_cfile: str | None = None
    cur_cfn: str | None = None
    pending_call: tuple[int, int] | None = None

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
            if pending_call is not None:
                count, target = pending_call
                pending_call = None
                callee = cur_cfn or "???"
                callee_file = cur_cfile if cur_cfile is not None else cur_file
                cur_cfile = None
                key = (cur_file, line)
                p._acc(p.line_calls, key, vec)
                p.line_callcount[key] += count
                p.line_fn.setdefault(key, cur_fn)
                p._acc(p.fn_calls, cur_fn, vec)
                p._acc_call(p.callees, (cur_file, line, callee), count, vec)
                p._acc_call(p.callers[callee], (cur_fn, cur_file, line), count, vec)
                if callee not in p.fn_entry:
                    p.fn_entry[callee] = (callee_file, target)
                p.fn_home.setdefault(callee, callee_file)
                p.file_ob.setdefault(callee_file, cur_cob or cur_ob)
                cur_cob = None
            else:
                key = (cur_file, line)
                p._acc(p.line_self, key, vec)
                p.line_fn.setdefault(key, cur_fn)
                p._acc(p.fn_self, cur_fn, vec)
                p.file_ob.setdefault(cur_file, cur_ob)
            continue

        # `key=value` position/association specs vs `key: value` header lines:
        # whichever separator comes first decides (fn= names may contain
        # "::", header values may contain "=").
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
                count = int(parts[0])
                target = decode(parts[1 + line_idx], line_idx) if len(parts) > 1 + line_idx else 0
                pending_call = (count, target)
            elif key in ("jfi", "jfn"):
                unc("fl" if key == "jfi" else "fn", val)
            # jump=, jcnd=, and anything else: ignored
            continue
        if colon == -1:
            continue
        key, val = raw[:colon], raw[colon + 1:].strip()
        if key == "events":
            p.events = val.split()
            nev = len(p.events)
        elif key == "event":
            name, terms, long = _parse_event_header(val)
            if long:
                p.event_long[name] = long
            if terms is not None:
                p.derived.append((name, terms, long))
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
    defined = {n for n, _, _ in p.derived}
    for name, terms, long in DERIVED_DEFAULTS:
        if name not in defined and all(raw in p.events for _, raw in terms):
            p.derived.append((name, terms, long))
            p.event_long.setdefault(name, long)
    for name, _, long in p.derived:
        p.event_long.setdefault(name, long)
    return p


def self_check(p: Profile) -> tuple[int, int, float]:
    """(sum of self-cost lines, summary, ratio) for the first event."""
    self_sum = sum(vec[0] for vec in p.line_self.values() if vec)
    total = p.summary[0] if p.summary else self_sum
    ratio = self_sum / total if total else float("nan")
    return self_sum, total, ratio


# ----------------------------------------------------------------------------
# Several files as one profile
# ----------------------------------------------------------------------------


def merge(profiles: list[Profile]) -> Profile:
    """One profile over several: every per-line, per-function and call-graph
    cost summed, first-seen entries (home file, entry line) kept, summaries
    added. Each file must record the same events in the same order; the
    cache geometry (`desc:`) of the first is kept. The command becomes the
    shared program followed by every run's arguments, comma separated."""
    if len(profiles) == 1:
        return profiles[0]
    first = profiles[0]
    for q in profiles[1:]:
        if q.events != first.events:
            raise ValueError(f"cannot merge profiles with different events: {first.events} vs {q.events}")
    p = Profile()
    p.events = list(first.events)
    p.event_long = dict(first.event_long)
    p.derived = list(first.derived)
    p.desc = list(first.desc)
    p.positions = list(first.positions)
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
            p._acc(p.line_self, key, vec)
        for key, vec in q.line_calls.items():
            p._acc(p.line_calls, key, vec)
        for key, n in q.line_callcount.items():
            p.line_callcount[key] += n
        for key, fn in q.line_fn.items():
            p.line_fn.setdefault(key, fn)
        for fn, home in q.fn_home.items():
            p.fn_home.setdefault(fn, home)
        for fn, vec in q.fn_self.items():
            p._acc(p.fn_self, fn, vec)
        for fn, vec in q.fn_calls.items():
            p._acc(p.fn_calls, fn, vec)
        for fn, entry in q.fn_entry.items():
            p.fn_entry.setdefault(fn, entry)
        for key, (count, vec) in q.callees.items():
            p._acc_call(p.callees, key, count, vec)
        for callee, table in q.callers.items():
            for key, (count, vec) in table.items():
                p._acc_call(p.callers[callee], key, count, vec)
        for file, ob in q.file_ob.items():
            p.file_ob.setdefault(file, ob)
    return p


def load(paths: list[str]) -> Profile:
    """Parse every file and merge them into one profile."""
    profiles = []
    for path in paths:
        with open(path, encoding="utf-8", errors="replace") as f:
            profiles.append(parse_callgrind(f.read()))
    return merge(profiles)
