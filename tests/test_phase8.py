from pathlib import Path
from time import perf_counter
import tempfile

from app.catalogue import import_catalogue_csv


def test_delivery_documents_exist():
    root = Path(__file__).resolve().parents[1]
    for name in ("REPORT.md", "EVIDENCE.md", "SOURCES.md", "AI_USE.md",
                 "Submission-Form-Guide.md", "Demo-Script.md"):
        assert (root / name).is_file()


def test_one_thousand_catalogue_rows_complete_under_five_minutes():
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "catalogue.csv"
        lines = ["name,url,platform_key,surface,language"]
        lines.extend(
            f"Destination {index},https://example.com/{index},forum,topic,en"
            for index in range(1000)
        )
        path.write_text("\n".join(lines), encoding="utf-8")
        started = perf_counter()
        report = import_catalogue_csv(path)
        elapsed = perf_counter() - started
        assert report["imported"] == 1000
        assert elapsed < 300
