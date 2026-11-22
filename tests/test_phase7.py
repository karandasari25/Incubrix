from app.catalogue import import_catalogue_csv
from app.ai import MockAIAdapter, confirm_captured_rules
from app.recommendation import rank_destinations
from app.tailoring import tailor_rendition
from app.connectors.loader import ConnectorLoader


def test_csv_import_normalizes_deduplicates_and_reports_bad_rows(tmp_path):
    path = tmp_path / "catalogue.csv"
    path.write_text(
        "name,url,platform_key,surface,language\n"
        "One,HTTPS://Example.com/forum/,forum,topic,en\n"
        "Duplicate,https://example.com/forum,forum,topic,en\n"
        "Bad,not-a-url,forum,topic,en\n",
        encoding="utf-8",
    )
    report = import_catalogue_csv(str(path))
    assert report["imported"] == 1
    assert report["duplicates"] == 1
    assert report["bad_rows"] == 1
    assert report["rows"][2]["errors"]


def test_mock_ai_adapter_requires_human_confirmation():
    adapter = MockAIAdapter()
    candidate = adapter.capture_rules("Promotional posts require a disclosure")
    assert candidate["status"] == "pending_confirmation"
    assert confirm_captured_rules(candidate) == "Use of captured AI rules requires human confirmation"


def test_relevance_score_is_bounded_and_reasoned():
    destinations = [
        {"id": "video", "audience_tags": ["video", "creators"], "relevance_score": 5,
         "relevance_reason": "Strong video creator audience"},
        {"id": "finance", "audience_tags": ["finance"], "relevance_score": 2,
         "relevance_reason": "Limited audience fit"},
    ]
    ranked = rank_destinations(destinations, {"audience": ["video", "creators"]})
    assert ranked[0]["id"] == "video"
    assert 1 <= ranked[0]["relevance_score"] <= 5


def test_destination_tailoring_adds_canonical_and_truncates_word_boundary():
    rendition = tailor_rendition(
        {"title": "A" * 300, "body": "word " * 100, "canonical_link": "https://example.com/post",
         "tags": ["one", "two"]},
        {"surface": "forum", "category": "community"},
        {"title_max": 30, "body_max": 80},
    )
    assert len(rendition["title"]) <= 30
    assert "https://example.com/post" in rendition["body"]
    assert not rendition["title"].endswith(" ")
    assert "#one" in rendition["tags"]


def test_three_extra_manifests_load():
    loader = ConnectorLoader()
    for key in ("mrss", "hashnode", "kit"):
        manifest = loader.load(key)
        assert manifest["key"] == key
