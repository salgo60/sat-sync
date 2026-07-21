from dataclasses import dataclass

from sat_sync.rules.codes import FindingCode


@dataclass(slots=True)
class Finding:
    code: FindingCode
    severity: str
    source: str
    object_id: str