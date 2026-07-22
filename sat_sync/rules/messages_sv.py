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
    FindingCode.WD_OSM_001: {
        "title": "Wikidata och OSM stämmer inte överens",
        "description": "Samma externa objekt mappar till flera SAT-identifierare, eller flera externa identifierare mappar till samma SAT-ID.",
    },
    FindingCode.SAT_UNKOWN_001: {
        "title": "Okänd SAT-identifierare",
        "description": "En SAT-identifierare hittades i externa källor men är inte registrerad i den lokala databasen.",
    },
}