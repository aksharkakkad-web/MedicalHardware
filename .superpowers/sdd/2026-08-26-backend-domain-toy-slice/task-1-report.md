# Task 1 Report: Monitoring Suitability State

## What changed

Implemented the pure standard-library monitoring suitability domain logic. The new API models presence, monitoring state, and deterministic reasons, and derives an immutable `MonitoringSnapshot` from assignment validity, device health, presence, and signal quality.

Invalid assignment or unhealthy device takes precedence and makes monitoring unavailable. Resident-away pauses resident-specific measurements and baseline learning without a warning reason beyond `resident_away`. Possible multi-person presence limits resident-specific monitoring. Unknown presence and low signal quality produce limited monitoring. Only known resident presence with acceptable signal quality is active and eligible for learning.

## Files

- `backend/app/domain/monitoring.py`
- `tests/monitoring_domain/__init__.py`
- `tests/monitoring_domain/test_monitoring.py`

## TDD evidence

RED command:

```text
$ python3 -m unittest tests/monitoring_domain/test_monitoring.py -v
...
ImportError: Failed to import test module: test_monitoring
ModuleNotFoundError: No module named 'backend.app.domain.monitoring'
FAILED (errors=1)
```

Focused GREEN command:

```text
$ python3 -m unittest tests/monitoring_domain/test_monitoring.py -v
....
Ran 4 tests in 0.000s

OK
```

Full-suite GREEN command:

```text
$ python3 -m unittest discover -s tests -v
..............
Ran 14 tests in 1.097s

OK
```

Additional verification: `python3 -m compileall -q backend tests` completed successfully, and `git diff --check` reported no whitespace errors.

## Self-review

- Confirmed the implementation is pure Python standard-library code with no database, API, authentication, notification, sensor-processing, or production-threshold dependencies.
- Confirmed the snapshot is frozen and reasons preserve deterministic ordering.
- Confirmed unavailable conditions take precedence over presence and quality states, while away and possible-multi-person states prevent resident-specific learning and measurements.
- Confirmed existing event and repository-policy tests remain green.

## Concerns

- The default `minimum_quality=0.6` is a domain-demo value from the task brief, not a production threshold; hardware validation should determine production policy later.
- The generic command `python3 -m unittest discover -v` finds no tests because this repository requires `-s tests`; the meaningful full-suite command is recorded above.
