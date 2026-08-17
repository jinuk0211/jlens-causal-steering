import importlib.util
from pathlib import Path


def _load_script():
    path = Path(__file__).parents[1] / "scripts" / "audit_core7_benchmark_protocol.py"
    spec = importlib.util.spec_from_file_location("audit_core7_benchmark_protocol", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_checked_protocol_is_implementation_ready():
    script = _load_script()
    root = Path(__file__).parents[1]
    report = script.audit_protocol(
        root,
        root.parent / "tau2-bench",
        matrix_path=root / "outputs" / "taubench-airline-failure-matrix.json",
    )

    assert report["implementation_ready"]
    assert report["implementation_checks"]["core7_matrix_coverage"]["passed"]
    assert report["implementation_checks"]["jservo_adaptive_controls"]["passed"]
    assert report["implementation_checks"]["remote_only_no_local_model"]["passed"]
    assert report["implementation_checks"]["official_airline_split"]["passed"]
    assert report["empirical_checks"]["taubench_reviewed_conditions"]["evidence"]["expected"] == 83
    assert report["empirical_checks"]["toolalign_paired_analyses"]["evidence"]["expected"] == 16
