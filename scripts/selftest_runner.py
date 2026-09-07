#!/usr/bin/env python3
"""Mutation tests for run_conformance.py and scripts/check_baseline.py.

The question this file exists to answer is: *what would these report if the
thing they claim to check were absent?* A conformance runner that reports PASS
because it loaded no shapes, matched no focus nodes, or swallowed a parse error
is worse than no runner at all, because it manufactures confidence. A ratcheting
baseline that only ever goes green is the same failure wearing a different hat.

The baseline cases matter most, because the gate is the only thing in this repo
whose job is to decide that a red suite is acceptable. Four properties are
asserted, and the second is the one that makes the mechanism legitimate rather
than a suppression list:

  * a failure not in the baseline fails the gate;
  * a baselined failure that starts PASSING fails the gate, so the list shrinks
    deliberately instead of calcifying;
  * the key is (fixture, reason), so a fixture that changes how it fails is
    treated as the new fact it is;
  * a missing, unparseable, pin-mismatched or unowned baseline is exit 2 and can
    never read as success.

Every case builds its input in a temporary directory and asserts on
machine-readable output. **Nothing here mutates a tracked file**, and no mutated
copy is ever written inside the repo.

Run:  python3 scripts/selftest_runner.py --spec-dir /path/to/spec
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import rdflib
from rdflib import BNode

# One case here removes a shape at the RDF level and writes the result back into
# a STAGED COPY of the spec checkout, so this file parses and re-serialises a
# shapes graph. rdflib rewrites the lexical form of a typed literal on parse
# unless this is off, which would leave the staged shapes differing from the real
# ones in more than the one shape the test meant to remove. The runner disables
# it for the same reason; see the comment in run_conformance.py.
rdflib.NORMALIZE_LITERALS = False

REPO = Path(__file__).resolve().parent.parent
RUNNER = REPO / "scripts" / "run_conformance.py"
GATE = REPO / "scripts" / "check_baseline.py"

# The fixture the positive-direction mutation tests operate on. Chosen because
# clinical:MedicationShape is one of the most constrained shapes in the suite,
# so a single removed triple is unambiguously attributable.
POSITIVE_FIXTURE = "med-001.json"
POSITIVE_MUTATION_TARGET = 'clinical:drugName "Lisinopril" ;'
POSITIVE_EXPECTED_CONSTRAINT = "clinical:MedicationShape / path clinical:drugName / MinCountConstraintComponent"

# The negative fixture the inverse-direction test repairs. proxy-002 is the only
# negative fixture in the suite that carries Turtle at all (see README).
NEGATIVE_FIXTURE = "proxy-002.json"
NEGATIVE_REPAIR_ANCHOR = 'cascade:proxyScope "read-only" ;'
NEGATIVE_REPAIR = 'cascade:proxyScope "read-only" ;\n    cascade:proxyRelationship "spouse" ;'

# An unrelated, independently-shaped fixture staged alongside a mutated one. The
# runner aborts a whole run that evaluates zero constraints, so a single-fixture
# tree whose only fixture is unshaped never reaches per-fixture reporting. The
# companion keeps the suite-level guard honest while the per-fixture assertion
# is made.
COMPANION_FIXTURE = "profile-001.json"

# The `.WARN.` fixture the warning-polarity tests operate on. Chosen because it
# is a single node whose warning comes from a shape of its own
# (cascade:AttachmentMediaTypeShape) while every Violation-severity constraint on
# it lives in a different shape (cascade:AttachmentShape), so "repair the
# warning" and "introduce a violation" are two independent one-line mutations and
# neither can be mistaken for the other.
WARN_FIXTURE = "core/attachment-no-media-type.WARN.ttl"
WARN_EXPECTED_SHAPE = "cascade:AttachmentMediaTypeShape"
# Repairing what the fixture is warning about: state the media type.
WARN_REPAIR_ANCHOR = '    cascade:hashAlgorithm "sha-256" ;'
WARN_REPAIR = (
    '    cascade:hashAlgorithm "sha-256" ;\n'
    '    cascade:attachmentMediaType "application/pdf" ;'
)
# Introducing a Violation alongside the warning: uppercase the digest, which
# cascade:contentHash's sh:pattern rejects.
WARN_VIOLATE_FROM = "8dd3c6b5f593b25cb9dc0094d67323d16c3bbc9584eda019726a38dd2cc7a471"
WARN_VIOLATE_TO = "8DD3C6B5F593B25CB9DC0094D67323D16C3BBC9584EDA019726A38DD2CC7A471"


class SelfTestFailure(AssertionError):
    pass


def run_runner(spec_dir: Path, fixtures_dir: Path, extra=()) -> tuple[int, dict, str]:
    """Invoke the runner and return (exit code, parsed JSON results, stderr)."""
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
        json_path = Path(tmp.name)
    try:
        proc = subprocess.run(
            [
                sys.executable, str(RUNNER),
                "--spec-dir", str(spec_dir),
                "--fixtures-dir", str(fixtures_dir),
                "--json", str(json_path),
                "--quiet", "--allow-spec-drift",
                *extra,
            ],
            capture_output=True, text=True,
        )
        payload = {}
        if json_path.exists() and json_path.stat().st_size:
            payload = json.loads(json_path.read_text(encoding="utf-8"))
        return proc.returncode, payload, proc.stderr
    finally:
        json_path.unlink(missing_ok=True)


def result_for(payload: dict, path: str) -> dict:
    for entry in payload.get("fixtures", []):
        if entry["path"] == path:
            return entry
    raise SelfTestFailure(f"runner returned no result for {path}")


def stage_fixture(tmp: Path, name: str, transform=None, companion: str | None = None) -> Path:
    """Copy one fixture into an isolated tree, optionally mutating its Turtle."""
    fixtures = tmp / "fixtures"
    fixtures.mkdir(parents=True, exist_ok=True)
    names = [name] + ([companion] if companion else [])
    for candidate in names:
        doc = json.loads((REPO / "fixtures" / candidate).read_text(encoding="utf-8"))
        if transform is not None and candidate == name:
            doc["expectedOutput"]["turtle"] = transform(doc["expectedOutput"]["turtle"])
        (fixtures / candidate).write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    return fixtures


def stage_ttl_fixture(tmp: Path, relpath: str, transform=None) -> Path:
    """Copy one `.ttl` fixture into an isolated tree, optionally mutating it.

    Kept separate from stage_fixture() rather than folded into it: a JSON fixture
    carries its polarity in `shouldAccept` and its Turtle in a field, while a
    `.ttl` fixture carries its polarity in its FILENAME and is its own body. The
    filename is load-bearing here, so it is preserved verbatim including the
    `.WARN.` infix the polarity is read from.
    """
    fixtures = tmp / "fixtures"
    dest = fixtures / relpath
    dest.parent.mkdir(parents=True, exist_ok=True)
    body = (REPO / "fixtures" / relpath).read_text(encoding="utf-8")
    if transform is not None:
        body = transform(body)
    dest.write_text(body, encoding="utf-8")
    return fixtures


def stage_spec(tmp: Path, spec_dir: Path, transform=None) -> Path:
    """Copy the spec ontologies into an isolated tree, optionally mutating them."""
    dest = tmp / "spec"
    shutil.copytree(spec_dir / "ontologies", dest / "ontologies")
    if transform is not None:
        transform(dest)
    return dest


# --------------------------------------------------------------------------
# Cases
# --------------------------------------------------------------------------

def case_unmutated_positive_passes(spec_dir, tmp):
    """Control for the positive mutation: the fixture as authored must pass."""
    fixtures = stage_fixture(tmp, POSITIVE_FIXTURE)
    code, payload, _ = run_runner(spec_dir, fixtures)
    entry = result_for(payload, POSITIVE_FIXTURE)
    if entry["outcome"] != "pass":
        raise SelfTestFailure(f"{POSITIVE_FIXTURE} should pass unmutated, got {entry['reason']}")
    if entry["constraintChecks"] <= 0:
        raise SelfTestFailure(
            f"{POSITIVE_FIXTURE} passed with {entry['constraintChecks']} constraint checks. "
            "A pass that evaluated nothing is the defect this runner exists to catch."
        )
    if code != 0:
        raise SelfTestFailure(f"expected exit 0 on an all-pass tree, got {code}")
    return f"{POSITIVE_FIXTURE} passes with {entry['constraintChecks']} constraint checks"


def case_positive_mutation_is_caught(spec_dir, tmp):
    """Break exactly one constraint: the runner must name that constraint."""
    fixtures = stage_fixture(
        tmp, POSITIVE_FIXTURE,
        transform=lambda t: t.replace(POSITIVE_MUTATION_TARGET, "", 1),
    )
    code, payload, _ = run_runner(spec_dir, fixtures)
    entry = result_for(payload, POSITIVE_FIXTURE)
    if entry["outcome"] != "fail" or entry["reason"] != "VIOLATIONS":
        raise SelfTestFailure(
            f"removing {POSITIVE_MUTATION_TARGET!r} should fail with VIOLATIONS, "
            f"got {entry['outcome']}/{entry['reason']}"
        )
    if not any(POSITIVE_EXPECTED_CONSTRAINT in v for v in entry["violations"]):
        raise SelfTestFailure(
            f"failure did not name the broken constraint. Expected "
            f"{POSITIVE_EXPECTED_CONSTRAINT!r}, got {entry['violations']}"
        )
    if len(entry["violations"]) != 1:
        raise SelfTestFailure(
            "one broken constraint should produce exactly one violation, got "
            f"{len(entry['violations'])}: {entry['violations']}"
        )
    if code == 0:
        raise SelfTestFailure("runner exited 0 on a tree containing a failure")
    return f"1 constraint broken, 1 violation reported, named: {POSITIVE_EXPECTED_CONSTRAINT}"


def case_unrepaired_negative_passes(spec_dir, tmp):
    """Control for the inverse mutation: the negative fixture is rejected today."""
    fixtures = stage_fixture(tmp, NEGATIVE_FIXTURE)
    _code, payload, _ = run_runner(spec_dir, fixtures)
    entry = result_for(payload, NEGATIVE_FIXTURE)
    if entry["outcome"] != "pass":
        raise SelfTestFailure(f"{NEGATIVE_FIXTURE} should pass, got {entry['reason']}")
    if not entry["violations"]:
        raise SelfTestFailure("a negative fixture that passes must have violated something")
    return f"{NEGATIVE_FIXTURE} rejected by: {entry['violations'][0].split(' :: ')[0]}"


def case_repaired_negative_is_reported(spec_dir, tmp):
    """Repair what the negative fixture is negative about: it must be flagged."""
    fixtures = stage_fixture(
        tmp, NEGATIVE_FIXTURE,
        transform=lambda t: t.replace(NEGATIVE_REPAIR_ANCHOR, NEGATIVE_REPAIR, 1),
    )
    _code, payload, _ = run_runner(spec_dir, fixtures)
    entry = result_for(payload, NEGATIVE_FIXTURE)
    if entry["outcome"] != "fail" or entry["reason"] != "NO_VIOLATION":
        raise SelfTestFailure(
            "repairing the violated constraint should be reported as unexpectedly "
            f"conforming (NO_VIOLATION), got {entry['outcome']}/{entry['reason']}"
        )
    return "repaired negative reported as NO_VIOLATION (unexpectedly conforming)"


def case_unmutated_warn_passes(spec_dir, tmp):
    """Control for the warning mutations: the `.WARN.` fixture as authored passes.

    A pass here is only meaningful if it is a pass for the RIGHT reason, so this
    also asserts that the warning exists, that it names the shape that issued it,
    and that nothing rejected the record. A `.WARN.` fixture that passed with an
    empty warning list would be the vacuous green this runner exists to prevent.
    """
    fixtures = stage_ttl_fixture(tmp, WARN_FIXTURE)
    code, payload, _ = run_runner(spec_dir, fixtures)
    entry = result_for(payload, WARN_FIXTURE)
    if entry["polarity"] != "warn":
        raise SelfTestFailure(
            f"a filename carrying '.WARN.' must be read as warn polarity, "
            f"got {entry['polarity']!r}"
        )
    if entry["outcome"] != "pass":
        raise SelfTestFailure(f"{WARN_FIXTURE} should pass unmutated, got {entry['reason']}")
    if not entry["warnings"]:
        raise SelfTestFailure(
            "a warn fixture that passes must have been warned about something. "
            "An empty warning list is a pass that asserted nothing."
        )
    if entry["violations"]:
        raise SelfTestFailure(
            f"a warn fixture must NOT be rejected, got violations: {entry['violations']}"
        )
    if not any(WARN_EXPECTED_SHAPE in w for w in entry["warnings"]):
        raise SelfTestFailure(
            f"warning did not name {WARN_EXPECTED_SHAPE!r}, got {entry['warnings']}"
        )
    if code != 0:
        raise SelfTestFailure(f"expected exit 0 on an all-pass tree, got {code}")
    return f"warned by {WARN_EXPECTED_SHAPE}, 0 violations, {entry['constraintChecks']} checks"


def case_repaired_warn_is_reported(spec_dir, tmp):
    """Repair what the warn fixture is warning about: it must be flagged.

    This is the mutation that makes the whole `.WARN.` polarity mean something.
    Without it, a fixture nothing warns about would sail through as a pass, which
    is the failure mode a two-polarity runner had for warning-severity
    constraints: `.VALID.ttl` passes whether or not anything fires.
    """
    fixtures = stage_ttl_fixture(
        tmp, WARN_FIXTURE,
        transform=lambda t: t.replace(WARN_REPAIR_ANCHOR, WARN_REPAIR, 1),
    )
    code, payload, _ = run_runner(spec_dir, fixtures)
    entry = result_for(payload, WARN_FIXTURE)
    if entry["outcome"] != "fail" or entry["reason"] != "NO_WARNING":
        raise SelfTestFailure(
            "repairing the warned-about property should be reported as NO_WARNING, "
            f"got {entry['outcome']}/{entry['reason']} with warnings {entry['warnings']}"
        )
    if code == 0:
        raise SelfTestFailure("runner exited 0 on a tree containing a failure")
    return "repaired warn fixture reported as NO_WARNING (nothing noticed it)"


def case_warn_fixture_that_violates_is_caught(spec_dir, tmp):
    """The other half: a warn fixture must be REPORTED, never REJECTED.

    A `.WARN.` fixture that also trips a Violation is not evidence about the
    warning. The record would be thrown out, and the value the fixture exists to
    exercise never reaches a reader, so a runner that accepted it would let a
    Violation-severity regression hide inside a warning fixture.
    """
    fixtures = stage_ttl_fixture(
        tmp, WARN_FIXTURE,
        transform=lambda t: t.replace(WARN_VIOLATE_FROM, WARN_VIOLATE_TO),
    )
    code, payload, _ = run_runner(spec_dir, fixtures)
    entry = result_for(payload, WARN_FIXTURE)
    if entry["outcome"] != "fail" or entry["reason"] != "VIOLATIONS":
        raise SelfTestFailure(
            "a warn fixture that trips a Violation must fail with VIOLATIONS, "
            f"got {entry['outcome']}/{entry['reason']}"
        )
    if not entry["warnings"]:
        raise SelfTestFailure(
            "the warning should still be reported alongside the violation, so the "
            "report says what the fixture was for"
        )
    if code == 0:
        raise SelfTestFailure("runner exited 0 on a tree containing a failure")
    return "warn fixture carrying a Violation fails with VIOLATIONS, warning still reported"


def case_absent_shape_is_not_a_pass(spec_dir, tmp):
    """The standing review question, executed.

    Delete EVERY shape that reaches the fixture and re-run. If the runner still
    said PASS, every green result in this suite would be meaningless.

    Both shapes have to go, and which ones they are is a property of the fixture
    rather than of the runner. med-001.json is a clinical:Medication, so
    clinical:MedicationShape reaches it by sh:targetClass; it also carries
    health:startDate, so clinical:MedicationDateSpellingShape (clinical v1.19)
    reaches it by sh:targetSubjectsOf. Removing only the first leaves one shape
    still matching, so the runner reports PASS at a non-zero check count and is
    CORRECT to: constraints did run. Stripping one shape and asserting UNSHAPED
    would be asserting something false about the fixture, so the mutation strips
    both and the case keeps meaning what it says.
    """
    def strip_medication_shapes(dest: Path):
        # Remove the shapes at the RDF level rather than by text surgery: they
        # span blank lines, so cutting on whitespace leaves broken Turtle
        # and the run aborts for the wrong reason.
        from rdflib import Graph, URIRef

        path = dest / "ontologies" / "clinical" / "v1" / "clinical.shapes.ttl"
        graph = Graph()
        graph.parse(path, format="turtle")
        pending = [
            URIRef("https://ns.cascadeprotocol.org/clinical/v1#MedicationShape"),
            URIRef("https://ns.cascadeprotocol.org/clinical/v1#MedicationDateSpellingShape"),
        ]
        seen = set()
        while pending:
            node = pending.pop()
            if node in seen:
                continue
            seen.add(node)
            for _p, obj in list(graph.predicate_objects(node)):
                if isinstance(obj, BNode):
                    pending.append(obj)
            graph.remove((node, None, None))
        path.write_text(graph.serialize(format="turtle"), encoding="utf-8")

    fixtures = stage_fixture(tmp, POSITIVE_FIXTURE, companion=COMPANION_FIXTURE)
    spec_copy = stage_spec(tmp, spec_dir, strip_medication_shapes)
    code, payload, _ = run_runner(spec_copy, fixtures)
    entry = result_for(payload, POSITIVE_FIXTURE)
    if entry["outcome"] == "pass":
        raise SelfTestFailure(
            "removing every shape that reaches the fixture still produced PASS. "
            "The runner is reporting conformance it never checked."
        )
    if entry["reason"] != "UNSHAPED" or entry["constraintChecks"] != 0:
        raise SelfTestFailure(
            f"expected UNSHAPED with 0 constraint checks, got {entry['reason']} "
            f"with {entry['constraintChecks']}"
        )
    if code == 0:
        raise SelfTestFailure("runner exited 0 with an unshaped fixture")
    return "both reaching shapes removed -> UNSHAPED (0 checks), not PASS"


def case_unparseable_fixture_is_an_error(spec_dir, tmp):
    """A fixture whose RDF does not parse must fail, never count as a pass."""
    fixtures = stage_fixture(
        tmp, POSITIVE_FIXTURE,
        transform=lambda t: t + "\n<urn:broken> clinical:drugName \n",
        companion=COMPANION_FIXTURE,
    )
    _code, payload, _ = run_runner(spec_dir, fixtures)
    entry = result_for(payload, POSITIVE_FIXTURE)
    if entry["outcome"] != "fail" or entry["reason"] != "PARSE_ERROR":
        raise SelfTestFailure(
            f"unparseable Turtle should be PARSE_ERROR, got {entry['outcome']}/{entry['reason']}"
        )
    return "unparseable Turtle -> PARSE_ERROR"


def case_empty_shapes_aborts(spec_dir, tmp):
    """No shapes loaded must abort the run, not validate everything vacuously."""
    def empty_all_shapes(dest: Path):
        for path in dest.glob("ontologies/*/*/*.shapes.ttl"):
            path.write_text("# emptied by selftest\n", encoding="utf-8")

    fixtures = stage_fixture(tmp, POSITIVE_FIXTURE)
    spec_copy = stage_spec(tmp, spec_dir, empty_all_shapes)
    code, _payload, stderr = run_runner(spec_copy, fixtures)
    if code != 2:
        raise SelfTestFailure(f"empty shapes should abort with exit 2, got {code}")
    if "SELF-CHECK FAILED" not in stderr:
        raise SelfTestFailure(f"abort did not explain itself: {stderr!r}")
    return "empty shapes -> exit 2, SELF-CHECK FAILED"


def case_malformed_shapes_aborts(spec_dir, tmp):
    """A shapes file that does not parse must abort, not silently shrink the constraint set."""
    def corrupt(dest: Path):
        path = dest / "ontologies" / "clinical" / "v1" / "clinical.shapes.ttl"
        path.write_text(path.read_text(encoding="utf-8") + "\nclinical:Broken a sh:NodeShape \n",
                        encoding="utf-8")

    fixtures = stage_fixture(tmp, POSITIVE_FIXTURE)
    spec_copy = stage_spec(tmp, spec_dir, corrupt)
    code, _payload, stderr = run_runner(spec_copy, fixtures)
    if code != 2 or "does not parse" not in stderr:
        raise SelfTestFailure(
            f"a malformed shapes file should abort with exit 2, got {code}: {stderr[:200]!r}"
        )
    return "malformed shapes file -> exit 2, named the file"


def pinned_commit() -> str:
    text = (REPO / "scripts" / "SPEC_PIN").read_text(encoding="utf-8")
    return next(l.split("=", 1)[1].strip() for l in text.splitlines() if l.startswith("commit="))


def case_spec_pin_is_enforced(spec_dir, tmp):
    """A spec checkout that is not at the pinned commit must be refused.

    The refusal is staged rather than hoped for. An earlier version of this case
    asserted the refusal only when the caller's own spec checkout happened to sit
    off the pin, and took a weaker "matches the pin, accepted" branch otherwise —
    which became the normal state as soon as the pin was advanced to spec main,
    so the assertion that matters silently stopped running. Here the drifted
    checkout is built: the spec ontologies are copied into a throwaway git repo
    whose HEAD is a fresh commit and therefore cannot equal the pin.
    """
    fixtures = stage_fixture(tmp, POSITIVE_FIXTURE)
    drifted = stage_spec(tmp, spec_dir)
    git = ["git", "-c", "user.email=selftest@example.invalid", "-c", "user.name=selftest",
           "-c", "commit.gpgsign=false", "-C", str(drifted)]
    for cmd in (["init", "--quiet"], ["add", "-A"], ["commit", "--quiet", "-m", "throwaway"]):
        subprocess.run(git + cmd, capture_output=True, text=True, check=True)
    head = subprocess.run(git + ["rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    commit = pinned_commit()
    if not head:
        raise SelfTestFailure("could not stage a drifted spec checkout; git produced no HEAD")
    if head == commit:
        raise SelfTestFailure("staged checkout collided with the pin, which cannot happen")

    proc = subprocess.run(
        [sys.executable, str(RUNNER), "--spec-dir", str(drifted),
         "--fixtures-dir", str(fixtures), "--quiet"],
        capture_output=True, text=True,
        env={**os.environ, "CASCADE_SPEC_DIR": ""},
    )
    if proc.returncode != 2 or "SPEC_PIN" not in proc.stderr:
        raise SelfTestFailure(
            f"spec at {head[:7]} differs from pin {commit[:7]} but the runner returned "
            f"{proc.returncode} instead of refusing: {proc.stderr[:200]!r}"
        )

    # And the inverse: the same checkout must be accepted with --allow-spec-drift,
    # or the refusal above could be any unrelated abort.
    ok = subprocess.run(
        [sys.executable, str(RUNNER), "--spec-dir", str(drifted),
         "--fixtures-dir", str(fixtures), "--quiet", "--allow-spec-drift"],
        capture_output=True, text=True,
        env={**os.environ, "CASCADE_SPEC_DIR": ""},
    )
    if ok.returncode == 2:
        raise SelfTestFailure(
            f"--allow-spec-drift did not lift the refusal: {ok.stderr[:200]!r}"
        )
    return f"staged drifted checkout ({head[:7]}) refused; --allow-spec-drift lifts it"


# --------------------------------------------------------------------------
# Baseline gate cases
# --------------------------------------------------------------------------

def write_baseline(tmp: Path, entries, spec_pin="PIN", name="baseline.json") -> Path:
    path = tmp / name
    path.write_text(json.dumps({
        "$comment": "selftest",
        "specPin": spec_pin,
        "entries": [
            {"fixture": f, "reason": r, "ownedBy": o, "detail": "selftest"}
            for f, r, o in entries
        ],
    }, indent=2) + "\n", encoding="utf-8")
    return path


def write_results(tmp: Path, fixtures, spec_pin="PIN", checks=42, name="results.json") -> Path:
    """A minimal but structurally faithful run_conformance.py --json payload."""
    path = tmp / name
    failed = sum(1 for _p, _r, outcome in fixtures if outcome != "pass")
    path.write_text(json.dumps({
        "specPin": spec_pin,
        "constraintChecks": checks,
        "counts": {
            "passed": len(fixtures) - failed, "failed": failed,
            "skipped": 0, "total": len(fixtures),
        },
        "fixtures": [
            {"path": p, "id": p, "polarity": "positive", "outcome": outcome,
             "reason": reason, "constraintChecks": 7, "types": [], "violations": [], "detail": ""}
            for p, reason, outcome in fixtures
        ],
    }, indent=2) + "\n", encoding="utf-8")
    return path


def run_gate(results: Path, baseline: Path) -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, str(GATE), "--results", str(results), "--baseline", str(baseline)],
        capture_output=True, text=True,
    )
    return proc.returncode, proc.stdout + proc.stderr


def case_ratchet_holds_when_nothing_changed(spec_dir, tmp):
    """Control. An unchanged tree is green — and the baseline was really compared."""
    results = write_results(tmp, [("a.json", "OK", "pass"), ("b.json", "UNSHAPED", "fail")])
    baseline = write_baseline(tmp, [("b.json", "UNSHAPED", "spec")])
    code, out = run_gate(results, baseline)
    if code != 0:
        raise SelfTestFailure(f"unchanged tree should hold the ratchet, got {code}:\n{out}")
    if "baseline entries      : 1" not in out or "still failing as known: 1" not in out:
        raise SelfTestFailure(
            "the gate went green without showing that it compared a non-empty baseline. "
            f"An empty or unread baseline must never read as success:\n{out}"
        )
    return "unchanged tree -> RATCHET HELD, 1 baseline entry compared and matched"


def case_new_failure_fails_the_ratchet(spec_dir, tmp):
    """Direction one: a failure that is not in the baseline must go red, by name."""
    results = write_results(tmp, [
        ("b.json", "UNSHAPED", "fail"),
        ("intruder.json", "VIOLATIONS", "fail"),
    ])
    baseline = write_baseline(tmp, [("b.json", "UNSHAPED", "spec")])
    code, out = run_gate(results, baseline)
    if code != 1:
        raise SelfTestFailure(f"a new failure must fail the gate, got exit {code}:\n{out}")
    if "intruder.json" not in out or "REGRESSION" not in out:
        raise SelfTestFailure(f"gate failed without naming the new failure:\n{out}")
    return "unbaselined failure -> exit 1, REGRESSION, names intruder.json"


def case_unexpected_pass_fails_the_ratchet(spec_dir, tmp):
    """Direction two, and the reason this mechanism is not a suppression list.

    A baselined failure that starts passing must go red, so the list shrinks by
    a deliberate edit rather than quietly describing a world that has moved on.
    """
    results = write_results(tmp, [("b.json", "OK", "pass"), ("c.json", "UNSHAPED", "fail")])
    baseline = write_baseline(tmp, [
        ("b.json", "UNSHAPED", "spec"),
        ("c.json", "UNSHAPED", "spec"),
    ])
    code, out = run_gate(results, baseline)
    if code != 1:
        raise SelfTestFailure(
            f"a baselined fixture that now passes must fail the gate, got exit {code}. "
            f"Without this the baseline is a suppression list:\n{out}"
        )
    if "IMPROVEMENT NOT RECORDED" not in out or "b.json" not in out:
        raise SelfTestFailure(f"gate failed without telling the author to remove b.json:\n{out}")
    if "Remove these entries" not in out:
        raise SelfTestFailure(f"gate did not say what to do about it:\n{out}")
    return "baselined fixture now passes -> exit 1, IMPROVEMENT NOT RECORDED, names b.json"


def case_changed_reason_fails_the_ratchet(spec_dir, tmp):
    """The key is (fixture, reason). A fixture that fails differently is a new fact."""
    results = write_results(tmp, [("b.json", "VIOLATIONS", "fail")])
    baseline = write_baseline(tmp, [("b.json", "UNSHAPED", "spec")])
    code, out = run_gate(results, baseline)
    if code != 1:
        raise SelfTestFailure(
            f"UNSHAPED -> VIOLATIONS on an already-failing fixture must fail the gate, "
            f"got exit {code}. Keying on the fixture alone is how a ratchet starts lying:\n{out}"
        )
    if "UNSHAPED -> VIOLATIONS" not in out:
        raise SelfTestFailure(f"gate did not report the reason change:\n{out}")
    return "same fixture, different reason -> exit 1, reports UNSHAPED -> VIOLATIONS"


def case_unusable_baseline_is_never_success(spec_dir, tmp):
    """Missing, malformed, pin-mismatched or unowned: all exit 2, never green."""
    results = write_results(tmp, [("b.json", "UNSHAPED", "fail")])
    checks = []

    code, out = run_gate(results, tmp / "does-not-exist.json")
    checks.append(("missing", code, "not found" in out))

    bad = tmp / "malformed.json"
    bad.write_text("{ this is not json", encoding="utf-8")
    code2, out2 = run_gate(results, bad)
    checks.append(("malformed", code2, "could not be read" in out2))

    noentries = tmp / "noentries.json"
    noentries.write_text(json.dumps({"specPin": "PIN"}) + "\n", encoding="utf-8")
    code3, out3 = run_gate(results, noentries)
    checks.append(("no entries list", code3, "no `entries`" in out3))

    drifted = write_baseline(tmp, [("b.json", "UNSHAPED", "spec")],
                             spec_pin="OTHER", name="drifted.json")
    code4, out4 = run_gate(results, drifted)
    checks.append(("pin mismatch", code4, "re-measured" in out4))

    unowned = write_baseline(tmp, [("b.json", "UNSHAPED", "UNASSIGNED")], name="unowned.json")
    code5, out5 = run_gate(results, unowned)
    checks.append(("unassigned owner", code5, "graveyard" in out5))

    empty_run = write_results(tmp, [], checks=0, name="emptyrun.json")
    baseline = write_baseline(tmp, [("b.json", "UNSHAPED", "spec")])
    code6, out6 = run_gate(empty_run, baseline)
    checks.append(("degenerate run", code6, "zero executed fixtures" in out6))

    # A run produced with --allow-spec-drift validated against shapes the pin
    # does not name, while still reporting the pinned SHA. Ratcheting it would
    # compare a baseline to evidence about a different vocabulary.
    drifted_run = json.loads(results.read_text(encoding="utf-8"))
    drifted_run["specDrifted"] = True
    drifted_run["specHead"] = "deadbeef"
    drifted_path = tmp / "driftedrun.json"
    drifted_path.write_text(json.dumps(drifted_run, indent=2) + "\n", encoding="utf-8")
    code7, out7 = run_gate(drifted_path, baseline)
    checks.append(("drifted run", code7, "--allow-spec-drift" in out7))

    for label, code, explained in checks:
        if code != 2:
            raise SelfTestFailure(f"{label} baseline returned exit {code}, expected 2")
        if not explained:
            raise SelfTestFailure(f"{label} aborted without explaining itself")
    return f"{len(checks)} unusable-baseline cases all exit 2 and say why"


CASES = [
    ("unmutated positive fixture passes", case_unmutated_positive_passes),
    ("one broken constraint is caught and named", case_positive_mutation_is_caught),
    ("unrepaired negative fixture passes", case_unrepaired_negative_passes),
    ("repaired negative is reported as conforming", case_repaired_negative_is_reported),
    ("unmutated warn fixture passes, warned and unrejected", case_unmutated_warn_passes),
    ("repaired warn is reported as NO_WARNING", case_repaired_warn_is_reported),
    ("warn fixture that violates fails with VIOLATIONS", case_warn_fixture_that_violates_is_caught),
    ("absent shape yields UNSHAPED, not PASS", case_absent_shape_is_not_a_pass),
    ("unparseable fixture is an error", case_unparseable_fixture_is_an_error),
    ("empty shapes graph aborts the run", case_empty_shapes_aborts),
    ("malformed shapes file aborts the run", case_malformed_shapes_aborts),
    ("spec pin is enforced", case_spec_pin_is_enforced),
    ("ratchet holds when nothing changed", case_ratchet_holds_when_nothing_changed),
    ("new failure fails the ratchet", case_new_failure_fails_the_ratchet),
    ("unexpected pass fails the ratchet", case_unexpected_pass_fails_the_ratchet),
    ("changed failure reason fails the ratchet", case_changed_reason_fails_the_ratchet),
    ("unusable baseline is never success", case_unusable_baseline_is_never_success),
]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--spec-dir", default=os.environ.get("CASCADE_SPEC_DIR"))
    args = parser.parse_args(argv)

    spec_dir = Path(args.spec_dir).resolve() if args.spec_dir else (REPO.parent / "spec")
    if not spec_dir.is_dir():
        sys.stderr.write(f"selftest: spec checkout not found at {spec_dir}\n")
        return 2

    print("run_conformance.py mutation tests")
    print("=" * 72)
    failures = 0
    for name, fn in CASES:
        with tempfile.TemporaryDirectory(prefix="cascade-conf-selftest-") as tmpdir:
            try:
                detail = fn(spec_dir, Path(tmpdir))
                print(f"  PASS  {name}")
                print(f"          {detail}")
            except SelfTestFailure as exc:
                failures += 1
                print(f"  FAIL  {name}")
                print(f"          {exc}")
    print("-" * 72)
    print(f"{len(CASES) - failures} passed / {failures} failed / {len(CASES)} total")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
