from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).parents[1]
BENCHMARK = ROOT / "benchmarks" / "openadmet_cyp_2026"
CONTRACT_PATH = BENCHMARK / "global_v2_m1_synthetic_contract.json"
PARENT_PATH = BENCHMARK / "global_v2_m1_screen_contract.json"
CONTRACT_SHA256 = "f80a6e8d7735a67ddebf636958aea0b56e738afbc3d10bcea2450ec168048df7"


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _component_pool() -> tuple[list[str], list[str]]:
    development: list[str] = []
    confirmatory: list[str] = []
    counter = 0
    while len(development) < 40 or len(confirmatory) < 10:
        component = hashlib.sha256(
            f"cypshift-m1-synthetic-component-v1|{counter}".encode()
        ).hexdigest()
        material = f"openadmet-global-v2-confirmatory-v1|20260824|{component}"
        value = int.from_bytes(hashlib.sha256(material.encode()).digest()[:8], "big")
        target = confirmatory if value % 5 == 0 else development
        limit = 10 if target is confirmatory else 40
        if len(target) < limit:
            target.append(component)
        counter += 1
    return development, confirmatory


def test_m1_synthetic_contract_has_exact_identity_and_parents() -> None:
    contract = _load(CONTRACT_PATH)
    assert _sha256(CONTRACT_PATH) == CONTRACT_SHA256
    assert contract["schema_version"] == (
        "cypshift.openadmet_cyp_2026.global_v2_m1_synthetic_contract.v1"
    )
    assert contract["gate"] == "G2_4B_EXP_M1_SYNTHETIC_CONTRACT_FROZEN"
    assert contract["status"] == (
        "contract_only_no_runtime_install_or_synthetic_execution_authority"
    )
    assert contract["base_commit"] == "8ebc45bc5585d495ed3b2cd920bbc6f2e3ae80b3"
    for parent in contract["parents"].values():
        path = BENCHMARK / parent["path"]
        assert path.is_file()
        assert _sha256(path) == parent["sha256"]


def test_cpu_only_host_profile_is_exact_and_fails_closed() -> None:
    host = _load(CONTRACT_PATH)["host_profile"]
    assert host["platform"] == "Linux x86_64"
    assert host["cpu_vendor"] == "AuthenticAMD"
    assert host["cpu_model_name"] == "AMD Ryzen 9 7950X 16-Core Processor"
    assert (host["cpu_family"], host["cpu_model"], host["cpu_stepping"]) == (
        25,
        97,
        2,
    )
    assert host["physical_cores"] == 16
    assert host["logical_processors"] == 32
    assert host["mem_total_kib_observed"] >= 30 * 1024 * 1024
    assert host["cuda_devices"] == host["rocm_devices"] == 0
    assert "exactly zero" in host["gpu_policy"]
    assert "Drift fails before a probe" in host["execution_preflight"]


def test_runtime_is_exact_cpu_torch_and_isolated_from_public_core() -> None:
    runtime = _load(CONTRACT_PATH)["runtime_contract"]
    assert runtime["isolation_directory"] == "research/multitask-mlp"
    assert runtime["python"] == "3.12.3"
    assert runtime["uv"] == "0.12.3"
    assert runtime["numpy"] == {
        "version": "2.5.2",
        "wheel": (
            "numpy-2.5.2-cp312-cp312-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl"
        ),
        "sha256": "3cdec01fa790a186d430433fdd4d4ffb70eed6f0eeb4bf05c8dbe2dce0a9bcb8",
    }
    assert runtime["rdkit"]["version"] == "2026.3.5"
    assert runtime["rdkit"]["sha256"] == (
        "b75944ba959d908e97b4d68754e5950216ac08aa81faf67cfd1d7a3cb5b2bad7"
    )
    torch = runtime["torch"]
    assert torch["version"] == "2.13.0+cpu"
    assert torch["wheel_sha256"] == (
        "4ca4a9394b0c771238a4f73590fdbbc4debad85ed0fa63d026ae1b085da7d6e2"
    )
    assert torch["metadata_sha256"] == (
        "b3c7f4b3f77d06f86a42aab7d0facef7b661ca3c22967bfcc396917d935dd335"
    )
    assert torch["required_extras"] == []
    root_project = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert '"torch' not in root_project
    assert "Do not add PyTorch" in runtime["root_boundary"]
    assert "network access disabled" in runtime["network_boundary"]


def test_worker_slots_are_disjoint_physical_cores_and_fully_bounded() -> None:
    determinism = _load(CONTRACT_PATH)["determinism_contract"]
    assert determinism["process_start_method"] == "spawn"
    assert determinism["maximum_concurrent_fits"] == 4
    assert determinism["intraop_threads_per_fit"] == 4
    assert determinism["interop_threads_per_fit"] == 1
    assert determinism["data_loader_workers"] == 0
    slots = list(determinism["worker_affinity"].values())
    assert len(slots) == 4
    assert all(len(slot) == 4 for slot in slots)
    assert sorted(core for slot in slots for core in slot) == list(range(16))
    assert sum(len(set(slot)) for slot in slots) == 16
    environment = determinism["environment"]
    assert environment["PYTHONHASHSEED"] == "0"
    assert set(environment.values()) >= {"4", "FALSE"}
    settings = "\n".join(determinism["torch_settings"])
    assert "use_deterministic_algorithms(True, warn_only=False)" in settings
    assert "set_deterministic_debug_mode('error')" in settings
    assert "mkldnn.enabled = False" in settings
    assert "torch.save" in determinism["byte_receipts"]


def test_feature_width_contexts_and_api_match_parent() -> None:
    contract = _load(CONTRACT_PATH)
    mechanics = contract["feature_and_preprocessing_mechanics"]
    parent = _load(PARENT_PATH)
    assert mechanics["official_shape"] == {
        "development_molecules": 3908,
        "input_columns": 2248,
        "morgan_columns": 2048,
        "descriptor_columns": 200,
    }
    assert (
        mechanics["official_shape"]["input_columns"]
        == parent["feature_contract"]["total_columns"]
    )
    assert "GetMorganGenerator" in mechanics["morgan_api"]
    assert "GetCountFingerprint" in mechanics["morgan_api"]
    assert "includeChirality=True" in mechanics["morgan_api"]
    assert mechanics["preprocessing_contexts"] == 3 * 5 * 4 + 3 * 5 == 75
    assert "target-blind" in mechanics["preprocessing_rule"]
    assert "system-specific transform" in mechanics["forbidden"]


def test_fixture_confirmatory_assignment_masks_and_structures_are_exact() -> None:
    fixture = _load(CONTRACT_PATH)["synthetic_fixture"]
    development, confirmatory = _component_pool()
    assert len(set(development) & set(confirmatory)) == 0
    assert len(development) == fixture["development_components"] == 40
    assert len(confirmatory) == fixture["confirmatory_components"] == 10
    assert fixture["molecules"] == 100
    assert fixture["molecules_per_component"] == 2
    smiles = ["C" * (index + 1) for index in range(fixture["molecules"])]
    assert len(set(smiles)) == 100
    for endpoint in range(4):
        finite = [index for index in range(80) if (index + endpoint) % 5 != 0]
        interval = [index for index in finite if (index + 2 * endpoint) % 4 != 0]
        assert len(finite) == 64
        assert len(interval) == 48
        assert len(finite) - len(interval) == 16
    assert fixture["targets"]["exact_counts_per_endpoint"] == {
        "finite_central": 64,
        "interval_eligible": 48,
        "point_only": 16,
        "missing_central": 16,
    }
    assert "parse zero values" in fixture["targets"]["confirmatory_rule"]


def test_fixture_folds_are_balanced_and_component_disjoint() -> None:
    development, _confirmatory = _component_pool()
    for seed in (20260810, 20260811, 20260812):
        outer_order = sorted(
            development,
            key=lambda component: hashlib.sha256(
                f"{seed}|OUTER|{component}".encode()
            ).hexdigest(),
        )
        outer_by_component = {
            component: rank % 5 for rank, component in enumerate(outer_order)
        }
        assert [list(outer_by_component.values()).count(fold) for fold in range(5)] == [
            8,
            8,
            8,
            8,
            8,
        ]
        for outer in range(5):
            training = [
                component
                for component in development
                if outer_by_component[component] != outer
            ]
            inner_order = sorted(
                training,
                key=lambda component: hashlib.sha256(
                    f"{seed}|{outer}|INNER|{component}".encode()
                ).hexdigest(),
            )
            inner = {component: rank % 4 for rank, component in enumerate(inner_order)}
            assert [list(inner.values()).count(fold) for fold in range(4)] == [8] * 4
            assert not set(inner) & {
                component
                for component in development
                if outer_by_component[component] == outer
            }


def test_model_double_fit_prediction_and_selection_arithmetic_is_exact() -> None:
    topology = _load(CONTRACT_PATH)["model_double_topology"]
    fits = topology["fit_counts_per_root"]
    assert fits["shared_two_loss_inner"] == 3 * 5 * 4 * 2 * 3 == 360
    assert fits["shared_selected_outer"] == 3 * 5 * 3 == 45
    assert fits["independent_two_loss_inner"] == 3 * 5 * 4 * 4 * 2 * 3 == 1440
    assert fits["independent_two_loss_outer"] == 3 * 5 * 4 * 2 * 3 == 360
    assert fits["permuted_selected_inner"] == 3 * 5 * 4 * 3 == 180
    assert fits["permuted_selected_outer"] == 3 * 5 * 3 == 45
    assert fits["total"] == sum(value for key, value in fits.items() if key != "total")
    rows = topology["prediction_rows_per_root"]
    one_inner = 80 * 4 * 3 * 4
    one_outer = 80 * 4 * 3
    assert rows["inner_raw"] == one_inner * 3 * 5 == 57600
    assert rows["inner_seed_averaged"] == one_inner * 5 == 19200
    assert rows["outer_raw"] == one_outer * 3 * 4 == 11520
    assert rows["outer_seed_averaged"] == one_outer * 4 == 3840
    assert topology["selection_tokens_per_root"] == {
        "shared_outer_loss": 15,
        "independent_endpoint_outer_loss": 60,
    }
    assert "five shared exact ties" in topology["selection_oracles"]


def test_real_probe_covers_every_form_seed_and_maximum_epoch_cost() -> None:
    probe = _load(CONTRACT_PATH)["real_runtime_probe"]
    assert probe["training_rows"] == 3908
    assert probe["prediction_rows"] == 997
    assert probe["input_columns"] == 2248
    assert probe["batch_size"] == 128
    assert probe["epochs_per_fit"] == 300
    assert probe["batches_per_epoch"] == 31
    assert probe["optimizer_steps_per_fit"] == 31 * 300 == 9300
    batches = probe["shared_family_batches"] + probe["independent_batches"]
    assert len(batches) == 4
    assert all(len(batch) == 4 for batch in batches)
    identities = [identity for batch in batches for identity in batch]
    assert len(identities) == probe["fits_per_root"] == 16
    assert probe["fits_across_two_roots"] == 32
    for seed in (20260824, 20260825, 20260826):
        assert any(f"shared CENTRAL seed {seed}" == value for value in identities)
        assert any(f"shared INTERVAL seed {seed}" == value for value in identities)
        assert any(f"independent CENTRAL seed {seed}" == value for value in identities)
        assert any(f"independent INTERVAL seed {seed}" == value for value in identities)
    assert sum("permuted" in value for value in identities) == 2
    assert sum("resource-repeat-1" in value for value in identities) == 2
    assert "excluded from every numerical seed" in probe["resource_repeat_rule"]


def test_resource_projection_is_worst_case_and_twenty_percent_bounded() -> None:
    contract = _load(CONTRACT_PATH)
    projection = contract["resource_projection"]
    parent_ceiling = _load(PARENT_PATH)["resource_ceiling"]
    classes = projection["scientific_fit_classes"]
    assert classes == {
        "shared_or_permuted": 630,
        "independent": 1800,
        "total": 2430,
    }
    assert 630 == 360 + 45 + 180 + 45
    assert 1800 == 1440 + 360
    assert "158 and 450 batches exactly" in projection["wall_formula"]
    assert "maximum individual child CPU" in projection["cpu_formula"]
    assert projection["maximum_projected_cpu_core_hours"] == (
        0.8 * parent_ceiling["cpu_core_hours"]
    )
    assert projection["maximum_projected_gpu_hours"] == 0
    assert projection["maximum_projected_restricted_storage_gb"] == (
        0.8 * parent_ceiling["restricted_storage_gb"]
    )
    assert round(projection["maximum_projected_wall_hours"] * 10) == 384
    assert projection["maximum_peak_rss_gib"] == 24
    assert "No alternate device" in projection["logic"]


def test_capabilities_formal_attempt_and_terminals_are_one_shot() -> None:
    contract = _load(CONTRACT_PATH)
    firewall = contract["capability_firewall"]
    assert "cannot resolve any private official path" in firewall["fixture_builder"]
    assert "cannot read a target" in firewall["preprocessor"]
    assert "cannot resolve outer-validation truth" in firewall["inner_model"]
    assert "zero" in firewall["forbidden_counters"]
    attempt = contract["formal_attempt_contract"]
    assert attempt["maximum_attempts"] == 1
    assert attempt["roots"] == 2
    assert "reviewed signed source-binding claim" in attempt["precondition"]
    assert "no retry" in attempt["no_replace"].lower()
    assert attempt["network"] == "Disabled for both roots and every child process."
    terminal = contract["terminal_contract"]
    assert len(terminal["required_terminal_files"]) == 8
    assert "four-file scientific tree" in terminal["cross_root_equivalence"]
    assert "root-specific timing" in terminal["cross_root_equivalence"]
    assert "terminal" in terminal["failure"]


def test_contract_freeze_opens_nothing_but_bounded_future_implementation() -> None:
    contract = _load(CONTRACT_PATH)
    assert all(
        value == 0 for value in contract["current_milestone_accounting"].values()
    )
    assert all(value is None for value in contract["future_source_bindings"].values())
    authority = contract["current_authority"]
    assert authority["contract_and_static_tests"]
    assert not any(
        value
        for name, value in authority.items()
        if name != "contract_and_static_tests"
    )
    future = contract["post_integration_implementation_authority"]
    assert future["research_environment_creation"]
    assert future["implementation"]
    assert future["real_torch_smoke_limit"] == {
        "maximum_fits": 4,
        "maximum_epochs_per_fit": 3,
        "maximum_training_rows": 64,
        "input_columns": 2248,
        "maximum_concurrent_fits": 1,
        "resource_timing_authority": False,
    }
    assert not future["formal_two_root_probe"]
    assert not future["official_inputs"]
    assert "Record every smoke" in future["rule"]
    assert "do not run the two-root 32-fit resource probe" in contract["next_gate"]
