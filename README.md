# Cascade Protocol Conformance Test Suite

Version: 1.2
Date: 2026-08-08

## Overview

The Cascade Protocol Conformance Test Suite validates that SDK implementations correctly serialize health data to RDF/Turtle format according to the Cascade Protocol specification. It provides a standardized set of test fixtures that any SDK (Swift, Python, JavaScript, etc.) can run against to verify conformance.

The suite also ships its own runner (`scripts/run_conformance.py`), which executes every fixture against the SHACL shapes published by `spec`, and a ratchet (`scripts/check_baseline.py`) that gates CI on whether anything got worse — or got better without [`KNOWN_FAILURES.json`](KNOWN_FAILURES.json) being updated. See [Running the suite](#running-the-suite), [Current status](#current-status) and [What a green CI run means](#what-a-green-ci-run-means).

### Record fixtures (`fixtures/*.json`)

Every count below is derived from the fixture files themselves, not maintained by hand.

| Data Type | Fixture Prefix | Count | Description |
|---|---|---|---|
| Medication | `med-` | 11 | Prescription drugs, OTC medications |
| Condition | `cond-` | 7 | Medical conditions, diagnoses |
| Lab Result | `lab-` | 13 | Laboratory test observations |
| Vital Sign | `vital-` | 7 | Clinical vital sign observations |
| Allergy | `allergy-` | 6 | Allergies and intolerances |
| Patient Profile | `profile-` | 5 | Demographics and identity |
| Coverage | `coverage-` | 4 | Insurance and coverage |
| Pod Structure | `pod-` | 4 | LDP containers and manifests |
| Immunization | `imm-` | 3 | Vaccine records |
| Family History | `fam-` | 3 | Family medical history |
| Procedure | `proc-` | 4 | Procedures and surgical history |
| Social History | `social-` | 3 | Social/behavioral history: consumer-reported (health v2.4) and EHR-extracted (clinical v1.8) |
| Daily Activity Snapshot | `dailyactivity-` | 2 | One day of activity metrics from a wearable (health v2.5) |
| Daily Sleep Snapshot | `dailysleep-` | 2 | One night of sleep metrics from a wearable (health v2.5) |
| Daily Vital Reading | `dailyvital-` | 2 | One day's aggregated vital sign inside a history container (health v2.5) |
| Proxy Agent | `proxy-` | 2 | Caregiver-proxy actor operating a patient's Pod (core v3.3) |
| Benefit Statement | `benefit-` | 1 | Explanation of benefits |
| Claim Record | `claim-` | 1 | Insurance claim records |
| Denial Notice | `denial-` | 1 | Coverage denial notices |
| Implanted Device | `device-` | 1 | Implanted medical devices |
| Encounter | `encounter-` | 3 | Clinical encounters and visits |
| Imaging Study | `imaging-` | 1 | Imaging studies and results |
| Medication Administration | `medadmin-` | 1 | Medication administration events |
| Supplement | `supp-` | 2 | Dietary supplements and OTC products (`clinical:SupplementShape`) |
| Data Absence | `absent-` | 3 | A record whose primary value is absent for a stated reason (`cascade:dataAbsentReason`, core v3.6) |
| **Total** | | **92** | 25 data types |

### RDF fixtures (`fixtures/**/*.ttl`)

71 further fixtures are Turtle files rather than JSON records. They carry their polarity in the filename and are executed by the same runner. There are **three** polarities:

| Suffix | Polarity | The claim |
|---|---|---|
| `*.VALID.ttl`, or no suffix | positive | No `sh:Violation`. |
| `*.INVALID.ttl` | negative | At least one `sh:Violation`; something rejects it. |
| `*.WARN.ttl` | warn | At least one `sh:Warning` **and** no `sh:Violation`; something notices it and nothing rejects it. |

The third exists because Cascade shapes report a value that existing data already carries at `sh:Warning` rather than rejecting it — the ratchet `core` v3.5 wrote down, and which `clinical` v1.16 applied to five `clinical:status` bindings. Neither of the other two polarities can state that claim: `.INVALID.ttl` fails such a fixture with `NO_VIOLATION`, and `.VALID.ttl` passes it while reporting nothing about the warning, which is the same silence the binding was added to end.

| Directory | Count | Positive | Negative | Warn | What it covers |
|---|---|---|---|---|---|
| `core/` | 15 | 6 | 8 | 1 | AIExtracted provenance; the `core` v3.5 ORIGIN axis (`cascade:sourceIdentity`); and the `core` v3.7 `cascade:Attachment` store — one negative per Violation constraint, three path/digest negatives, and the media-type warning |
| `clinical/` | 12 | 7 | 2 | 3 | Social history in Turtle form, and the `clinical` v1.16 batch: encounter facts and participation, the two document status axes and the two attribution axes, and three of the five `clinical:status` binding sets |
| `genomics/phenopackets/` | 9 | 9 | 0 | 0 | GA4GH Phenopacket conversion oracles |
| `genomics/fhir-genomics-ig/` | 7 | 7 | 0 | 0 | HL7 Genomics Reporting IG bundle conversion oracles |
| `evidence/` | 7 | 3 | 4 | 0 | Assertion facet / evidence grounding rules (evidence v1-draft) |
| `workbench/` | 7 | 4 | 3 | 0 | Filing, notes and follow-ups (workbench v1-draft) |
| `health/` | 4 | 2 | 0 | 2 | The two `clinical:status` binding sets that `health.shapes.ttl` owns (`health` v2.8) |
| `genomics/clinvar/` | 4 | 4 | 0 | 0 | ClinVar VCV conversion oracles |
| `advisory/` | 2 | 2 | 0 | 0 | Advisory reclassification oracles (advisory v1-draft) |
| `coverage/` | 2 | 1 | 1 | 0 | `coverage:status` (`coverage` v1.5) |
| `genomics/vcf/` | 1 | 1 | 0 | 0 | VCF conversion oracle |
| `genomics/vrs/` | 1 | 1 | 0 | 0 | GA4GH VRS allele conversion oracle |
| **Total** | **71** | **47** | **18** | **6** | |

**Grand total: 163 executable fixtures** (92 JSON + 71 Turtle), which is the number `scripts/run_conformance.py` reports on every run. The JSON table above had drifted from the files by seven — `absent-` was missing entirely and `lab-` and `proc-` were behind — and is corrected here against a run.

A further 94 files under `fixtures/` are the source side of those conversion oracles (`*.input.xml`, `*.input.json`, `*.input.ldpatch`, `*.input.vcf.gz`), their `*.gaps.json` sidecars, and `INVENTORY.md` files. They carry no RDF of their own, so the SHACL runner does not execute them; each has a corresponding `*.expected.ttl` that it does execute. The runner reports them by category on every run so the number is auditable rather than assumed.

## Running the suite

```bash
python3 -m pip install -r scripts/requirements.txt

# Clone the pinned spec revision (see scripts/SPEC_PIN for the commit)
git clone https://github.com/the-cascade-protocol/spec.git ../spec
git -C ../spec checkout "$(grep '^commit=' scripts/SPEC_PIN | cut -d= -f2)"

# 1. the truth: execute and report every fixture
python3 scripts/run_conformance.py --spec-dir ../spec --json results.json

# 2. the gate: did anything get worse, or better without the record being updated?
python3 scripts/check_baseline.py --results results.json
```

`--spec-dir` also reads from `$CASCADE_SPEC_DIR`, and defaults to `../spec`. Useful flags: `--json PATH` writes machine-readable results, `--select GLOB` restricts the run while debugging (CI never uses it), `--quiet` suppresses the text report.

The two commands answer different questions and the split is deliberate. The runner reports what is true and exits `1` while any fixture fails, which it will for as long as the vocabulary has gaps. The gate decides whether that is acceptable, by comparing the report against the enumerated baseline in [`KNOWN_FAILURES.json`](KNOWN_FAILURES.json). Nothing is filtered out of the report to make the gate pass.

Runner exit codes: `0` every fixture passed, `1` one or more failed, `2` the runner's own self-checks failed and no fixture result should be believed.
Gate exit codes: `0` the ratchet held, `1` the ratchet was violated in either direction, `2` the gate could not run or the baseline is unusable.

### What the runner actually does

There is no SDK under test here, so the runner takes the second of the two mechanisms described under [Testing Strategy](#testing-strategy): it validates the Turtle each fixture declares (`expectedOutput.turtle` for a JSON fixture, the file body for a `.ttl` fixture) against the union of every `*.shapes.ttl` in the pinned `spec` checkout.

Loading all shapes at once rather than one file per `vocabulary` field is deliberate. A single record routinely spans namespaces (a `clinical:Medication` also carries `cascade:` provenance), and SHACL only fires a shape whose target actually matches, so a wider shapes graph can only ever evaluate more constraints, never fewer.

`rdfs:subClassOf` axioms are extracted from the ontology files and supplied as the ontology graph, because `sh:targetClass` is subclass-aware ([SHACL 2.1.3.1](https://www.w3.org/TR/shacl/#targetClass)). Only the subclass triples are mixed in, not whole ontologies, so ontology terms cannot themselves become focus nodes.

### Why a fixture with no applicable shape is a failure, not a pass

Validating a record whose class no shape targets returns `conforms = true` after evaluating zero constraints. That result is indistinguishable from real conformance, and it is the failure mode this runner exists to prevent.

So the runner computes, independently of the SHACL engine, how many constraint parameters were reachable from a matched focus node, and reports `UNSHAPED` when that count is zero. Failure reasons are:

| Reason | Meaning |
|---|---|
| `VIOLATIONS` | Positive or warn fixture; the shapes reported at least one `sh:Violation` |
| `NO_VIOLATION` | Negative fixture; the shapes reported none, so nothing rejected it |
| `NO_WARNING` | Warn fixture; the shapes reported no `sh:Warning`, so nothing noticed it |
| `UNSHAPED` | No shape targets any subject, so zero constraints ran |
| `NO_TURTLE` | The fixture declares no RDF body, so there is nothing to validate |
| `PARSE_ERROR` | The fixture's RDF does not parse |
| `READ_ERROR` | The file could not be read or decoded |
| `SCHEMA_INVALID` | The fixture JSON does not satisfy `schema/fixture-schema.json` |

The runner aborts the whole run (exit 2) rather than reporting anything if the shapes graph is empty, if a shapes or ontology file fails to parse, if no shape declares a constraint, or if zero constraints were evaluated across the entire suite. Each of those is a way a runner can report PASS while testing nothing.

`scripts/selftest_runner.py` is the proof that the above holds. It mutates fixtures, shapes and baselines in temporary directories and asserts the runner and the gate notice: that breaking one constraint produces exactly one violation naming that constraint, that repairing a negative fixture is reported as unexpectedly conforming, that repairing what a warn fixture warns about is reported as `NO_WARNING`, that a warn fixture which trips a Violation fails rather than passing, that deleting a shape yields `UNSHAPED` rather than `PASS`, that a drifted `spec` checkout is refused, and that the ratchet fails **in both directions** — on a failure the baseline does not list, and on a baselined failure that starts passing. No mutated copy is ever written inside the repository. Run it with `python3 scripts/selftest_runner.py --spec-dir ../spec`.

### The spec pin

`scripts/SPEC_PIN` names the exact `spec` commit the suite is validated against, and the runner refuses to run against any other checkout. Without a pin the suite silently tracks whatever is on `spec` `main`, so a run that passed yesterday can pass today for a different reason, or start failing because of a vocabulary change nobody in this repository chose to adopt.

To re-pin:

1. Check out the new `spec` revision and note its full SHA and its `VOCAB_VERSIONS` line.
2. Update `commit=` and `vocab=` in `scripts/SPEC_PIN`.
3. Run `python3 scripts/run_conformance.py --spec-dir ../spec --json results.json` and record the before and after counts in the pull request. A re-pin that changes the pass count is a vocabulary change with consequences, and the pull request should say what they are.
4. Re-measure `KNOWN_FAILURES.json` in the same commit: set its `specPin` to the new SHA and reconcile its entries. The gate refuses to run when the two disagree, and names the exact edit. Different shapes give different results, so **a re-pin requiring a baseline update is the ratchet working**, not a failure.
5. Update `VOCAB_VERSIONS` at the repository root only once fixtures actually cover the new vocabulary. The pin and `VOCAB_VERSIONS` answer different questions: the pin says what the shapes came from, `VOCAB_VERSIONS` says what the fixtures cover.

The runner also refuses a checkout that sits at the pinned commit but has uncommitted changes under `ontologies/`: the shapes being validated would then not be the ones that SHA describes, and every result would be attributed to a revision that does not describe them.

`--allow-spec-drift` bypasses both checks for local experiments against unreleased vocabulary. CI never passes it, the results file records that it was used, and the gate refuses to ratchet a run that used it — a drifted run is not evidence about the pinned vocabulary.

### Continuous integration

`.github/workflows/conformance.yml` runs on every push to `main` and every pull request, in two jobs:

- **runner mutation tests** runs `scripts/selftest_runner.py`. This job is green and must stay green. If it goes red, no result from the other job means anything.
- **fixture suite** runs every fixture, prints the whole report, then ratchets it against `KNOWN_FAILURES.json`. The suite itself is still red and the report still names all 28 failures; the job is green only while nothing has got worse and nothing has got better without the record being updated. See [What a green CI run means](#what-a-green-ci-run-means).

## Current status

As of the pinned revision in `scripts/SPEC_PIN` (`spec` at core 3.7, health 2.8, clinical 1.16, coverage 1.5, checkup 3.3):

```
passed  135
failed   28
skipped   0
total   163        63,353 constraint checks evaluated
```

The first execution of these fixtures, against the older `spec` revision the pin
originally named, was **43 passed / 68 failed / 0 skipped / 111 total**. Three things
moved it: 19 fixtures started passing on their own when `spec` defined and shaped the
classes they had always asserted; 22 were fixed here; 50 were added. No fixture that
passed has since failed. The remaining 28 break down as:

| Reason | Count | Owned by | Notes |
|---|---|---|---|
| `VIOLATIONS` | 16 | `spec` (4), undecided (12) | Fifteen are conversion oracles under `fixtures/genomics/`; the sixteenth is `clinical/status-laboratoryreport-in-progress.WARN.ttl`, described under [A defect the v1.16 batch found](#a-defect-the-v116-batch-found) below. Each `.expected.ttl` records what the importer currently emits from the neighbouring `.input.json`, so a violation means either the importer must emit more or the shape must ask less. Three are settled — GA4GH Phenopackets do not carry a date of birth or a biological sex, so `cascade:PatientProfileShape` is stricter than the source format can satisfy. The other twelve need triage one at a time. |
| `UNSHAPED` | 9 | `spec` | A class a fixture asserts and no shape targets, so zero constraints run: `clinical:ImplantedDevice`, `clinical:MedicationAdministration`, `clinical:ImagingStudy`, `clinical:CoverageRecord`, `coverage:ClaimRecord`, `coverage:BenefitStatement`, `coverage:DenialNotice`, `ldp:BasicContainer` (`pod-001`, `pod-003`). **None of these is fixable in this repository**: the missing artefact is a shape in `spec`. `proc-001/002/003` left this row at core 3.6 / health 2.7 / clinical 1.15: they asserted `health:ProcedureRecord`, which `health.ttl` never defined, and clinical v1.15 ruled `clinical:` the canonical procedure spelling, so they were retargeted onto `clinical:Procedure` and all three now run against real constraints. |
| `NO_TURTLE` | 3 | `conformance` | Comment-only placeholder `.ttl` files: two unauthored advisory oracles, and `genomics/phenopackets/biosamples-SAMN05324082.expected.ttl`, which is deliberately empty because it asserts `detect() === false` — not a SHACL assertion, so it needs a different home. |

Each of the 28 is enumerated in [`KNOWN_FAILURES.json`](KNOWN_FAILURES.json) with the
constraint it violates and the repo that owns the fix.

### A defect the v1.16 batch found

`clinical` v1.16 states that all five of its `clinical:status` bindings are
`sh:Warning`, so an out-of-set status is reported and never rejected. That holds on
`clinical:ClinicalDocumentShape` and **fails on every class that reaches it through
`sh:node`**. SHACL defines conformance as an *empty* result set, so a nested
`sh:Warning` makes the value node non-conforming and the outer `sh:node` constraint
then reports a `sh:Violation` at its own default severity.

All six document subtypes are affected — `LaboratoryReport`, `ProgressNote`,
`DischargeSummary`, `ConsultationNote`, `ImagingReport`, `VisitSummary` — and the
escalation applies to `clinical:documentReferenceStatus` as well as to
`clinical:status`. On `ProgressNote` the underlying warning is not even reported, only
an opaque `NodeConstraintComponent`, so a reader cannot tell which field was wrong.

Reproduced on two independent engines, which is what rules out an implementation
quirk: pyshacl 0.30.1 (this runner) and cascade-cli 0.17.0 (rdf-validate-shacl) agree
on the verdict, and both agree the `ClinicalDocument` twin is only warned.

`clinical/status-laboratoryreport-in-progress.WARN.ttl` asserts what the release
*says* rather than what the shapes currently do, and is baselined under `ownedBy:
spec`. The ratchet fails in both directions, so when `spec` fixes the severity the
entry must be removed in the same commit.

The six fixtures added for core v3.5 were measured in both directions before they
were committed. Against the previous pin (`spec` 9461fa9, core 3.4) the two negatives
report `NO_VIOLATION` — nothing rejects them, because `cascade:SourceIdentityShape`
does not exist there. Against the pin now named, both are rejected and all four
positives pass. A negative fixture that has never been observed red is not a test.

`clinical:Encounter` was on the `UNSHAPED` list until clinical v1.14 shaped it.
`encounter-001` had been reporting `conforms=true` while evaluating **zero**
constraints; it now evaluates 29, and its baseline entry is removed. That is the
shape of every entry on this list: the fixture was always correct, and the thing
missing was a shape.

### What a green CI run means

**Not "everything passes".** The suite is red on its own terms and the runner's report
says so on every run, naming every failure. The *job* is green when the ratchet holds:

- a failure appears that `KNOWN_FAILURES.json` does not list → **red**, naming it;
- a listed failure starts **passing** → **red**, telling you to remove the entry.

The second is why this is a ratchet and not a suppression list. A baseline that only
catches new failures grows and never shrinks; one that also fails when the truth
improves can only shrink deliberately. Entries are keyed on `(fixture, reason)`, so a
fixture that goes `UNSHAPED` → `VIOLATIONS` fails the gate even though it was already
failing — that is a new fact about the world.

The baseline never grows on its own. Adding an entry is an explicit committed edit
carrying an `ownedBy`. `check_baseline.py --regenerate` exists, writes anything new as
`ownedBy: "UNASSIGNED"`, and the gate refuses to pass while any entry is unassigned;
**using it needs justifying in the pull request.** The gate also exits 2 rather than
green if the baseline is missing or unparseable, if the run evaluated zero constraints,
if the run used `--allow-spec-drift`, or if the baseline was measured against a
different `spec` revision than the run used.

**Advancing `scripts/SPEC_PIN` is expected to require a baseline update, and that is
the mechanism working, not a failure.** Different shapes produce different results:
`spec` PR #13, for instance, tightens `genomics:CopyNumberVariantShape`, which adds a
violation to `genomics/phenopackets/retinoblastoma.expected.ttl`. Re-measure the
baseline in the same commit that moves the pin; the gate names the one-line fix.

**None of this permits weakening the runner.** Do not skip a fixture, relax an
assertion, or soften a shape to make a fixture pass. Do not baseline a failure this
repository could fix — that is what the `ownedBy` field is for and why 13 of the 31 say
`spec`. A runner that passes everything is a runner that tests nothing, which is the
state this repository was in before it had one.

Both ratchet directions, and every one of the exit-2 refusals, are mutation-tested in
`scripts/selftest_runner.py` and run in CI.

### A negative fixture is the only one that can catch a validator that stopped validating

Until this suite was first executed, **19 of its 20 negative fixtures declared
`expectedOutput.turtle: ""`**. A shapes-based runner validates that string, so those
19 were validating an empty graph: they reported the same result no matter what the
shapes said. Only `proxy-002` worked. Each now carries the serialization of its own
`input`, defect included, and is rejected by the constraint its `shaclConstraintViolated`
field names — verified one fixture at a time, and verified again by repairing only the
named defect and confirming the rejection goes away.

Where a class has no shape, a negative fixture is not merely missing but **impossible**:
there is no constraint to violate, so the fixture would evaluate zero constraints and
assert nothing. That is why seven of the data types above still have a positive fixture
and no negative. It is a vocabulary gap, not a fixture-authoring gap, and adding an
inert negative would hide it rather than close it.

`fixtures/evidence/` (7 of 7) and `fixtures/workbench/` (7 of 7) pass cleanly, and both
include negative fixtures the shapes correctly reject, which is what a healthy fixture
set looks like.

## Fixture Format

Each fixture is a JSON file conforming to `schema/fixture-schema.json`. Here is an annotated example:

```json
{
  "id": "med-001",
  "description": "Happy path: Active prescription medication (Lisinopril) with core required fields from EHR import",
  "dataType": "Medication",
  "vocabulary": "clinical",
  "input": {
    "id": "urn:uuid:med0-0001-aaaa-bbbb-ccccddddeeee",
    "type": "MedicationRecord",
    "medicationName": "Lisinopril",
    "isActive": true,
    "dataProvenance": "ClinicalGenerated",
    "schemaVersion": "1.3",
    "dose": "20 mg",
    "frequency": "once daily",
    "route": "oral",
    "provenanceClass": "healthKitFHIR"
  },
  "expectedOutput": {
    "turtle": "@prefix cascade: <https://ns.cascadeprotocol.org/core/v1#> ...",
    "validationMode": "shacl-valid"
  },
  "shouldAccept": true,
  "tags": ["happy-path", "clinical", "ehr-import"]
}
```

### Field Reference

| Field | Required | Description |
|---|---|---|
| `id` | Yes | Unique fixture ID in format `{prefix}-{number}` (e.g., `med-001`) |
| `description` | Yes | Human-readable description of what this fixture tests |
| `dataType` | Yes | One of: `Medication`, `Condition`, `Allergy`, `LabResult`, `VitalSign`, `PatientProfile`, `Immunization`, `Coverage`, `PodStructure`, `SocialHistoryRecord`, `ProxyAgent`, ... (full enum in `schema/fixture-schema.json`) |
| `vocabulary` | Yes | Primary namespace: `health`, `clinical`, `core`, `coverage`, `cascade` |
| `input` | Yes | Plain JSON object representing the data an SDK would receive before serialization |
| `expectedOutput.turtle` | Yes | Expected RDF/Turtle output with namespace prefix declarations |
| `expectedOutput.validationMode` | Yes | `shacl-valid` or `exact-match` |
| `shouldAccept` | Yes | `true` for valid inputs, `false` for inputs that should be rejected |
| `tags` | Yes | Array of classification tags for filtering |
| `shaclConstraintViolated` | Conditional | Required when `shouldAccept` is `false`; describes which SHACL constraint is violated |
| `notes` | No | Optional explanatory notes |

### Input JSON Format

The `input` field represents data as a plain JSON object that an SDK would receive before serialization. Field names use camelCase mappings of the Turtle predicates:

- `clinical:drugName` becomes `medicationName`
- `cascade:dataProvenance` becomes `dataProvenance` (value is the local name, e.g., `"ClinicalGenerated"`)
- `cascade:schemaVersion` becomes `schemaVersion`
- `clinical:drugCode` (multiple values) becomes `drugCodes` (array of URIs)
- `health:affectsVitalSigns` (RDF list) becomes `affectsVitalSigns` (array of strings)

Nested blank nodes (e.g., emergency contacts, addresses) are represented as nested JSON objects.

### Namespace Prefixes

All Turtle output uses these canonical namespace prefixes:

```turtle
@prefix cascade: <https://ns.cascadeprotocol.org/core/v1#> .
@prefix health:  <https://ns.cascadeprotocol.org/health/v1#> .
@prefix clinical: <https://ns.cascadeprotocol.org/clinical/v1#> .
@prefix coverage: <https://ns.cascadeprotocol.org/coverage/v1#> .
@prefix fhir:    <http://hl7.org/fhir/> .
@prefix sct:     <http://snomed.info/sct/> .
@prefix loinc:   <http://loinc.org/rdf#> .
@prefix rxnorm:  <http://www.nlm.nih.gov/research/umls/rxnorm/> .
@prefix xsd:     <http://www.w3.org/2001/XMLSchema#> .
@prefix prov:    <http://www.w3.org/ns/prov#> .
```

## Running Fixtures Against an SDK

The pseudocode below is for SDK implementers wiring these fixtures into their own test suite. It is not what `scripts/run_conformance.py` does: that runner has no SDK to call, so it takes the post-validation branch only. See [What the runner actually does](#what-the-runner-actually-does).

### General Algorithm

```
for each fixture file in fixtures/:
    fixture = parse JSON file

    if fixture.shouldAccept:
        # Positive test case
        output = sdk.serialize(fixture.input)

        if fixture.expectedOutput.validationMode == "shacl-valid":
            assert shacl_validate(output, appropriate_shapes_file) has no Violations
        else if fixture.expectedOutput.validationMode == "exact-match":
            assert normalize(output) == normalize(fixture.expectedOutput.turtle)
    else:
        # Negative test case
        assert sdk.serialize(fixture.input) raises ValidationError
        # OR
        output = sdk.serialize(fixture.input)
        assert shacl_validate(output, appropriate_shapes_file) reports Violation
```

### Pseudocode (Python)

```python
import json
import glob
from pathlib import Path

def run_conformance_suite(sdk, shapes_dir, fixtures_dir):
    """Run all conformance fixtures against an SDK implementation."""
    results = {"passed": 0, "failed": 0, "errors": []}

    for fixture_path in sorted(glob.glob(f"{fixtures_dir}/*.json")):
        with open(fixture_path) as f:
            fixture = json.load(f)

        try:
            if fixture["shouldAccept"]:
                # Serialize the input
                turtle_output = sdk.serialize(
                    data_type=fixture["dataType"],
                    data=fixture["input"]
                )

                if fixture["expectedOutput"]["validationMode"] == "shacl-valid":
                    # Validate against SHACL shapes
                    shapes_file = get_shapes_file(fixture["vocabulary"], shapes_dir)
                    violations = shacl_validate(turtle_output, shapes_file)
                    assert len(violations) == 0, f"SHACL violations: {violations}"

                elif fixture["expectedOutput"]["validationMode"] == "exact-match":
                    # Normalize and compare
                    expected = normalize_turtle(fixture["expectedOutput"]["turtle"])
                    actual = normalize_turtle(turtle_output)
                    assert expected == actual, f"Output mismatch"

                results["passed"] += 1
            else:
                # Negative test: expect failure
                try:
                    turtle_output = sdk.serialize(
                        data_type=fixture["dataType"],
                        data=fixture["input"]
                    )
                    # If serialization succeeds, SHACL validation should fail
                    shapes_file = get_shapes_file(fixture["vocabulary"], shapes_dir)
                    violations = shacl_validate(turtle_output, shapes_file)
                    assert len(violations) > 0, \
                        f"Expected SHACL violation: {fixture['shaclConstraintViolated']}"
                    results["passed"] += 1
                except ValidationError:
                    # SDK correctly rejected invalid input
                    results["passed"] += 1

        except Exception as e:
            results["failed"] += 1
            results["errors"].append({
                "fixture": fixture["id"],
                "error": str(e)
            })

    return results

def get_shapes_file(vocabulary, shapes_dir):
    """Map vocabulary to SHACL shapes file."""
    mapping = {
        "health": "health.shapes.ttl",
        "clinical": "clinical.shapes.ttl",
        "core": "core.shapes.ttl",
        "coverage": "coverage.shapes.ttl",
        "cascade": "core.shapes.ttl",
    }
    return Path(shapes_dir) / mapping[vocabulary]
```

### Pseudocode (Swift)

```swift
func runConformanceSuite(fixtures: [URL], serializer: CascadeSerializer) -> TestResults {
    var results = TestResults()

    for fixtureURL in fixtures {
        let fixture = try JSONDecoder().decode(ConformanceFixture.self, from: Data(contentsOf: fixtureURL))

        if fixture.shouldAccept {
            // Positive test: serialization should succeed and output should be SHACL-valid
            let turtleOutput = try serializer.serialize(dataType: fixture.dataType, input: fixture.input)

            switch fixture.expectedOutput.validationMode {
            case .shaclValid:
                let violations = SHACLValidator.validate(turtleOutput, shapes: shapesFile(for: fixture.vocabulary))
                XCTAssertTrue(violations.isEmpty, "Fixture \(fixture.id): \(violations)")
            case .exactMatch:
                let expected = normalizeTurtle(fixture.expectedOutput.turtle)
                let actual = normalizeTurtle(turtleOutput)
                XCTAssertEqual(expected, actual, "Fixture \(fixture.id): output mismatch")
            }
            results.passed += 1
        } else {
            // Negative test: serialization should fail or produce SHACL-invalid output
            XCTAssertThrowsError(try serializer.serialize(dataType: fixture.dataType, input: fixture.input))
            results.passed += 1
        }
    }
    return results
}
```

## Normalization Algorithm for Exact-Match Mode

When `validationMode` is `"exact-match"`, the test runner must normalize both the expected and actual Turtle output before comparison. This prevents false failures due to whitespace differences, triple ordering, or blank node label differences.

The normalization algorithm follows **RDFC-1.0** (RDF Dataset Canonicalization):

### Steps

1. **Parse to quads.** Parse both Turtle strings into sets of RDF quads (subject, predicate, object, graph). Use any standards-compliant Turtle parser.

2. **Canonicalize blank nodes.** Apply the RDFC-1.0 algorithm (formerly URDNA2015) to assign deterministic identifiers to blank nodes. This ensures that blank node labels like `_:b0` and `_:b1` are assigned consistently based on the graph structure, not the order they appear in the serialization.

3. **Sort triples.** Sort all quads lexicographically by (subject, predicate, object, graph). For URI terms, sort by the full URI string. For literals, sort by (value, datatype, language tag).

4. **Normalize whitespace.** Remove trailing whitespace from each line. Normalize line endings to `\n`. Remove empty lines between triples.

5. **Compare.** The normalized quad sets must be identical.

### Reference Implementations

- **JavaScript:** Use the `rdf-canonize` npm package (implements RDFC-1.0)
- **Python:** Use `rdflib` with `rdflib.compare.isomorphic()` for graph comparison
- **Java:** Use Apache Jena's `IsoMatcher` for graph isomorphism
- **Swift:** Parse with a Turtle parser and compare sorted triple sets

### Example

Given two serializations of the same data:

```turtle
# Serialization A
<urn:uuid:abc> a clinical:Medication ;
    clinical:drugName "Aspirin" ;
    clinical:status "active" .

# Serialization B (different triple order, extra whitespace)
<urn:uuid:abc> clinical:status "active" ;
    a clinical:Medication ;
    clinical:drugName "Aspirin" .
```

After normalization, both produce the same canonical form and the comparison passes.

## Negative Test Cases

Negative fixtures (`shouldAccept: false`) verify that an SDK correctly rejects invalid input or produces output that fails SHACL validation. Each negative fixture includes a `shaclConstraintViolated` field describing which constraint is violated.

### Derivation from SHACL Shapes

Negative test cases are systematically derived from the SHACL shapes files:

1. **Required field violations:** For each `sh:minCount 1` constraint, create a fixture missing that field.
   - Example: `med-008` omits `medicationName` (maps to `clinical:drugName`, required by `MedicationShape`)

2. **Pattern violations:** For each `sh:pattern` constraint, create a fixture with an invalid format.
   - Example: `med-010` uses `schemaVersion: "1"` instead of `"1.3"` (violates `^[0-9]+\.[0-9]+$`)

3. **Enumeration violations:** For each `sh:in` constraint, create a fixture with a value not in the allowed list.
   - Example: `vital-007` uses `vitalType: "painScore"` (not in the enumerated vital types)

4. **Length violations:** For each `sh:minLength` constraint, create a fixture with an empty string.
   - Example: `allergy-006` uses `allergen: ""` (violates `sh:minLength 1`)

### SHACL Shapes Reference

The SHACL shapes files that define validation constraints live in the `spec` repository, at the commit named in `scripts/SPEC_PIN`:

- `ontologies/clinical/v1/clinical.shapes.ttl` -- Medication, Allergy, LabResult, Condition, VitalSign, Immunization
- `ontologies/health/v1/health.shapes.ttl` -- HealthProfile, wellness statistics
- `ontologies/core/v1/core.shapes.ttl` -- PatientProfile, Address, EmergencyContact, PharmacyInfo, ProxyAgent
- `ontologies/coverage/v1/coverage.shapes.ttl` -- InsurancePlan
- `ontologies/{advisory,evidence,genomics,workbench}/v1-draft/*.shapes.ttl` -- draft vocabularies exercised by the RDF fixtures

The runner loads all of them. Ten shapes files, 5,485 triples, 99 node shapes at the pinned revision.

### Testing Strategy

SDKs may handle negative cases in two ways:

1. **Pre-validation:** The SDK validates input before serialization and throws a `ValidationError` (or equivalent) for invalid data. The test passes if the error is raised.

2. **Post-validation:** The SDK serializes the data regardless, and a SHACL validator detects the violation. The test passes if SHACL validation reports at least one `sh:Violation`.

Both approaches are acceptable. The conformance suite verifies the outcome (invalid data is detected), not the mechanism.

## Coverage Matrix

Categories per data type, for the 76 record fixtures. Each fixture carries exactly one of these five tags, so the columns sum to the row total. Counts are derived from the fixtures' own `tags` arrays.

| Data Type | Happy Path | Full Fields | Multi-Code | Provenance | Negative | Total |
|---|---|---|---|---|---|---|
| Medication | 2 | 1 | 2 | 3 | 3 | 11 |
| Condition | 2 | 1 | 1 | 1 | 2 | 7 |
| Lab Result | 3 | 1 | 2 | 1 | 3 | 10 |
| Vital Sign | 2 | 1 | 1 | 1 | 2 | 7 |
| Allergy | 2 | 1 | -- | 1 | 2 | 6 |
| Patient Profile | 1 | 1 | -- | 1 | 2 | 5 |
| Coverage | 1 | 1 | -- | 1 | 1 | 4 |
| Pod Structure | 2 | -- | -- | -- | 2 | 4 |
| Immunization | 2 | -- | -- | -- | 1 | 3 |
| Family History | 1 | 1 | -- | -- | 1 | 3 |
| Procedure | 1 | 1 | -- | -- | 1 | 3 |
| Social History | 1 | 1 | -- | 1 | -- | 2 |
| Proxy Agent | 1 | -- | -- | -- | 1 | 2 |
| Benefit Statement | 1 | -- | -- | -- | -- | 1 |
| Claim Record | 1 | -- | -- | -- | -- | 1 |
| Denial Notice | 1 | -- | -- | -- | -- | 1 |
| Implanted Device | 1 | -- | -- | -- | -- | 1 |
| Encounter | 2 | -- | -- | -- | 1 | 3 |
| Imaging Study | 1 | -- | -- | -- | -- | 1 |
| Medication Administration | 1 | -- | -- | -- | -- | 1 |
| **Total** | **29** | **10** | **6** | **10** | **22** | **76** |

The 40 RDF fixtures are not tagged this way; their split is 33 positive and 7 negative, tabulated above.

This matrix has never covered every record fixture: rows for `DailyActivitySnapshot`,
`DailyVitalReading` and `DailySleepSnapshot` are absent, and `social-001` and
`dailyactivity-001` each carry two category tags rather than one, so 76 of the 83 record
fixtures are represented here. That predates this table's current numbers and is left as
it stands rather than quietly re-derived; the fixture counts in the tables at the top of
this file are the complete ones.

### Tag Descriptions

- **happy-path**: Minimal valid record with required fields and common optional fields
- **full-fields**: Record with all possible properties populated
- **multi-code**: Record with multiple terminology system codes (e.g., RxNorm + SNOMED CT)
- **provenance**: Tests specific provenance scenarios (EHRVerified, SelfReported, DeviceGenerated)
- **negative**: Invalid input that should be rejected or fail SHACL validation
- **required-field**: Negative test missing a required field (`sh:minCount 1`)
- **enum-constraint**: Negative test with an invalid enumerated value (`sh:in`)
- **pattern-constraint**: Negative test with an invalid format (`sh:pattern` or `sh:minLength`)

## Data Sources

Test data is derived from two sources:

1. **Reference Patient Pod** (`reference-patient-pod/`): Realistic synthetic patient data for Alex Rivera, a 52-year-old male with hypertension, diabetes, asthma, and hyperlipidemia. Positive fixtures extract real records from these TTL files.

   **This repository is the pod's canonical home.** `cascade-cli` reads it from here. `cascadeprotocol.org` publishes a generated copy at `/reference-patient-pod/`, kept byte-identical by that repo's `scripts/sync-reference-pod.sh` and guarded by its `--check` mode. Change the pod here; a change made anywhere else is drift.

2. **SHACL Shapes Files** (`../spec/ontologies/*/v1/*.shapes.ttl`, at the revision named in `scripts/SPEC_PIN`): Machine-readable validation constraints. Negative fixtures are systematically derived by violating each `sh:Violation`-severity constraint.

   **This suite observes `sh:Violation` only, and that is a real coverage boundary.** The runner passes `allow_warnings=True` to pyshacl and `extract_violations()` discards every result whose `sh:resultSeverity` is not `sh:Violation`. So a constraint published at `sh:Warning` or `sh:Info` cannot be exercised here at all: no negative fixture can be written against it, because the fixture would report zero violations and the runner would score it as a failure forever. Deleting such a constraint from `spec` outright leaves this suite completely green, which was confirmed by mutation rather than assumed.

   This matters because the ratchet pattern the vocabularies use — publish a new constraint at `sh:Warning`, raise it to `sh:Violation` a release later once the warning is observably absent from conforming output — puts every constraint in its *first* release outside this suite's reach. Two such constraints exist at the pinned revision: `clinical:VitalSignShape`'s interpretation value set and `clinical:ProcedureNameSpellingShape`. Their behaviour is verified against the real validator elsewhere, and each becomes testable here on the release that raises it to `sh:Violation`. When that happens, add the negative fixture in the same change that raises the severity.

## Adding New Fixtures

To add a new fixture:

1. Create a JSON file in `fixtures/` following the naming convention `{prefix}-{NNN}.json`
2. Validate the fixture against `schema/fixture-schema.json`
3. For positive fixtures, ensure the Turtle output is SHACL-valid against the appropriate shapes file
4. For negative fixtures, include the `shaclConstraintViolated` field **and** populate `expectedOutput.turtle` with the invalid serialization. An empty `turtle` gives a shapes-based runner nothing to reject, which is why 19 existing negative fixtures currently fail.
5. Update the coverage matrix in this README
6. Run `python3 scripts/run_conformance.py --spec-dir ../spec` and confirm the new fixture is reported, with a non-zero constraint check count. A new fixture that lands in `UNSHAPED` is not testing anything yet.

Fixture IDs must be unique and follow the pattern `^[a-z]+-[0-9]{3}$`.
