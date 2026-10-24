from dataclasses import dataclass

@dataclass
class Identity:

    sat_id: str | None

    osm_id: int | str | None = None

    wikidata: str | None = None

    name: str | None = None