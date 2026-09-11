import copy
from html.parser import HTMLParser

import pytest

from generate_osm_ref_report import (
    CATEGORY_EN,
    CATEGORY_ORDER,
    build_report as build_ref_report,
    render_report as render_ref_report,
)
from generate_osm_trail_report import (
    build_report as build_trail_report,
    render_report as render_trail_report,
)
from report_i18n import attribute, text


class ReportMarkup(HTMLParser):
    def __init__(self, markup):
        super().__init__(convert_charrefs=True)
        self.elements = []
        self.feed(markup)

    def handle_starttag(self, tag, attrs):
        self.elements.append((tag, dict(attrs)))


@pytest.fixture(params=["ref", "trail"])
def rendered_report(request):
    if request.param == "ref":
        report = build_ref_report(
            [{"type": "node", "id": 1, "tags": {"amenity": "toilets"}}], "test"
        )
        render = render_ref_report
    else:
        report = build_trail_report(
            [{
                "type": "relation",
                "id": 19012437,
                "members": [],
                "tags": {"name": "SAT"},
            }], "test"
        )
        render = render_trail_report
    original = copy.deepcopy(report)
    markup = render(report)
    assert render(report) == markup
    assert report == original
    return ReportMarkup(markup)


def test_reports_have_translated_titles_controls_and_captions(rendered_report):
    elements = rendered_report.elements
    title = next(attrs for tag, attrs in elements if tag == "title")
    assert title["data-en"].startswith("OSM ")
    assert title["data-sv"] != title["data-en"]
    button = next(attrs for tag, attrs in elements if attrs.get("id") == "lang-btn")
    assert button["type"] == "button"
    for tag, attrs in elements:
        if tag == "input":
            assert attrs["data-sv-placeholder"] == attrs["placeholder"]
            assert attrs["data-en-placeholder"].startswith("Search ")
        if tag in {"input", "select"}:
            assert attrs["data-en-aria-label"]
        if tag == "img":
            assert attrs["data-sv-alt"] == attrs["alt"]
            assert attrs["data-en-alt"].startswith("Swedish ")
    captions = [attrs for tag, attrs in elements if tag == "small"]
    assert len(captions) == 3
    assert all("Text within the image is in Swedish." in a["data-en"] for a in captions)


def test_report_navigation_carries_language(rendered_report):
    links = [
        attrs
        for tag, attrs in rendered_report.elements
        if tag == "a" and attrs.get("href", "").startswith("sat_")
    ]
    assert len(links) == 3
    assert all("data-lang-link" in attrs for attrs in links)


def test_all_osm_categories_have_english_labels():
    assert set(CATEGORY_EN) == set(CATEGORY_ORDER)
    assert all(CATEGORY_EN.values())
    assert CATEGORY_EN["Vindskydd"] == "Trail shelter"
    assert CATEGORY_EN["Övrigt"] == "Other"


def test_translation_helpers_escape_text_and_attribute_values():
    unsafe = '"><script>alert(1)</script>&'
    markup = ReportMarkup(text(unsafe, unsafe, "strong"))
    assert markup.elements == [("strong", {"data-sv": unsafe, "data-en": unsafe})]
    assert unsafe not in text(unsafe, unsafe)
    attrs = ReportMarkup(f'<input {attribute("placeholder", unsafe, unsafe)}>').elements[0][1]
    assert attrs == {
        "placeholder": unsafe,
        "data-sv-placeholder": unsafe,
        "data-en-placeholder": unsafe,
    }
