from enum import StrEnum


class FindingCode(StrEnum):
    SAT_WD_001 = "SAT-WD-001"  # Missing in Wikidata
    SAT_OSM_001 = "SAT-OSM-001"  # Missing in OSM
    WD_OSM_001 = "WD-OSM-001"  # Wikidata and OSM mismatch
    SAT_UNKOWN_001 = "SAT-UNK-001"  # Unknown SAT ID from external source
