from sat_sync.rules.codes import FindingCode

MESSAGES = {
    FindingCode.SAT_WD_001: {
        "title": "Saknar Wikidata-länk",
        "description": "SAT-objektet saknar en länk till ett Wikidata-objekt.",
    },
    FindingCode.SAT_OSM_001: {
  	    "title": "Saknas i OpenStreetMap",
         "description": "Det statiska SAT-identifieraren finns inte i OpenStreetMap.",
},
}