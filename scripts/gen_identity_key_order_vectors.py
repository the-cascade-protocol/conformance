#!/usr/bin/env python3
"""Independent oracle for the identity key-order vectors in
`fixtures/deterministic-ids/test-vectors.json`.

WHY AN INDEPENDENT ORACLE. The rule under test is a SORT ORDER, and every
current implementation is written in JavaScript, where the natural string
comparison is UTF-16 code-unit order. An expected value produced by any of
those implementations would therefore assert whatever they already do, which
is exactly the question the vectors exist to settle. Python's `sorted()` on
`str` compares by Unicode CODE POINT natively, so this script states the rule
as core v3.6 writes it ("sort ascending by Unicode code point") without
borrowing an answer from an implementation.

Code-unit order and code-point order agree across the Basic Multilingual
Plane and disagree exactly when an astral-plane character (encoded in UTF-16
as a surrogate pair beginning D800..DBFF) is compared with a BMP character
above U+D7FF. `keyOrderVectors` includes one such pair deliberately.

Run:
    python3 scripts/gen_identity_key_order_vectors.py --check
        Recompute every vector already recorded in test-vectors.json and
        report any that disagrees. Exits 1 on disagreement.

    python3 scripts/gen_identity_key_order_vectors.py --emit
        Print the `keyOrderVectors` array as JSON, for pasting into
        test-vectors.json.

    python3 scripts/gen_identity_key_order_vectors.py --emit-members
        Print the astral member-order entries destined for the
        `multiValuedFieldVectors` array, for pasting into test-vectors.json.

WHY THERE ARE TWO EMIT FLAGS. The key sort and the member sort are two separate
lines of code in every implementation, and an implementation can get one right
while the other still compares UTF-16 code units. `keyOrderVectors` measures the
first; the entries `--emit-members` produces live in `multiValuedFieldVectors`
and measure the second, on the same astral/BMP pair, so a fix that touches only
one site cannot read as green.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
VECTORS = REPO / "fixtures" / "deterministic-ids" / "test-vectors.json"


def deterministic_uuid(text: str) -> str:
    """CDP-UUID: SHA-1 of the input laid out as a version-5 UUID.

    Not RFC 4122 name-based UUIDv5 (there is no namespace in the hash input).
    Its only guarantee is cross-implementation stability for the same input
    string. The input is hashed as UTF-8.
    """
    h = hashlib.sha1(text.encode("utf-8")).hexdigest()
    variant = f"{((int(h[16:18], 16) & 0x3F) | 0x80):02x}"
    return f"{h[0:8]}-{h[8:12]}-5{h[13:16]}-{variant}{h[18:20]}-{h[20:32]}"


def canonical_field_value(value):
    """Canonical form of one content-field value (core v3.6).

    A scalar passes through untouched. A list has null/blank-after-trim members
    discarded, survivors trimmed, deduplicated, sorted ascending by code point,
    and joined with U+002C. A list with no survivor is absent.
    """
    if value is None:
        return None
    if not isinstance(value, list):
        return value
    survivors = {m.strip() for m in value if m is not None and m.strip()}
    return ",".join(sorted(survivors)) if survivors else None


def identity_string(resource_type: str, content_fields: dict) -> str:
    """Build the string that is hashed.

    THE LINE UNDER TEST is `sorted(...)`: Python orders `str` by Unicode code
    point, which is what core v3.6 requires of the key order. Insertion order
    of `content_fields` is irrelevant by construction, which is what vector
    `key-order-insertion-independence` asserts of an implementation.
    """
    pairs = []
    for k, v in content_fields.items():
        cv = canonical_field_value(v)
        if cv is None or not cv.strip():
            continue
        pairs.append((k, cv))
    pairs.sort(key=lambda kv: kv[0])
    return f"{resource_type}::" + "|".join(f"{k}={v}" for k, v in pairs)


def content_hashed_uri(resource_type: str, content_fields: dict) -> str:
    return f"urn:uuid:{deterministic_uuid(identity_string(resource_type, content_fields))}"


PATIENT = "urn:uuid:patient-smith"

# The astral pair. U+1D51E MATHEMATICAL FRAKTUR SMALL A is encoded in UTF-16 as
# the surrogate pair D835 DD1E, so its FIRST code unit (D835) is BELOW U+FF01
# and its CODE POINT (1D51E) is ABOVE it. The two orders therefore disagree,
# and this is the only shape of input on which they can.
ASTRAL = "\U0001D51E"
FULLWIDTH_BANG = "！"

KEY_ORDER_VECTORS = [
    {
        "label": "key-order-insertion-independence-a",
        "comment": (
            "Identity keys are sorted before hashing, so the order in which a caller "
            "happens to build the object MUST NOT reach the identifier. This entry and "
            "the '-b' entry below are the same four fields inserted in two different "
            "orders and MUST mint the same URI."
        ),
        "proves": ["key-order-independence"],
        "resourceType": "Patient",
        "contentFields": {
            "dob": "1985-03-15",
            "family": "Smith",
            "given": "John",
            "sex": "male",
        },
    },
    {
        "label": "key-order-insertion-independence-b",
        "comment": (
            "The SAME four fields inserted in reverse order. Its expectedUri MUST equal "
            "'key-order-insertion-independence-a' byte for byte, and both MUST equal the "
            "pre-existing contentHashedUriVectors entry 'patient-john-smith'."
        ),
        "proves": ["key-order-independence"],
        "resourceType": "Patient",
        "contentFields": {
            "sex": "male",
            "given": "John",
            "family": "Smith",
            "dob": "1985-03-15",
        },
    },
    {
        "label": "key-order-underscore-after-uppercase",
        "comment": (
            "Discriminates code point from locale collation on ASCII alone. U+005F LOW "
            "LINE sorts AFTER U+0041 'A' by code point, so the identity string is "
            "'Alpha=...|_under=...'. A locale collation (ICU root, and JavaScript's "
            "localeCompare) treats '_' as punctuation with lower primary weight and "
            "would emit '_under' first, minting a different identifier. Note that the "
            "pair '_under'/'alpha' does NOT discriminate: U+0061 'a' is already above "
            "U+005F, so both orders agree on it. The capital is load-bearing."
        ),
        "proves": ["key-order-code-point-not-locale"],
        "resourceType": "Observation",
        "contentFields": {
            "_under": "u",
            "Alpha": "a",
        },
    },
    {
        "label": "key-order-bmp-non-ascii-control",
        "comment": (
            "CONTROL. U+00E9 'e-acute' and U+007A 'z' are both on the Basic Multilingual "
            "Plane, so UTF-16 code-unit order and Unicode code-point order agree: 'z' "
            "(007A) precedes 'e-acute' (00E9). A locale collation would emit 'e-acute' "
            "first, so this still discriminates code point from locale while every "
            "implementation is expected to pass it. It is here so that a failure on the "
            "astral vector below can be attributed to the surrogate pair specifically "
            "and not to non-ASCII handling in general."
        ),
        "proves": ["key-order-code-point-not-locale"],
        "resourceType": "Observation",
        "contentFields": {
            "é": "e-acute",
            "z": "zed",
        },
    },
    {
        "label": "key-order-astral-vs-bmp",
        "comment": (
            "THE DIVERGENCE. U+FF01 FULLWIDTH EXCLAMATION MARK and U+1D51E MATHEMATICAL "
            "FRAKTUR SMALL A. By CODE POINT, which is what core v3.6 states, FF01 < "
            "1D51E and U+FF01 comes first; this expectedUri asserts that. By UTF-16 "
            "CODE-UNIT order, which is what a JavaScript string comparison performs, "
            "U+1D51E's leading surrogate D835 is below FF01 and the astral key comes "
            "first, minting a different identifier. Whether the protocol means code "
            "point as written or the code-unit behaviour its current implementations "
            "share is an OPEN cross-implementation question; this vector asserts the "
            "rule as written and `keyOrderImplementationStatus` records who diverges."
        ),
        "proves": ["key-order-code-point-not-locale", "key-order-astral-plane"],
        "resourceType": "Observation",
        "contentFields": {
            ASTRAL: "fraktur",
            FULLWIDTH_BANG: "fullwidth",
        },
    },
]


# The same divergence, one step lower down: not the order of the identity KEYS
# but the order of the MEMBERS of a single set-valued field. `canonical_field_value`
# above sorts those, and every current implementation sorts them with a bare
# `.sort()`, which is UTF-16 code-unit order. Until this vector existed the member
# sort was unmeasured, so an implementation could correct its key comparator, pass
# every keyOrderVectors entry, and still mint a divergent identifier for any record
# whose field held an astral member.
MEMBER_ORDER_VECTORS = [
    {
        "label": "condition-member-order-astral-vs-bmp",
        "comment": (
            "THE DIVERGENCE, AT THE MEMBER SORT. A set-valued field holding U+FF01 "
            "FULLWIDTH EXCLAMATION MARK and U+1D51E MATHEMATICAL FRAKTUR SMALL A. By "
            "CODE POINT, which is what core v3.6 states, FF01 < 1D51E and the field "
            "canonicalizes to the fullwidth character first; this expectedUri asserts "
            "that. By UTF-16 CODE-UNIT order, which is what a bare JavaScript "
            "`Array.prototype.sort()` performs, U+1D51E's leading surrogate D835 is "
            "below FF01 and the astral member comes first, minting a different "
            "identifier. This is the member-sort twin of keyOrderVectors' "
            "'key-order-astral-vs-bmp': the two sorts are separate lines of code in "
            "every implementation, so correcting one does not imply the other. The "
            "members are also listed here in the OPPOSITE order to the canonical one, "
            "so an implementation that does not sort at all fails this too."
        ),
        "proves": ["order-independence", "member-order-astral-plane"],
        "resourceType": "Condition",
        "contentFields": {
            "patient": PATIENT,
            "snomedCode": [ASTRAL, FULLWIDTH_BANG],
        },
    },
]


def _expand(vectors: list) -> list:
    out = []
    for v in vectors:
        entry = dict(v)
        entry["canonicalIdentityString"] = identity_string(v["resourceType"], v["contentFields"])
        entry["expectedUri"] = content_hashed_uri(v["resourceType"], v["contentFields"])
        out.append(entry)
    return out


def build() -> list:
    return _expand(KEY_ORDER_VECTORS)


def build_members() -> list:
    return _expand(MEMBER_ORDER_VECTORS)


def check() -> int:
    """Recompute every vector already in the file and report disagreements.

    This is the proof that the oracle reproduces the corpus rather than merely
    agreeing with itself: the pre-existing entries were produced by a different
    implementation in a different language, and this script must land on their
    bytes before its new entries mean anything.
    """
    doc = json.loads(VECTORS.read_text(encoding="utf-8"))
    bad = 0
    checked = 0

    for v in doc.get("primitiveVectors", []):
        checked += 1
        got = deterministic_uuid(v["input"])
        if got != v["expectedUuid"]:
            bad += 1
            print(f"MISMATCH primitiveVectors/{v['label']}: {got} != {v['expectedUuid']}")

    for v in doc.get("contentHashedUriVectors", []):
        checked += 1
        got = f"urn:uuid:{deterministic_uuid(v['identityString'])}"
        if got != v["expectedUri"]:
            bad += 1
            print(f"MISMATCH contentHashedUriVectors/{v['label']}: {got} != {v['expectedUri']}")

    for group in ("multiValuedFieldVectors", "keyOrderVectors"):
        for v in doc.get(group, []):
            checked += 1
            s = identity_string(v["resourceType"], v["contentFields"])
            if s != v["canonicalIdentityString"]:
                bad += 1
                print(f"MISMATCH {group}/{v['label']} identity string:\n  got {s!r}\n  rec {v['canonicalIdentityString']!r}")
            got = f"urn:uuid:{deterministic_uuid(s)}"
            if got != v["expectedUri"]:
                bad += 1
                print(f"MISMATCH {group}/{v['label']}: {got} != {v['expectedUri']}")

    print(f"oracle checked {checked} vector(s); {bad} disagreement(s)")
    return 1 if bad else 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--check", action="store_true",
                   help="recompute every vector in test-vectors.json and report disagreements")
    g.add_argument("--emit", action="store_true",
                   help="print the keyOrderVectors array as JSON")
    g.add_argument("--emit-members", action="store_true",
                   help="print the astral member-order entries for multiValuedFieldVectors as JSON")
    args = p.parse_args(argv)
    if args.check:
        return check()
    json.dump(build_members() if args.emit_members else build(), sys.stdout, indent=2, ensure_ascii=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
