# Wellness Conformance Fixtures (Inventory)

**Vocabulary covered:** `health` v2.10 and `core` v3.10, the wellness and
fitness round (spec branch `feat/health-v2-10`).

Standalone SHACL-validation fixtures with polarity in the filename, as in
`../core/INVENTORY.md`.

| File | Polarity | What it asserts |
|---|---|---|
| `health-v2-10-records.VALID.ttl` | VALID | One wellness document holding a named `health:DailyVitalReading` with its UTC interval, statistic, cut zone and device; a `health:Workout` whose route is a `cascade:Attachment`; a `health:SleepSession` with stage totals and a source-supplied score; and the two `health:Device` records they point at. Expected: zero Violations and zero Warnings, so any Warning here is a regression. |

Related fixtures filed by the shape that owns the constraint:
`../health/aggregate-v2-9-shape.WARN.ttl`,
`../health/sleep-quality-deprecated.WARN.ttl`, `../core/statistic-mean.WARN.ttl`,
`../core/day-zone.VALID.ttl`, `../core/day-zone-offset.WARN.ttl`, and the JSON
fixtures `workout-*`, `sleepsession-*`, `healthdevice-*`.

Run against the branch (the pin moves only when the spec branch merges):

```sh
python3 scripts/run_conformance.py --spec-dir ../spec-wt-health-v2-10 --allow-spec-drift
```

Fully synthetic.
