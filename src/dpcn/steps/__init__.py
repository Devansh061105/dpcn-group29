"""Pipeline steps. Each module exposes `run(cfg, oa, argv)` and raises StepFailed on a failed check."""


class StepFailed(RuntimeError):
    pass
