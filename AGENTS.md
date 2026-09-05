# AGENTS.md

Conformance fixtures and the canonical reference Patient Pod for the Cascade Protocol. Every SDK and tool must pass the fixtures here before releasing.

## Start here

- `CLAUDE.md` -- fixture format, the ratcheting baseline, current vocabulary coverage and the known gaps class by class.
- `CONTRIBUTING.md` -- setup, what must be green, PR conventions, how to add a fixture.
- `scripts/SPEC_PIN` -- the `spec` revision this suite is measured against, and the counts measured there.

`CLAUDE.md` and this file describe the same repository. `CLAUDE.md` is loaded automatically by Claude Code; this file exists so any coding agent finds the same instructions.

## Protocol context

<https://cascadeprotocol.org/llms.txt> is the protocol index: install, quick start, data types, MCP server, security model, vocabulary versions, deployment sequence. About 95 lines, meant to be read in full.

Do **not** load `llms-full.txt` from that site. It is roughly 1.3 MB, larger than most working contexts, and as of 2026-08-20 its ontology section is known to be incomplete. Read the TTL files in [`spec`](https://github.com/the-cascade-protocol/spec) instead.

## Ground rules

- **Never resolve a failure by weakening the runner.** Do not skip a fixture, relax an assertion, or soften a shape to make a fixture pass.
- **A `.ttl` fixture has THREE possible polarities, and the filename is the assertion.** `*.VALID.ttl` must produce no `sh:Violation`; `*.INVALID.ttl` must produce at least one; `*.WARN.ttl` must produce at least one `sh:Warning` **and** no `sh:Violation`. Reach for the third whenever the constraint under test is `sh:Warning` severity — which is what the `core` v3.5 ratchet makes a value that existing data already carries. Filing such a case as `.VALID.ttl` is the silent-pass failure mode in a new costume: it goes green whether or not anything fires.
- **A fixture reported `UNSHAPED` asserts nothing.** No shape targets it, zero constraints ran, and its PASS is vacuous. The shape belongs in `spec` first.
- **`KNOWN_FAILURES.json` fails in BOTH directions.** An unlisted failure fails CI; a listed failure that starts passing also fails CI. Do not remove the second half, it is the whole reason the list is a ratchet rather than a suppression list. Entries are keyed on (fixture, reason).
- **Always say which `spec` revision you measured against.** The same fixtures score very differently against different vocabulary. Never quote a number obtained with `--allow-spec-drift` as the suite's result.
- **`reference-patient-pod/` is canonical here.** Other repositories carry generated copies held byte-identical to it. Edit it here and nowhere else.

## What must be green

`spec` must be a sibling checkout at the commit named in `scripts/SPEC_PIN`.

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r scripts/requirements.txt
git -C ../spec checkout "$(grep '^commit=' scripts/SPEC_PIN | cut -d= -f2)"

python3 scripts/run_conformance.py --spec-dir ../spec --json results.json  # the truth
python3 scripts/check_baseline.py --results results.json                   # the gate
python3 scripts/selftest_runner.py --spec-dir ../spec                      # proof the gate can fail
python3 scripts/check_literal_fidelity.py                                  # proof the parser did not rewrite the fixtures
```

The suite is red on its own terms; the job is green only when nothing got worse and nothing got better without `KNOWN_FAILURES.json` being updated. The gate exits 2, rather than passing, if the baseline is missing or unparseable, if the run evaluated zero constraints, if it used `--allow-spec-drift`, or if the baseline and the run disagree about the `spec` revision.

## Conventions

- Commits: `feat(fixtures):`, `fix(fixtures):`.
- Tags: `conformance-v{YYYY-MM-DD}`, applied promptly after merge because SDK releases reference them.
- Branch from `main`; open a PR rather than pushing to it.
- Record counts and the `spec` revision in the PR body. Report anything you could not run rather than leaving it implied.
