from dataclasses import dataclass, field
from typing import Optional


@dataclass
class StepSpec:
    action:      str
    target_path: Optional[str] = None
    payload:     Optional[str] = None
    mode:        str = "apply"


@dataclass
class StepResult:
    step:           StepSpec
    status:         str          # applied, dry_run_ok, vetoed, io_failed, error, pending_approval
    transaction_id: Optional[str] = None
    io_committed:   Optional[int] = None
    http_status:    int           = 0
    raw:            dict          = field(default_factory=dict)


@dataclass
class MissionContext:
    mission_id:        str
    finalizer_id:      str
    steps:             list           # list[StepSpec]
    guardian_id:       Optional[str] = None
    max_retries:       int            = 3
    retry_delay_secs:  float          = 2.0
    approval_ttl_secs: int            = 86400
