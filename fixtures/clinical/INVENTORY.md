# Clinical Conformance Fixtures (Inventory)

**Vocabulary covered:** `clinical` v1.4 (`social-history-smoking.ttl`, the
`clinical:` spelling of social history), `clinical` v1.16 (the encounter,
document and status batch below) and `clinical` v1.19 (the medication effective
dates and the deprecated `health:` spellings of them).

## Fixture kind

Standalone SHACL-validation fixtures, not conversion oracles. Each file is
validated directly and carries its polarity in its name:

- `<slug>.VALID.ttl` MUST pass: no `sh:Violation`.
- `<slug>.INVALID.ttl` MUST be rejected: at least one `sh:Violation`.
- `<slug>.WARN.ttl` MUST be **noticed but not rejected**: at least one
  `sh:Warning` AND no `sh:Violation`.

The third polarity is new in this batch and it exists because clinical v1.16
needed it. Five of the release's rulings are `sh:Warning` bindings, per the
ratchet core v3.5 wrote down: a value that existing data already carries is
*reported*, never rejected, and the severity is raised only after a release in
which the warning is observably absent from conforming output. A two-polarity
runner cannot state that claim. `.INVALID.ttl` fails such a fixture with
`NO_VIOLATION`, and `.VALID.ttl` passes it while asserting nothing about the
warning, which is the same silence clinical v1.16 exists to end. See the note at
the top of `scripts/run_conformance.py`.

Every byte is synthetic: invented hospital, clinicians, visit numbers, document
identifiers and dates. The OIDs are under the HL7 example arc.

## Fixtures

### Encounter and participation (clinical v1.16)

| Fixture | Expect | Scenario |
|---|---|---|
| `encounter-inpatient-full.VALID.ttl` | PASS | Every encounter fact the release added, on one inpatient admission: all three `Encounter.class` Coding members, two `encounterReason` values, both `hospitalization` fields, two participations in **different** roles, and two business identifiers in `{system}\|{value}` token form alongside one `sourceRecordId`. Inpatient rather than ambulatory on purpose: `admitSource` and `dischargeDisposition` are the signal that separates an admission from an office visit, and neither is meaningful on a clinic visit. |
| `encounter-participant-standalone.VALID.ttl` | PASS | A `clinical:EncounterParticipant` with nothing pointing at it. Cascade validates a pod **file by file**, so a participation written to a different file from its encounter arrives exactly like this, and `clinical:EncounterParticipantShape` targets the class rather than a path from an encounter. Also carries a second, **local** role code, which an extensibly-bound source may conformantly send. |
| `encounter-participant-two-names.INVALID.ttl` | FAIL | Two individuals on one participation. `Encounter.participant.individual` is 0..1, and this is the corruption the shape's cardinality constraints exist to stop: a reader given two names under one role cannot tell whose the specialty is. Everything else is correct, so only `sh:maxCount` catches it. |
| `encounter-two-admit-sources.INVALID.ttl` | FAIL | Two admission sources on one admission. Violates a cardinality the **release itself chose** on a property that did not exist under v1.15, so the fixture is evidence about this release rather than about older vocabulary. |

### Document status and attribution (clinical v1.16)

| Fixture | Expect | Scenario |
|---|---|---|
| `document-two-statuses-two-authors.VALID.ttl` | PASS | All four axes on one document, each saying something different: `clinical:status` "final" (the content), `clinical:documentReferenceStatus` "current" (the pod's pointer), two `documentAuthorName` values (who wrote it), one `authenticatorName` (who signed it, a third person), and `providerName` at its single permitted value so the repeatable author list is shown coexisting with the `sh:maxCount 1` that was discarding authors. |

### The `clinical:status` bindings (clinical v1.16)

Three of the five binding sets live here; the other two are on `health:` shapes
and are in [`../health/INVENTORY.md`](../health/INVENTORY.md). Each is a PASS
case and a warning case that differ in exactly one respect: membership of the
bound value set.

| Fixture | Expect | Scenario |
|---|---|---|
| `status-vitalsign-final.VALID.ttl` | PASS | `Observation.status`, 8 codes. |
| `status-vitalsign-completed.WARN.ttl` | WARN | "completed" — a real FHIR code on *workflow* resources and in no `Observation.status` value set. What a converter writes when it maps a general "this is done" state onto an observation. |
| `status-clinicaldocument-appended.VALID.ttl` | PASS | **"appended" is the point.** It is one of the six codes in `diagnostic-report-status` and **not** in `composition-status`, so this fixture passes only under the wider set the release deliberately bound to `clinical:ClinicalDocumentShape`. A fixture using "final" would pass under either binding and prove nothing about which was chosen. |
| `status-clinicaldocument-in-progress.WARN.ttl` | WARN | "in-progress" is out of set under the wider binding *and* the narrower one, so this fixture keeps meaning what it means if the ratchet later narrows the DocumentReference-derived subtypes to `composition-status`. |
| `status-laboratoryreport-corrected.VALID.ttl` | PASS | "corrected" is what distinguishes a result that **replaced** an earlier wrong one from the wrong one itself. Also absent from `composition-status`, so it too passes only under the wider set. |
| `status-laboratoryreport-in-progress.WARN.ttl` | WARN **(currently FAILS — see below)** | The same value as the ClinicalDocument twin, on the class that reaches `ClinicalDocumentShape` through `sh:node`. |

### The medication effective dates (clinical v1.19)

`clinical:startDate` and `clinical:endDate` have existed since clinical v1.0 and
no shape named either, while a reference import path wrote the effective period
to `health:startDate` and `health:endDate` — predicates the health vocabulary
does not define. FHIR R4 `MedicationStatement.effective[x]` is
[1..1 must-support in the IPS MedicationStatement profile](https://hl7.org/fhir/uv/ips/StructureDefinition-MedicationStatement-uv-ips.html),
so the only supplier for a required IPS element was a pair of predicates nothing
constrained and no context mapped. This is the `clinical:procedureName` defect of
v1.15 in two more places, and v1.19 resolves it the same way: the declared
`clinical:` spellings win, and the `health:` ones get a warning and a window.

| Fixture | Expect | Scenario |
|---|---|---|
| `medication-dates-lisinopril.VALID.ttl` | PASS | **Both precisions on one record, which is the point.** `clinical:startDate "2024-03-11"^^xsd:date` and `clinical:endDate "2025-01-15T09:30:00Z"^^xsd:dateTime`. The property shapes are an `sh:or` over `xsd:date` and `xsd:dateTime`, the `health:onsetDate` form, because FHIR's `dateTime` primitive permits date precision and a source that recorded a calendar day must not be given an invented midnight. A record with two dates of the *same* precision would pass under a shape that had picked either branch alone and would prove nothing about the `sh:or`; this one fails unless both branches exist. |
| `medication-dates-health-spelling.WARN.ttl` | WARN | **The importer's current output, unchanged.** Same drug, same dosage, same dates as the `.VALID.` sibling, differing in the predicate and nothing else. Asserts two `sh:Warning` results from `clinical:MedicationDateSpellingShape`, one per spelling, **and no `sh:Violation`** — the second half being the whole compatibility claim, since unlike `procedureName` these dates are optional and no pod fails today for carrying them this way. |
| `medication-dates-string.WARN.ttl` | WARN | `clinical:startDate "March 2024"` as a plain literal. Not gibberish and not a typo: it is what a source that recorded a **month** produces when a converter has nowhere to put month precision and copies the display text through. A malformed date would prove only that a datatype constraint is a datatype constraint; a plain string proves the constraint is reached at all, since through v1.18 the shape named neither date and a start date of any shape whatsoever was accepted in silence. |

**A limit this set records rather than hides.** FHIR permits a `YYYY-MM` date
and `xsd:date` does not admit one, so a month-precision value has no lossless
literal in either branch of the `sh:or`. No fixture can assert a form that has
no legal spelling; the `.WARN.` fixture's header states the limit and what a
converter should do instead of inventing a day.

**What the spelling fixture is for after this release.** clinical v1.19 says the
warning shapes are removed once the warning is observably absent from conforming
output. `medication-dates-health-spelling.WARN.ttl` must be retired in the same
commit that removes `clinical:MedicationDateSpellingShape`; until then, its
continuing to warn is the record that the window is still open.

**Measured on the corpus, and worth recording separately.** `med-001` through
`med-007` already carried `health:startDate` (`med-007` also `health:endDate`).
At the v1.19 pin each of them reports the spelling warning and every one still
**passes**, because a positive fixture is defined by the absence of
`sh:Violation`. The defect was sitting in this repository's own fixtures and
nothing could see it before this release.

## A defect this batch found, and did not paper over

`status-laboratoryreport-in-progress.WARN.ttl` is listed in
[`KNOWN_FAILURES.json`](../../KNOWN_FAILURES.json), owned by `spec`.

clinical v1.16 states that all five `clinical:status` bindings are `sh:Warning`,
so an out-of-set status is reported and never rejected. That holds on
`clinical:ClinicalDocumentShape` and **fails on every class that reaches it
through `sh:node`**. SHACL defines conformance as an *empty* result set, so a
nested `sh:Warning` makes the value node non-conforming, and the outer `sh:node`
constraint then reports a `sh:Violation` at its own default severity. The lab
report is therefore rejected for a value the release says should only be warned
about.

The blast radius is all six document subtypes — `LaboratoryReport`,
`ProgressNote`, `DischargeSummary`, `ConsultationNote`, `ImagingReport`,
`VisitSummary` — and it applies to `clinical:documentReferenceStatus` as well as
to `clinical:status`. On `ProgressNote` the underlying warning is not even
reported, only an opaque `NodeConstraintComponent`, so a reader cannot tell which
field was wrong.

Measured on two independent engines, which is what rules out an implementation
quirk: pyshacl 0.30.1 (this runner) and cascade-cli 0.17.0 (rdf-validate-shacl)
agree on the verdict, and both agree the `ClinicalDocument` twin is only warned.

The fixture asserts what clinical v1.16 says rather than what the shapes
currently do, and the baseline entry is what keeps that honest: the ratchet fails
in both directions, so when `spec` fixes the severity the entry must be removed
in the same commit.

## Verification

Measured in both directions. Only the RED-first half makes a negative or a
warning fixture mean anything.

```sh
# RED first: against the previous pin (spec d37901e, clinical v1.15), where none
# of these constraints exists.
python3 scripts/run_conformance.py --spec-dir <spec@d37901e> --allow-spec-drift \
  --select 'clinical/encounter*' --select 'clinical/document*' --select 'clinical/status*'
#   Both INVALID fixtures report NO_VIOLATION; all three WARN fixtures report
#   NO_WARNING; both participant fixtures report UNSHAPED with 0 constraint checks,
#   because clinical:EncounterParticipant does not exist there.

# GREEN: against the pin now named in scripts/SPEC_PIN (clinical v1.16).
python3 scripts/run_conformance.py --spec-dir <spec@pin> --select 'clinical/*'
#   11 passed / 1 failed / 12 total (the 12th is the legacy social-history fixture);
#   status-laboratoryreport-in-progress.WARN.ttl is the failure, as recorded above.
```

The positive fixtures are not proven by passing — they pass under both pins,
because the release is strictly widening. What proves them is the **constraint
check count**, which rises at the new pin for every one of them: the encounter
goes 33 → 57, the document 38 → 48, the ClinicalDocument status case 34 → 44 and
the lab report 71 → 94. A positive fixture whose count did not move would be
green without touching the new vocabulary at all.

Cross-checked with the real CLI validator, pointed at shapes taken from the spec
checkout rather than its own embedded copy (which is one release behind until
the step-4 sync lands):

```sh
cascade validate fixtures/clinical/<fixture> --shapes <flat dir of spec *.shapes.ttl>
```

All eleven verdicts agree with this runner's, including the lab report failure.

### Verification — the clinical v1.19 medication-date fixtures

Same two-run shape, and only the RED-first half makes the two warning fixtures
mean anything.

```sh
# RED first: against the previous pin (spec 0d07ade, clinical v1.18), where none
# of the three constraints exists.
python3 scripts/run_conformance.py --spec-dir <spec@0d07ade> --allow-spec-drift \
  --select 'clinical/medication-dates-*'
#   1 passed / 2 failed. Both WARN fixtures report NO_WARNING at 55 constraint
#   checks each: they are SHAPED — clinical:MedicationShape reaches them — and
#   nothing notices what they carry.

# GREEN: against the pin now named in scripts/SPEC_PIN (clinical v1.19).
python3 scripts/run_conformance.py --spec-dir <spec@pin> \
  --select 'clinical/medication-dates-*'
#   3 passed / 0 failed. 59 checks for the VALID and string cases, 61 for the
#   health-spelling case (the two extra are the spelling shape's property
#   shapes firing).
```

`medication-dates-lisinopril.VALID.ttl` passes under both pins, because the
release is strictly widening; its count going 55 → 59 is what shows the two new
property shapes evaluating rather than the fixture merely surviving.
