from copy import deepcopy
from html.parser import HTMLParser

import pytest

from generate_use_cases import ROOT, bi, render_html, validate_cases
from use_cases_data import CASES, PERSONAS, REFERENCE


class Page(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.elements = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        self.elements.append((tag, dict(attrs)))


def test_all_reference_personas_have_traceable_tasks():
    validate_cases(CASES)
    assert len(PERSONAS) == 43
    assert len(CASES) == 16
    assert {ref for case in CASES for ref in case["refs"]} == set(range(1, 44))
    page = Page(render_html())
    ids = [attrs["id"] for _, attrs in page.elements if "id" in attrs]
    assert len(ids) == len(set(ids))
    assert all(f"UC-{number}" in ids for number in range(1, 44))
    assert all(case["id"] in ids for case in CASES)
    links = [attrs["href"] for tag, attrs in page.elements if tag == "a"]
    assert all(f"{REFERENCE}#UC-{number}" in links for number in range(1, 44))
    assert all(link[1:] in ids for link in links if link.startswith("#"))


def test_existing_tool_and_evidence_links_resolve():
    page = Page(render_html())
    for tag, attrs in page.elements:
        if tag == "a":
            href = attrs["href"]
            if not href.startswith(("#", "https://")):
                assert (ROOT / href).is_file(), href
    assert all(case["tools"] and case["evidence"] for case in CASES)


def test_assessment_does_not_claim_flyer_services_are_implemented():
    by_id = {case["id"]: case for case in CASES}
    assert by_id["SAT-08"]["status"] == "partial"  # Booking links, not inventory.
    assert by_id["SAT-11"]["status"] == "planned"  # Trip sharing.
    assert by_id["SAT-12"]["status"] == "planned"  # Events and subscriptions.
    assert [case["id"] for case in CASES if case["status"] == "available"] == ["SAT-14"]


def test_page_is_deterministic_bilingual_and_readable_without_javascript():
    html = render_html()
    assert html == render_html()
    page = Page(html)
    cards = [attrs for tag, attrs in page.elements if tag == "article"]
    assert len(cards) == 16
    assert all("hidden" not in card for card in cards)
    assert 'lang="sv"' in html and 'lang="en"' in html
    assert bi("<script>", '"test"') == '<span lang="sv">&lt;script&gt;</span><span lang="en">&quot;test&quot;</span>'


def test_published_page_matches_generator():
    assert (ROOT / "sat_use_cases.html").read_text(encoding="utf-8") == render_html()


def test_infographic_is_linked_and_explained_in_both_languages():
    html = render_html()
    page = Page(html)
    image = next(attrs for tag, attrs in page.elements if tag == "img")
    assert image["src"] == "assets/sat-use-cases-infographic.jpg"
    assert (ROOT / image["src"]).is_file()
    assert image["width"] == "1024" and image["height"] == "1536"
    assert image["aria-describedby"] == "infographic-caption"
    assert any(tag == "a" and attrs.get("href") == image["src"]
               for tag, attrs in page.elements)
    assert "Konceptöversikt" in html and "Concept overview" in html
    assert "inte en interaktiv karta" in html and "not an interactive map" in html


def test_validation_rejects_unmapped_personas_and_missing_translations():
    cases = deepcopy(CASES)
    for case in cases:
        case["refs"] = [ref for ref in case["refs"] if ref != 43]
    with pytest.raises(ValueError, match="Every original persona"):
        validate_cases(cases)
    cases = deepcopy(CASES)
    cases[0]["gap"] = ("Text", "")
    with pytest.raises(ValueError, match="Missing translation"):
        validate_cases(cases)
