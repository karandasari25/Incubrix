from pathlib import Path
import json

import yaml

from app.main import app
from app.manifest import build_output_manifest
from app.output import OutputStore


def test_openapi_document_matches_running_application_paths():
    path = Path(__file__).resolve().parents[1] / "openapi.yaml"
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    running = app.openapi()
    running_paths = set(running["paths"])
    documented_paths = set(document["paths"])
    assert documented_paths == running_paths
    assert document["openapi"].startswith("3.")
    assert "openapi" in document


def test_output_manifest_contains_required_fields():
    manifest = build_output_manifest(
        providers={"discourse": "1.0.0"},
        settings={"simulation_mode": True},
        seed=42,
        timings={"publish_seconds": 0.01},
        warnings=["mock result"],
        cost_estimate=0.0,
    )
    assert set(("providers", "settings", "seed", "timings", "cost_estimate",
                "warnings", "licence_rights")) == set(manifest)


def test_simulation_output_store_writes_downloadable_file(tmp_path):
    store = OutputStore(root=tmp_path, simulation_mode=True)
    link = store.save("test/result.json", json.dumps({"ok": True}).encode())
    file_path = tmp_path / "test" / "result.json"
    assert file_path.is_file()
    assert link.startswith("simulation://")


def test_batch_cli_module_exposes_one_folder_operation(tmp_path):
    from app.batch import collect_inputs
    folder = tmp_path / "inputs"
    folder.mkdir()
    (folder / "one.json").write_text(json.dumps({"title": "One"}), encoding="utf-8")
    assert collect_inputs(folder) == [folder / "one.json"]


def test_callback_signature_is_hmac_sha256():
    from app.callback import sign_callback
    signature = sign_callback({"job_id": "job-1"}, "test-secret")
    assert len(signature) == 64
