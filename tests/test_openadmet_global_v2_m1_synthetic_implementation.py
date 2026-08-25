from __future__ import annotations

import csv
import importlib
import io
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).parents[1]
RESEARCH = ROOT / "research" / "multitask-mlp"
sys.path.insert(0, str(RESEARCH))
m1 = importlib.import_module("m1_runner")
synthetic = importlib.import_module("run_m1_synthetic")


def _rows(value: bytes) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(value.decode(), newline="")))


def test_implementation_binds_exact_parents_and_isolated_cpu_lock() -> None:
    contract, parent = m1.static_contract()
    assert contract["gate"] == "G2_4B_EXP_M1_SYNTHETIC_CONTRACT_FROZEN"
    assert parent["fit_and_prediction_budget"]["exact_new_neural_fits"] == 2430
    assert m1.sha256_path(m1.CONTRACT) == m1.CONTRACT_SHA256
    assert m1.sha256_path(m1.PARENT) == m1.PARENT_SHA256
    project = (RESEARCH / "pyproject.toml").read_text(encoding="utf-8")
    lock = (RESEARCH / "uv.lock").read_text(encoding="utf-8")
    assert 'requires-python = "==3.12.3"' in project
    assert "torch==2.13.0+cpu" in project
    assert "4ca4a9394b0c771238a4f73590fdbbc4debad85ed0fa63d026ae1b085da7d6e2" in lock
    assert "3cdec01fa790a186d430433fdd4d4ffb70eed6f0eeb4bf05c8dbe2dce0a9bcb8" in lock
    assert "b75944ba959d908e97b4d68754e5950216ac08aa81faf67cfd1d7a3cb5b2bad7" in lock
    forbidden = (
        "nvidia-",
        "cuda-",
        "cudnn",
        "nccl",
        "rocm",
        "triton",
        "torchvision",
        "torchaudio",
        "torchtext",
    )
    assert not any(f'name = "{name}' in lock for name in forbidden)
    assert '"torch' not in (ROOT / "pyproject.toml").read_text(encoding="utf-8")


def test_fit_topology_is_complete_unique_and_exact_by_class() -> None:
    identities = m1.enumerate_fit_identities()
    assert len(identities) == len(set(identities)) == 2430
    counts: dict[tuple[str, str], int] = {}
    for identity in identities:
        counts[(identity.stage, identity.system)] = (
            counts.get((identity.stage, identity.system), 0) + 1
        )
    assert counts == {
        ("INNER", "SHARED"): 360,
        ("OUTER", "SHARED"): 45,
        ("INNER", "INDEPENDENT"): 1440,
        ("OUTER", "INDEPENDENT"): 360,
        ("INNER", "PERMUTED"): 180,
        ("OUTER", "PERMUTED"): 45,
    }
    assert m1.enumerate_fit_identities(reverse_execution_order=True) == list(
        reversed(identities)
    )


def test_initialization_epoch_and_loss_oracles_match_contract() -> None:
    shared = m1.FitIdentity(
        "INNER", "SHARED", 20260810, 0, 0, "CENTRAL_MAE", 20260824, None
    )
    permuted = m1.FitIdentity(
        "INNER", "PERMUTED", 20260810, 0, 0, "CENTRAL_MAE", 20260824, None
    )
    assert shared.initialization_seed == permuted.initialization_seed
    outer = m1.FitIdentity(
        "OUTER", "SHARED", 20260810, 0, None, "CENTRAL_MAE", 20260824, None
    )
    epochs = sorted(
        m1.deterministic_best_epoch(
            m1.FitIdentity(
                "INNER",
                "SHARED",
                20260810,
                0,
                inner,
                "CENTRAL_MAE",
                20260824,
                None,
            )
        )
        for inner in range(4)
    )
    assert m1.outer_epoch(outer) == (epochs[1] + epochs[2]) // 2
    assert [
        m1.shared_loss_token(seed, outer_fold)
        for seed in m1.REPEAT_SEEDS
        for outer_fold in range(5)
    ].count("CENTRAL_MAE") == 10
    selected = [
        m1.independent_loss_token(seed, outer_fold, endpoint)
        for seed in m1.REPEAT_SEEDS
        for outer_fold in range(5)
        for endpoint in m1.ENDPOINTS
    ]
    assert selected.count("CENTRAL_MAE") == 40
    assert selected.count("INTERVAL_DEAD_ZONE") == 20


def test_opposite_execution_order_model_double_files_are_byte_identical() -> None:
    canonical = m1.model_double_files(reverse_execution_order=False)
    reverse = m1.model_double_files(reverse_execution_order=True)
    assert canonical == reverse
    rows = _rows(canonical["model_double_fit_receipts.csv"])
    assert len(rows) == 2430
    assert len({row["fit_receipt_sha256"] for row in rows}) == 2430
    selections = _rows(canonical["loss_selection_receipts.csv"])
    assert len(selections) == 75
    predictions = json.loads(canonical["prediction_receipts.json"])
    assert predictions["inner_raw_rows"] == 57600
    assert predictions["inner_seed_averaged_rows"] == 19200
    assert predictions["outer_raw_rows"] == 11520
    assert predictions["outer_seed_averaged_rows"] == 3840


def test_fixture_is_exact_and_reverse_order_has_same_receipt() -> None:
    canonical = synthetic.build_fixture(reverse=False)
    reverse = synthetic.build_fixture(reverse=True)
    receipt_a = synthetic.fixture_receipt(canonical)
    receipt_b = synthetic.fixture_receipt(reverse)
    assert receipt_a == receipt_b
    assert receipt_a["molecules"] == 100
    assert receipt_a["development_molecules"] == 80
    assert receipt_a["confirmatory_molecules"] == 20
    assert receipt_a["development_truth_rows"] == 320
    assert receipt_a["confirmatory_truth_values_parsed"] == 0
    assert receipt_a["fold_rows"] == 1200
    expected_counts = {
        "finite_central": 64,
        "interval_eligible": 48,
        "point_only": 16,
        "missing_central": 16,
    }
    assert all(
        counts == expected_counts for counts in receipt_a["counts_by_endpoint"].values()
    )


def test_fixture_components_never_cross_a_fold_boundary() -> None:
    fixture = synthetic.build_fixture(reverse=False)
    folds = fixture["folds"]
    for seed in m1.REPEAT_SEEDS:
        for outer in m1.OUTER_FOLDS:
            cell = [
                row
                for row in folds
                if row["repeat_seed"] == seed and row["outer_fold"] == outer
            ]
            by_component: dict[str, list[dict[str, object]]] = {}
            for row in cell:
                by_component.setdefault(str(row["component"]), []).append(row)
            assert len(by_component) == 40
            for rows in by_component.values():
                assert len(rows) == 2
                assert len({row["is_outer_validation"] for row in rows}) == 1
                assert len({row["inner_fold"] for row in rows}) == 1
            outer_components = {
                component
                for component, rows in by_component.items()
                if rows[0]["is_outer_validation"]
            }
            inner_components = {
                component
                for component, rows in by_component.items()
                if rows[0]["inner_fold"] is not None
            }
            assert len(outer_components) == 8
            assert not outer_components & inner_components


def test_preprocessing_is_training_only_shared_and_canonical() -> None:
    rng = np.random.Generator(np.random.PCG64(11))
    raw = rng.normal(size=(12, 2248))
    raw[:, :2048] = rng.integers(0, 5, size=(12, 2048))
    raw[1, 2050] = np.nan
    raw[:, 2051] = 3.0
    train = np.arange(8)
    transformed_a, receipt_a = m1.preprocess_features(raw, train)
    changed = raw.copy()
    changed[8:] += 1000.0
    transformed_b, receipt_b = m1.preprocess_features(changed, train)
    assert receipt_a.medians_sha256 == receipt_b.medians_sha256
    assert receipt_a.means_sha256 == receipt_b.means_sha256
    assert receipt_a.scales_sha256 == receipt_b.scales_sha256
    assert transformed_a.dtype == np.float32
    assert np.array_equal(transformed_a[:8], transformed_b[:8])
    assert np.isfinite(transformed_a).all()
    assert np.all(transformed_a[:, 2051] == 0.0)


def test_permutation_preserves_intact_bundle_multiset_and_scope() -> None:
    rows: list[dict[str, object]] = []
    for index in range(12):
        rows.append(
            {
                "molecule_id": f"m{index:02d}",
                "component": f"c{index // 2:02d}",
                "eligible": index != 11,
                "central": float(index),
                "lower": float(index) - 0.1,
                "upper": float(index) + 0.1,
                "std": 0.05,
                "raw_missingness": f"mask-{index}",
                "assay_source": f"assay-{index}",
                "provenance": f"provenance-{index}",
            }
        )
    output = m1.permute_label_bundles(
        rows,
        repeat_seed=20260810,
        outer_fold=0,
        inner_fold=0,
        endpoint="CYP1A2",
        loss_id="CENTRAL_MAE",
    )
    assert output != rows
    assert output[11] == rows[11]
    fields = (
        "central",
        "lower",
        "upper",
        "std",
        "raw_missingness",
        "assay_source",
        "provenance",
    )
    assert sorted(tuple(row[field] for field in fields) for row in rows[:-1]) == sorted(
        tuple(row[field] for field in fields) for row in output[:-1]
    )


def test_torch_engine_source_has_exact_architecture_optimizer_and_forbiddens() -> None:
    source = m1.SCRIPT.read_text(encoding="utf-8")
    for text in (
        "torch.nn.Linear(FEATURE_WIDTH, 512)",
        "torch.nn.Linear(512, 256)",
        "torch.nn.Linear(256, 64)",
        "torch.nn.Linear(64, 1)",
        "torch.nn.Dropout(0.1)",
        "torch.optim.AdamW",
        "weight_decay=0.0001",
        "torch.use_deterministic_algorithms(True, warn_only=False)",
        "torch.backends.mkldnn.enabled = False",
    ):
        assert text in source
    for forbidden in (
        "torch.compile",
        "autocast",
        "GradScaler",
        "clip_grad",
        "DataLoader",
    ):
        assert forbidden not in source


def test_real_probe_batches_cover_every_form_seed_and_exact_repeats() -> None:
    batches = synthetic.probe_identities()
    assert len(batches) == 4
    assert all(len(batch) == 4 for batch in batches)
    labels = [label for batch in batches for label, _identity in batch]
    identities = {label: identity for batch in batches for label, identity in batch}
    assert len(labels) == 16
    for seed in m1.MODEL_SEEDS:
        for system in ("shared", "independent"):
            for loss in ("CENTRAL", "INTERVAL"):
                assert f"{system} {loss} seed {seed}" in labels
    assert sum(label.startswith("permuted") for label in labels) == 2
    assert (
        identities["independent CENTRAL seed 20260824"]
        == identities["independent CENTRAL seed 20260824 resource-repeat-1"]
    )
    assert (
        identities["independent INTERVAL seed 20260824"]
        == identities["independent INTERVAL seed 20260824 resource-repeat-1"]
    )


def _fake_formal_root(root: Path) -> None:
    root.mkdir()
    files = m1.model_double_files()
    files["fixture_receipt.json"] = m1.json_bytes(
        synthetic.fixture_receipt(synthetic.build_fixture(reverse=False))
    )
    labels = [label for batch in synthetic.probe_identities() for label, _ in batch]
    rows = []
    for index, label in enumerate(labels):
        canonical_label = label.replace(" resource-repeat-1", "")
        independent = label.startswith("independent")
        rows.append(
            {
                "batch_index": index // 4,
                "slot_index": index % 4,
                "probe_label": label,
                "architecture_class": (
                    "independent" if independent else "shared_or_permuted"
                ),
                "loss_id": (
                    "INTERVAL_DEAD_ZONE" if "INTERVAL" in label else "CENTRAL_MAE"
                ),
                "model_seed": label.split("seed ")[1].split()[0],
                "child_wall_seconds": 5.0,
                "child_cpu_seconds": 2.0 if independent else 4.0,
                "peak_rss_kib": 1_000_000,
                "parameter_sha256": m1.sha256_bytes(
                    f"parameter|{canonical_label}".encode()
                ),
                "prediction_sha256": m1.sha256_bytes(
                    f"prediction|{canonical_label}".encode()
                ),
                "prediction_rows": 997,
                "prediction_columns": 1 if independent else 4,
            }
        )
    files["runtime_probe_receipts.csv"] = m1.csv_bytes(synthetic.PROBE_FIELDS, rows)
    files["resource_observations.json"] = m1.json_bytes(
        {
            "preprocessing_wall_seconds": 2.0,
            "preprocessing_cpu_seconds": 1.0,
            "batch_walls": [
                {
                    "batch_index": index,
                    "architecture_class": (
                        "shared_or_permuted" if index < 2 else "independent"
                    ),
                    "wall_seconds": 10.0 if index < 2 else 5.0,
                }
                for index in range(4)
            ],
            "nonfit_nonpreprocessing_wall_seconds": 3.0,
            "nonfit_nonpreprocessing_cpu_seconds": 1.0,
            "environment_bytes": 1_000_000_000,
            "cache_bytes": 500_000_000,
            "work_bytes": 500_000_000,
            "maximum_simultaneous_child_rss_kib": 4_000_000,
            "gpu_hours": 0,
        }
    )
    for name, value in files.items():
        (root / name).write_bytes(value)


def test_resource_projection_uses_worst_conservative_formulas(tmp_path: Path) -> None:
    root_a = tmp_path / "a"
    root_b = tmp_path / "b"
    _fake_formal_root(root_a)
    _fake_formal_root(root_b)
    projection = synthetic.project_resources(root_a, root_b)
    assert projection["accepted"]
    assert projection["gates"] == {
        "cpu": True,
        "gpu": True,
        "wall": True,
        "storage": True,
        "rss": True,
    }
    assert (
        projection["projected_wall_hours"] == (158 * 10 + 450 * 5 + 75 * 2 + 3) / 3600
    )
    assert (
        projection["projected_cpu_core_hours"]
        == (630 * 4 + 1800 * 2 + 75 * 1 + 1) / 3600
    )
    assert projection["projected_gpu_hours"] == 0


def test_formal_claim_authenticates_every_source_and_fixed_path(tmp_path: Path) -> None:
    claim = {
        "schema_version": "cypshift.openadmet_cyp_2026.m1_formal_attempt_claim.v1",
        "contract_sha256": m1.CONTRACT_SHA256,
        "maximum_attempts": 1,
        "consumed": False,
        "attempt_id": "g2-4c-m1-synthetic-attempt-1",
        "source_bindings": {
            "research_pyproject_sha256": m1.sha256_path(RESEARCH / "pyproject.toml"),
            "research_python_pin_sha256": m1.sha256_path(RESEARCH / ".python-version"),
            "research_uv_lock_sha256": m1.sha256_path(RESEARCH / "uv.lock"),
            "m1_runner_sha256": m1.sha256_path(m1.SCRIPT),
            "m1_synthetic_driver_sha256": m1.sha256_path(synthetic.SCRIPT),
            "focused_test_sha256": m1.sha256_path(Path(__file__)),
        },
        "paths": {
            "root_a": str(tmp_path / "a"),
            "root_b": str(tmp_path / "b"),
            "receipt_root": str(tmp_path / "receipt"),
            "environment_root": str(RESEARCH / ".venv"),
            "cache_root": str(tmp_path / "cache"),
        },
    }
    path = tmp_path / "claim.json"
    path.write_bytes(m1.json_bytes(claim))
    assert synthetic.load_formal_claim(path) == claim
    claim["maximum_attempts"] = 2
    path.write_bytes(m1.json_bytes(claim))
    with np.testing.assert_raises_regex(m1.M1Error, "attempt count"):
        synthetic.load_formal_claim(path)
