from sat_sync.rules.codes import FindingCode

MESSAGES = {
    FindingCode.SAT_WD_001: {
        "title": "Missing Wikidata link",
        "description": "The SAT object has no linked Wikidata item.",
    },
    FindingCode.SAT_OSM_001: {
        "title": "Missing in OpenStreetMap",
        "description": "The static SAT identifier does not exist in OpenStreetMap.",
    },
    FindingCode.WD_OSM_001: {
        "title": "Wikidata and OSM mismatch",
        "description": "The same external object maps to multiple SAT identifiers, or multiple external identifiers map to the same SAT ID.",
    },
    FindingCode.SAT_UNKOWN_001: {
        "title": "Unknown SAT identifier",
        "description": "A SAT identifier was found in external sources but is not registered in the local database.",
    },
}


