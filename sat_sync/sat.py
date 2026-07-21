from pathlib import Path
import json

from .models import Identity


def identities(datafile: Path):
    with open(datafile, encoding="utf-8") as f:
        data = json.load(f)
        
    return [
        Identity(
            sat_id=item["sat_id"],
            name=item["name"],
        )
        for item in data
    ]