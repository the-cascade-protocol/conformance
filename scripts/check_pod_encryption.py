#!/usr/bin/env python3
"""Run the Pod encryption vectors in `pod-encryption/` against an implementation.

The vectors are implementation-neutral (see pod-encryption/vectors.json). This
harness drives one implementation through its command-line interface, for which
there is one adapter so far: `cascade-cli`, the TypeScript reference tool.

    python3 scripts/check_pod_encryption.py --cascade "node /path/to/cli/dist/index.js"
    python3 scripts/check_pod_encryption.py --cascade cascade          # installed on PATH

What each kind of vector asks of the implementation, through the adapter:

  positive      every key opens the fixture and the sealed bytes decrypt to the
                stated plaintext (`pod decrypt` on a scratch copy); a key the
                fixture lists under mustNotOpenWith is refused as incorrect.
  negative      the header is refused BEFORE any key derivation, with the
                expected outcome. A refusal reported as an incorrect passphrase
                means a key was derived first, and counts as a failure.
  accept        the header opens with the given key.
  filesystem    the layout is built in a scratch directory; header layouts must
                be refused as malformed, link layouts must never be followed.

The result is ratcheted against pod-encryption/KNOWN_FAILURES.json the same way
scripts/check_baseline.py ratchets the SHACL suite: a failure that is not listed
fails the run, AND a listed failure for this implementation that now passes fails
the run, so the list can only shrink deliberately. Entries for implementations
this harness does not drive are reported and not checked.

Exit 0: nothing new failed and nothing listed started passing. Exit 1: the
ratchet moved. Exit 2: the harness itself could not run (no implementation,
unreadable manifest).
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ROOT = REPO / "pod-encryption"
TIMEOUT = 60  # seconds; a FIFO or device that hangs the reader must not hang the harness

# ── cascade-cli adapter ──────────────────────────────────────────────────────
# `cascade --json pod info <dir>` opens the Pod with CASCADE_POD_PASSPHRASE.
# Exit 0 is opened. Exit 2 carries a JSON line on stderr whose `reason` names
# the outcome. The cli reports "no wrap of a kind this tool implements" under
# the same reason as an unknown version (both mean "a newer tool wrote this").
CLI_REASON = {
    "manifest-malformed": "malformed",
    "manifest-version-unsupported": ("unsupported-version", "cannot-open"),
    "passphrase-incorrect": "incorrect-secret",
}
IMPLEMENTATION = "cascade-cli"


class Cli:
    def __init__(self, command: str):
        self.argv = shlex.split(command)

    def run(self, args: list[str], passphrase: str | None, cwd: Path) -> tuple[int, str, str]:
        env = {k: v for k, v in os.environ.items() if not k.startswith("CASCADE_POD_")}
        if passphrase is not None:
            env["CASCADE_POD_PASSPHRASE"] = passphrase
        try:
            r = subprocess.run(self.argv + args, cwd=cwd, env=env, capture_output=True, text=True,
                               timeout=TIMEOUT, stdin=subprocess.DEVNULL)
        except subprocess.TimeoutExpired:
            return -1, "", "TIMEOUT"
        return r.returncode, r.stdout, r.stderr

    def open_pod(self, pod: Path, passphrase: str) -> tuple[str, str]:
        """Return (outcome, detail): opened, malformed, unsupported-version|cannot-open, incorrect-secret, timeout, error."""
        code, out, err = self.run(["--json", "pod", "info", str(pod)], passphrase, pod.parent)
        if code == -1:
            return "timeout", "no answer within the time limit"
        if code == 0:
            try:
                info = json.loads(out)
            except json.JSONDecodeError:
                return "error", "exit 0 without JSON"
            if not info.get("encrypted"):
                return "not-encrypted", "opened, and reported the Pod as NOT encrypted"
            return "opened", ""
        reason = ""
        for line in reversed(err.strip().splitlines()):
            try:
                reason = json.loads(line).get("reason", "")
                break
            except (json.JSONDecodeError, AttributeError):
                continue
        mapped = CLI_REASON.get(reason)
        if mapped is None:
            return "error", f"exit {code}, reason {reason or '(none)'}"
        return (mapped if isinstance(mapped, str) else "|".join(mapped)), reason


def matches(outcome: str, expect: str) -> bool:
    return expect in outcome.split("|")


# ── scratch Pods ─────────────────────────────────────────────────────────────

def header_pod(scratch: Path, name: str, header: bytes) -> Path:
    pod = scratch / name
    (pod / "settings").mkdir(parents=True)
    (pod / "settings" / "encryption.json").write_bytes(header)
    return pod


def build_filesystem(scratch: Path, setup: str) -> Path:
    pod = scratch / setup / "pod"
    outside = scratch / setup / "outside"
    outside.mkdir(parents=True)
    valid = (ROOT / "positive/ts-produced-v1.1/pod/settings/encryption.json").read_bytes()
    if setup in ("record-file-symlink-outside-pod", "container-symlink-outside-pod"):
        shutil.copytree(ROOT / "positive/ts-produced-v1.1/pod", pod)
        shutil.copytree(ROOT / "positive/ts-produced-v1.1/pod", outside / "copy")
        if setup == "record-file-symlink-outside-pod":
            (pod / "clinical/medications.ttl").unlink()
            (pod / "clinical/medications.ttl").symlink_to(outside / "copy/clinical/medications.ttl")
        else:
            shutil.rmtree(pod / "clinical")
            (pod / "clinical").symlink_to(outside / "copy/clinical", target_is_directory=True)
        return pod
    settings = pod / "settings"
    if setup.startswith("settings-symlink"):
        pod.mkdir(parents=True)
        real = outside / "settings"
        real.mkdir()
        if setup == "settings-symlink-with-header":
            (real / "encryption.json").write_bytes(valid)
        settings.symlink_to(real, target_is_directory=True)
        return pod
    settings.mkdir(parents=True)
    header = settings / "encryption.json"
    if setup == "header-is-directory":
        header.mkdir()
    elif setup == "header-symlink-to-valid-header":
        (outside / "encryption.json").write_bytes(valid)
        header.symlink_to(outside / "encryption.json")
    elif setup == "header-dangling-symlink":
        header.symlink_to(outside / "missing.json")
    elif setup == "header-fifo":
        os.mkfifo(header)
    elif setup == "header-symlink-to-dev-zero":
        header.symlink_to("/dev/zero")
    else:
        raise ValueError(f"unknown file system setup {setup!r}")
    return pod


# ── the run ──────────────────────────────────────────────────────────────────

def run_all(cli: Cli, manifest: dict, scratch: Path) -> dict[str, tuple[bool, str, str]]:
    """id -> (passed, failure reason code, detail)."""
    results: dict[str, tuple[bool, str, str]] = {}

    for fx in manifest["positive"]:
        src = ROOT / fx["path"]
        problems = []
        for i, key in enumerate(fx["passphrases"]):
            work = scratch / f"{fx['id']}-{i}"
            if fx["layout"] == "envelope":
                pod = work / "pod"
                (pod / "settings").mkdir(parents=True)
                shutil.copy(src / "encryption.json", pod / "settings/encryption.json")
                (pod / "notes").mkdir()
                shutil.copy(src / "resource.bin", pod / "notes/resource.txt")
            else:
                pod = work / "pod"
                shutil.copytree(src, pod)
            code, _, err = cli.run(["--json", "pod", "decrypt", str(pod)], key, work)
            if code != 0:
                problems.append(f"key {i + 1}: decrypt exited {code}: {err.strip()[-160:]}")
                continue
            if (pod / "settings/encryption.json").exists():
                problems.append(f"key {i + 1}: header still present after decrypt")
            if fx["layout"] == "envelope":
                if (pod / "notes/resource.txt").read_bytes() != (src / "plaintext.txt").read_bytes():
                    problems.append(f"key {i + 1}: decrypted bytes differ from plaintext.txt")
        for key in fx.get("mustNotOpenWith", []):
            outcome, _ = cli.open_pod(src, key)
            if outcome != "incorrect-secret":
                problems.append(f"a key that must not open it gave {outcome}")
        results[fx["id"]] = (not problems, "POSITIVE_FAILED" if problems else "", "; ".join(problems))

    for v in manifest["vectors"]:
        pod = header_pod(scratch, v["id"], (ROOT / v["header"]).read_bytes())
        outcome, detail = cli.open_pod(pod, v["tryWith"])
        if matches(outcome, v["expect"]):
            results[v["id"]] = (True, "", "")
        elif v["expect"] == "opened":
            results[v["id"]] = (False, "REFUSED", f"{outcome} ({detail})")
        elif outcome in ("opened", "not-encrypted"):
            results[v["id"]] = (False, "ACCEPTED", outcome)
        elif outcome == "incorrect-secret":
            results[v["id"]] = (False, "DERIVED", "refused only after deriving a key")
        elif outcome == "timeout":
            results[v["id"]] = (False, "TIMEOUT", "")
        else:
            results[v["id"]] = (False, "WRONG_OUTCOME", f"{outcome} ({detail}), expected {v['expect']}")

    for v in manifest["filesystem"]:
        pod = build_filesystem(scratch, v["setup"])
        if v["expect"] == "not-followed":
            code, out, _ = cli.run(["--json", "pod", "query", str(pod), "--medications"],
                                   "birch meadow anchor violet copper lantern", pod.parent)
            followed = code == 0 and "Lisinopril" in out
            results[v["id"]] = (not followed, "FOLLOWED" if followed else "",
                                "returned records read through the link" if followed else "")
            continue
        outcome, detail = cli.open_pod(pod, "birch meadow anchor violet copper lantern")
        if matches(outcome, v["expect"]):
            results[v["id"]] = (True, "", "")
        elif outcome in ("opened", "not-encrypted"):
            results[v["id"]] = (False, "ACCEPTED", outcome)
        elif outcome == "timeout":
            results[v["id"]] = (False, "TIMEOUT", "")
        else:
            results[v["id"]] = (False, "WRONG_OUTCOME", f"{outcome} ({detail})")
    return results


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--cascade", required=True, help='the cascade command, e.g. "node ../cli/dist/index.js"')
    p.add_argument("--keep", action="store_true", help="keep the scratch directory")
    args = p.parse_args(argv)

    try:
        manifest = json.loads((ROOT / "vectors.json").read_text(encoding="utf-8"))
        baseline = json.loads((ROOT / "KNOWN_FAILURES.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: cannot read the vectors or the baseline: {exc}", file=sys.stderr)
        return 2
    cli = Cli(args.cascade)
    code, out, err = cli.run(["--version"], None, REPO)
    if code != 0:
        print(f"ERROR: `{args.cascade} --version` failed: {err.strip()}", file=sys.stderr)
        return 2
    version = out.strip()

    scratch = Path(tempfile.mkdtemp(prefix="pod-encryption-"))
    try:
        results = run_all(cli, manifest, scratch)
    finally:
        if args.keep:
            print(f"scratch kept at {scratch}")
        else:
            shutil.rmtree(scratch, ignore_errors=True)

    listed = {(e["vector"], e["reason"]): e for e in baseline["entries"] if e["implementation"] == IMPLEMENTATION}
    others = [e for e in baseline["entries"] if e["implementation"] != IMPLEMENTATION]
    failed = {(vid, r[1]): r[2] for vid, r in results.items() if not r[0]}
    new = sorted(set(failed) - set(listed))
    gone = sorted(set(listed) - set(failed))
    unknown_ids = sorted({vid for vid, _ in listed} - set(results))

    total = len(results)
    print(f"{IMPLEMENTATION} {version}: {total - len(failed)} passed / {len(failed)} failed / {total} total")
    for (vid, reason), detail in sorted(failed.items()):
        mark = "known" if (vid, reason) in listed else "NEW"
        print(f"  [{mark}] {vid} {reason}: {detail}")
    for vid, reason in gone:
        print(f"  [NOW PASSING] {vid} {reason}: remove it from pod-encryption/KNOWN_FAILURES.json")
    for vid in unknown_ids:
        print(f"  [STALE] {vid}: listed for {IMPLEMENTATION} but not a vector")
    if others:
        print(f"  {len(others)} listed failure(s) for other implementations, not run by this harness")
    ok = not new and not gone and not unknown_ids
    print(f"Verdict: {'OK' if ok else 'RATCHET MOVED'}  ({len(failed) - len(new)} known / {len(new)} new / {len(gone)} now passing)")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
