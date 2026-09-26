#!/usr/bin/env python3
"""Generate, or check, the Pod encryption header vectors in `pod-encryption/`.

The format under test is specified in the `spec` repository, `pod-encryption.md`.
This script writes three things from ONE table (`VECTORS` below), so the files
and the manifest that describes them cannot drift apart:

  pod-encryption/negative/*.json   headers every reader MUST refuse
  pod-encryption/accept/*.json     headers every reader MUST open
  pod-encryption/vectors.json      the manifest: every positive fixture, every
                                   generated vector, and every file system
                                   vector (layouts a harness builds at test
                                   time, because a repository cannot carry a
                                   FIFO or a device portably)

Every generated header is derived from a committed positive fixture by one
mutation, so a reader that wrongly ACCEPTS a negative vector would open it with
the fixture's test-only key. That makes a missed refusal observable (the Pod
opens) instead of looking like an ordinary wrong-key failure. Vectors that
change the decoded salt or wrapped key cannot keep the key working; a reader
that wrongly accepts one derives a key first, which is a failure in itself.

No cryptography runs here: every mutation edits JSON text or bytes, and the
accept vectors reuse wraps from the positive fixtures unchanged. Standard
library only.

Run:
    python3 scripts/gen_pod_encryption_vectors.py --write
        Regenerate every vector file and vectors.json.

    python3 scripts/gen_pod_encryption_vectors.py --check
        Regenerate in memory and compare with what is committed. Exits 1 on any
        difference, extra file or missing file. CI runs this.
"""

from __future__ import annotations

import argparse
import base64
import copy
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ROOT = REPO / "pod-encryption"
POS = ROOT / "positive"

SPEC = "pod-encryption.md"

# Test-only keys. They protect nothing but the synthetic fixtures in this
# directory and must never be used for a real Pod.
KEY_V10 = "conformance-passphrase-do-not-reuse"
KEY_A = "copper velvet orbit lantern mossy quartz"
KEY_B = "birch meadow anchor violet copper lantern"

MALFORMED = "malformed"
UNSUPPORTED = "unsupported-version"
CANNOT_OPEN = "cannot-open"
OPENED = "opened"


def load(rel: str) -> dict:
    return json.loads((POS / rel).read_text(encoding="utf-8"))


V11 = load("rust-produced-v1.1/single/encryption.json")   # one wrap, opens with KEY_A
V11_TWO = load("rust-produced-v1.1/two-wrap/encryption.json")  # KEY_A, KEY_B
V10 = load("rust-produced-v1.0/encryption.json")           # opens with KEY_V10


def dump(obj) -> bytes:
    return (json.dumps(obj, indent=2) + "\n").encode("utf-8")


def v11(mut=None) -> dict:
    h = copy.deepcopy(V11)
    if mut:
        mut(h)
    return h


def v10(mut=None) -> dict:
    h = copy.deepcopy(V10)
    if mut:
        mut(h)
    return h


def wrap0(h: dict) -> dict:
    return h["wraps"][0]


def keychain(**extra) -> dict:
    w = {"by": "device-keychain", "label": None, "createdAt": None}
    w.update(extra)
    return w


def b64(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")


SALT = wrap0(V11)["kdfParams"]["salt"]
SALT_RAW = base64.b64decode(SALT)
WDEK = wrap0(V11)["wrappedDek"]
WDEK_RAW = base64.b64decode(WDEK)


def replace_once(text: str, old: str, new: str) -> str:
    assert text.count(old) == 1, f"expected exactly one {old!r}"
    return text.replace(old, new)


def text_mut(old: str, new: str, base=None) -> bytes:
    """Mutate the serialized TEXT, for lexical vectors a dict cannot express."""
    return replace_once(dump(base if base is not None else v11()).decode("utf-8"), old, new).encode("utf-8")


def set_path(h: dict, path: list, value):
    node = h
    for k in path[:-1]:
        node = node[k]
    node[path[-1]] = value


def delete(path: list):
    def m(h):
        node = h
        for k in path[:-1]:
            node = node[k]
        del node[path[-1]]
    return m


def setter(path: list, value):
    return lambda h: set_path(h, path, value)


def padded_to(obj: dict, size: int) -> bytes:
    """A valid header padded with trailing JSON whitespace to exactly `size` bytes."""
    raw = dump(obj)
    assert len(raw) <= size
    return raw + b" " * (size - len(raw))


KDF = ["wraps", 0, "kdfParams"]

# (id, slug, expected outcome, spec section, passphrase to try, bytes, what it tests)
VECTORS = [
    # ── JSON and encoding (spec 4.1, 5.1) ──────────────────────────────────
    ("N-001", "not-json", MALFORMED, "4.1", KEY_A,
     dump(v11())[:-40], "truncated JSON"),
    ("N-002", "top-level-array", MALFORMED, "4.1", KEY_A,
     b"[]\n", "the top-level value is not an object"),
    ("N-003", "byte-order-mark", MALFORMED, "5.1", KEY_A,
     b"\xef\xbb\xbf" + dump(v11()), "a UTF-8 byte order mark before an otherwise valid header"),
    ("N-004", "invalid-utf8", MALFORMED, "5.1", KEY_A,
     replace_once(dump(v11()).decode("utf-8"), '"primary"', '"prim\udcffary"').encode("utf-8", "surrogateescape"),
     "a byte 0xFF (never valid UTF-8) inside the label of an otherwise valid header"),
    ("N-005", "header-65537-bytes", MALFORMED, "5.1, 5.3", KEY_A,
     padded_to(v11(), 65537), "a valid header padded with whitespace to one byte over the limit"),

    # ── version, algorithm, wraps (spec 4.2, 5.4) ──────────────────────────
    ("N-006", "version-missing", MALFORMED, "4.2, 5.4", KEY_A,
     dump(v11(delete(["version"]))), "no `version` member"),
    ("N-007", "version-not-string", MALFORMED, "4.2, 5.4", KEY_A,
     text_mut('"version": "1.1"', '"version": 1.1'), "`version` written as a number"),
    ("N-008", "version-unknown", UNSUPPORTED, "4.2, 5.4", KEY_A,
     dump(v11(setter(["version"], "2.0"))), "a version this reader does not know"),
    ("N-009", "version-near-miss", UNSUPPORTED, "4.2", KEY_A,
     dump(v11(setter(["version"], "1.10"))), "`1.10` is not `1.1`: versions are compared as exact strings"),
    ("N-010", "version-padded", UNSUPPORTED, "4.2, 4.5", KEY_A,
     dump(v11(setter(["version"], " 1.1"))), "a leading space: never trimmed"),
    ("N-011", "algorithm-other", MALFORMED, "4.2", KEY_A,
     dump(v11(setter(["algorithm"], "aes-128-gcm"))), "an algorithm other than aes-256-gcm"),
    ("N-012", "algorithm-case", MALFORMED, "4.2, 4.5", KEY_A,
     dump(v11(setter(["algorithm"], "AES-256-GCM"))), "names are case-sensitive"),
    ("N-013", "algorithm-missing", MALFORMED, "4.2", KEY_A,
     dump(v11(delete(["algorithm"]))), "no `algorithm` member"),
    ("N-014", "wraps-missing", MALFORMED, "4.2", KEY_A,
     dump(v11(delete(["wraps"]))), "no `wraps` member"),
    ("N-015", "wraps-empty-v1.1", MALFORMED, "4.2, 6.2", KEY_A,
     dump(v11(setter(["wraps"], []))), "an empty wraps list, version 1.1"),
    ("N-016", "wraps-empty-v1.0", MALFORMED, "4.2, 4.4", KEY_V10,
     dump(v10(setter(["wraps"], []))), "an empty wraps list, version 1.0"),
    ("N-017", "wraps-not-array", MALFORMED, "4.2", KEY_A,
     dump(v11(lambda h: set_path(h, ["wraps"], h["wraps"][0]))), "`wraps` is an object, not a list"),
    ("N-018", "wrap-not-object", MALFORMED, "4.2", KEY_A,
     dump(v11(lambda h: h["wraps"].append("passphrase"))), "a wrap that is a string"),

    # ── wrap kind (spec 4.3) ───────────────────────────────────────────────
    ("N-019", "by-empty", MALFORMED, "4.3", KEY_A,
     dump(v11(lambda h: h["wraps"].insert(0, keychain(by="")))), "a wrap with `by` \"\" is malformed, not an unknown kind to skip"),
    ("N-020", "by-missing", MALFORMED, "4.3", KEY_A,
     dump(v11(lambda h: h["wraps"].insert(0, {"label": None, "createdAt": None}))), "a wrap with no `by`"),
    ("N-021", "by-not-string", MALFORMED, "4.3", KEY_A,
     dump(v11(lambda h: h["wraps"].insert(0, keychain(by=1)))), "a wrap whose `by` is a number"),
    ("N-022", "only-unimplemented-wraps", CANNOT_OPEN, "4.3, 5.4", KEY_A,
     dump(v11(setter(["wraps"], [keychain()]))), "valid, but no wrap of a kind the reader implements"),

    # ── version 1.1 wrap members (spec 4.3) ────────────────────────────────
    ("N-023", "v1.1-top-level-kdfParams", MALFORMED, "4.3", KEY_A,
     dump(v11(lambda h: h.update(kdfParams=copy.deepcopy(wrap0(h)["kdfParams"])))), "1.1 must not carry a top-level kdfParams"),
    ("N-024", "v1.1-top-level-kdf", MALFORMED, "4.3", KEY_A,
     dump(v11(lambda h: h.update(kdf="argon2id"))), "1.1 must not carry a top-level kdf"),
    ("N-025", "v1.1-top-level-kdfParams-null", MALFORMED, "4.3", KEY_A,
     dump(v11(lambda h: h.update(kdfParams=None))), "presence, not value: a null top-level kdfParams is still refused"),
    ("N-026", "v1.1-label-missing", MALFORMED, "4.3", KEY_A,
     dump(v11(delete(["wraps", 0, "label"]))), "`label` is required on every 1.1 wrap (null is allowed, absent is not)"),
    ("N-027", "v1.1-createdAt-missing", MALFORMED, "4.3", KEY_A,
     dump(v11(delete(["wraps", 0, "createdAt"]))), "`createdAt` is required on every 1.1 wrap"),
    ("N-028", "v1.1-label-not-string", MALFORMED, "4.3", KEY_A,
     dump(v11(setter(["wraps", 0, "label"], 1))), "a label that is a number"),
    ("N-029", "v1.1-createdAt-not-string", MALFORMED, "4.3", KEY_A,
     dump(v11(setter(["wraps", 0, "createdAt"], 1727110000))), "a createdAt that is a number"),
    ("N-030", "v1.1-unimplemented-wrap-label-missing", MALFORMED, "4.3", KEY_A,
     dump(v11(lambda h: h["wraps"].insert(0, {"by": "device-keychain"}))), "the three common members are required on a wrap of any kind"),
    ("N-031", "v1.1-no-kdf", MALFORMED, "4.3", KEY_A,
     dump(v11(delete(["wraps", 0, "kdf"]))), "a passphrase wrap without its own kdf"),
    ("N-032", "v1.1-no-kdfParams", MALFORMED, "4.3", KEY_A,
     dump(v11(delete(["wraps", 0, "kdfParams"]))), "a passphrase wrap without its own kdfParams"),
    ("N-033", "v1.1-kdfParams-not-object", MALFORMED, "4.3", KEY_A,
     dump(v11(setter(KDF, "argon2id"))), "kdfParams is a string"),
    ("N-034", "v1.1-no-wrappedDek", MALFORMED, "4.3", KEY_A,
     dump(v11(delete(["wraps", 0, "wrappedDek"]))), "a passphrase wrap with nothing to open"),

    # ── version 1.0 (spec 4.4) ─────────────────────────────────────────────
    ("N-035", "v1.0-no-top-level-kdf", MALFORMED, "4.4", KEY_V10,
     dump(v10(delete(["kdf"]))), "1.0 requires the top-level kdf"),
    ("N-036", "v1.0-no-top-level-kdfParams", MALFORMED, "4.4", KEY_V10,
     dump(v10(delete(["kdfParams"]))), "1.0 requires the top-level kdfParams"),
    ("N-037", "v1.0-unused-kdfParams-outside-limits", MALFORMED, "4.4, 5.3", KEY_V10,
     dump(v10(lambda h: (set_path(h, ["kdfParams", "m"], 131073), set_path(h, ["wraps"], [{"by": "device-keychain"}])))),
     "1.0 top-level parameters are held to the limits even when no wrap uses them"),
    ("N-038", "v1.0-wrappedDek-59-bytes", MALFORMED, "4.4, 5.3", KEY_V10,
     dump(v10(setter(["wraps", 0, "wrappedDek"], b64(base64.b64decode(wrap0(V10)["wrappedDek"])[:59])))), "the 1.0 wrap is held to the same wrappedDek length"),

    # ── limits (spec 5.3) ──────────────────────────────────────────────────
    ("N-039", "kdf-argon2i", MALFORMED, "5.3", KEY_A,
     dump(v11(setter(["wraps", 0, "kdf"], "argon2i"))), "a KDF other than argon2id"),
    ("N-040", "t-zero", MALFORMED, "5.3", KEY_A, dump(v11(setter(KDF + ["t"], 0))), "t below 1"),
    ("N-041", "t-seven", MALFORMED, "5.3", KEY_A, dump(v11(setter(KDF + ["t"], 7))), "t above 6"),
    ("N-042", "p-zero", MALFORMED, "5.3", KEY_A, dump(v11(setter(KDF + ["p"], 0))), "p below 1"),
    ("N-043", "p-five", MALFORMED, "5.3", KEY_A, dump(v11(setter(KDF + ["p"], 5))), "p above 4"),
    ("N-044", "m-below-8p", MALFORMED, "5.3", KEY_A,
     dump(v11(lambda h: (set_path(h, KDF + ["p"], 2), set_path(h, KDF + ["m"], 15)))), "m below 8 * p"),
    ("N-045", "m-above-max", MALFORMED, "5.3", KEY_A, dump(v11(setter(KDF + ["m"], 131073))), "m one KiB above 128 MiB"),
    ("N-046", "t-negative", MALFORMED, "5.3", KEY_A, dump(v11(setter(KDF + ["t"], -3))), "a negative cost"),
    ("N-047", "passphrase-wraps-7", MALFORMED, "5.3", KEY_A,
     dump(v11(lambda h: set_path(h, ["wraps"], [copy.deepcopy(wrap0(h)) for _ in range(7)]))), "seven passphrase wraps"),
    ("N-048", "wraps-17", MALFORMED, "5.3", KEY_A,
     dump(v11(lambda h: h["wraps"].extend(keychain() for _ in range(16)))), "seventeen wraps of any kind"),
    ("N-049", "bad-later-wrap", MALFORMED, "5.2, 5.3", KEY_A,
     dump(v11(lambda h: h["wraps"].append(dict(copy.deepcopy(V11_TWO["wraps"][1]), kdfParams=dict(V11_TWO["wraps"][1]["kdfParams"], t=7))))),
     "the first wrap is valid and opens; a later wrap is outside the limits, so the whole header is refused"),

    # ── number form (spec 4.5) ─────────────────────────────────────────────
    ("N-050", "t-string", MALFORMED, "4.5", KEY_A, text_mut('"t": 3', '"t": "3"'), "a cost written as a string"),
    ("N-051", "t-fraction", MALFORMED, "4.5", KEY_A, text_mut('"t": 3', '"t": 3.0'), "3.0: an integer value, not an integer literal"),
    ("N-052", "m-exponent", MALFORMED, "4.5", KEY_A, text_mut('"m": 65536', '"m": 6.5536e4'), "an exponent"),
    ("N-053", "p-exponent", MALFORMED, "4.5", KEY_A, text_mut('"p": 1', '"p": 1e0'), "1e0 denotes 1 and is still refused"),

    # ── binary values (spec 4.5, 5.3) ──────────────────────────────────────
    ("N-054", "salt-15-bytes", MALFORMED, "4.5, 5.3", KEY_A, dump(v11(setter(KDF + ["salt"], b64(SALT_RAW[:15])))), "a 15-byte salt"),
    ("N-055", "salt-17-bytes", MALFORMED, "4.5, 5.3", KEY_A, dump(v11(setter(KDF + ["salt"], b64(SALT_RAW + b"!")))), "a 17-byte salt"),
    ("N-056", "salt-unpadded", MALFORMED, "4.5", KEY_A, dump(v11(setter(KDF + ["salt"], SALT.rstrip("=")))), "padding removed"),
    ("N-057", "salt-leading-space", MALFORMED, "4.5", KEY_A, dump(v11(setter(KDF + ["salt"], " " + SALT))), "never trimmed"),
    ("N-058", "salt-embedded-newline", MALFORMED, "4.5", KEY_A, dump(v11(setter(KDF + ["salt"], SALT[:12] + "\n" + SALT[12:]))), "a line break inside the value"),
    ("N-059", "salt-url-safe", MALFORMED, "4.5", KEY_A,
     dump(v11(setter(KDF + ["salt"], base64.urlsafe_b64encode(bytes([0xFB, 0xFF] * 8)).decode("ascii")))),
     "the URL-safe alphabet (a different salt, so a reader that accepts it fails the tag instead)"),
    ("N-060", "salt-nonzero-pad-bits", MALFORMED, "4.5", KEY_A,
     dump(v11(setter(KDF + ["salt"], SALT[:-3] + chr(ord(SALT[-3]) + 1) + "=="))), "non-canonical: unused bits in the last character are not zero"),
    ("N-061", "wrappedDek-59-bytes", MALFORMED, "4.5, 5.3", KEY_A, dump(v11(setter(["wraps", 0, "wrappedDek"], b64(WDEK_RAW[:59])))), "one byte short"),
    ("N-062", "wrappedDek-61-bytes", MALFORMED, "4.5, 5.3", KEY_A, dump(v11(setter(["wraps", 0, "wrappedDek"], b64(WDEK_RAW + b"\0")))), "one byte long"),
    ("N-063", "wrappedDek-trailing-space", MALFORMED, "4.5", KEY_A, dump(v11(setter(["wraps", 0, "wrappedDek"], WDEK + " "))), "never trimmed"),
    ("N-064", "wrappedDek-not-string", MALFORMED, "4.3", KEY_A, dump(v11(setter(["wraps", 0, "wrappedDek"], 60))), "a number"),

    # ── headers a reader MUST open (spec 4.1, 4.3, 4.4, 5.3, 5.5) ──────────
    ("A-001", "unknown-kind-skipped", OPENED, "4.3", KEY_A,
     dump(v11(lambda h: h["wraps"].insert(0, keychain()))), "a reserved kind before the passphrase wrap is skipped"),
    ("A-002", "unknown-kind-members-not-interpreted", OPENED, "4.3", KEY_A,
     dump(v11(lambda h: h["wraps"].insert(0, keychain(kdf=7, kdfParams="opaque", wrappedDek=42)))),
     "members of an unimplemented wrap other than by, label and createdAt are not read or validated"),
    ("A-003", "near-miss-by-is-unknown-kind", OPENED, "4.3, 4.5", KEY_A,
     dump(v11(lambda h: h["wraps"].insert(0, keychain(by=" passphrase")))), "\" passphrase\" is an unknown kind, skipped, not a malformed passphrase wrap"),
    ("A-004", "createdAt-free-text", OPENED, "4.3", KEY_A,
     dump(v11(setter(["wraps", 0, "createdAt"], "not a date"))), "createdAt is checked for type only, never parsed"),
    ("A-005", "label-null", OPENED, "4.3", KEY_A,
     dump(v11(setter(["wraps", 0, "label"], None))), "a null label"),
    ("A-006", "duplicate-salts", OPENED, "5.5", KEY_A,
     dump(v11(lambda h: h["wraps"].append(copy.deepcopy(wrap0(h))))), "readers accept two wraps with the same salt (writers never produce one)"),
    ("A-007", "unknown-members-ignored", OPENED, "4.1", KEY_A,
     dump(v11(lambda h: (h.update({"x-note": "ignored"}), wrap0(h).update({"x-note": "ignored"})))), "unknown top-level and wrap members are ignored"),
    ("A-008", "member-order-and-whitespace", OPENED, "4.1", KEY_A,
     (json.dumps({k: V11[k] for k in reversed(list(V11))}, separators=(",", ":")) + "\n").encode("utf-8"),
     "member order and insignificant whitespace do not matter"),
    ("A-009", "header-65536-bytes", OPENED, "5.1, 5.3", KEY_A,
     padded_to(v11(), 65536), "a valid header padded to exactly the limit"),
    ("A-010", "six-passphrase-wraps", OPENED, "5.3", KEY_B,
     dump(v11(lambda h: set_path(h, ["wraps"], [copy.deepcopy(V11_TWO["wraps"][0]) for _ in range(5)] + [copy.deepcopy(V11_TWO["wraps"][1])]))),
     "six passphrase wraps, the last one opening: at the limit, and every wrap is tried in order"),
    ("A-011", "sixteen-wraps", OPENED, "5.3", KEY_A,
     dump(v11(lambda h: h["wraps"].extend(keychain() for _ in range(15)))), "sixteen wraps of any kind"),
    ("A-012", "v1.0-two-passphrase-wraps", OPENED, "4.4, 6.4", KEY_V10,
     dump(v10(lambda h: h["wraps"].append(copy.deepcopy(h["wraps"][0])))), "readable; only migration refuses it"),
    ("A-013", "v1.0-wrap-unknown-members", OPENED, "4.4", KEY_V10,
     dump(v10(lambda h: h["wraps"][0].update(label=5))), "a 1.0 wrap defines no label: any other member is ignored"),
    ("A-014", "v1.0-unimplemented-wrap-first", OPENED, "4.4", KEY_V10,
     dump(v10(lambda h: h["wraps"].insert(0, {"by": "device-keychain"}))), "a 1.0 reserved kind (no label or createdAt in 1.0) is skipped"),
]

# Built at test time by a harness; nothing is committed for these.
FILESYSTEM_VECTORS = [
    {"id": "F-001", "setup": "header-is-directory", "expect": MALFORMED, "spec": "4.1, 5.1",
     "description": "settings/encryption.json is a directory. The Pod is encrypted and the header is refused."},
    {"id": "F-002", "setup": "header-symlink-to-valid-header", "expect": MALFORMED, "spec": "5.1, 8",
     "description": "settings/encryption.json is a symbolic link to a valid header outside the Pod. Never followed; refused."},
    {"id": "F-003", "setup": "header-dangling-symlink", "expect": MALFORMED, "spec": "4.1, 5.1",
     "description": "settings/encryption.json is a symbolic link to nothing. The Pod is encrypted (not plaintext) and the header is refused."},
    {"id": "F-004", "setup": "header-fifo", "expect": MALFORMED, "spec": "5.1",
     "description": "settings/encryption.json is a FIFO with no writer. Refused without blocking."},
    {"id": "F-005", "setup": "header-symlink-to-dev-zero", "expect": MALFORMED, "spec": "5.1",
     "description": "settings/encryption.json is a symbolic link to /dev/zero. Refused, reading at most 65,537 bytes."},
    {"id": "F-006", "setup": "settings-symlink-with-header", "expect": MALFORMED, "spec": "4.1, 5.1",
     "description": "settings is a symbolic link to a directory holding a valid header. Refused."},
    {"id": "F-007", "setup": "settings-symlink-without-header", "expect": MALFORMED, "spec": "4.1",
     "description": "settings is a symbolic link to a directory with no header. The Pod is encrypted, not plaintext, and the header is refused."},
    {"id": "F-008", "setup": "record-file-symlink-outside-pod", "expect": "not-followed", "spec": "8",
     "description": "In the ts-produced-v1.1 Pod, clinical/medications.ttl is replaced by a symbolic link to a sealed copy of it outside the Pod. A reader refuses the path or skips it; it never returns the linked file's records."},
    {"id": "F-009", "setup": "container-symlink-outside-pod", "expect": "not-followed", "spec": "8",
     "description": "In the ts-produced-v1.1 Pod, the clinical directory is replaced by a symbolic link to a copy of it outside the Pod. Never followed."},
]

POSITIVE = [
    {"id": "P-001", "path": "positive/ts-produced-v1.0", "layout": "envelope", "headerVersion": "1.0",
     "producedBy": "cascade-cli (TypeScript)", "passphrases": [KEY_V10],
     "proves": "a reader opens a 1.0 header and a sealed resource written by the TypeScript implementation"},
    {"id": "P-002", "path": "positive/rust-produced-v1.0", "layout": "envelope", "headerVersion": "1.0",
     "producedBy": "an independent Rust implementation", "passphrases": [KEY_V10],
     "proves": "a reader opens a 1.0 header and a sealed resource written by the Rust implementation"},
    {"id": "P-003", "path": "positive/rust-produced-v1.1/single", "layout": "envelope", "headerVersion": "1.1",
     "producedBy": "an independent Rust implementation", "passphrases": [KEY_A],
     "proves": "a 1.1 header with one passphrase wrap carrying its own KDF parameters"},
    {"id": "P-004", "path": "positive/rust-produced-v1.1/two-wrap", "layout": "envelope", "headerVersion": "1.1",
     "producedBy": "an independent Rust implementation", "passphrases": [KEY_A, KEY_B],
     "proves": "two wraps of one data key, each with its own salt; either key opens it, and the second is reached by trying wraps in order"},
    {"id": "P-005", "path": "positive/ts-produced-v1.1/pod", "layout": "pod", "headerVersion": "1.1",
     "producedBy": "cascade-cli (TypeScript): an encrypted Pod created under one key, one synthetic record imported, then re-wrapped under a second key",
     "passphrases": [KEY_B], "mustNotOpenWith": [KEY_A],
     "proves": "a whole Pod as written: every file sealed except the plaintext-by-design ones, a 1.0 header migrated to 1.1 by a re-wrap, the new key opens it and the old key no longer does"},
]


def generate() -> dict[Path, bytes]:
    out: dict[Path, bytes] = {}
    ids = set()
    manifest_vectors = []
    for vid, slug, expect, section, key, data, note in VECTORS:
        assert vid not in ids, vid
        ids.add(vid)
        folder = "accept" if expect == OPENED else "negative"
        rel = f"{folder}/{vid}-{slug}.json"
        out[ROOT / rel] = data
        manifest_vectors.append({
            "id": vid,
            "header": rel,
            "expect": expect,
            "spec": f"{SPEC} section {section}",
            "tryWith": key,
            "description": note,
        })
    manifest = {
        "description": "Cross-implementation vectors for the Cascade Pod encryption format.",
        "spec": f"the-cascade-protocol/spec, {SPEC}, version 1.0",
        "generatedBy": "scripts/gen_pod_encryption_vectors.py (do not edit by hand; run it with --write)",
        "testOnlyKeys": "Every passphrase in this file is a TEST-ONLY value that protects nothing but these synthetic fixtures. Never use one for a real Pod.",
        "outcomes": {
            MALFORMED: "refused before any key derivation: the header breaks a rule or a limit",
            UNSUPPORTED: "refused before any key derivation: a header version this reader does not know",
            CANNOT_OPEN: "refused before any key derivation: valid, but no wrap of a kind the reader implements",
            OPENED: "the header validates and the given key opens it",
            "not-followed": "a symbolic link inside the Pod is refused or skipped; its target is never read",
        },
        "howToRun": "For a negative or accept vector: make an empty directory, write the header bytes to settings/encryption.json inside it, and open it as a Pod with tryWith as the key. For a file system vector: build the described layout in a scratch directory. scripts/check_pod_encryption.py does this for an implementation's command-line interface.",
        "positive": POSITIVE,
        "vectors": manifest_vectors,
        "filesystem": FILESYSTEM_VECTORS,
    }
    out[ROOT / "vectors.json"] = (json.dumps(manifest, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    return out


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--write", action="store_true", help="regenerate every vector file and vectors.json")
    g.add_argument("--check", action="store_true", help="fail if the committed files differ from a fresh generation")
    args = p.parse_args(argv)

    files = generate()
    committed = {
        path for folder in ("negative", "accept") if (ROOT / folder).is_dir()
        for path in (ROOT / folder).iterdir() if path.is_file()
    } | ({ROOT / "vectors.json"} if (ROOT / "vectors.json").exists() else set())

    if args.write:
        for stale in committed - set(files):
            stale.unlink()
        for path, data in files.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        print(f"wrote {len(files)} files ({len(VECTORS)} header vectors, {len(FILESYSTEM_VECTORS)} file system vectors, {len(POSITIVE)} positive fixtures)")
        return 0

    problems = []
    for path, data in sorted(files.items()):
        if not path.exists():
            problems.append(f"missing: {path.relative_to(REPO)}")
        elif path.read_bytes() != data:
            problems.append(f"differs: {path.relative_to(REPO)}")
    for extra in sorted(committed - set(files)):
        problems.append(f"not generated by this script: {extra.relative_to(REPO)}")
    for fx in POSITIVE:
        if not (ROOT / fx["path"]).is_dir():
            problems.append(f"positive fixture missing: {fx['path']}")
    if problems:
        print("Pod encryption vectors are out of date. Run scripts/gen_pod_encryption_vectors.py --write and commit.")
        for line in problems:
            print("  " + line)
        return 1
    print(f"OK: {len(VECTORS)} header vectors, {len(FILESYSTEM_VECTORS)} file system vectors and {len(POSITIVE)} positive fixtures match.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
