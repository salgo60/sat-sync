import io
import json
import runpy
from pathlib import Path

import pytest

from osm_display_name import osm_display_name


@pytest.mark.parametrize("tags, expected", [
    ({"emergency": "defibrillator"}, "emergency=defibrillator"),
    ({"tourism": "viewpoint"}, "tourism=viewpoint"),
    ({"name": "Existing", "description:sv": "Description"}, "Existing"),
    ({"description:sv": " Svenska ", "description": "Other"}, "Svenska"),
    ({"name": " ", "description:sv": " ", "description": "Description",
      "tourism": "viewpoint"}, "Description"),
    ({"access": "yes", "wheelchair": "no"}, "OSM node:123"),
    ({"emergency": "no", "tourism": "viewpoint"}, "tourism=viewpoint"),
    ({"name": "OSM community meeting place"}, "OSM community meeting place"),
])
def test_osm_display_label_priority(tags, expected):
    assert osm_display_name(tags, "node:123") == expected


def test_converter_and_dashboard_keep_candidate_labels(tmp_path, monkeypatch):
    from generate_poi_dashboard import POIDashboardGenerator
    root = Path(__file__).resolve().parents[1]
    examples = [
        (13930058601, {"emergency": "defibrillator"}, "emergency=defibrillator"),
        (13144299619, {"tourism": "viewpoint"}, "tourism=viewpoint"),
        (863394760, {"tourism": "viewpoint"}, "tourism=viewpoint"),
        (123, {"description:sv": "</script><b>Beskrivning</b>"}, "</script><b>Beskrivning</b>"),
        (124, {"name": "OSM community meeting place"}, "OSM community meeting place"),
    ]
    features = [
        {"properties": {"osm_id": osm_id, "tags": tags},
         "geometry": {"type": "Point", "coordinates": [18.9, 59.3]}}
        for osm_id, tags, _ in examples
    ]
    (tmp_path / "osm_postpass_data.json").write_text(json.dumps({"features": features}))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **kw: io.BytesIO(b'{"features": []}'))
    runpy.run_path(str(root / "convert_osm_raw_candidates.py"))
    candidates = json.loads((tmp_path / "osm_candidates.json").read_text())["features"]
    assert [f["properties"]["name"] for f in candidates] == [item[2] for item in examples]
    generator = POIDashboardGenerator(email="test@example.com")
    monkeypatch.setattr(generator, "fetch_latest_pr", lambda: (0, ""))
    html = generator.generate_html([], [], {}, [], osm_candidates=candidates)
    encoded = html.split("const osmCandidateMapData = ", 1)[1].split(";\n", 1)[0]
    data = json.loads(encoded)
    assert [p["name"] for p in data] == [item[2] for item in examples]
    assert "</script><b>" not in encoded
    assert all(p["category"] == "Övrigt" for p in data)
