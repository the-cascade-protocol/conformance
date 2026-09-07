# Health Conformance Fixtures (Inventory)

**Vocabulary covered:** `health` v2.8 — the two `clinical:status` bindings that
health v2.8 / `health.shapes.ttl` v1.5 declares — and `health` v2.9 /
`clinical` v1.18, the coded allergen, the coded manifestation, the allergy type
and the criticality that `health.shapes.ttl` v1.6 declares on
`health:AllergyRecordShape`.

## Why these are filed under `health/` when the predicate is `clinical:`

`health.shapes.ttl` declares `clinical:status` on `health:LabResultRecordShape`
and `health:AllergyRecordShape` rather than minting a `health:` spelling for it.
The reason is stated at the constraint: `clinical:status` is the domain-free
status carrier both import paths already write, and a second spelling would give
one fact two predicates.

These fixtures are therefore filed by the shape that **owns the constraint**, not
by the namespace of the predicate. The other three of the release's five
`clinical:status` binding sets are on `clinical:` shapes and live in
[`../clinical/INVENTORY.md`](../clinical/INVENTORY.md).

## Fixture kind

Standalone SHACL-validation fixtures. Polarity is in the filename:
`.VALID.ttl` must pass, `.INVALID.ttl` must be rejected, and `.WARN.ttl` must be
**noticed but not rejected** — at least one `sh:Warning` and no `sh:Violation`.
The `.WARN.` polarity is what lets a `sh:Warning` binding be asserted at all; see
[`../clinical/INVENTORY.md`](../clinical/INVENTORY.md) for why the two-polarity
form cannot state the claim.

Every byte is synthetic.

## Fixtures

| Fixture | Expect | Scenario |
|---|---|---|
| `status-labresult-final.VALID.ttl` | PASS | `Observation.status`, 8 codes, required binding, verbatim. A lab result record is converted from a FHIR Observation. |
| `status-labresult-completed.WARN.ttl` | WARN | "completed" — a real FHIR code on workflow resources, in no `Observation.status` value set. What is lost while this is unchecked is specific: "amended" and "corrected" are what distinguish a superseded result from the one that replaced it, and a status carrier accepting any string cannot make that distinction. |
| `status-allergy-inactive.VALID.ttl` | PASS | `AllergyIntolerance.clinicalStatus`, **three** codes: active \| inactive \| resolved. Carries `clinical:verificationStatus "confirmed"` alongside, because the pair is what shows the two axes are separate elements with separate value sets. |
| `status-allergy-entered-in-error.WARN.ttl` | WARN | **The load-bearing case of the whole status family.** See below. |
| `coded-allergy-penicillin.VALID.ttl` | PASS | health v2.9, the whole repair on one node: an RxNorm `health:allergenCode` beside the display text, **two** SNOMED `health:manifestationCode` values with **two** matching `health:reaction` literals (one per manifestation), and `health:allergySeverity "severe"` beside `clinical:criticality "high"`. |
| `coded-allergy-criticality-moderate.WARN.ttl` | WARN | **The load-bearing case of the v2.9 set.** See below. |
| `coded-allergy-type-sensitivity.WARN.ttl` | WARN | `"sensitivity"`, the plausible third word for a two-code required binding (`allergy` \| `intolerance`). It is what an intake form prints for both, so it is the value a converter passes through unexamined, and it collapses the immune / non-immune distinction the element exists to make. |
| `coded-allergy-allergen-code-string.WARN.ttl` | WARN | `health:allergenCode "7980"`, a string literal where an IRI belongs. `sh:nodeKind sh:IRI` is the *only* constraint the property carries — no pattern, no maxCount, both deliberately — so a bare literal is the only thing that can violate it, and a malformed IRI would assert nothing. It is also the realistic mistake: `code.coding[].code` arrives from FHIR as the JSON string `"7980"` and the whole work of the property is joining it to `code.coding[].system`. |

## Why the allergy warning fixture is the important one

Every other warning fixture in this batch uses a value that is wrong everywhere.
This one uses a value that is **right in three other places and wrong here**.

`entered-in-error` is a real code and it is legal under three of the five value
sets clinical v1.16 binds: on a lab result, on a vital sign and on a document. It
is excluded from `AllergyIntolerance.clinicalStatus`, which has exactly three
codes, and that exclusion is the one deliberate narrowing in the release. The
reason is stated at the constraint: admitting it beside "inactive" and "resolved"
would merge *"the patient no longer reacts to this"* with *"this allergy was
never real"*, which are opposite clinical facts and the one pair a
safety-relevant record must never conflate.

So the fixture is not testing that a shape rejects nonsense. It is the only way
to show that the allergy set is three codes **by choice** rather than by
oversight, and it is what fails if someone later "completes" the set to four to
match its siblings.

The repudiation the record is reaching for has a correct home, and the sibling
`.VALID.` fixture shows it: `clinical:verificationStatus`, a different element
with a different four-code value set that *does* contain `entered-in-error`.

## Why the criticality warning fixture is the important one of the v2.9 set

Same argument as the status family above, on a different axis, and it is why
`"moderate"` was chosen over a nonsense string.

`"moderate"` is a real code and it is legal *on this very record*:
`health:allergySeverity` binds `AllergyIntolerance.reaction.severity` to
`mild | moderate | severe` and `"moderate"` is the middle member. It is absent
from `AllergyIntolerance.criticality`, which is `low | high | unable-to-assess`.

So the fixture is not testing that a shape rejects gibberish. Criticality is the
risk a **future** exposure carries; severity is what an **observed** reaction
was. A converter that folds one into the other — the behaviour health v2.9
documents against — produces exactly this record when the fold runs backwards,
and nothing before this binding existed would have noticed. It is also what
fails if someone later "harmonises" the two value sets by admitting
`mild | moderate | severe` here, which would make the two predicates
interchangeable and the distinction unrecoverable.

The sibling `coded-allergy-penicillin.VALID.ttl` shows the correct form: both
axes stated, on one record, with different values.

## What no fixture here covers, deliberately

An allergy with **two reactions of differing severity**. health v2.9 is flat by
choice — manifestations and one severity sit on the record, not inside a nested
reaction node — so there is nothing for a fixture to instantiate and nothing for
a shape to check. The choice and its reasoning are in health.ttl's v2.9
changelog. This paragraph exists so the gap is recorded rather than inferred.

## Verification

```sh
# RED first: against the previous pin (spec d37901e, health v2.7), where neither
# binding exists.
python3 scripts/run_conformance.py --spec-dir <spec@d37901e> --allow-spec-drift \
  --select 'health/*'
#   Both WARN fixtures report NO_WARNING: nothing notices them.

# GREEN: against the pin now named in scripts/SPEC_PIN (health v2.8).
python3 scripts/run_conformance.py --spec-dir <spec@pin> --select 'health/*'
#   4 passed / 0 failed.
```

The two positives pass under both pins, because the release is strictly widening,
so passing is not what proves them. The constraint check count is: the lab result
goes 34 → 37 and the allergy 22 → 28 between the two pins, which is the new
bindings actually evaluating.

Cross-checked with `cascade validate --shapes <spec shapes>` (cascade-cli 0.17.0,
a different SHACL engine): all four verdicts agree with this runner's.

For the four v2.9 fixtures, the same two-run shape:

```sh
# RED first: against spec `main` before the health v2.9 / clinical v1.18 change,
# where none of the four constraints exists.
python3 scripts/run_conformance.py --spec-dir <spec@main> --allow-spec-drift \
  --select 'health/coded-allergy-*'
#   1 passed / 3 failed. All three WARN fixtures report NO_WARNING at 28
#   constraint checks each: they are shaped, and nothing notices them.

# GREEN: against the pin now named in scripts/SPEC_PIN.
python3 scripts/run_conformance.py --spec-dir <spec@pin> \
  --select 'health/coded-allergy-*'
#   4 passed / 0 failed, 36 constraint checks each.
```

`coded-allergy-penicillin.VALID.ttl` passes under both, because the release is
strictly widening; its count going 28 → 36 is what shows the four new property
shapes evaluating rather than the fixture merely surviving.
