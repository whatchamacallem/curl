from __future__ import annotations

import collections, dataclasses, functools, os, posixpath, re, sys
from collections.abc import Sequence
from typing import Literal, NamedTuple, TypeAlias, TypeVar

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import settings

# All constants needed from settings.py have to be loaded here before anything
# else.
_CACHE_ROOT_DIR: str = ""
_DERIVED_COUNTER_TERMS: dict[str, dict[str, int]] = {}
_RANKING_COUNTER_NAME: str = ""
settings.load_into(__name__)

# One cost number per counter, in the order the file's "events:" line names
# them. That line is callgrind's own wire format and keeps its spelling.
Costs: TypeAlias = list[int]
# Where a source file came from, deciding whether the heat map shows it.
Group = Literal["repo", "system", "external"]
# The key type of whichever table a shared accumulate helper is given.
_Key = TypeVar("_Key")

# The curl checkout, three levels up from here -- every path is
# reported relative to it.
REPO_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)


# Every cached external source tree, <package>/<version> under the cache
# root the front line scripts fill. Empty until one of them has run.
@functools.cache
def external_source_roots() -> tuple[str, ...]:
    root = os.path.expanduser(_CACHE_ROOT_DIR)
    if not os.path.isdir(root):
        return ()
    found: list[str] = []
    for package in sorted(os.listdir(root)):
        versions = os.path.join(root, package)
        if not os.path.isdir(versions):
            continue
        for version in sorted(os.listdir(versions)):
            tree = os.path.join(versions, version)
            if os.path.isdir(tree):
                found.append(tree)
    return tuple(found)


# Caller - The one place a function was called from.
class Caller(NamedTuple):
    # who did the calling
    function: str
    # the file that call sits in
    file: str
    # the line that call sits on
    line: int


# CallSite - One line that calls one callee -- the other end of a Caller.
class CallSite(NamedTuple):
    # the file doing the calling
    file: str
    # the line doing the calling
    line: int
    # who gets called
    callee: str


# CounterSchema - One recorded counter list, resolved once: each recorded
# name's slot, and every derived counter those names can add up to.
class CounterSchema:
    # Index the recorded names and resolve the derived counter table.
    def __init__(self, counters: Sequence[str]) -> None:
        self.counters = list(counters)
        self.recorded_slots = {
            name: slot for slot, name in enumerate(counters)
        }
        self.derived_counters = [
            ResolvedDerivedCounter(
                name,
                tuple(
                    ResolvedTerm(coefficient, self.recorded_slots[input_name])
                    for input_name, coefficient in terms.items()
                ),
            )
            for name, terms in _DERIVED_COUNTER_TERMS.items()
            if all(input_name in self.recorded_slots for input_name in terms)
        ]
        self.derived_terms = {
            entry.name: entry.terms for entry in self.derived_counters
        }

    # Every counter a page may show: recorded first, then the ones added up.
    def counter_names(self) -> list[str]:
        return list(self.counters) + [
            entry.name for entry in self.derived_counters
        ]

    # Pull one named counter out of a cost vector, recorded or derived.
    def value(self, costs: Costs, name: str) -> int:
        slot = self.recorded_slots.get(name)
        if slot is not None:
            return costs[slot] if slot < len(costs) else 0
        terms = self.derived_terms.get(name)
        if terms is None:
            raise KeyError(name)
        return sum(
            term.coefficient
            * (
                costs[term.counter_index]
                if term.counter_index < len(costs)
                else 0
            )
            for term in terms
        )


# LineProfile - Cost per line and per function, indexed every way the
# pages ask for. A subtraction is one: a delta carries no call graph.
@dataclasses.dataclass
class LineProfile:
    # the recorded counters, in cost-vector order
    counters: list[str] = dataclasses.field(default_factory=list)
    # the profiled command line
    command: str = ""
    # callgrind's own total -- the self-check divides by it
    summary: list[int] = dataclasses.field(default_factory=list)
    # cost spent on the line itself
    line_self: dict[SourceLine, Costs] = dataclasses.field(
        default_factory=dict
    )
    # which function owns the line
    line_function: dict[SourceLine, str] = dataclasses.field(
        default_factory=dict
    )
    # the file a function is declared in
    function_home: dict[str, str] = dataclasses.field(default_factory=dict)
    # cost in the function itself, not in what it calls
    function_self: dict[str, Costs] = dataclasses.field(default_factory=dict)
    # per (function, line) cost -- the only per-context table, and
    # what a diff subtracts
    function_lines: collections.defaultdict[str, dict[SourceLine, Costs]] = (
        dataclasses.field(
            default_factory=lambda: collections.defaultdict(dict)
        )
    )
    # the line to jump to when opening a function
    function_entry: dict[str, SourceLine] = dataclasses.field(
        default_factory=dict
    )
    # the binary each file was compiled into
    file_ob: dict[str, str] = dataclasses.field(default_factory=dict)

    # Every counter a page may show: recorded first, then the ones we add up.
    def counter_names(self) -> list[str]:
        return counter_schema(tuple(self.counters)).counter_names()

    # The derived counters this run can supply, each input counter's name
    # swapped for its slot. Resolved once per distinct counter list.
    def resolved_derived_counters(self) -> list[ResolvedDerivedCounter]:
        return list(counter_schema(tuple(self.counters)).derived_counters)

    # The whole run's cost: callgrind's own summary line.
    def totals(self) -> Costs:
        if not self.summary:
            raise ValueError(f"no summary: command={self.command!r}")
        return list(self.summary)

    # Pull one named counter out of a cost vector, recorded or derived.
    def value(self, costs: Costs, name: str) -> int:
        return counter_schema(tuple(self.counters)).value(costs, name)

    # An all-zero cost vector of the right width for this profile.
    def zeros(self) -> Costs:
        return [0] * len(self.counters)


# PathInfo - One source path, resolved three ways at once.
class PathInfo(NamedTuple):
    # repo-relative, safe to print into a page
    display: str
    # readable on this box, or None when the source is gone
    local: str | None
    # repo, system or external
    group: Group


# Profile - Everything one callgrind run measured: the per-line costs
# plus the call graph a full recording carries and a delta does not.
@dataclasses.dataclass
class Profile(LineProfile):
    # cost spent below the calls made from it
    line_calls: dict[SourceLine, Costs] = dataclasses.field(
        default_factory=dict
    )
    # how many calls the line made
    line_call_count: collections.defaultdict[SourceLine, int] = (
        dataclasses.field(default_factory=lambda: collections.defaultdict(int))
    )
    # cost below everything the function calls
    function_calls: dict[str, Costs] = dataclasses.field(default_factory=dict)
    # per call site, how many calls and what they cost
    callees: dict[CallSite, Tally] = dataclasses.field(default_factory=dict)
    # the same the other way round: per callee, who called it
    callers: collections.defaultdict[str, dict[Caller, Tally]] = (
        dataclasses.field(
            default_factory=lambda: collections.defaultdict(dict)
        )
    )


# ResolvedDerivedCounter - One derived counter whose input names have been
# swapped for the cost-vector slots holding them, ready to sum.
class ResolvedDerivedCounter(NamedTuple):
    # what to call it
    name: str
    # the slots to add up, with weights
    terms: tuple[ResolvedTerm, ...]


# ResolvedTerm - One weighted slot of a cost vector.
class ResolvedTerm(NamedTuple):
    # what to multiply it by
    coefficient: int
    # which slot of the cost vector
    counter_index: int


# SourceLine - One line of one file -- the key most tables here are keyed by.
class SourceLine(NamedTuple):
    # the file, exactly as callgrind spelled it
    file: str
    # 1-based line number
    line: int


# Tally - A cost plus how many calls produced it.
@dataclasses.dataclass
class Tally:
    # how many calls
    count: int
    # what they cost between them
    costs: Costs


# Callgrind - Reads callgrind's output format into a Profile.
class Callgrind:
    # matches a "(7)" name reference, with the name when it is spelled out
    NAME_COMPRESSION_RE = re.compile(r"^\((\d+)\)(?: (.*))?$")

    # CompressedNames - Callgrind writes "(7) name" once, then just
    # "(7)" -- this remembers which is which.
    class CompressedNames:
        # Start with no names learned, one table per name kind.
        def __init__(self) -> None:
            self.names: dict[str, dict[str, str]] = {
                "fl": {},
                "fn": {},
                "ob": {},
            }

        # Expand one "(7)" back to its name, learning it where spelled out.
        # A miss is a dropped line: "(7)" would reach a page as the name.
        def uncompress(self, kind: str, value: str) -> str:
            match = Callgrind.NAME_COMPRESSION_RE.match(value)
            if not match:
                return value
            ident, name = match.group(1), match.group(2)
            if name is not None:
                self.names[kind][ident] = name
                return name
            known = self.names[kind].get(ident)
            if known is None:
                sys.exit(
                    f"error: {kind}=({ident}) refers to a name this file"
                    " never spelled out"
                )
            return known

    # PendingCall - A "calls=" line, waiting for the cost line that follows it.
    class PendingCall(NamedTuple):
        # how many times
        call_count: int
        # the line jumped to
        target_line: int

    # PositionDecoder - Cost lines give positions relative to the last
    # one -- this tracks the running value.
    class PositionDecoder:
        # Start on the one-column "line" positions callgrind defaults to.
        def __init__(self) -> None:
            self.count = 1
            self.line_index = 0
            self.previous: list[int] = [0]

        # Read one position token: "*" repeats, "+n"/"-n" step,
        # anything else is absolute.
        def decode(self, token: str, position: int) -> int:
            if token == "*":
                return self.previous[position]
            if token[0] == "+":
                return self.previous[position] + int(token[1:])
            if token[0] == "-":
                return self.previous[position] - int(token[1:])
            if token.startswith("0x") or token.startswith("0X"):
                return int(token, 16)
            return int(token)

        # Start over for a new "positions:" line, finding which column
        # holds the line number.
        def reset(self, names: Sequence[str]) -> None:
            self.count = len(names)
            self.line_index = (
                names.index("line") if "line" in names else self.count - 1
            )
            self.previous = [0] * self.count

        # Advance past one cost line's positions and hand back the
        # line number it lands on.
        def step(self, tokens: Sequence[str]) -> int:
            for position in range(self.count):
                self.previous[position] = self.decode(
                    tokens[position], position
                )
            return self.previous[self.line_index]

    # Give every still-unplaced function an entry line, so the pages
    # can link to it.
    def entries_fill(self, profile: Profile) -> None:
        for function, lines in profile.function_lines.items():
            home = profile.function_home.get(function)
            if function in profile.function_entry or home is None:
                continue
            line = next(
                (key.line for key in lines if key.file == home and key.line), 0
            )
            if line:
                profile.function_entry[function] = SourceLine(home, line)

    # Read every given file and merge them into one profile.
    def load(self, paths: Sequence[str]) -> Profile:
        return self.merge([self.load_one(path) for path in paths])

    # Read one file, and refuse it unless its per-line costs add up
    # to its own summary.
    def load_one(self, path: str) -> Profile:
        with open(path, encoding="utf-8", errors="replace") as handle:
            profile = self.parse(handle.read())
        if not profile.counters:
            sys.exit(
                f"error: no 'events:' line -- not a callgrind file? ({path})"
            )
        self_sum = sum(
            costs[0] for costs in profile.line_self.values() if costs
        )
        total = profile.totals()[0]
        if total == 0:
            sys.exit(f"error: callgrind summary total is 0 ({path})")
        ratio = self_sum / total
        print(
            f"ratio (must be 1.0000): {ratio:.4f}  {os.path.basename(path)}",
            file=sys.stderr,
        )
        if abs(ratio - 1.0) > 1e-6:
            sys.exit(
                "error: per-line self cost does not add up to"
                f" callgrind's summary ({path})"
            )
        return profile

    # Add several profiles of the same counters together.
    def merge(self, profiles: Sequence[Profile]) -> Profile:
        if len(profiles) == 1:
            return profiles[0]
        first = profiles[0]
        for other in profiles[1:]:
            if other.counters != first.counters:
                sys.exit(
                    "error: cannot merge profiles with different counters:"
                    f" {first.counters} vs {other.counters}"
                )
        merged = Profile(counters=list(first.counters))
        merged.command = self.merge_command(profiles)
        if not all(other.summary for other in profiles):
            sys.exit(
                "error: cannot merge profiles, one has no summary:"
                f" {[other.command for other in profiles]}"
            )
        merged.summary = [
            sum(
                other.summary[index] if index < len(other.summary) else 0
                for other in profiles
            )
            for index in range(max(len(other.summary) for other in profiles))
        ]
        for other in profiles:
            self.merge_one(merged, other)
        return merged

    # One command line standing for all of them, sharing the program
    # name when they agree on it.
    def merge_command(self, profiles: Sequence[Profile]) -> str:
        commands = [other.command.split() for other in profiles]
        if all(
            command and command[0] == commands[0][0] for command in commands
        ):
            return (
                commands[0][0]
                + " "
                + ", ".join(" ".join(command[1:]) for command in commands)
            )
        return " + ".join(other.command for other in profiles)

    # Fold one profile's every table into the one being built.
    def merge_one(self, merged: Profile, other: Profile) -> None:
        for key, costs in other.line_self.items():
            costs_accumulate(merged.line_self, key, costs)
        for key, costs in other.line_calls.items():
            costs_accumulate(merged.line_calls, key, costs)
        for key, count in other.line_call_count.items():
            merged.line_call_count[key] += count
        for key, function in other.line_function.items():
            merged.line_function.setdefault(key, function)
        for function, home in other.function_home.items():
            merged.function_home.setdefault(function, home)
        for function, costs in other.function_self.items():
            costs_accumulate(merged.function_self, function, costs)
        for function, lines in other.function_lines.items():
            for key, costs in lines.items():
                costs_accumulate(merged.function_lines[function], key, costs)
        for function, costs in other.function_calls.items():
            costs_accumulate(merged.function_calls, function, costs)
        for function, entry in other.function_entry.items():
            merged.function_entry.setdefault(function, entry)
        for site, tally in other.callees.items():
            tally_accumulate(merged.callees, site, tally.count, tally.costs)
        for callee, callers in other.callers.items():
            for caller, tally in callers.items():
                tally_accumulate(
                    merged.callers[callee], caller, tally.count, tally.costs
                )
        for file, ob in other.file_ob.items():
            merged.file_ob.setdefault(file, ob)

    # Walk the file once, carrying the current file/function/object
    # as callgrind's headers change them.
    def parse(self, text: str) -> Profile:
        profile = Profile()
        names = Callgrind.CompressedNames()
        positions = Callgrind.PositionDecoder()

        counter_count = 0
        cur_file = "???"
        cur_function = "???"
        cur_ob = "???"
        cur_callee_ob: str | None = None
        cur_callee_file: str | None = None
        cur_callee_function: str | None = None
        pending_call: Callgrind.PendingCall | None = None

        for raw_line in text.split("\n"):
            if not raw_line or raw_line[0] == "#":
                continue
            first_char = raw_line[0]
            if first_char.isdigit() or first_char in "+-*":
                tokens = raw_line.split()
                line = positions.step(tokens)
                costs = [int(token) for token in tokens[positions.count :]]
                if len(costs) < counter_count:
                    costs.extend([0] * (counter_count - len(costs)))
                key = SourceLine(cur_file, line)
                if pending_call is not None:
                    callee = cur_callee_function or "???"
                    callee_file = (
                        cur_callee_file
                        if cur_callee_file is not None
                        else cur_file
                    )
                    cur_callee_file = None
                    costs_accumulate(profile.line_calls, key, costs)
                    profile.line_call_count[key] += pending_call.call_count
                    profile.line_function.setdefault(key, cur_function)
                    costs_accumulate(
                        profile.function_calls, cur_function, costs
                    )
                    tally_accumulate(
                        profile.callees,
                        CallSite(cur_file, line, callee),
                        pending_call.call_count,
                        costs,
                    )
                    tally_accumulate(
                        profile.callers[callee],
                        Caller(cur_function, cur_file, line),
                        pending_call.call_count,
                        costs,
                    )
                    if callee not in profile.function_entry:
                        profile.function_entry[callee] = SourceLine(
                            callee_file, pending_call.target_line
                        )
                    profile.function_home.setdefault(callee, callee_file)
                    profile.file_ob.setdefault(
                        callee_file, cur_callee_ob or cur_ob
                    )
                    cur_callee_ob = None
                    pending_call = None
                else:
                    costs_accumulate(profile.line_self, key, costs)
                    profile.line_function.setdefault(key, cur_function)
                    costs_accumulate(
                        profile.function_self, cur_function, costs
                    )
                    costs_accumulate(
                        profile.function_lines[cur_function], key, costs
                    )
                    profile.file_ob.setdefault(cur_file, cur_ob)
                continue

            equals_index = raw_line.find("=")
            colon_index = raw_line.find(":")
            if equals_index != -1 and (
                colon_index == -1 or equals_index < colon_index
            ):
                key, val = (
                    raw_line[:equals_index],
                    raw_line[equals_index + 1 :],
                )
                if key in ("fl", "fi", "fe"):
                    cur_file = names.uncompress("fl", val)
                elif key == "fn":
                    cur_function = names.uncompress("fn", val)
                    profile.function_home.setdefault(cur_function, cur_file)
                    cur_callee_file = None
                elif key == "ob":
                    cur_ob = names.uncompress("ob", val)
                elif key == "cob":
                    cur_callee_ob = names.uncompress("ob", val)
                elif key in ("cfl", "cfi"):
                    cur_callee_file = names.uncompress("fl", val)
                elif key == "cfn":
                    cur_callee_function = names.uncompress("fn", val)
                elif key in ("jfi", "jfn"):
                    # --collect-jumps names a jump target in the fl/fn name
                    # spaces: learned, but neither current name moves.
                    names.uncompress("fl" if key == "jfi" else "fn", val)
                elif key == "calls":
                    parts = val.split()
                    if len(parts) <= 1 + positions.line_index:
                        sys.exit(f"error: malformed 'calls=' line: {raw_line}")
                    target_line = positions.decode(
                        parts[1 + positions.line_index], positions.line_index
                    )
                    pending_call = Callgrind.PendingCall(
                        int(parts[0]), target_line
                    )
                continue
            if colon_index == -1:
                continue
            key, val = (
                raw_line[:colon_index],
                raw_line[colon_index + 1 :].strip(),
            )
            if key == "events":
                profile.counters = val.split()
                counter_count = len(profile.counters)
            elif key == "positions":
                positions.reset(val.split())
            elif key == "cmd":
                profile.command = val
            elif key in ("summary", "totals"):
                values = [int(v) for v in val.split()]
                if len(values) >= len(profile.summary):
                    profile.summary = values

        self.entries_fill(profile)
        return profile


# The one parser every profile is read through.
_PROFILE_PARSER = Callgrind()


# How one line's baseline slot is spelled, everywhere it is written and
# everywhere it is read back. Both sides of the diff use it.
def baseline_line_key(function: str, display: str, line: int | str) -> str:
    return f"{function}\n{display}\n{line}"


# One normalized external path inside a cached source tree, or None.
# A build subdirectory prefix is spelled twice or not at all, never more.
def cached_source_of(display: str) -> str | None:
    if display.startswith(".."):
        return None
    parts = display.split("/")
    wanted = [display]
    # "./elf/./elf/dl-cache.c" normalizes with its build subdirectory
    # doubled, while "./elf/../misc/sbrk.c" already lost it to the ".."
    if len(parts) > 1 and parts[0] == parts[1]:
        wanted.append("/".join(parts[1:]))
    for tree in external_source_roots():
        for relative in wanted:
            local = os.path.join(tree, relative)
            if os.path.isfile(local):
                return local
    return None


# Add a cost vector into a table, starting a fresh entry when the key is new.
def costs_accumulate(
    table: dict[_Key, Costs], key: _Key, costs: Costs
) -> None:
    current = table.get(key)
    if current is None:
        table[key] = list(costs)
    else:
        costs_add(current, costs)


# Add one cost vector into another, in place.
def costs_add(dst: Costs, src: Costs) -> None:
    for index, value in enumerate(src):
        dst[index] += value


# Pad a vector to the recorded width so a slot's index never moves, then
# trim trailing zeros. No derived slot is stored -- those sum from these.
def costs_fit(costs: Costs, width: int) -> Costs:
    return costs_trim(list(costs) + [0] * (width - len(costs)))


# Subtract two cost vectors, treating a missing slot as zero.
def costs_sub(modified: Costs, baseline: Costs) -> Costs:
    return [
        (modified[index] if index < len(modified) else 0)
        - (baseline[index] if index < len(baseline) else 0)
        for index in range(max(len(modified), len(baseline)))
    ]


# Drop a vector's trailing zeros: a slot nothing would read back is not
# worth the bytes on a page or in a stored file.
def costs_trim(costs: Costs) -> Costs:
    length = len(costs)
    while length and costs[length - 1] == 0:
        length -= 1
    return costs[:length]


# Every counter a vector written against these recorded ones can supply:
# the recorded ones, then the derived ones they add up to.
def counter_names(counters: Sequence[str]) -> list[str]:
    return counter_schema(tuple(counters)).counter_names()


# The resolved schema of one recorded counter list, built once per
# distinct list and shared by every lookup against it.
@functools.cache
def counter_schema(counters: tuple[str, ...]) -> CounterSchema:
    return CounterSchema(counters)


# Pull one named counter out of a stored cost vector -- the one door a
# derived counter is computed through outside a live profile.
def counter_value(counters: Sequence[str], costs: Costs, name: str) -> int:
    return counter_schema(tuple(counters)).value(costs, name)


# How a path prints on a page: an external file carries its owning object,
# so same-named headers stay apart. Both sides of a baseline key use it.
def display_path_of(path: str, object_path: str) -> str:
    info = path_norm(path)
    if info.group != "external":
        return info.display
    owner = os.path.basename(object_path) or "(unknown object)"
    return f"{owner}/{info.display}"


# Work out how to print a path, whether we can still read it, and
# where it came from.
def path_norm(path: str) -> PathInfo:
    if path == "???":
        return PathInfo("(unknown)", None, "external")
    root = REPO_ROOT + "/"
    if os.path.isabs(path):
        path = posixpath.normpath(path)
    if path.startswith(root):
        relative = path[len(root) :]
        local = os.path.join(REPO_ROOT, relative)
        return PathInfo(
            relative, local if os.path.isfile(local) else None, "repo"
        )
    if os.path.isabs(path):
        if os.path.isfile(path):
            return PathInfo(path.lstrip("/"), path, "system")
        return PathInfo(path.lstrip("/"), None, "external")
    candidate = os.path.join(REPO_ROOT, path)
    if os.path.isfile(candidate):
        return PathInfo(posixpath.normpath(path), candidate, "repo")
    display = posixpath.normpath(path)
    cached = cached_source_of(display)
    if cached is not None:
        return PathInfo(display, cached, "system")
    return PathInfo(display, None, "external")


# Read callgrind files into one profile, refusing any that do not add up.
def profile_load(paths: Sequence[str]) -> Profile:
    return _PROFILE_PARSER.load(paths)


# Refuse a counter list that cannot supply the ranking counter, rather
# than a bare KeyError from a value lookup further in.
def ranking_counter_check(counters: Sequence[str], source: str) -> None:
    if _RANKING_COUNTER_NAME in counter_names(counters):
        return
    sys.exit(
        f"error: {source} cannot supply {_RANKING_COUNTER_NAME}, the"
        f" counter every page ranks and divides by: it records"
        f" {' '.join(counters)}"
    )


# Add a call count and its cost into a table, starting a fresh entry
# when the key is new.
def tally_accumulate(
    table: dict[_Key, Tally], key: _Key, count: int, costs: Costs
) -> None:
    current = table.get(key)
    if current is None:
        table[key] = Tally(count, list(costs))
    else:
        current.count += count
        costs_add(current.costs, costs)
