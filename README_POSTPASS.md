# Hämta data från PostPass (>900 poster)

## Problem
- Overpass API: 703 element med `ref:stockholmarchipelagotrail`
- PostPass (Geofabrik): **>900 element** (bättre indexering)

## Lösning: Överpass Turbo + PostPass SQL

### Steg 1: Kör query i Overpass Turbo
1. Gå till: https://overpass-turbo.eu/
2. Paste denna query i editorn:

```
{{data:sql,server=https://postpass.geofabrik.de/api/0.2/}}
SELECT osm_id, tags, geom
FROM postpass_pointlinepolygon
WHERE tags ? 'ref:stockholmarchipelagotrail'
```

3. Klicka "Run" (▶)
4. Vänta på resultat (kan ta 10-30 sekunder)
5. Klicka "Export" → "GeoJSON" → spara som `osm_postpass_data.json`

### Steg 2: Integrera i dashboard
```bash
# Flytta filen till sat-sync mappen
mv ~/Downloads/osm_postpass_data.json ./osm_postpass_data.json

# Konvertera till dashboard-format
python3 convert_postpass_to_dashboard.py

# Regenerera dashboard
python3 generate_poi_dashboard.py
```

### Steg 3: Använd i dashboard
Datakällor blir:
- SAT POI: 679
- OSM (standard): 342
- OSM (PostPass): 900+ ← NYTT!

## Varför PostPass?
- **Bättre cachning**: Geofabrik uppdaterar postgis-databasen dagligen
- **Snabbare SQL-queries**: Indexerad databas vs live OSM API
- **Mer data**: Överpass indexerar bara ett urval
- **Flexibel filtrering**: SQL WHERE-villkor

## Tekniska detaljer
- PostPass URL: `https://postpass.geofabrik.de/api/0.2/`
- Tabeller: `postpass_point`, `postpass_line`, `postpass_polygon`, `postpass_pointlinepolygon`
- Format: SQL med GeoJSON geom-kolumn
- Bbox-filtrering: `geom && '((18,58.8),(19,59.5))'::box2d`

## Framtida automation
När PostPass exponerar ett publikt API-endpoint kan vi automatisera:
```python
import requests
response = requests.post(
    'https://postpass.geofabrik.de/api/0.2/',
    data=SQL_QUERY,
    timeout=120
)
```

Tills dess: manuell export från Overpass Turbo
