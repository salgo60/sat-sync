from dataclasses import dataclass

@dataclass
class Identity:

    sat_id: str

    osm_id: int | None = None

    wikidata: str | None = None

    name: str | None = None