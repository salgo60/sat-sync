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
}

