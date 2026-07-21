import json
from sat_sync.sources.taginfo import TaginfoSource


def test_taginfo_source_starts_empty():

    source = TaginfoSource()

    assert source.identifiers() == set()
    


def test_create_taginfo_source():
    source = TaginfoSource()
    assert source is not None



def test_taginfo_reads_identifiers(tmp_path):

    data = [
        {"value": "sat:poi:abc12"},
        {"value": "sat:pier:def34"},
    ]

    filename = tmp_path / "taginfo.json"
    filename.write_text(json.dumps(data))

    source = TaginfoSource(filename)

    assert source.identifiers() == {
        "sat:poi:abc12",
        "sat:pier:def34",
    }