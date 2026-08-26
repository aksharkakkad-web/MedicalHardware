# Task 2 Report: Calibration Eligibility and Recalibration

## Changes

- Added `backend/app/domain/calibration.py` with the synthetic calibration domain:
  `BaselineStatus`, `CalibrationPolicy`, `CalibrationProgress`,
  `observe_calibration_window()`, and `start_recalibration()`.
- Added the focused test package and three required behavior tests in
  `tests/calibration_domain/`.
- Eligible learning requires `learning_allowed=True`, `concerning=False`, and
  `unresolved_anomaly=False`. Ineligible windows increment exclusions and do not
  advance learning. Setup changes reset physical calibration while retaining
  prior setup-version history.

## TDD evidence

### RED

Command:

```text
python3 -m unittest tests/calibration_domain/test_calibration.py -v
```

Result (before implementation):

```text
test_calibration (unittest.loader._FailedTest.test_calibration) ... ERROR
ModuleNotFoundError: No module named 'backend.app.domain.calibration'
Ran 1 test in 0.000s
FAILED (errors=1)
```

### GREEN

Command:

```text
python3 -m unittest tests/calibration_domain/test_calibration.py -v
```

Result:

```text
test_eligible_windows_advance_calibration ... ok
test_ineligible_windows_never_advance_calibration ... ok
test_setup_change_preserves_history_but_restarts_physical_calibration ... ok
Ran 3 tests in 0.000s
OK
```

## Full-suite evidence

Command:

```text
python3 -m unittest discover -s tests -p 'test_*.py'
```

Result:

```text
Ran 17 tests in 1.076s
OK
```

The repository's bare `python3 -m unittest discover -v` invocation was also
checked; it discovers no tests because this repository's suite is rooted at
`tests/`. The workflow-equivalent `discover -s tests -p 'test_*.py'` command
passed all 17 tests.

## Self-review

- Policy validation rejects a non-positive partial threshold and an established
  threshold that does not exceed it.
- Calibration transitions are monotonic with respect to eligible-window count:
  NEW becomes CALIBRATING on observation, then PARTIAL and ESTABLISHED at the
  configured synthetic thresholds.
- Concerning and unresolved-anomaly windows are excluded even if monitoring
  would otherwise allow learning.
- Recalibration requires a changed setup version and preserves setup history.
- Implementation is immutable (`frozen=True`) and has no persistence, API,
  authentication, notification, clinical, or real sensor behavior.

## Concerns

None for the scoped toy behavior. The public API accepts the Task 1
`baseline_learning_allowed` value as the `learning_allowed` boolean; integration
with actual snapshots remains outside this task's brief.
