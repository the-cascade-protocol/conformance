# Core Conformance Fixtures (Inventory)

**Vocabulary covered:** `core` v3.3 (`cascade:AIExtractionActivity` provenance),
`core` v3.5 (the ORIGIN axis, `cascade:sourceIdentity`), `core` v3.7
(`cascade:Attachment`, the content-addressed document store) and `core` v3.9
(the pod owner's name on the extended profile).

## Fixture kind

Standalone SHACL-validation fixtures, not conversion oracles. Each file is
validated directly and carries its polarity in its name:

- `<slug>.VALID.ttl` (and the unsuffixed legacy `ai-extracted-medication.ttl`)
  MUST pass validation.
- `<slug>.INVALID.ttl` MUST fail validation: at least one `sh:Violation`.
- `<slug>.WARN.ttl` MUST be **noticed but not rejected**: at least one
  `sh:Warning` AND no `sh:Violation`. New with the core v3.7 batch; see
  `attachment-no-media-type.WARN.ttl` below and the note at the top of
  `scripts/run_conformance.py`.

Every byte is synthetic: invented organizations, endpoints, identifiers, people
and values. The OIDs are under the HL7 example arc.

## The three source axes (core v3.5)

A record carries three different answers to three different questions, and the
fixtures below exist because collapsing any two of them is a defect that has been
measured on real pods:

| Axis | Property | Question |
|---|---|---|
| ORIGIN | `cascade:sourceIdentity` | Which ORGANIZATION the record came from, canonically, whatever transport carried it. The only one usable as a reconciliation key. |
| LABEL | `clinical:sourceEHR` | What to CALL that organization on screen. Source-worded, so two spellings of one organization are two labels. |
| INGESTION | `cascade:sourceSystem` | How and when the data entered the Pod. Never an origin. |

## Fixtures

| Fixture | Expect | Scenario |
|---|---|---|
| `ai-extracted-medication.ttl` | PASS | An `AIExtracted` medication linked to its `cascade:AIExtractionActivity` (core v3.0/v3.3). |
| `source-identity-org.VALID.ttl` | PASS | `org:` tier. An organization was derivable, so the identity carries a normalized slug. All three axes present and all three saying different things. |
| `source-identity-namespace.VALID.ttl` | PASS | `ns:` tier. No organization was derivable, but the record's identifiers have an assigning authority (a C-CDA `<id>` root OID). |
| `source-identity-transport.VALID.ttl` | PASS | `transport:` tier, the honest last resort. Nothing named or located an organization, so the value restates the ingestion label under a prefix that tells a consumer the origin is UNKNOWN. |
| `source-identity-two-transports-one-system.VALID.ttl` | PASS | **The invariant.** One synthetic health system exporting twice. The LABEL differs (endpoint domain vs custodian organization name) and the INGESTION batch differs, and the ORIGIN is identical. A consumer grouping by ORIGIN sees one system; a consumer grouping by either other axis sees two. |
| `source-identity-unprefixed.INVALID.ttl` | FAIL | The display label written straight into the origin axis, with no scheme, so a consumer cannot tell what was actually derived. Rejected on `sh:pattern`. |
| `source-identity-repeated.INVALID.ttl` | FAIL | Two origins on one record. Both values are individually well formed, so only the cardinality constraint catches it. Rejected on `sh:maxCount`. |

## The pod owner's name (core v3.9)

An IPS cannot be produced without a Patient, and
[Patient-uv-ips](https://hl7.org/fhir/uv/ips/StructureDefinition-Patient-uv-ips.html)
makes `Patient.name` `1..*` with the SHALL:populate obligation and invariant
`ips-pat-1` (at least one of `family`, `given`, `text`). Through core v3.8 no
ontology in `spec` declared a name for the pod owner at all. core v3.9 puts it on
`<#me>` in `profile/extended.ttl`, using `foaf:givenName`, `foaf:familyName` and
`foaf:name`. **No `cascade:` term is minted** — FOAF already defines all three —
so what these fixtures exercise is a shape, not a vocabulary addition.

The name is PHI, which is why it is here and not in `profile/card.ttl`:
`pod-structure.md` section 3.2 makes `card.ttl` the publicly-readable profile
document and forbids PHI in it, and its `foaf:name` stays a generic display name
shown before the pod is unlocked. `profile/extended.ttl` is inside the encrypted
pod like every other pod file.

**Every fixture in this group carries `cascade:dateOfBirth`, and that is not
decoration.** An extended profile carries no `rdf:type` of its own — it adds
predicates to the same `<#me>` subject `card.ttl` types `foaf:Person` — so
`cascade:ExtendedProfileShape` targets the SUBJECTS OF `cascade:dateOfBirth`. A
`<#me>` carrying only names would match no shape at all and the runner would
report `UNSHAPED`, which is a vacuous pass wearing a failure's name.

| Fixture | Expect | Scenario |
|---|---|---|
| `extended-profile-name.VALID.ttl` | PASS | All three name properties on `<#me>`, beside the section 3.6 example's date of birth, telephone, email and address. This is the shape of the file an IPS Patient entry is built from: `family` ← `foaf:familyName`, `given` ← `foaf:givenName`, `text` ← `foaf:name`. `cascade:biologicalSex` is `"male"` rather than the `"M"` the section 3.6 example prints, because `"male"` is a member of the value set `core.ttl` declares and `"M"` is not; nothing reaches the property on an untyped node today, which is exactly why the fixture must not carry the spelling the vocabulary rejects. |
| `extended-profile-name-only.VALID.ttl` | PASS | `foaf:name` alone. A name known only as one string — the source never separated it, or the person's name does not divide into given and family parts — is legal, and it is what `Patient.name.text` carries; `ips-pat-1` is satisfied on `text` alone. What this fixture catches is a shape that required `givenName` or `familyName`, whose cure a producer would reach for is splitting the string on a space and guessing which half is which. It must report **nothing**, at any severity, while still being reached. |
| `extended-profile-empty-family.WARN.ttl` | WARN | `foaf:familyName ""`. The empty string is what a form with an untouched field writes, and the triple that reaches the pod claims the family name *is* the empty string — a different fact from having none recorded, and indistinguishable from it in every rendering afterwards. `sh:minLength 1` notices it. `.WARN.` and not `.INVALID.` because the constraint enters at Warning per the core v3.5 ratchet: a profile is reported, never thrown away, over a blank field. Filing it `.INVALID.ttl` would fail with `NO_VIOLATION`. |
| `extended-profile-two-given.WARN.ttl` | WARN | Two `foaf:givenName` values. The cardinality is a deliberate 1 and the proposal says so, even though FOAF places no cardinality on the property and FHIR's `HumanName.given` is `0..*`: two triples have no order, so a consumer rebuilding the name produces `"Jordan Alex"` as readily as `"Alex Jordan"`. A second given name goes in `foaf:name`, which carries the whole name in the order the person writes it. `.WARN.` for the same ratchet reason as above. |

### Extended profile verification

```sh
# RED first: against the previous pin (spec a5a194a, core v3.8), where
# cascade:ExtendedProfileShape does not exist.
python3 scripts/run_conformance.py --spec-dir <spec@a5a194a> --allow-spec-drift
#   All four report UNSHAPED with 0 constraint checks.

# GREEN: against the pin now named in scripts/SPEC_PIN (core v3.9).
python3 scripts/run_conformance.py --spec-dir <spec@pin> --select 'core/extended-profile*'
#   4 passed / 0 failed; 9 constraint checks each.
```

`UNSHAPED` is a **stronger** RED here than the `NO_WARNING` a `.WARN.` fixture
usually gives at the previous pin. At core v3.8 there is no shape in the entire
published set that reaches an untyped `<#me>`, so nothing could have noticed the
empty family name or the second given name — nothing was looking at the node.
A `--select 'core/extended-profile*'` run at that pin does not even complete: the
runner's own self-check aborts with *"zero constraint checks evaluated across the
entire suite"*, which is the same fact stated by the harness instead of by a
verdict. So the RED above is measured with a full-suite run, and the four rows
are read out of it.

**One measurement belongs here rather than in a fixture,** because it is the
release's compatibility claim rather than a new assertion.
`cascade:PatientProfile` nodes carry `cascade:dateOfBirth` too, so the new shape
also reaches eight fixtures that were already in this repository:

| Fixture | Constraint checks, core v3.8 → v3.9 | Verdict |
|---|---|---|
| `profile-001.json` | 32 → 41 | pass, unchanged |
| `profile-002.json` | 76 → 85 | pass, unchanged |
| `profile-003.json` | 32 → 41 | pass, unchanged |
| `profile-005.json` | 32 → 41 | pass, unchanged |
| `genomics/phenopackets/bethlem-myopathy.expected.ttl` | 53 → 62 | fail `VIOLATIONS`, same `genomics:` reasons |
| `genomics/phenopackets/v2-cohort.expected.ttl` | 164 → 191 | fail `VIOLATIONS`, same `genomics:` reasons |
| `genomics/phenopackets/v2-family.expected.ttl` | 193 → 220 | fail `VIOLATIONS`, same `genomics:` reasons |
| `genomics/phenopackets/v2-phenopacket.expected.ttl` | 100 → 109 | fail `VIOLATIONS`, same `genomics:` reasons |

Every one keeps its verdict and its reason; only the counts move.
`profile-004.json` carries no `cascade:dateOfBirth` and stays at 32, which is the
control. Absence of a name is deliberately NOT a finding in core v3.9, so there
is no negative fixture for a profile that omits all three properties; every other
fixture in this repository omits them and none changes verdict, which exercises
that claim 173 times rather than asserting it once.

## Attachments (core v3.7)

A record that says "the report is at this URL" stops being answerable the moment
the URL stops resolving. core v3.7 stores the bytes under
`attachments/{algorithm}/{digest}` and puts a small `cascade:Attachment` node in
the Turtle. **The file's name is its digest**, which is what makes the
arrangement checkable rather than merely tidy: a consumer hashes what it read and
compares it with where it read it from, so nothing has to be trusted to keep name
and content in agreement, and both cross-source deduplication and idempotent
re-import follow with no further mechanism.

`cascade:AttachmentShape` requires exactly three facts at Violation severity, and
there is one negative fixture per requirement, because each answers a different
"and then what?":

| Fixture | Expect | Scenario |
|---|---|---|
| `attachment-linked-report.VALID.ttl` | PASS | The full node — path, digest, algorithm, media type, byte size, title — **and the record that points at it**, so `cascade:HasAttachmentEdgeShape` is exercised too. The attachment is an IRI, not a blank node, because the edge shape wants one: that is what lets the record and the attachment live in different files, which is how a pod partitioned by record type actually stores them. |
| `attachment-no-path.INVALID.ttl` | FAIL | Violation 1 of 3. Digest and algorithm are both present and well formed, so the node can say exactly *which* bytes it means — and there is still nothing to open. A content address is not a location. |
| `attachment-no-content-hash.INVALID.ttl` | FAIL | Violation 2 of 3. Nothing distinguishes the right bytes from any other bytes at that path, so a re-import that wrote a different document to the same filename is undetectable. The path still *ends* in a digest-shaped segment, and that is deliberately not a substitute: a shape reading the digest out of the filename would be trusting the producer to keep name and content in agreement, which is the one thing this design refuses to do. |
| `attachment-no-hash-algorithm.INVALID.ttl` | FAIL | Violation 3 of 3, and the least obvious. Path and digest are both there, so a reader might call this complete. Without the algorithm the digest cannot be recomputed, so it cannot be checked, so the previous requirement is decorative and the node asserts integrity it does not provide. Guessing from the digest's length is not a check: `sh:pattern` sets a floor of 32 characters and no ceiling, precisely so the algorithm can be replaced. |
| `attachment-absolute-path.INVALID.ttl` | FAIL | A portability defect. Pods are copied, synced, restored and re-rooted routinely, and an absolute path is a statement about one machine's filesystem that breaks silently: the reference still parses, still satisfies every other constraint, and simply stops resolving. |
| `attachment-parent-traversal-path.INVALID.ttl` | FAIL | **The safety case.** A `..` segment makes an attachment reference a way to read a file *outside* the Pod, so a consumer that resolves paths naively — joining them onto the pod root and opening the result, which is the obvious implementation — can be walked out of the store by data it was given. Rejecting it in the shape puts the check in one place instead of in every consumer that remembers to write it. |
| `attachment-uppercase-digest.INVALID.ttl` | FAIL | **The same digest as the VALID fixture's, cased differently.** The two strings denote identical bytes, and accepting both would hold one document under two names, which defeats the deduplication content addressing exists to provide. The second half is the filesystem: this string is a filename, and a case-insensitive filesystem — the default on macOS, where this project's reference implementations run — collides the two spellings on one machine and not on another. A defect that depends on which laptop ran the import is worse than one that always happens. |
| `attachment-no-media-type.WARN.ttl` | WARN | Media type is split across two shapes so its two severities are unambiguous: the **form** of the value is a Violation in `cascade:AttachmentShape` (two media types on one set of bytes is a defect), while its **presence** is only a Warning in `cascade:AttachmentMediaTypeShape` (stored bytes with no stated type are awkward to render but not lost, and a missing one must not invalidate the record pointing at them). So this fixture belongs with the path-and-digest negatives by subject matter and with the `clinical:status` fixtures by severity. Filing it `.INVALID.ttl` would fail with `NO_VIOLATION` and would assert something core v3.7 explicitly declined to say. |

The pattern on `cascade:attachmentPath` is stated **positively** — `"/"`-separated
segments each beginning with an alphanumeric — and that is not a stylistic
preference. SHACL evaluates `sh:pattern` with XPath `fn:matches`, whose regular
expression language is XSD 1.1 and has **no lookahead assertion**, so a "reject
these three things" pattern is not expressible at all; an engine that accepted
one would be applying its host language's regex rather than the specification's.
Written positively, a leading `/` fails on the first character, a `://` fails
because `:` is outside the set, and `..` and `.` fail because a segment must
start with an alphanumeric — with no rule mentioning any of the three.

The digest used across all eight fixtures is real rather than invented, so the
arrangement's central claim is reproducible from the fixture itself:

```sh
printf 'cascade-conformance-attachment-fixture-v1\n' | shasum -a 256
# 8dd3c6b5f593b25cb9dc0094d67323d16c3bbc9584eda019726a38dd2cc7a471
```

FHIR's `Attachment.hash` is deliberately not followed: it fixes SHA-1, which is
collision-broken, and a collision in a content-addressed store is a mechanism by
which one document silently replaces another. The algorithm is named explicitly
from the RFC 6920 registry instead, with no `sh:in`, because the registry gains
entries over time and an enum would have to be revised to accept a stronger hash
— the wrong direction for a constraint whose whole purpose is to let the
algorithm be replaced.

### Attachment verification

```sh
# RED first: against the previous pin (spec d37901e, core v3.6), where
# cascade:Attachment is not a class any shape targets.
python3 scripts/run_conformance.py --spec-dir <spec@d37901e> --allow-spec-drift \
  --select 'core/attachment*'
#   All six negatives and the WARN fixture report UNSHAPED with 0 constraint
#   checks: there is no constraint to violate, so none of them is a test there.

# GREEN: against the pin now named in scripts/SPEC_PIN (core v3.7).
python3 scripts/run_conformance.py --spec-dir <spec@pin> --select 'core/attachment*'
#   8 passed / 0 failed; 21 constraint checks on each standalone node.
```

`attachment-linked-report.VALID.ttl` passes under both pins, so passing is not
what proves it: at the old pin its attachment node matched no shape and only the
lab record was checked. The constraint count going 34 → 59 is the attachment node
and the edge becoming reachable.

Cross-checked with `cascade validate --shapes <spec shapes>` (cascade-cli 0.17.0,
a different SHACL engine): all eight verdicts agree with this runner's.

## Verification

Measured in both directions, which is the only thing that makes the two
`source-identity` negatives mean anything:

```sh
# RED first: against the previous pin (spec 9461fa9, core 3.4), where
# cascade:SourceIdentityShape does not exist.
python3 scripts/run_conformance.py --spec-dir <spec@9461fa9> --allow-spec-drift \
  --select 'core/source-identity*'
#   4 passed / 2 failed — both negatives report NO_VIOLATION: nothing rejects them.

# GREEN: against the pin now named in scripts/SPEC_PIN (core 3.5).
python3 scripts/run_conformance.py --spec-dir <spec@pin> --select 'core/*'
#   7 passed / 0 failed, 319 constraint checks.
```

Absence of `cascade:sourceIdentity` is deliberately NOT a finding in core v3.5, so
there is no negative fixture for a record that omits it. Every other fixture in
this repository omits it and continues to pass, which is that compatibility claim
being exercised 122 times rather than asserted once.
