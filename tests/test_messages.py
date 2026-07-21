from sat_sync.rules.codes import FindingCode
from sat_sync.rules.messages_en import MESSAGES as EN
from sat_sync.rules.messages_sv import MESSAGES as SV


def test_all_codes_have_translations():
    for code in FindingCode:
        assert code in EN
        assert code in SV


def test_language_catalogs_have_same_keys():
    assert EN.keys() == SV.keys()