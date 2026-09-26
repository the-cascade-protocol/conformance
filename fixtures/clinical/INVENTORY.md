# Clinical Conformance Fixtures (Inventory)

**Vocabulary covered:** `clinical` v1.4 (`social-history-smoking.ttl`, the
`clinical:` spelling of social history), `clinical` v1.16 (the encounter,
document and status batch below), `clinical` v1.19 (the medication effective
dates and the deprecated `health:` spellings of them) and `clinical` v1.20
(the canonical narrative-text spelling, `clinical:documentType`, and the two
undeclared narrative spellings' migration window).

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

### The narrative text spelling and `clinical:documentType` (clinical v1.20)

`clinical:narrativeText`'s comment is restated as the canonical spelling for FHIR
`Narrative.text.div` **and** C-CDA section text alike; through v1.19 it named FHIR
only. `clinical:documentType` is declared for the first time, a human-readable
document-type label distinct from the closed-slug `cascade:documentType`. Three
new shapes, all `sh:Warning`, target the same seven document classes as the
v1.16 status bindings: `clinical:NarrativeTextCountShape` (`sh:maxCount 1` on
`clinical:narrativeText`, relaxed from the `sh:Violation` it carried on
`ClinicalDocumentShape` through v1.19), `clinical:DocumentTypeShape`
(`sh:datatype xsd:string`, `sh:maxCount 1` on `clinical:documentType`) and
`clinical:NarrativeTextSpellingShape` (`sh:targetSubjectsOf` on the two
undeclared spellings `cascade:narrativeText` and `clinical:content`, `sh:maxCount
0` on each -- the migration-window signal).

| Fixture | Expect | Scenario |
|---|---|---|
| `document-ccda-section-narrative.VALID.ttl` | PASS | The release's target state: one `clinical:narrativeText` (a converted C-CDA section narrative, markup already stripped) and one `clinical:documentType` ("Progress Note"), no legacy spelling. Trips none of the three new shapes. |
| `document-legacy-narrative-spelling.WARN.ttl` | WARN | The same section text written to **both** `cascade:narrativeText` and `clinical:content`, and to neither canonical spelling -- the pre-release C-CDA importer's actual output. Two `sh:Warning` results from `clinical:NarrativeTextSpellingShape`'s two unioned targets, one per predicate, and no `sh:Violation`. |
| `document-documenttype-repeated.WARN.ttl` | WARN | Two `clinical:documentType` values on one document (an addendum note whose importer appended a second label rather than replacing the first). One `sh:Warning` from `clinical:DocumentTypeShape`'s own `sh:maxCount 1`, and no `sh:Violation`. Deliberately carries no narrative text of any spelling, to isolate the claim to the `documentType` axis. |
| `document-narrative-text-repeated.WARN.ttl` | WARN | Two `clinical:narrativeText` values on one document, modelling the exact scenario `clinical:NarrativeTextCountShape`'s own comment names: two C-CDA sections sharing one LOINC section code (here, 51847-2, Assessment and Plan) converting onto one section record, because that record's identity does not yet separate them. One `sh:Warning` from `NarrativeTextCountShape`'s own `sh:maxCount 1`, and no `sh:Violation`. This is the constraint the release relaxes from `sh:Violation` on `ClinicalDocumentShape` itself, so it is the fixture most directly evidencing what v1.20 changed. |

**Measured on the corpus, and worth recording separately.** Five pre-existing
document fixtures (`document-two-statuses-two-authors.VALID`,
`status-clinicaldocument-appended.VALID`,
`status-clinicaldocument-in-progress.WARN`,
`status-laboratoryreport-corrected.VALID`,
`status-laboratoryreport-in-progress.WARN`) are also reached by
`NarrativeTextCountShape` and `DocumentTypeShape`, since both target the same
seven classes as the v1.16 status shapes. Each picks up one or two additional
constraint checks; none trips a warning, since each carries at most one
`clinical:narrativeText`, no `clinical:documentType` and no legacy spelling.

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

### Verification — the clinical v1.20 narrative and documentType fixtures

Same two-run shape, and only the RED-first half makes the three warning
fixtures mean anything.

```sh
# RED first: against the previous pin (spec 735bb57, clinical v1.19), where
# none of the three new shapes exists.
python3 scripts/run_conformance.py --spec-dir <spec@735bb57> --allow-spec-drift \
  --select 'clinical/document-ccda-section-narrative*' \
  --select 'clinical/document-legacy-narrative-spelling*' \
  --select 'clinical/document-documenttype-repeated*' \
  --select 'clinical/document-narrative-text-repeated*'
#   1 passed / 3 failed / 4 total, 188 constraint checks. The legacy-spelling
#   and documentType-repeated WARN fixtures report NO_WARNING: nothing on
#   either legacy spelling or a repeated clinical:documentType is noticed
#   there. document-narrative-text-repeated.WARN is red in the sharper way
#   this release's relaxation is actually about: it is REJECTED, reported
#   VIOLATIONS, because through v1.19 clinical:ClinicalDocumentShape's own
#   sh:maxCount 1 on clinical:narrativeText fired at its default severity,
#   sh:Violation, rather than on a separate Warning-severity shape. The VALID
#   fixture already passes, at 44 checks, which is what an additive release
#   means for a record carrying no legacy spelling.

# GREEN: against the pin now named in scripts/SPEC_PIN (clinical v1.20).
python3 scripts/run_conformance.py --spec-dir <spec@pin> \
  --select 'clinical/document-ccda-section-narrative*' \
  --select 'clinical/document-legacy-narrative-spelling*' \
  --select 'clinical/document-documenttype-repeated*' \
  --select 'clinical/document-narrative-text-repeated*'
#   4 passed / 0 failed / 4 total, 198 constraint checks: 50 for the VALID
#   fixture, 46 for the documentType-repeated case, 52 for the legacy-spelling
#   case, 50 for the narrative-text-repeated case.
```

`document-ccda-section-narrative.VALID.ttl` passes under both pins, because the
release is strictly widening; its count going 44 → 50 is what shows the two new
class-targeted shapes evaluating rather than the fixture merely surviving.

Measured across the full 190-fixture pre-existing set at both pins (not merely
the four new files): 163 passed / 27 failed at 735bb57, 167 passed / 27 failed
at the new pin, the same 27 `(fixture, reason)` pairs at both. Five pre-existing
document fixtures pick up one or two additional constraint checks each at the
new pin (`NarrativeTextCountShape` and `DocumentTypeShape` reach the same seven
classes the v1.16 status shapes do) and none of them changes verdict.
