import argparse
import json
from pathlib import Path

import httpx


def collect_inputs(source: str | Path) -> list[Path]:
    source = Path(source)
    if source.is_file():
        return [source]
    if not source.is_dir():
        raise ValueError(f"Input source does not exist: {source}")
    return sorted(path for path in source.rglob("*") if path.is_file()
                  and path.suffix.lower() in {".json", ".csv"})


def run_batch(api_url: str, source: str | Path, output_dir: str | Path) -> dict:
    source_files = collect_inputs(source)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    results = []
    for index, path in enumerate(source_files, start=1):
        payload = json.loads(path.read_text(encoding="utf-8")) if path.suffix.lower() == ".json" else {
            "csv_file": str(path),
            "destinations": [],
        }
        idempotency_key = f"batch-{index}-{path.stem}"
        response = httpx.post(
            f"{api_url.rstrip('/')}/api/v1/publish",
            json=payload,
            headers={"Idempotency-Key": idempotency_key},
            timeout=30,
        )
        result = {
            "input": str(path),
            "http_status": response.status_code,
            "response": response.json(),
        }
        (output_dir / f"{index:04d}-{path.stem}.json").write_text(
            json.dumps(result, indent=2),
            encoding="utf-8",
        )
        results.append(result)
    summary = {"count": len(results), "results": results}
    (output_dir / "batch-summary.json").write_text(
        json.dumps(summary, indent=2),
        encoding="utf-8",
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Run IncuBrix batch inputs")
    parser.add_argument("--api-url", default="http://127.0.0.1:8000")
    parser.add_argument("--source", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    run_batch(args.api_url, args.source, args.output_dir)


if __name__ == "__main__":
    main()
