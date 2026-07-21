from dataclasses import dataclass, field
from typing import Any

@dataclass(slots=True)
class Finding:
    code: FindingCode
    severity: str
    source: str
    object_id: str