import sys
import tempfile
from pathlib import Path
from time import perf_counter

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))

from app.catalogue import import_catalogue_csv


def run_benchmark() -> dict:
    with tempfile.TemporaryDirectory() as temp_dir:
        csv_path = Path(temp_dir) / "benchmark_1000.csv"
        lines = ["name,url,platform_key,surface,language"]
        for i in range(950):
            lines.append(f"Destination {i},https://benchmark.example.com/dest/{i},discourse,topic,en")
        # Add 30 duplicates
        for i in range(30):
            lines.append(f"Dup Destination {i},https://benchmark.example.com/dest/{i},discourse,topic,en")
        # Add 20 bad URLs
        for i in range(20):
            lines.append(f"Bad Destination {i},not-a-valid-url,lemmy,post,en")

        csv_path.write_text("\n".join(lines), encoding="utf-8")

        started = perf_counter()
        report = import_catalogue_csv(csv_path)
        elapsed = perf_counter() - started

        result = {
            "total_rows": len(lines) - 1,
            "imported": report["imported"],
            "duplicates": report["duplicates"],
            "bad_rows": report["bad_rows"],
            "elapsed_seconds": round(elapsed, 4),
            "rows_per_second": round((len(lines) - 1) / max(elapsed, 0.001), 2),
            "target_seconds": 300,
            "passed": elapsed < 300,
        }

        # Write or append to docs/benchmarks.md
        benchmarks_file = root / "docs" / "benchmarks.md"
        benchmarks_file.parent.mkdir(parents=True, exist_ok=True)
        content = (
            "# Performance Benchmarks\n\n"
            "## 1. Catalogue Import Benchmark (1,000 rows)\n\n"
            f"- **Target**: 1,000 rows in < 300 seconds (5 minutes)\n"
            f"- **Measured time**: {result['elapsed_seconds']}s\n"
            f"- **Throughput**: {result['rows_per_second']} rows/sec\n"
            f"- **Imported**: {result['imported']}\n"
            f"- **Duplicates detected**: {result['duplicates']}\n"
            f"- **Bad rows rejected**: {result['bad_rows']}\n"
            f"- **Status**: {'PASSED' if result['passed'] else 'FAILED'}\n\n"
        )
        if benchmarks_file.exists():
            existing = benchmarks_file.read_text(encoding="utf-8")
            if "## 1. Catalogue Import Benchmark" in existing:
                # replace section or rewrite
                benchmarks_file.write_text(content, encoding="utf-8")
            else:
                benchmarks_file.write_text(existing + "\n" + content, encoding="utf-8")
        else:
            benchmarks_file.write_text(content, encoding="utf-8")

        print(f"Benchmark completed: {result['elapsed_seconds']}s for {result['total_rows']} rows. Passed: {result['passed']}")
        return result


if __name__ == "__main__":
    run_benchmark()
