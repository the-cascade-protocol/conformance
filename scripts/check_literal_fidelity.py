#!/usr/bin/env python3
"""Prove that parsing a fixture does not change the literals it authored.

RDF 1.1 Concepts section 3.3 says two literals are the same term only if their
lexical form, datatype IRI and language tag are all equal. A parser that returns
`"2026-02-14T08:00:00+00:00"` for a document that wrote
`"2026-02-14T08:00:00Z"^^xsd:dateTime` has therefore not returned the document's
data; it has returned different data that happens to have the same value. The
same is true of `"132"^^xsd:double` coming back as `"132.0"`.

rdflib does exactly that by default: `rdflib.NORMALIZE_LITERALS` is `True`, and
`Literal.__new__` replaces the authored lexical form with the canonical
serialisation of the parsed Python value whenever the datatype is one it
recognises. Nothing warns. This repository publishes fixtures whose whole
purpose is to be compared byte-for-byte across implementations, so a rewrite
between the file and the graph is a defect in the runner, not a detail.

WHAT THIS SCRIPT ASSERTS

Two things, and it needs both because either one alone can be vacuous:

  1. FIDELITY (the gate).  Every typed literal in every Turtle document in this
     repository must survive a parse under the runner's own rdflib settings
     with its lexical form unchanged. A non-zero count here fails the script.

  2. EXPOSURE (reported, never gated).  The same corpus parsed under rdflib's
     DEFAULT settings, to measure how much of it rdflib would rewrite if the
     runner ever stopped disabling normalisation. This number is expected to be
     large. It is what makes assertion 1 meaningful: a fidelity check that never
     had anything to catch proves nothing, so the script prints the size of what
     it is holding back.

WHY THERE IS A SECOND, INDEPENDENT READER

Asking rdflib whether rdflib preserved the file is circular. So the authored
literals are also read straight out of the file bytes by a small Turtle scanner
in this script (`scan_typed_literals`), which knows about comments, IRI
references, the four string forms, escape sequences, and the numeric and boolean
shorthands, and shares no code with rdflib. The set of typed literals the
scanner finds must equal the set the faithful parse reports. If the two readers
disagree the script exits 2 and reports nothing else, because at that point it
cannot tell which of them is wrong.

Exit codes: 0 no fidelity mismatch (or --report-only),
            1 at least one typed literal changed under the runner's settings,
            2 the two readers disagree, so no result from this run is usable.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

try:
    import rdflib
    from rdflib import Graph, Literal
except ImportError as exc:  # pragma: no cover - environment problem
    sys.stderr.write(
        f"literal fidelity: missing dependency ({exc}).\n"
        "Install with: python3 -m pip install -r scripts/requirements.txt\n"
    )
    raise SystemExit(2)

REPO = Path(__file__).resolve().parent.parent
XSD = "http://www.w3.org/2001/XMLSchema#"

# Importing the runner is what applies the runner's literal policy, and that is
# deliberate: the gate below must measure THE RUNNER, not a setting this script
# makes for itself. A check that configured rdflib and then congratulated itself
# on the result would stay green after someone deleted the line in
# `run_conformance.py` that it exists to protect. Importing is side-effect free
# beyond that -- the runner's work is behind `if __name__ == "__main__"`.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_conformance  # noqa: E402,F401  (imported for its rdflib configuration)

RUNNER_NORMALIZE = rdflib.NORMALIZE_LITERALS

# Datatypes Turtle lets a document write without `^^`, and what each shorthand
# means. Included because rdflib normalises these too: `1.2e2` comes back as
# `120.0`, so a scanner that only looked for `^^` would under-report.
SHORTHAND = {
    "integer": XSD + "integer",
    "decimal": XSD + "decimal",
    "double": XSD + "double",
    "boolean": XSD + "boolean",
}

# Ordered longest-first: a DOUBLE is a prefix-compatible extension of a DECIMAL,
# which is a prefix-compatible extension of an INTEGER, so the alternatives must
# be tried in that order or `1.2e2` lexes as the integer `1`.
NUMERIC_RE = re.compile(
    r"[+-]?(?:"
    r"(?:[0-9]+\.[0-9]*|\.[0-9]+|[0-9]+)[eE][+-]?[0-9]+"  # DOUBLE
    r"|[0-9]*\.[0-9]+"                                     # DECIMAL
    r"|[0-9]+"                                             # INTEGER
    r")"
)

ECHAR = {"t": "\t", "b": "\b", "n": "\n", "r": "\r", "f": "\f",
         '"': '"', "'": "'", "\\": "\\"}

# Characters that end a bare token (PNAME, keyword, number) in Turtle.
TOKEN_BREAK = set(" \t\r\n#<>\"'[](),;.^@")


class ScanError(Exception):
    """The scanner could not read the document. Never swallowed: an unreadable
    document is not a document with no literals in it."""


def _unescape(text: str) -> str:
    """Turtle ECHAR + UCHAR, so the scanner reports the same string rdflib does."""
    out = []
    i = 0
    while i < len(text):
        c = text[i]
        if c != "\\":
            out.append(c)
            i += 1
            continue
        if i + 1 >= len(text):
            raise ScanError("string ends in a backslash")
        n = text[i + 1]
        if n in ECHAR:
            out.append(ECHAR[n])
            i += 2
        elif n == "u":
            out.append(chr(int(text[i + 2:i + 6], 16)))
            i += 6
        elif n == "U":
            out.append(chr(int(text[i + 2:i + 10], 16)))
            i += 10
        else:
            raise ScanError(f"unknown escape \\{n}")
    return "".join(out)


def scan_typed_literals(text: str) -> set[tuple[str, str]]:
    """Read every typed literal out of Turtle source, lexical form untouched.

    Returns a set of (datatype IRI, lexical form) pairs. A set, not a list,
    because the thing it is compared against is an rdflib Graph, which is a set
    of triples and so cannot represent a duplicate.

    This is a scanner, not a parser: it does not check that the document is
    well-formed Turtle, only that it can tell literals apart from everything
    that can look like one -- text inside comments, inside IRI references, and
    inside other strings, and digits inside prefixed names.
    """
    prefixes: dict[str, str] = {}
    found: set[tuple[str, str]] = set()
    i, n = 0, len(text)

    def skip_ws(j: int) -> int:
        """Whitespace and comments, which may be interleaved between a string
        and the `^^` that types it."""
        while j < n:
            if text[j] in " \t\r\n":
                j += 1
            elif text[j] == "#":
                while j < n and text[j] != "\n":
                    j += 1
            else:
                break
        return j

    def read_iriref(j: int) -> tuple[str, int]:
        end = text.find(">", j + 1)
        if end < 0:
            raise ScanError(f"unterminated IRI reference at offset {j}")
        return _unescape(text[j + 1:end]), end + 1

    def read_pname(j: int) -> tuple[str, int]:
        start = j
        while j < n and text[j] not in TOKEN_BREAK:
            j += 1
        # A prefixed name may legally contain a dot; a statement-terminating dot
        # may not be followed by a name character. Give back any trailing dots.
        tok = text[start:j]
        while tok.endswith("."):
            tok = tok[:-1]
            j -= 1
        return tok, j

    def resolve(tok: str) -> str:
        pfx, _, local = tok.partition(":")
        if pfx + ":" not in prefixes and pfx not in prefixes:
            raise ScanError(f"prefix {pfx!r} used before it was declared")
        base = prefixes.get(pfx + ":", prefixes.get(pfx, ""))
        return base + local

    while i < n:
        c = text[i]

        if c in " \t\r\n":
            i += 1
            continue

        if c == "#":
            while i < n and text[i] != "\n":
                i += 1
            continue

        if c == "<":
            _iri, i = read_iriref(i)
            continue

        if c in "\"'":
            # Longest form first, or `"""a"""` lexes as an empty string.
            for q in (c * 3, c):
                if text.startswith(q, i):
                    quote = q
                    break
            j = i + len(quote)
            body = []
            while True:
                if j >= n:
                    raise ScanError(f"unterminated string literal at offset {i}")
                if text[j] == "\\":
                    body.append(text[j:j + 2])
                    j += 2
                    continue
                if text.startswith(quote, j):
                    break
                body.append(text[j])
                j += 1
            lexical = _unescape("".join(body))
            i = j + len(quote)

            after = skip_ws(i)
            if text.startswith("^^", after):
                after = skip_ws(after + 2)
                if after < n and text[after] == "<":
                    dt, i = read_iriref(after)
                else:
                    tok, i = read_pname(after)
                    dt = resolve(tok)
                found.add((dt, lexical))
            elif after < n and text[after] == "@":
                # Language tag: rdf:langString, not a typed literal.
                _tok, i = read_pname(after + 1)
            continue

        if c == "@" or (
            text[i:i + 6].upper() == "PREFIX" and i + 6 < n and text[i + 6] in " \t\r\n"
        ) or (
            text[i:i + 4].upper() == "BASE" and i + 4 < n and text[i + 4] in " \t\r\n"
        ):
            tok, j = read_pname(i + 1 if c == "@" else i)
            keyword = tok.lower()
            if keyword in ("prefix", "base"):
                j = skip_ws(j)
                if keyword == "prefix":
                    name, j = read_pname(j)
                    j = skip_ws(j)
                    iri, j = read_iriref(j)
                    prefixes[name if name.endswith(":") else name + ":"] = iri
                else:
                    _iri, j = read_iriref(j)
                i = j
                continue
            i = j
            continue

        if c in "[](),;.":
            i += 1
            continue

        if c == "^":
            # A `^^` not preceded by a string is not something Turtle allows;
            # step over the caret rather than guess.
            i += 1
            continue

        # A bare token: a number, `true`/`false`, `a`, a prefixed name, or a
        # blank node label. Only the first two are literals.
        #
        # Numbers are matched BEFORE prefixed names and directly against the
        # source, not against a token read by `read_pname`. `read_pname` gives
        # back trailing dots, because a dot may end a statement -- and `412.5`
        # would come back as `412`, silently splitting one decimal into two
        # integers. The number is accepted only if what follows it cannot be
        # part of a name, so `pots:v1` and `sh:pattern` are never read as digits.
        m = NUMERIC_RE.match(text, i)
        if m and (m.end() >= n or text[m.end()] in TOKEN_BREAK):
            tok = m.group(0)
            if "e" in tok or "E" in tok:
                found.add((SHORTHAND["double"], tok))
            elif "." in tok:
                found.add((SHORTHAND["decimal"], tok))
            else:
                found.add((SHORTHAND["integer"], tok))
            i = m.end()
            continue

        tok, j = read_pname(i)
        if not tok:
            i += 1
            continue
        if tok in ("true", "false"):
            found.add((SHORTHAND["boolean"], tok))
        i = j

    return found


def typed_literals(graph: Graph) -> set[tuple[str, str]]:
    return {
        (str(o.datatype), str(o))
        for _s, _p, o in graph
        if isinstance(o, Literal) and o.datatype is not None
    }


def normalised_form(lexical: str, datatype: str) -> str:
    """What rdflib's default settings would store for this authored literal."""
    return str(Literal(lexical, datatype=rdflib.URIRef(datatype), normalize=True))


def turtle_documents(repo: Path) -> list[tuple[str, str]]:
    """Every Turtle document this repository publishes, as (label, source).

    JSON fixtures carry their Turtle in `expectedOutput.turtle`, so the file
    itself is not Turtle and a directory walk for `*.ttl` would miss most of the
    corpus.
    """
    docs: list[tuple[str, str]] = []
    for path in sorted((repo / "fixtures").rglob("*.json")):
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        if not isinstance(doc, dict):
            continue
        turtle = (doc.get("expectedOutput") or {}).get("turtle") if isinstance(
            doc.get("expectedOutput"), dict
        ) else None
        if isinstance(turtle, str) and turtle.strip():
            rel = path.relative_to(repo)
            docs.append((f"{rel}#expectedOutput.turtle", turtle))
    for root in ("fixtures", "reference-patient-pod"):
        for path in sorted((repo / root).rglob("*.ttl")):
            docs.append((str(path.relative_to(repo)), path.read_text(encoding="utf-8")))
    return docs


def parse(source: str, label: str, normalize: bool) -> Graph:
    previous = rdflib.NORMALIZE_LITERALS
    rdflib.NORMALIZE_LITERALS = normalize
    try:
        graph = Graph()
        graph.parse(
            data=source,
            format="turtle",
            publicID=f"https://conformance.cascadeprotocol.org/fixtures/{label}#",
        )
        return graph
    finally:
        rdflib.NORMALIZE_LITERALS = previous


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--repo", type=Path, default=REPO)
    ap.add_argument(
        "--report-only", action="store_true",
        help="print the report and exit 0 even when literals were rewritten. "
             "For running this as an observation rather than a gate.",
    )
    args = ap.parse_args(argv)

    docs = turtle_documents(args.repo)
    if not docs:
        sys.stderr.write(
            "literal fidelity: SELF-CHECK FAILED: no Turtle documents found under "
            f"{args.repo}. A check with no corpus reports success on everything.\n"
        )
        return 2

    disagreements: list[str] = []
    unparseable: list[str] = []
    infidelity: list[tuple[str, str, str, str]] = []
    exposure: list[tuple[str, str, str, str]] = []
    exposure_files: set[str] = set()
    exposure_by_datatype: Counter = Counter()
    literal_total = 0

    for label, source in docs:
        try:
            faithful = parse(source, label, normalize=False)
        except Exception as exc:
            unparseable.append(f"{label}: {str(exc).replace(chr(10), ' ')[:140]}")
            continue

        # Reader 2: the file bytes, with no rdflib in the loop.
        try:
            scanned = scan_typed_literals(source)
        except ScanError as exc:
            disagreements.append(f"{label}: scanner failed: {exc}")
            continue

        parsed = typed_literals(faithful)
        if scanned != parsed:
            for item in sorted(parsed - scanned):
                disagreements.append(f"{label}: parser saw a literal the file scan did not: {item}")
            for item in sorted(scanned - parsed):
                disagreements.append(f"{label}: file scan saw a literal the parser did not: {item}")
            continue

        literal_total += len(parsed)
        for s, p, o in faithful:
            if not isinstance(o, Literal) or o.datatype is None:
                continue
            authored = str(o)
            rewritten = normalised_form(authored, str(o.datatype))
            if rewritten != authored:
                exposure.append((label, str(p), authored, rewritten))
                exposure_files.add(label)
                exposure_by_datatype[str(o.datatype).rsplit("#", 1)[-1]] += 1

        # The gate: the runner's own settings, whatever they currently are.
        try:
            as_the_runner_sees_it = parse(source, label, normalize=RUNNER_NORMALIZE)
        except Exception as exc:
            unparseable.append(f"{label}: {str(exc).replace(chr(10), ' ')[:140]}")
            continue
        runner_view = typed_literals(as_the_runner_sees_it)
        if runner_view != parsed:
            for s, p, o in faithful:
                if not isinstance(o, Literal) or o.datatype is None:
                    continue
                authored = str(o)
                rewritten = normalised_form(authored, str(o.datatype))
                if rewritten != authored:
                    infidelity.append((label, str(p), authored, rewritten))

    print("Typed-literal fidelity")
    print("=" * 72)
    print(f"  rdflib version            : {rdflib.__version__}")
    print(f"  runner NORMALIZE_LITERALS : {RUNNER_NORMALIZE}  "
          f"(read from scripts/run_conformance.py)")
    print(f"  Turtle documents scanned  : {len(docs)}")
    print(f"  typed literals compared   : {literal_total}")
    print("")

    if unparseable:
        print("Documents that did not parse (not this script's business, but not silent either)")
        print("-" * 72)
        for line in unparseable:
            print(f"  {line}")
        print("")

    if disagreements:
        print("READER DISAGREEMENT -- no result from this run is usable")
        print("-" * 72)
        for line in disagreements[:40]:
            print(f"  {line}")
        if len(disagreements) > 40:
            print(f"  ... and {len(disagreements) - 40} more")
        print("")
        print("The file scanner and the lexically-faithful parse do not agree on what")
        print("this repository contains. Fix that before reading any number above.")
        return 2

    print("Exposure: what rdflib's DEFAULT settings would rewrite (reported, not gated)")
    print("-" * 72)
    print(f"  ground triples rewritten  : {len(exposure)}")
    print(f"  documents affected        : {len(exposure_files)} of {len(docs)}")
    for dt, count in sorted(exposure_by_datatype.items(), key=lambda kv: (-kv[1], kv[0])):
        print(f"      {count:5d}  xsd:{dt}")
    if exposure:
        print("  first ten, as (document, predicate, authored, rdflib):")
        for label, pred, authored, rewritten in exposure[:10]:
            print(f"      {label}")
            print(f"        {pred}")
            print(f"          authored {authored!r} -> rdflib {rewritten!r}")
    print("")

    print("Fidelity: what the runner's current settings actually rewrite (GATED)")
    print("-" * 72)
    print(f"  typed literals changed    : {len(infidelity)}")
    for label, pred, authored, rewritten in infidelity[:40]:
        print(f"      {label}")
        print(f"        {pred}")
        print(f"          authored {authored!r} -> rdflib {rewritten!r}")
    if len(infidelity) > 40:
        print(f"      ... and {len(infidelity) - 40} more")
    print("")

    if infidelity:
        print(f"Verdict: LITERALS REWRITTEN  ({len(infidelity)} changed across "
              f"{len({m[0] for m in infidelity})} document(s))")
        if args.report_only:
            print("(--report-only: exiting 0 anyway)")
            return 0
        return 1

    print(f"Verdict: LEXICALLY FAITHFUL  ({literal_total} typed literals, none changed; "
          f"{len(exposure)} would change under rdflib's defaults)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
