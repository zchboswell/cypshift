from __future__ import annotations

import csv
import hashlib
import io
import json
import math
from pathlib import Path
from typing import Any, cast
from urllib.parse import urlparse

import pytest

ROOT = Path(__file__).resolve().parents[1]
BENCHMARK = ROOT / "benchmarks" / "openadmet_cyp_2026"
CONTRACT = BENCHMARK / "global_v3_g4_gin300_capability_contract.json"
RUNTIME_MANIFEST = BENCHMARK / "global_v3_g4_gin300_linux_x86_64_runtime_manifest.json"
NOTICES = BENCHMARK / "global_v3_g4_gin300_third_party_notices.md"
CONTRACT_SHA256 = "df8796575c3d6093dd4038f4268417a979b8edca14245a7acff26e3db18eaa44"
RUNTIME_MANIFEST_SHA256 = (
    "67b58fc5eb9d1d3c0652bad9fa85eb1e688ed4bfb93d9ee107cad4db3e0ace01"
)
NOTICES_SHA256 = "b76b026a7ed61c0c33cc9f78d66ca235e01e9d2c504126238e0f6e0f58e18deb"

RUNTIME_PACKAGE_ALLOWLIST = {
    "aiobotocore",
    "aiohttp",
    "aioitertools",
    "aiosignal",
    "annotated-types",
    "async-timeout",
    "attrs",
    "botocore",
    "cachetools",
    "catboost",
    "certifi",
    "charset-normalizer",
    "cloudpickle",
    "contourpy",
    "cycler",
    "datamol",
    "decorator",
    "dgl",
    "dgllife",
    "filelock",
    "fonttools",
    "frozenlist",
    "fsspec",
    "future",
    "gcsfs",
    "google-api-core",
    "google-auth",
    "google-auth-oauthlib",
    "google-cloud-core",
    "google-cloud-storage",
    "google-crc32c",
    "google-resumable-media",
    "googleapis-common-protos",
    "graphviz",
    "h5py",
    "huggingface-hub",
    "hyperopt",
    "idna",
    "importlib-resources",
    "jinja2",
    "jmespath",
    "joblib",
    "kiwisolver",
    "loguru",
    "markupsafe",
    "matplotlib",
    "molfeat",
    "mordredcommunity",
    "mpmath",
    "multidict",
    "networkx",
    "numpy",
    "oauthlib",
    "packaging",
    "pandas",
    "pillow",
    "platformdirs",
    "plotly",
    "pmapper",
    "protobuf",
    "psutil",
    "py4j",
    "pyarrow",
    "pyasn1",
    "pyasn1-modules",
    "pydantic",
    "pydantic-core",
    "pyparsing",
    "python-dateutil",
    "python-dotenv",
    "pytz",
    "pyyaml",
    "rdkit",
    "regex",
    "requests",
    "requests-oauthlib",
    "rsa",
    "s3fs",
    "safetensors",
    "scikit-learn",
    "scipy",
    "selfies",
    "sentencepiece",
    "six",
    "sympy",
    "tenacity",
    "threadpoolctl",
    "tokenizers",
    "torch",
    "tqdm",
    "transformers",
    "typing-extensions",
    "tzdata",
    "urllib3",
    "wrapt",
    "yarl",
}

TOP_LEVEL_KEYS = {
    "schema_version",
    "recorded_at_utc",
    "freeze_date",
    "gate",
    "status",
    "contract_id",
    "experiment_id",
    "base_commit",
    "purpose",
    "targeted_failure",
    "occam_boundary",
    "contract_only_boundary",
    "integrated_d147_lineage",
    "bound_public_parents",
    "tracked_d148_dependencies",
    "future_d149_implementation_package",
    "rights_provenance_and_notices",
    "network_fetch_offline_sandbox_and_cleanup",
    "snap_to_dgl_tensor_conversion",
    "graph_and_embedding_contract",
    "official_shaped_synthetic_capability",
    "resource_projection",
    "future_d150_result_contract",
    "future_d150_formal_one_use_boundary",
    "terminal_classification",
    "current_d148_accounting",
    "invalidation",
    "next_gate",
}


def _reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON constant: {value}")


def _strict_int(value: str) -> int:
    if value == "-0":
        raise ValueError("negative zero")
    return int(value)


def _strict_float(value: str) -> float:
    parsed = float(value)
    if value.startswith("-") and parsed == 0.0:
        raise ValueError("negative zero")
    if not math.isfinite(parsed):
        raise ValueError(f"non-finite JSON number: {value}")
    return parsed


def _strict_load(raw: bytes) -> dict[str, Any]:
    value = json.loads(
        raw,
        object_pairs_hook=_reject_duplicates,
        parse_int=_strict_int,
        parse_float=_strict_float,
        parse_constant=_reject_constant,
    )
    assert isinstance(value, dict)
    return cast(dict[str, Any], value)


def _load(path: Path = CONTRACT) -> dict[str, Any]:
    return _strict_load(path.read_bytes())


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_json_bytes(value: dict[str, Any]) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2).encode()
        + b"\n"
    )


def _resolved_public_path(relative: str, *, anchor: Path = BENCHMARK) -> Path:
    path = (anchor / relative).resolve()
    path.relative_to(ROOT)
    return path


def test_d148_contract_is_canonical_and_binds_exact_integrated_d147() -> None:
    raw = CONTRACT.read_bytes()
    contract = _strict_load(raw)
    assert raw == _canonical_json_bytes(contract)
    assert hashlib.sha256(raw).hexdigest() == CONTRACT_SHA256
    assert set(contract) == TOP_LEVEL_KEYS
    assert contract["schema_version"] == (
        "cypshift.openadmet_cyp_2026.global_v3_g4_gin300_capability_contract.v1"
    )
    assert contract["gate"] == "G3_2_EXP_G4_GIN300_CAPABILITY_CONTRACT_FROZEN"
    assert contract["status"] == contract["gate"]
    assert contract["contract_id"] == "GLOBAL_V3_G4_GIN300_CAPABILITY"
    assert contract["experiment_id"] == "EXP-G4-GIN300"
    assert contract["base_commit"] == ("b5cf47c6bc8ccc2dc29c7167b1a436d792338509")

    with pytest.raises(ValueError, match="duplicate JSON key"):
        _strict_load(b'{"gate":"a","gate":"b"}')
    with pytest.raises(ValueError, match="non-finite JSON constant"):
        _strict_load(b'{"value":NaN}')
    with pytest.raises(ValueError, match="negative zero"):
        _strict_load(b'{"value":-0}')
    with pytest.raises(ValueError, match="negative zero"):
        _strict_load(b'{"value":-0.0}')

    lineage = contract["integrated_d147_lineage"]
    assert lineage["commit"] == contract["base_commit"]
    assert lineage["parent_commit"] == ("d029bb3b154f1721d094dae76e5587c0c927da2e")
    assert "valid SSH signature for zchboswell" in lineage["commit_signature"]
    assert lineage["pull_request"] == 184
    assert lineage["pull_request_merge_mode"] == (
        "mergeCommit equals signed head exactly; no hosted rewrite"
    )
    assert lineage["pull_request_ci_run"] == 33327853790
    assert lineage["pull_request_ci_lanes_green"] == 3
    assert lineage["post_main_push_ci_run"] == 33328374514
    assert lineage["post_main_ci_lanes_green"] == 3

    expected = {
        "d147_contract": (
            BENCHMARK / "global_v3_g4_gin300_contract.json",
            "b48dc0c39c12b06cdd99693539cca18b99c73d8b801e81a416e52a798df8fd4e",
            37_092,
            485,
        ),
        "d147_static_test": (
            ROOT / "tests" / "test_openadmet_global_v3_g4_gin300_contract.py",
            "c32e8054da4c92f763c065c8d58d340993f6917c5c6a6d3580659febea69e3dc",
            31_371,
            815,
        ),
    }
    for name, (path, digest, size, lines) in expected.items():
        receipt = lineage[name]
        assert _sha256(path) == receipt["sha256"] == digest
        assert path.stat().st_size == receipt["size_bytes"] == size
        assert len(path.read_bytes().splitlines()) == receipt["lines"] == lines
    assert lineage["d147_static_test"]["focused_result"] == "9 passed"
    assert "G2-7G remains UNDERPOWERED" in lineage["required_state"]
    assert "no old claim" in lineage["required_state"]


def test_only_exact_public_parents_and_tracked_d148_files_are_bound() -> None:
    contract = _load()
    parents = contract["bound_public_parents"]
    assert set(parents) == {
        "challenge_contract",
        "global_v2_contract",
        "fixed_maplight_reproduction",
        "maplight_source_contract",
        "historical_gin_contract",
        "fixture",
        "challenge_rules_snapshot",
    }
    for name in (
        "challenge_contract",
        "global_v2_contract",
        "fixed_maplight_reproduction",
        "maplight_source_contract",
        "historical_gin_contract",
    ):
        receipt = parents[name]
        assert set(receipt) == {"path", "sha256"}
        path = _resolved_public_path(receipt["path"])
        assert path.is_file()
        assert _sha256(path) == receipt["sha256"]

    fixture_receipt = parents["fixture"]
    fixture = _resolved_public_path(fixture_receipt["path"])
    assert (
        _sha256(fixture)
        == fixture_receipt["sha256"]
        == ("70ae570bbdbb5c8a225cfd20ab72f0d8f8b43dc1a3a6b2d3356bc52f4f4a513c")
    )
    assert fixture.stat().st_size == fixture_receipt["size_bytes"] == 267
    rows = list(csv.DictReader(io.StringIO(fixture.read_text(encoding="utf-8"))))
    assert len(rows) == fixture_receipt["data_rows"] == 8
    assert fixture_receipt["physical_lines"] == 9
    assert (
        list(rows[0])
        == fixture_receipt["columns"]
        == [
            "fixture_id",
            "pandas_index",
            "raw_smiles",
        ]
    )
    assert "redistributable synthetic" in fixture_receipt["rights"]

    rules = parents["challenge_rules_snapshot"]
    assert rules["space_revision"] == ("4a87b2dcc800036b745e4c7bbb0023be817b5408")
    assert rules["config_sha256"] == (
        "342cd287e63a79c61b8e18fa46e81950ebb7333b6e91ee427af18426e04ca52f"
    )
    assert "pretrained models are permitted" in rules["permission"]
    assert "does not waive third-party rights" in rules["permission"]

    tracked = contract["tracked_d148_dependencies"]
    assert set(tracked) == {
        "linux_runtime_manifest",
        "third_party_notices",
        "runtime_cutoff_exception",
    }
    runtime = tracked["linux_runtime_manifest"]
    assert set(runtime) == {
        "path",
        "schema_version",
        "sha256",
        "size_bytes",
        "lines",
        "cpu_only",
        "package_count",
        "wheel_count",
        "dependency_edge_count",
        "selected_wheel_total_size_bytes",
        "resolved_package_set_sha256",
        "selected_wheel_inventory_sha256",
        "dependency_edges_sha256",
        "license_assignment_count",
        "license_assignments_sha256",
        "runtime_distribution_artifact_count",
        "runtime_distribution_total_size_bytes",
        "runtime_distribution_inventory_sha256",
        "runtime_distribution_inventory_canonical_bytes",
        "runtime_distribution_inventory_digest_rule",
        "molfeat_extras",
        "transformer_extra_boundary",
        "interpreter",
        "rule",
    }
    assert _resolved_public_path(runtime["path"]) == RUNTIME_MANIFEST
    assert runtime["schema_version"] == (
        "cypshift.openadmet_cyp_2026."
        "global_v3_g4_gin300_linux_x86_64_runtime_manifest.v1"
    )
    manifest = _load(RUNTIME_MANIFEST)
    inventory = manifest["inventory"]
    assert _sha256(RUNTIME_MANIFEST) == runtime["sha256"] == RUNTIME_MANIFEST_SHA256
    assert RUNTIME_MANIFEST.stat().st_size == runtime["size_bytes"] == 166_425
    assert len(RUNTIME_MANIFEST.read_bytes().splitlines()) == runtime["lines"] == 4_008
    assert runtime["cpu_only"] is True
    assert runtime["package_count"] == inventory["package_count"] == 96
    assert runtime["wheel_count"] == inventory["selected_wheel_count"] == 96
    assert runtime["dependency_edge_count"] == inventory["dependency_edge_count"] == 185
    assert (
        runtime["selected_wheel_total_size_bytes"]
        == inventory["selected_wheel_total_size_bytes"]
        == 539_395_366
    )
    for name in (
        "resolved_package_set_sha256",
        "selected_wheel_inventory_sha256",
        "dependency_edges_sha256",
        "license_assignments_sha256",
        "runtime_distribution_inventory_sha256",
    ):
        assert runtime[name] == inventory[name]
    assert runtime["license_assignment_count"] == 96
    assert runtime["runtime_distribution_artifact_count"] == 97
    assert runtime["runtime_distribution_total_size_bytes"] == 566_804_656
    assert runtime["runtime_distribution_inventory_canonical_bytes"] == 37_820
    assert "all 97 records" in runtime["runtime_distribution_inventory_digest_rule"]
    assert runtime["molfeat_extras"] == ["dgl", "transformer"]
    assert (
        "They grant no transformer model, tokenizer model"
        in runtime["transformer_extra_boundary"]
    )
    manifest_interpreter = manifest["target"]["interpreter"]
    contract_interpreter = runtime["interpreter"]
    assert (
        contract_interpreter["archive_sha256"] == manifest_interpreter["archive_sha256"]
    )
    assert (
        contract_interpreter["archive_size_bytes"]
        == manifest_interpreter["archive_size_bytes"]
    )
    assert (
        contract_interpreter["checksum_sidecar"]["sha256"]
        == (manifest_interpreter["checksum_sidecar"]["sha256"])
    )
    assert contract_interpreter["installed_executable_sha256"] is None
    assert (
        "D150 must record and bind it once"
        in contract_interpreter["installed_executable_rule"]
    )
    assert (
        "PYTHON.json inventory"
        in contract_interpreter["license"]["bundled_notice_rule"]
    )
    assert "does not fetch, extract, install, import, or execute" in runtime["rule"]
    notices = tracked["third_party_notices"]
    assert set(notices) == {"path", "sha256", "rule"}
    assert _resolved_public_path(notices["path"]) == NOTICES
    assert _sha256(NOTICES) == notices["sha256"] == NOTICES_SHA256
    assert NOTICES.stat().st_size == 12_456
    assert len(NOTICES.read_bytes().splitlines()) == 241
    assert "no checkpoint or pretraining data" in notices["rule"]

    exception = tracked["runtime_cutoff_exception"]
    assert set(exception) == {
        "package",
        "historical_version",
        "frozen_linux_version",
        "reason",
        "scientific_effect",
        "all_other_versions",
        "interpreter_cutoff_boundary",
    }
    assert exception["package"] == "future"
    assert exception["historical_version"] == "0.18.3"
    assert exception["frozen_linux_version"] == "1.0.0"
    assert "sole post-cutoff Python-package-wheel" in exception["reason"]
    assert "None is assumed" in exception["scientific_effect"]
    assert "All other Python package wheels preserve" in exception["all_other_versions"]
    assert "not a Python package wheel" in exception["interpreter_cutoff_boundary"]


def test_runtime_manifest_is_exact_wheel_only_cpu_closure() -> None:
    raw = RUNTIME_MANIFEST.read_bytes()
    manifest = _strict_load(raw)
    assert raw == _canonical_json_bytes(manifest)
    assert hashlib.sha256(raw).hexdigest() == RUNTIME_MANIFEST_SHA256
    assert set(manifest) == {
        "schema_version",
        "recorded_at_utc",
        "freeze_date",
        "manifest_id",
        "status",
        "purpose",
        "parent",
        "target",
        "resolver_contract",
        "source_indexes",
        "inventory",
        "packages",
        "license_catalog",
        "installation_policy",
        "known_risks_and_fail_closed_checks",
        "contract_only_accounting",
        "next_gate",
    }
    assert manifest["schema_version"] == (
        "cypshift.openadmet_cyp_2026."
        "global_v3_g4_gin300_linux_x86_64_runtime_manifest.v1"
    )
    assert manifest["manifest_id"] == "G3-G4-GIN300-D148-LINUX-X86_64-CPU-RUNTIME"
    assert manifest["status"] == "FROZEN_CONTRACT_ONLY"
    assert "metadata and contract evidence only" in manifest["purpose"]
    assert manifest["parent"] == {
        "base_commit": "b5cf47c6bc8ccc2dc29c7167b1a436d792338509",
        "contract_path": "global_v3_g4_gin300_contract.json",
        "contract_sha256": (
            "b48dc0c39c12b06cdd99693539cca18b99c73d8b801e81a416e52a798df8fd4e"
        ),
    }

    target = manifest["target"]
    assert target["operating_system"] == "Linux"
    assert target["architecture"] == "x86_64"
    assert target["cpu_only"] is True
    assert target["gpu_hours"] == 0
    assert target["implementation"] == "CPython"
    assert target["python_version"] == "3.10.13"
    assert target["python_abi"] == "cp310"
    assert "manylinux2014" in target["wheel_platform"]
    interpreter = target["interpreter"]
    assert interpreter["repository"] == "astral-sh/python-build-standalone"
    assert interpreter["python_build_standalone_release"] == "20240224"
    assert interpreter["tag_commit"] == ("61ace30326ba7c32325c6633665cc571ac56b82a")
    assert interpreter["version"] == target["python_version"]
    assert interpreter["archive_filename"] == (
        "cpython-3.10.13+20240224-x86_64-unknown-linux-gnu-install_only.tar.gz"
    )
    assert interpreter["archive_url"] == (
        "https://github.com/astral-sh/python-build-standalone/releases/download/"
        "20240224/cpython-3.10.13%2B20240224-x86_64-unknown-linux-gnu-"
        "install_only.tar.gz"
    )
    assert interpreter["archive_sha256"] == (
        "d995d032ca702afd2fc3a689c1f84a6c64972ecd82bba76a61d525f08eb0e195"
    )
    assert interpreter["archive_size_bytes"] == 27_409_290
    assert "not a Python package sdist" in interpreter["archive_type"]
    sidecar = interpreter["checksum_sidecar"]
    assert sidecar["content_without_terminal_newline"] == interpreter["archive_sha256"]
    assert sidecar["filename"] == f"{interpreter['archive_filename']}.sha256"
    assert sidecar["sha256"] == (
        "9e57b23cb72164f981d9c6a52bdb555557639de897631f54fe1255181464e4b3"
    )
    assert sidecar["size_bytes"] == 65
    assert sidecar["url"] == f"{interpreter['archive_url']}.sha256"
    assert interpreter["installed_executable_sha256"] is None
    assert "D148 and D149 cannot know this" in interpreter["installed_executable_rule"]
    assert (
        "D150 formal run must record it once"
        in (interpreter["installed_executable_rule"])
    )
    interpreter_license = interpreter["license"]
    assert interpreter_license["cpython_spdx_expression"] == "PSF-2.0"
    assert interpreter_license["build_project_spdx_expression"] == "BSD-3-Clause"
    assert "PYTHON.json license inventory" in interpreter_license["bundled_notice_rule"]
    assert (
        "prohibit archive redistribution" in interpreter_license["bundled_notice_rule"]
    )

    resolver = manifest["resolver_contract"]
    direct_roots = {
        "catboost==1.2.1",
        "dgl==1.1.2",
        "dgllife==0.3.2",
        "molfeat==0.9.2",
        "numpy==1.25.2",
        "pandas==2.0.3",
        "python-dotenv==1.0.0",
        "rdkit==2023.3.3",
        "scikit-learn==1.3.0",
        "scipy==1.11.2",
        "torch==2.0.1+cpu",
    }
    scientific_roots = {
        "catboost==1.2.1",
        "dgl==1.1.2",
        "dgllife==0.3.2",
        "molfeat==0.9.2",
        "numpy==1.25.2",
        "rdkit==2023.3.3",
        "torch==2.0.1+cpu",
    }
    assert set(resolver["direct_runtime_roots"]) == direct_roots
    assert set(resolver["scientific_roots"]) == scientific_roots
    assert resolver["molfeat_extras"] == ["dgl", "transformer"]
    assert (
        "imports its optional Hugging Face module"
        in resolver["historical_static_import_evidence"]["statement"]
    )
    for receipt_name in ("historical_lock", "historical_static_import_evidence"):
        receipt = resolver[receipt_name]
        path = _resolved_public_path(receipt["path"], anchor=RUNTIME_MANIFEST.parent)
        assert _sha256(path) == receipt["sha256"]
    assert resolver["uv_version"] == "0.12.3"
    assert "--python-version 3.10.13" in resolver["normalized_command"]
    assert "--torch-backend cpu" in resolver["normalized_command"]
    assert "--only-binary :all:" in resolver["normalized_command"]
    assert "96 exact wheels" in resolver["resolution_result"]
    assert "zero sdist/VCS/editable" in resolver["resolution_result"]
    assert resolver["historical_python_package_wheel_upload_cutoff_exclusive_utc"] == (
        "2023-11-07T00:00:00Z"
    )
    assert "not a Python package wheel" in resolver["interpreter_cutoff_boundary"]
    assert (
        "interpreter infrastructure distribution"
        in resolver["interpreter_cutoff_boundary"]
    )
    exception = resolver["infrastructure_exception"]
    assert exception["package"] == "future"
    assert exception["historical_version"] == "0.18.3"
    assert exception["replacement_version"] == "1.0.0"
    assert exception["replacement_wheel_sha256"] == (
        "929292d34f5872e70396626ef385ec22355a1fae8ad29e1a734c3e43f9fbc216"
    )
    assert "no wheel for future 0.18.3" in exception["historical_artifact_problem"]
    assert (
        "Non-scientific transitive compatibility substitution"
        in exception["scientific_status"]
    )
    assert "no tuning" in exception["authority"]

    indexes = {record["id"]: record for record in manifest["source_indexes"]}
    assert set(indexes) == {"pypi", "pytorch-cpu"}
    assert indexes["pypi"]["artifact_hosts"] == ["files.pythonhosted.org"]
    assert indexes["pytorch-cpu"] == {
        "id": "pytorch-cpu",
        "index_url": "https://download.pytorch.org/whl/cpu",
        "artifact_hosts": ["download-r2.pytorch.org"],
        "policy": (
            "Torch only; exact 2.0.1+cpu CPython 3.10 Linux x86_64 wheel. "
            "PyPI Torch is forbidden."
        ),
    }

    packages = manifest["packages"]
    assert len(packages) == 96
    assert [package["name"] for package in packages] == sorted(
        RUNTIME_PACKAGE_ALLOWLIST
    )
    assert len(RUNTIME_PACKAGE_ALLOWLIST) == 96
    by_name = {package["name"]: package for package in packages}
    assert len(by_name) == len(packages)
    assert {f"{name}=={record['version']}" for name, record in by_name.items()} >= (
        direct_roots
    )
    assert {
        f"{record['name']}=={record['version']}"
        for record in packages
        if "scientific-root" in record["roles"]
    } == scientific_roots
    assert {
        f"{record['name']}=={record['version']}"
        for record in packages
        if "direct-runtime-root" in record["roles"]
    } == direct_roots
    assert by_name["torch"]["version"] == "2.0.1+cpu"
    assert by_name["torch"]["source_index_id"] == "pytorch-cpu"
    assert all(
        package["source_index_id"] == "pypi"
        for package in packages
        if package["name"] != "torch"
    )
    transformer_imports = {
        "huggingface-hub",
        "regex",
        "safetensors",
        "sentencepiece",
        "tokenizers",
        "transformers",
    }
    assert transformer_imports <= set(by_name)
    cutoff = resolver["historical_python_package_wheel_upload_cutoff_exclusive_utc"]
    post_cutoff_wheels = [
        (package["name"], package["version"], package["wheel"]["upload_time_utc"])
        for package in packages
        if package["wheel"]["upload_time_utc"] >= cutoff
    ]
    assert post_cutoff_wheels == [("future", "1.0.0", "2024-02-21T11:52:35Z")]

    dependency_edges: list[str] = []
    selected_wheel_records: list[dict[str, Any]] = []
    catalog = manifest["license_catalog"]
    for package in packages:
        assert set(package) == {
            "name",
            "version",
            "roles",
            "source_index_id",
            "wheel",
            "dependencies",
            "license",
        }
        assert package["roles"]
        wheel = package["wheel"]
        expected_wheel_keys = {
            "filename",
            "url",
            "sha256",
            "size_bytes",
            "upload_time_utc",
            "tags",
        }
        if package["name"] == "torch":
            expected_wheel_keys.add("public_index_evidence")
        assert set(wheel) == expected_wheel_keys
        assert wheel["filename"].endswith(".whl")
        assert len(wheel["sha256"]) == 64
        int(wheel["sha256"], 16)
        assert wheel["size_bytes"] > 0
        assert wheel["tags"]
        if package["name"] == "torch":
            evidence = wheel["public_index_evidence"]
            assert evidence["index_fragment_algorithm"] == "sha256"
            assert evidence["index_fragment_sha256"] == wheel["sha256"]
            assert evidence["canonical_anchor_href"].endswith(
                f"#sha256={wheel['sha256']}"
            )
            assert evidence["index_page_url"] == (
                "https://download.pytorch.org/whl/cpu/torch/"
            )
        parsed = urlparse(wheel["url"])
        assert parsed.scheme == "https"
        assert parsed.hostname in indexes[package["source_index_id"]]["artifact_hosts"]
        selected_wheel_records.append(
            {
                "filename": wheel["filename"],
                "name": package["name"],
                "sha256": wheel["sha256"],
                "size_bytes": wheel["size_bytes"],
                "url": wheel["url"],
                "version": package["version"],
            }
        )
        for dependency in package["dependencies"]:
            dependency_name, separator, dependency_version = dependency.partition("==")
            assert separator == "=="
            assert dependency_name in by_name
            assert by_name[dependency_name]["version"] == dependency_version
            dependency_edges.append(
                f"{package['name']}=={package['version']}->{dependency}"
            )
        license_record = package["license"]
        assert license_record["canonical_license_ids"]
        assert set(license_record["canonical_license_ids"]) <= set(catalog)
        assert "Retain every license" in license_record["notice_obligation"]

    package_set_bytes = json.dumps(
        [f"{package['name']}=={package['version']}" for package in packages],
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode()
    wheel_inventory_bytes = json.dumps(
        selected_wheel_records,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    edge_bytes = json.dumps(
        sorted(dependency_edges),
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode()
    inventory = manifest["inventory"]
    expected_inventory = {
        "dependency_edge_count": 185,
        "dependency_edges_sha256": (
            "b7ce0c4706520beacbb761671706563c8a702d54022297f197c84048275d29b1"
        ),
        "direct_runtime_root_count": 11,
        "interpreter_archive_count": 1,
        "interpreter_archive_size_bytes": 27_409_290,
        "license_assignment_count": 96,
        "license_assignments_sha256": (
            "dafbe12e4300c29b08bda431ec3613271b5bc02df4f954c4927b9ba0140561fb"
        ),
        "package_count": 96,
        "post_cutoff_interpreter_distribution_count": 1,
        "post_cutoff_python_package_wheel_exception_count": 1,
        "resolved_package_set_sha256": (
            "f6bddf33d6b33c6319cd42513879ac0366619ee022ce451fe688ac588bf87e1c"
        ),
        "runtime_distribution_artifact_count": 97,
        "runtime_distribution_inventory_sha256": (
            "f1949018f8d3e572b727517465fb7dcdbc12a03aa01c8dcb36967c56910212b2"
        ),
        "runtime_distribution_total_size_bytes": 566_804_656,
        "scientific_root_count": 7,
        "selected_wheel_count": 96,
        "selected_wheel_inventory_sha256": (
            "f31d9d9b760c809d819ce5b0969e4339788b11659c45f2fdc3fbdb72f64edba9"
        ),
        "selected_wheel_total_size_bytes": 539_395_366,
        "transitive_runtime_dependency_count": 85,
    }
    digest_contract = inventory["runtime_distribution_inventory_digest_contract"]
    assert set(inventory) == set(expected_inventory) | {
        "runtime_distribution_inventory_digest_contract"
    }
    assert all(inventory[key] == value for key, value in expected_inventory.items())
    assert digest_contract["algorithm"] == "sha256"
    assert digest_contract["record_order_fields"] == [
        "artifact_type",
        "name",
        "version",
        "filename",
    ]
    assert digest_contract["canonical_json_serialization"] == {
        "allow_nan": False,
        "encoding": "UTF-8",
        "ensure_ascii": False,
        "indent": None,
        "separators": [",", ":"],
        "sort_keys": True,
        "terminal_newline": False,
    }
    assert len(dependency_edges) == inventory["dependency_edge_count"]
    assert (
        sum(package["wheel"]["size_bytes"] for package in packages)
        == inventory["selected_wheel_total_size_bytes"]
    )
    assert (
        hashlib.sha256(package_set_bytes).hexdigest()
        == inventory["resolved_package_set_sha256"]
    )
    assert (
        hashlib.sha256(wheel_inventory_bytes).hexdigest()
        == inventory["selected_wheel_inventory_sha256"]
    )
    assert (
        hashlib.sha256(edge_bytes).hexdigest() == inventory["dependency_edges_sha256"]
    )
    distribution_records = [
        {
            "artifact_type": "interpreter_archive",
            "filename": interpreter["archive_filename"],
            "name": "python",
            "sha256": interpreter["archive_sha256"],
            "size_bytes": interpreter["archive_size_bytes"],
            "url": interpreter["archive_url"],
            "version": interpreter["version"],
        }
    ]
    distribution_records.extend(
        {
            "artifact_type": "bdist_wheel",
            "filename": package["wheel"]["filename"],
            "name": package["name"],
            "sha256": package["wheel"]["sha256"],
            "size_bytes": package["wheel"]["size_bytes"],
            "url": package["wheel"]["url"],
            "version": package["version"],
        }
        for package in packages
    )
    distribution_records.sort(
        key=lambda record: tuple(
            record[field] for field in digest_contract["record_order_fields"]
        )
    )
    distribution_bytes = json.dumps(
        distribution_records,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    assert len(distribution_records) == 97
    assert len(distribution_bytes) == 37_820
    assert (
        hashlib.sha256(distribution_bytes).hexdigest()
        == (inventory["runtime_distribution_inventory_sha256"])
    )
    assert inventory["runtime_distribution_total_size_bytes"] == (
        inventory["selected_wheel_total_size_bytes"] + interpreter["archive_size_bytes"]
    )

    policy = manifest["installation_policy"]
    assert (
        "exactly one enumerated install-only interpreter archive"
        in policy["allowed_artifact_type"]
    )
    assert (
        "exactly one enumerated bdist_wheel per package"
        in policy["allowed_artifact_type"]
    )
    assert set(policy["forbidden_packages"]).isdisjoint(by_name)
    forbidden_tokens = set(policy["forbidden_accelerator_tokens_casefolded"])
    package_and_artifact_text = " ".join(
        [package["name"] for package in packages]
        + [package["wheel"]["filename"] for package in packages]
    ).casefold()
    assert all(token not in package_and_artifact_text for token in forbidden_tokens)
    assert (
        "record the installed executable hash"
        in policy["interpreter_artifact_boundary"]
    )
    assert "PYTHON.json licensing" in policy["interpreter_artifact_boundary"]
    assert "Network must be disabled before import" in policy["network_boundary"]
    assert (
        "do not modify pyproject.toml or uv.lock"
        in policy["project_dependency_boundary"]
    )
    assert "No resolver update" in policy["replacement_boundary"]
    assert "No model/tokenizer artifact" in policy["transformer_extra_boundary"]

    root_project = (ROOT / "pyproject.toml").read_text(encoding="utf-8").casefold()
    root_lock = (ROOT / "uv.lock").read_text(encoding="utf-8").casefold()
    for isolated_name in ("torch", "dgl", "dgllife", "molfeat", "catboost"):
        assert f'"{isolated_name}' not in root_project
        assert f'name = "{isolated_name}"' not in root_lock

    accounting = manifest["contract_only_accounting"]
    assert accounting
    assert all(value == 0 for value in accounting.values())
    assert accounting["interpreter_archives_downloaded"] == 0
    assert accounting["package_wheels_installed"] == 0
    assert accounting["runtime_environments_created"] == 0
    assert accounting["imports_executed_in_frozen_runtime"] == 0
    assert "Any artifact, rights, notice, import, tensor" in manifest["next_gate"]


def test_three_public_objects_rights_unknown_overlap_and_notices_are_exact() -> None:
    rights = _load()["rights_provenance_and_notices"]
    assert rights["supported_claim"] == "public pretrained-representation transfer"
    assert set(rights["forbidden_claims"]) == {
        "clean zero-shot transfer",
        "uncontaminated external validation",
        "strict family holdout from all pretraining",
        "known absence of OpenADMET structure overlap",
        "known absence of OpenADMET assay overlap",
        "artifact-specific license terms that the upstream metadata does not state",
    }
    lineage = rights["pretraining_lineage"]
    assert lineage["node_level"] == "approximately two million ZINC15 molecules"
    assert lineage["graph_level"] == (
        "approximately 456,000 ChEMBL molecules across 1,310 assays"
    )
    assert lineage["openadmet_structure_overlap"] == "unknown"
    assert lineage["openadmet_assay_overlap"] == "unknown"
    assert "both unknown-overlap facts" in lineage["disclosure"]

    snap = rights["snap"]
    assert snap["commit"] == "8b20528a83b8869ce16451305b32c827258d19a3"
    assert snap["checkpoint_git_blob"] == ("1f8de843feb5b51e73488a95096283028820583e")
    assert snap["checkpoint_sha256"] == (
        "375cd40af9f21d2a92ed1acbdea9efad14254c36703bb0e3a7e433e09e624ce1"
    )
    assert snap["checkpoint_size_bytes"] == 7_452_448
    assert snap["license"] == "MIT"
    assert "Sole canonical future feature-weight source" in snap["future_role"]

    dgl = rights["dgl_lifesci"]
    assert dgl["version"] == "0.3.2"
    assert dgl["commit"] == "20cee8f3a2be314e34c0e696e797884630d0863e"
    assert dgl["checkpoint_expected_size_bytes"] == 7_454_321
    assert dgl["checkpoint_expected_etag"] == "98fae61c9c23ce19ce4e57614f0f9450"
    assert dgl["checkpoint_sha256_at_freeze"] is None
    binding = dgl["checkpoint_sha256_binding"]
    assert "no trusted SHA-256 at D148 freeze" in binding
    assert "before any torch deserialization" in binding
    assert "bind that first hash" in binding
    assert "A second download is forbidden" in binding
    assert dgl["license"] == "Apache-2.0"
    assert "Parity-only" in dgl["future_role"]
    assert "never use it as a later official feature source" in dgl["future_role"]

    molfeat = rights["molfeat"]
    assert molfeat["version"] == "0.9.2"
    assert molfeat["commit"] == "4390f9fce25fa2da94338227f7c8f33a23e25b2a"
    assert molfeat["metadata_sha256"] == (
        "75ea305d643d800b8b272819a78b842d5aca1c4ad55d47207321ab9b81d44d02"
    )
    assert molfeat["artifact_sha256"] == (
        "6d0f8febad73e437772ebffc2ac32253d79f86ee138cfc233590ae50fb1cfeb9"
    )
    assert molfeat["artifact_size_bytes"] == 7_467_310
    assert molfeat["artifact_license_field"] is None
    assert molfeat["model_usage"] is None
    assert molfeat["license"] == "Apache-2.0"
    assert (
        "metadata does not state an artifact-specific license"
        in (molfeat["future_role"])
    )
    assert "local nonredistributed parity" in molfeat["future_role"]

    assert "Any contradiction" in rights["rights_acceptance_rule"]
    nonredistribution = rights["nonredistribution"]
    for forbidden_destination in (
        "Git",
        "CI artifacts",
        "submission files",
        "public terminals",
        "method-report attachments",
        "publication bundles",
    ):
        assert forbidden_destination in nonredistribution
    assert "only hashes, sizes, licenses/notices" in nonredistribution

    notice_text = NOTICES.read_text(encoding="utf-8")
    assert notice_text.endswith("\n")
    for required in (
        "SNAP",
        "MIT",
        "DGL-LifeSci",
        "Apache-2.0",
        "MolFeat",
        "ZINC15",
        "ChEMBL",
        "unknown",
        "nonredistribut",
        snap["checkpoint_sha256"],
        molfeat["artifact_sha256"],
    ):
        assert required.lower() in notice_text.lower()
    for runtime_notice in (
        "complete 96-wheel CPU-only closure",
        "97 runtime artifacts",
        "566,804,656 bytes",
        "python-build-standalone release `20240224`",
        "61ace30326ba7c32325c6633665cc571ac56b82a",
        "d995d032ca702afd2fc3a689c1f84a6c64972ecd82bba76a61d525f08eb0e195",
        "27,409,290 bytes",
        "PSF-2.0",
        "BSD-3-Clause",
        "sole Python package wheel uploaded",
    ):
        assert runtime_notice in notice_text
    assert "SHA-256 at D148 freeze: not yet known" in notice_text
    normalized_notice_text = " ".join(notice_text.split())
    assert (
        "hashed and immutably receipted before any deserialization"
        in normalized_notice_text
    )
    assert "Artifact-specific license field" in notice_text
    assert "absent (`null`)" in notice_text


def test_fetch_offline_sandbox_and_cleanup_are_fail_closed() -> None:
    policy = _load()["network_fetch_offline_sandbox_and_cleanup"]
    network = policy["formal_attempt_network_phase"]
    rights = _load()["rights_provenance_and_notices"]
    assert network["allowed_model_urls"] == [
        rights["snap"]["checkpoint_url"],
        rights["dgl_lifesci"]["checkpoint_url"],
        rights["molfeat"]["artifact_url"],
    ]
    method = network["method"]
    for required in (
        "Fetch sequentially",
        "ProxyHandler({})",
        "Accept-Encoding: identity",
        "credential handler",
        "exclusive-create staging files",
        "streaming SHA-256",
        "fsync",
        "atomic no-replace publication",
        "DGL ETag normalization and first-hash-before-deserialization rule",
    ):
        assert required in method
    forbidden = network["forbidden"]
    for blocked in (
        "Git clone",
        "model-store discovery",
        "unpinned index resolution",
        "cache reuse",
        "range-resume",
        "alternate mirror",
        "Hugging Face access",
        "telemetry",
        "fourth checkpoint/model object",
    ):
        assert blocked in forbidden

    offline = policy["offline_phase"]
    assert "every scientific import, deserialization" in offline["network"]
    assert "fresh nested Linux network namespace" in offline["network"]
    assert (
        "Any failed namespace isolation stops before import or load"
        in (offline["network"])
    )
    assert offline["environment"] == {
        "DGLBACKEND": "pytorch",
        "CUDA_VISIBLE_DEVICES": "",
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
        "MOLFEAT_MODEL_STORE_BUCKET": (
            "object_root/molfeat-store from verified_object_view_layout"
        ),
        "TOKENIZERS_PARALLELISM": "false",
    }
    for hidden in (
        "caller home",
        "credentials",
        "SSH agent",
        "official/protected roots",
        "portal state",
        "accelerator devices",
    ):
        assert hidden in offline["filesystem"]
    assert "Use spawn, never fork" in offline["workers"]
    assert "one 16-thread CatBoost fit" in offline["workers"]
    assert "interop and intraop threads to one" in offline["workers"]

    roots = policy["private_roots"]
    assert set(roots) == {
        "attempt_root",
        "runtime_root",
        "wheel_cache_root",
        "object_root",
        "claim_root",
        "publication_staging_root",
        "transactional_claim_staging_path",
        "rule",
    }
    root_values = [value for name, value in roots.items() if name != "rule"]
    assert len(root_values) == len(set(root_values)) == 7
    assert all(
        value.startswith("/home/zbos/cypshift-private/openadmet-2026/")
        for value in root_values
    )
    assert (
        "all six exact roots plus the transactional claim-staging path absent"
        in (roots["rule"])
    )
    assert "Symlinks, hard-link aliases, mount aliases" in roots["rule"]

    cleanup = policy["cleanup"]
    consumed_claim_retention = cleanup["consumed_claim_retention"]
    assert (
        "fixed consumed claim and its hash permanently read-only"
        in consumed_claim_retention
    )
    assert (
        "including after a crash before terminal publication"
        in consumed_claim_retention
    )
    assert "one-use tombstone" in consumed_claim_retention
    for forbidden_tombstone_action in (
        "deleted",
        "moved",
        "overwritten",
        "reset",
        "reused",
    ):
        assert forbidden_tombstone_action in consumed_claim_retention
    assert "verified SNAP checkpoint" in cleanup["success_retention"]
    assert "Retain no DGL checkpoint" in cleanup["success_retention"]
    assert "MolFeat checkpoint" in cleanup["success_retention"]
    assert (
        "remove the runtime, wheel cache, every checkpoint"
        in (cleanup["failure_retention"])
    )
    assert "EXP-G4-GIN300 closes" in cleanup["failure_retention"]
    assert (
        "Cleanup failure forces G3_G4_GIN300_FAILED"
        in (cleanup["preseal_verification"])
    )


def test_snap_to_dgl_mapping_is_complete_exact_and_tolerance_free() -> None:
    conversion = _load()["snap_to_dgl_tensor_conversion"]
    architecture = conversion["architecture"]
    assert architecture == {
        "num_layers": 5,
        "embedding_dimension": 300,
        "jumping_knowledge": "last",
        "dropout": 0.5,
        "node_embedding_cardinalities": [120, 3],
        "edge_embedding_cardinalities": [6, 3],
        "evaluation_mode": True,
        "pooling_after_gnn": "mean",
    }

    mappings = list(conversion["global_mapping"])
    per_layer = conversion["per_layer_mapping"]
    assert per_layer["layer_indices"] == "i in 0,1,2,3,4"
    assert len(per_layer["rules"]) == 11
    for layer in range(5):
        for rule in per_layer["rules"]:
            mappings.append(
                {
                    "snap": rule["snap"].format(i=layer),
                    "dgl": rule["dgl"].format(i=layer),
                    "shape": rule["shape"],
                    "dtype": rule["dtype"],
                }
            )
    assert per_layer["expanded_keys"] == 55
    assert len(mappings) == conversion["canonical_destination_key_count"] == 57
    assert len({entry["snap"] for entry in mappings}) == 57
    assert len({entry["dgl"] for entry in mappings}) == 57

    float32_elements = sum(
        math.prod(entry["shape"])
        for entry in mappings
        if entry["dtype"] == "torch.float32"
    )
    int64_elements = sum(
        math.prod(entry["shape"])
        for entry in mappings
        if entry["dtype"] == "torch.int64"
    )
    assert float32_elements == conversion["canonical_float32_elements"] == 1_860_900
    assert int64_elements == conversion["canonical_int64_scalar_elements"] == 5
    assert (
        conversion["canonical_raw_tensor_bytes"]
        == (4 * float32_elements + 8 * int64_elements)
        == 7_443_640
    )

    algorithm = conversion["conversion_algorithm"]
    for prohibited in (
        "key guessing",
        "missing key",
        "extra key",
        "transpose",
        "reshape",
        "squeeze",
        "cast",
        "byte swap",
        "device transfer",
    ):
        assert prohibited in algorithm
    assert "exact destination key set, dtype, shape" in algorithm
    tensor_gate = conversion["three_object_tensor_gate"]
    assert "exact tensor-byte equality" in tensor_gate
    assert "This tensor gate has no tolerance" in tensor_gate
    assert "Known hashes must pass first" in conversion["deserialization_safety"]
    assert "restricted weights-only mechanism" in conversion["deserialization_safety"]


def test_graph_construction_and_three_process_parity_are_frozen() -> None:
    graph = _load()["graph_and_embedding_contract"]
    assert "eight fixture raw_smiles strings exactly in file order" in graph["input"]
    assert "SHA-256 of each exact raw UTF-8 string" in graph["input"]
    assert "RDKit 2023.3.3 Chem.MolFromSmiles" in graph["rdkit_parse"]
    assert graph["atom_order"] == (
        "canonical_atom_order is false. Preserve RDKit atom indices from the "
        "parsed exact raw string."
    )
    assert "begin-to-end then end-to-begin" in graph["directed_edges"]
    assert "one self-loop per atom after all bond edges" in graph["directed_edges"]
    assert graph["atom_features"]["atomic_number"].endswith(
        "atomic_number minus one and cardinality 120"
    )
    assert "outside 0..2 fails" in graph["atom_features"]["chirality_type"]
    assert "self-loop index 4" in graph["edge_features"]["bond_type"]
    assert "self-loop direction 0" in graph["edge_features"]["bond_direction_type"]
    assert "Require byte-identical graph manifests" in graph["graph_fingerprint"]

    inference = graph["inference"]
    for required in (
        "one CPU batch of eight rows",
        "batch_size 32",
        "model.eval()",
        "torch.no_grad()",
        "one intraop and one interop thread",
        "five GIN layers",
        "JK last",
        "mean pooling",
        "8 by 300",
        "little-endian numpy float64",
        "C contiguity and finiteness",
        "non-pickle NPY v1.0",
    ):
        assert required in inference
    processes = graph["fresh_processes"]
    assert len(processes) == 3
    assert processes[0].startswith(
        "Process A deserializes the authenticated SNAP object exactly once"
    )
    assert "same Process A builds both scaled 3,908-row roots" in processes[0]
    assert "may not reload, redeserialize, respawn" in processes[0]
    assert processes[1].startswith("Process B loads only the authenticated native DGL")
    assert processes[2].startswith("Process C loads only the authenticated MolFeat")
    assert "every network path disabled" in processes[2]

    parity = graph["parity_decision"]
    assert "all exactly identical" in parity["primary_exact"]
    fallback = parity["predeclared_numeric_fallback"]
    assert "graph and tensor manifests are still exact" in fallback
    assert "all three pairwise maximum absolute" in fallback
    assert "max_abs <= 0.0000001 with rtol exactly zero" in fallback
    prediction = parity["prediction_fallback"]
    assert "both independently fitted real-probe candidate CatBoost models" in (
        prediction
    )
    assert "all eight fixture rows" in prediction
    for pair in (
        "converted SNAP versus DGL",
        "converted SNAP versus MolFeat",
        "DGL versus MolFeat",
    ):
        assert pair in prediction
    assert "Any prediction-byte difference fails" in prediction
    assert "may not be relaxed" in parity["no_observed_choice"]
    assert "Raw graphs, tensor values, embeddings" in graph["private_outputs"]


def test_synthetic_topology_controls_and_accounting_cover_the_full_design() -> None:
    synthetic = _load()["official_shaped_synthetic_capability"]
    assert synthetic["scientific_interpretation"].startswith("None.")
    assert "No metric is evaluated" in synthetic["scientific_interpretation"]
    topology = synthetic["topology"]
    assert topology["development_molecules"] == 3_908
    assert topology["development_components"] == 3_640
    assert topology["components_with_two_molecules"] == 268
    assert topology["components_with_one_molecule"] == 3_372
    assert 2 * 268 + 3_372 == 3_908
    assert topology["exact_raw_duplicate_pairs"] == 32
    assert topology["endpoints"] == ["CYP1A2", "CYP2C9", "CYP2D6", "CYP3A4"]
    assert topology["repeats"] == 3
    assert topology["outer_folds"] == 5
    assert topology["systems"] == [
        "G4-MAPL2563-GIN300",
        "G4-MAPL2563-SHUFFLED-GIN300",
        "G4-MAPL2563-NOISE300",
    ]
    assert topology["fit_identities"] == 3 * 3 * 5 * 4 == 180
    assert topology["prediction_rows_per_system"] == 3_908 * 3 * 4 == 46_896
    assert topology["prediction_rows_total"] == 3 * 46_896 == 140_688
    assert "Three systems times 3 repeats" in topology["formula"]

    assert "C000000 through C003639" in synthetic["identity_construction"]
    assert "M003640 through M003907" in synthetic["identity_construction"]
    assert "first 32 two-molecule components" in synthetic["identity_construction"]
    assert "Physical source order is not semantic" in synthetic["identity_construction"]
    folds = synthetic["fold_construction"]
    assert "(c + repeat_index) mod 5" in folds
    assert "exactly 728 components per fold" in folds
    assert "No identity, exact duplicate, or component crosses a fold" in folds

    features = synthetic["feature_construction"]
    assert (
        "exact raw duplicates receive identical features"
        in (features["raw_identity_index"])
    )
    assert "columns 2402, 2404, 2406, and 2408" in features["maplight"]
    assert "canonical quiet float64 NaN" in features["maplight"]
    assert "This is not a checkpoint embedding" in features["gin"]
    assert "3,908 by 2,863 float64 matrix" in features["candidate"]
    controls = features["controls"]
    for required in (
        "every repeat, fold, and train/validation partition",
        "D147 SeedSequence rules",
        "seeds 20260816 and 20260817",
        "sorted unique raw_structure_sha256 values",
        "Expand exact-raw duplicates identically",
        "No donor, identity, or vector crosses a partition",
    ):
        assert required in controls
    assert "All 15,632 values are finite" in features["labels"]
    assert "may not be called official or scientific" in features["labels"]

    roots = synthetic["two_roots"]
    assert (
        "ascending" in roots["root_a"]
        and "candidate, shuffle, noise" in roots["root_a"]
    )
    assert (
        "descending" in roots["root_b"]
        and "noise, shuffle, candidate" in roots["root_b"]
    )
    assert "Authenticate then canonical-sort" in roots["canonicalization"]
    assert "may not read, link, copy, cache" in roots["independence"]
    assert "byte-identical" in roots["equality"]

    model_double = synthetic["full_topology_model_double"]
    assert model_double["required_fits"] == 180
    assert model_double["required_predictions"] == 140_688
    assert model_double["baseline_refits"] == 0
    assert model_double["metric_evaluations"] == 0
    assert model_double["bootstrap_replicates"] == 0
    assert "must not open validation target bytes" in model_double["rule"]
    assert "freeze all rows before" in model_double["rule"]
    assert "family containment" in model_double["acceptance"]
    assert "no cross-root input" in model_double["acceptance"]


def test_six_real_fits_and_conservative_resource_projection_are_exact() -> None:
    contract = _load()
    probe = contract["official_shaped_synthetic_capability"]["real_catboost_probe"]
    assert probe["fits_per_root"] == 3
    assert probe["roots"] == 2
    assert probe["total_fits"] == 6
    assert probe["probe_cell"] == (
        "repeat_index 0, outer_fold 0, endpoint CYP1A2; one fit for each of the "
        "three systems per root"
    )
    assert "outside repeat-0 fold 0" in probe["training_rows"]
    assert "complete repeat-0 fold-0 population" in probe["training_rows"]
    assert "Full 2,863-column float64 matrices" in probe["features"]
    assert "contract-frozen redistributable synthetic" in probe["labels"]
    assert "No official target" in probe["labels"]
    model = probe["model"]
    assert model == {
        "api": "catboost.CatBoostRegressor",
        "loss_function": "MAE",
        "random_strength": 2,
        "random_seed": 1,
        "task_type": "CPU",
        "thread_count": 16,
        "verbose": 0,
        "allow_writing_files": False,
        "omitted": [
            "eval_set",
            "early_stopping_rounds",
            "use_best_model",
            "iterations",
            "nan_mode",
        ],
        "required_resolved_parameter_sha256": (
            "c56235a54a883a9a4488f1c8779f9013dae777af0f99cd92c9da1c4f51e61757"
        ),
    }
    assert "three eight-row parity matrices" in probe["prediction_requirements"]
    assert "root-to-root byte equality" in probe["prediction_requirements"]
    assert "No warm start, Pool reuse, quantization reuse" in probe["forbidden"]
    assert "second probe" in probe["forbidden"]

    projection = contract["resource_projection"]
    ceiling = projection["parent_execution_ceiling"]
    assert ceiling == {
        "cpu_core_hours": 96,
        "cpu_seconds": 345_600,
        "gpu_hours": 0,
        "restricted_storage_gb": 32,
        "restricted_storage_bytes_decimal": 32_000_000_000,
        "maximum_wall_hours": 12,
        "maximum_wall_seconds": 43_200,
        "maximum_peak_simultaneous_rss_gib": 16,
        "maximum_peak_simultaneous_rss_bytes": 17_179_869_184,
    }
    margin = projection["required_20_percent_margin"]
    assert margin == {
        "maximum_projected_cpu_core_hours": 76.8,
        "maximum_projected_cpu_seconds": 276_480,
        "maximum_projected_gpu_hours": 0,
        "maximum_projected_restricted_storage_gb": 25.6,
        "maximum_projected_restricted_storage_bytes_decimal": 25_600_000_000,
        "maximum_projected_wall_hours": 9.6,
        "maximum_projected_wall_seconds": 34_560,
        "maximum_peak_simultaneous_rss_gib": 12.8,
        "maximum_peak_simultaneous_rss_bytes_floor": 13_743_895_347,
    }
    assert margin["maximum_projected_cpu_core_hours"] == pytest.approx(
        0.8 * ceiling["cpu_core_hours"]
    )
    assert margin["maximum_projected_restricted_storage_gb"] == pytest.approx(
        0.8 * ceiling["restricted_storage_gb"]
    )
    assert "one monotonic wall clock without reset" in projection["measurement"]
    fit_projection = projection["fit_projection"]
    assert "sum the three complete measured real-CatBoost-probe stage" in (
        fit_projection
    )
    assert "multiply that sum by 60" in fit_projection
    assert "worse projected root independently for wall and CPU" in fit_projection
    assert "feature/control materialization, construction, fit" in fit_projection
    assert "all 782 validation predictions" in fit_projection
    assert "receipt hashing, and supervisor overhead" in fit_projection
    assert "Subtract nothing and assume no parallel speedup" in fit_projection
    assert "33,554,432 bytes" in projection["storage_projection"]
    assert (
        "two simultaneous 3,908 by 300 float64 NPY feature roots"
        in (projection["storage_projection"])
    )
    assert "without scaling down" in projection["rss_projection"]
    assert "exactly zero" in projection["gpu_projection"]
    assert "Exactly one one-thread GIN worker" in projection["concurrency"]
    assert "Do not overlap roots" in projection["concurrency"]
    assert (
        "every 20-percent-margin maximum passes conjunctively"
        in (projection["acceptance"])
    )
    assert projection["resource_failure_status"] == (
        "G3_G4_GIN300_RESOURCE_INFEASIBLE_PREFIT"
    )
    assert "No optimization pass" in projection["resource_failure_effect"]


def test_d149_zero_execution_package_and_d150_run_scope_are_exact() -> None:
    contract = _load()
    boundary = contract["contract_only_boundary"]
    assert boundary["current_authority"] == (
        "Static contract, exact runtime-manifest bytes, third-party notice bytes, "
        "and public static tests only."
    )
    for prohibited in (
        "create or install the runtime",
        "download or retain a wheel",
        "fetch or load any checkpoint",
        "deserialize any tensor or pickle",
        "implement a feature builder or runner",
        "execute parity or a model",
        "create or consume a claim",
        "open an official or private row",
        "scientific result",
    ):
        assert prohibited in boundary["current_prohibitions"]
    assert "not capability acceptance" in boundary["no_implicit_authority"]
    assert (
        "D149 create and validate the exact zero-execution"
        in (boundary["implementation_gate"])
    )
    assert (
        "D150 invoke the sole formal one-use attempt"
        in (boundary["implementation_gate"])
    )

    package = contract["future_d149_implementation_package"]
    assert set(package) == {
        "implementation_and_lock_paths",
        "public_test_paths",
        "public_result_path",
        "narrative_evidence_paths",
        "experiment_ledger_path",
        "d149_exact_allowed_created_or_modified_path_count",
        "d149_exact_allowed_created_or_modified_paths",
        "d149_zero_execution_authority",
        "d149_internal_freeze_delegation",
        "d149_result_presence",
        "d150_exact_allowed_created_or_modified_path_count",
        "d150_exact_allowed_created_or_modified_paths",
        "isolated_project_contract",
        "runtime_install_contract",
        "root_environment_immutability",
        "future_d150_outer_launcher",
        "future_d150_runner_local_supervision",
        "test_responsibilities",
        "no_other_file_or_api_rule",
    }
    implementation_paths = [
        "research/maplight-gin-openadmet/.python-version",
        "research/maplight-gin-openadmet/pyproject.toml",
        "research/maplight-gin-openadmet/uv.lock",
        "research/maplight-gin-openadmet/build_global_v3_g4_gin300_capability.py",
        "research/maplight-gin-openadmet/run_global_v3_g4_gin300_capability.py",
    ]
    test_paths = [
        "tests/test_openadmet_global_v3_g4_gin300_capability.py",
        "tests/test_openadmet_global_v3_g4_gin300_capability_result.py",
    ]
    narrative_paths = [
        "benchmarks/openadmet_cyp_2026/README.md",
        "docs/phases/PHASE_2_OPENADMET_GLOBAL_V2.md",
        "docs/phases/README.md",
        "docs/strategy/DECISIONS.md",
        "docs/strategy/NEXT_ORCHESTRATOR_PROMPT.md",
        "docs/strategy/PROJECT_STATE.md",
    ]
    ledger = "runs/experiment_ledger.csv"
    result = "benchmarks/openadmet_cyp_2026/global_v3_g4_gin300_capability_result.json"
    assert package["implementation_and_lock_paths"] == implementation_paths
    assert package["public_test_paths"] == test_paths
    assert package["narrative_evidence_paths"] == narrative_paths
    assert package["experiment_ledger_path"] == ledger
    assert package["public_result_path"] == result
    assert package["d149_exact_allowed_created_or_modified_path_count"] == 14
    assert package["d149_exact_allowed_created_or_modified_paths"] == (
        implementation_paths + test_paths + narrative_paths + [ledger]
    )
    assert package["d150_exact_allowed_created_or_modified_path_count"] == 8
    assert package["d150_exact_allowed_created_or_modified_paths"] == (
        [result] + narrative_paths + [ledger]
    )
    assert len(set(package["d149_exact_allowed_created_or_modified_paths"])) == 14
    assert len(set(package["d150_exact_allowed_created_or_modified_paths"])) == 8
    assert result not in package["d149_exact_allowed_created_or_modified_paths"]
    assert set(implementation_paths + test_paths).isdisjoint(
        package["d150_exact_allowed_created_or_modified_paths"]
    )
    assert not (ROOT / result).exists()
    assert "must remain absent throughout D149" in package["d149_result_presence"]

    zero = package["d149_zero_execution_authority"]
    for forbidden in (
        "fetch an artifact",
        "create or install a runtime",
        "import a scientific closure package",
        "open or deserialize a checkpoint",
        "create a private root",
        "execute parity/synthetic capability/CatBoost",
        "create or consume a claim",
        "create the result file",
    ):
        assert forbidden in zero
    delegation = package["d149_internal_freeze_delegation"]
    for required in (
        "exactly once and encode as immutable literal code",
        "closed control kind/stage/aggregate enum",
        "exact pipe/subprocess drain wiring",
        "dgllife.model.pretrain.property_prediction.create_property_model",
        "direct exact dgllife.model.gnn.gin.GIN",
        "strict 57-key state loading/eval",
        "MolFeat local-file-store/PretrainedDGLTransformer",
        "reject dynamic dispatch, alternate API, fallback, reflection",
        "D149 executes none of them",
        "outcome-neutral internal call/wire detail",
    ):
        assert required in delegation

    project = package["isolated_project_contract"]
    assert project["python_version_file_exact_bytes"] == "3.10.13\n"
    assert project["evidence_mirror_shape"] == {
        "lock_format": "uv lock version 1, revision 3",
        "package_tables": 97,
        "virtual_root_tables": 1,
        "runtime_distribution_tables": 96,
        "declared_root_requirements": 11,
        "transitive_dependency_edges_excluding_root_edges": 185,
        "pypi_wheel_records": 95,
        "pytorch_cpu_index_wheel_records": 1,
        "sdist_records": 0,
    }
    assert "pure standard-library tomllib projection" in project["lock_acceptance"]
    assert "never installation authority" in project["lock_acceptance"]

    responsibilities = package["test_responsibilities"]
    for state in (
        "absent+untracked passes D149",
        "present+untracked immediately after D150",
        "present+tracked requires Git mode 100644",
        "absent+tracked always fails",
    ):
        assert state in responsibilities["result_test"]
    assert (
        "live regular nonsymlink single-link 0444 sealed inode"
        in (responsibilities["result_test"])
    )
    assert (
        "filesystem mode 0644 or the original 0444" in (responsibilities["result_test"])
    )
    assert "may not create a fixture result" in responsibilities["result_test"]
    assert "collection policy are immutable" in responsibilities["no_collection_change"]
    assert (
        "D149 may create or modify exactly its 14 listed"
        in (package["no_other_file_or_api_rule"])
    )
    assert (
        "D150 may create or modify exactly its eight listed"
        in (package["no_other_file_or_api_rule"])
    )


def test_d150_launcher_supervision_sandbox_and_hard_limits_are_closed() -> None:
    package = _load()["future_d149_implementation_package"]
    root = package["root_environment_immutability"]
    assert _sha256(ROOT / root["pyproject_path"]) == root["pyproject_sha256"]
    assert _sha256(ROOT / root["uv_lock_path"]) == root["uv_lock_sha256"]
    launcher_python = root["launcher_interpreter"]
    assert launcher_python["exact_path"] == "/usr/bin/python3.12"
    assert launcher_python["version"] == "3.12.3"
    assert launcher_python["executable_sha256"] == (
        "1643dacd9feaedc58f3cc581e4d22577dfe25c09b10282936186ccf0f2e61118"
    )
    git = root["host_git"]
    assert git["exact_path"] == "/usr/bin/git"
    assert git["version"] == "2.43.0"
    assert git["executable_sha256"] == (
        "2a8c18fbf43da9f692d75474c72bea9dfd796c260b0f3dfe456376abc3bbd668"
    )
    assert git["exact_environment"] == {
        "PATH": "/usr/bin",
        "HOME": "/nonexistent",
        "LANG": "C",
        "LC_ALL": "C",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_OPTIONAL_LOCKS": "0",
        "GIT_NO_REPLACE_OBJECTS": "1",
    }
    assert len(git["authenticated_input_paths"]) == 11
    assert len(set(git["authenticated_input_paths"])) == 11
    assert "11 authenticated input paths" in git["rule"]
    assert "never for unrelated worktree state" in git["rule"]
    for rejected in (
        "config.worktree",
        "info/grafts",
        ".git/shallow",
        "objects/info/alternates",
        "refs/replace",
        "include/includeIf",
        "extensions.worktreeConfig",
        "core.worktree",
    ):
        assert rejected in git["repository_metadata_rejections"]
    assert "Git SHA-1 as sha1(`blob `" in git["byte_authentication"]
    assert "external pre-execution gate" in git["external_clean_main_precondition"]

    launcher = package["future_d150_outer_launcher"]
    assert launcher["exact_argv"] == [
        "/usr/bin/env",
        "-i",
        "PATH=/usr/bin",
        "LANG=C.UTF-8",
        "LC_ALL=C.UTF-8",
        "TZ=UTC",
        "PYTHONNOUSERSITE=1",
        "/usr/bin/python3.12",
        "-I",
        "-S",
        "-B",
        "research/maplight-gin-openadmet/run_global_v3_g4_gin300_capability.py",
    ]
    assert launcher["operator_entry_environment"] == {
        "PATH": "/usr/bin",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "TZ": "UTC",
        "PYTHONNOUSERSITE": "1",
    }
    assert "receives no LD_PRELOAD" in launcher["entry_environment_rule"]
    assert (
        "lineage_authenticated=true"
        in (launcher["mandatory_lineage_authenticated_checkpoint"])
    )
    assert (
        "creates no claim/root/result"
        in (launcher["mandatory_lineage_authenticated_checkpoint"])
    )
    assert (
        "seal_preflight_authenticated=true"
        in (launcher["mandatory_seal_preflight_authenticated_checkpoint"])
    )
    assert (
        "Every public result requires both"
        in (launcher["mandatory_seal_preflight_authenticated_checkpoint"])
    )
    assert launcher["internal_cli"].startswith(
        "The runner accepts exactly one private flag, --child"
    )
    assert (
        "form exactly one bounded ASCII stdout line"
        in (launcher["outer_completion_receipt"])
    )

    supervision = package["future_d150_runner_local_supervision"]
    assert set(supervision) == {
        "private_api",
        "host_sandbox_tool",
        "controller_boundary",
        "network_callsite_rule",
        "ready_checkpoint",
        "offline_worker_boundary",
        "offline_worker_sandbox",
        "single_observation",
        "bounded_channel_contract",
        "descendant_stdio_contract",
        "hard_resource_ceiling_enforcement",
        "outer_claim_boundary",
    }
    assert "Python standard-library" in supervision["controller_boundary"]
    assert (
        "never deserializes or opens checkpoint tensor payloads"
        in (supervision["controller_boundary"])
    )
    assert (
        "one statically identifiable runner fetch function"
        in (supervision["network_callsite_rule"])
    )
    assert "no worker has a network callsite" in supervision["offline_worker_boundary"]
    sandbox = supervision["offline_worker_sandbox"]
    argv = sandbox["exact_argv_template"]
    assert argv[:5] == [
        "bwrap",
        "--die-with-parent",
        "--new-session",
        "--unshare-all",
        "--clearenv",
    ]
    assert "<authenticated_builder_file>" in argv
    assert "<authenticated_eight_row_fixture>" in argv
    assert "<authenticated_runtime_root>" in argv
    assert "<verified_object_view>" in argv
    assert "No read-only bind of host / or repository root" in sandbox["mount_rule"]
    assert (
        "Bind the eight listed public input files individually"
        in (sandbox["mount_rule"])
    )
    assert "every proxy" in sandbox["environment_rule"]
    assert "--unshare-all supplies a new network" in sandbox["namespace_rule"]

    channel = supervision["bounded_channel_contract"]
    assert channel["controller_stdout_maximum_bytes"] == 65_536
    assert channel["controller_stderr_maximum_bytes"] == 65_536
    assert channel["control_frame_maximum_bytes"] == 16_384
    assert channel["control_frame_maximum_count"] == 64
    assert channel["control_stream_maximum_bytes"] == 1_048_576
    assert channel["child_payload_maximum_bytes"] == 524_288
    assert channel["outer_receipt_stdout_maximum_bytes"] == 128
    assert "schema_version, sequence, kind, stage, aggregate" in channel["framing"]
    assert (
        "D149 must freeze one closed kind/stage/aggregate-schema tuple"
        in (channel["framing"])
    )
    assert (
        "exactly two anonymous unidirectional Linux pipes"
        in (channel["ready_ack_transport"])
    )
    assert "stage child_ready_preclaim" in channel["ready_ack_transport"]
    assert "concurrently drains controller stdout, stderr" in channel["enforcement"]

    stdio = supervision["descendant_stdio_contract"]
    assert [
        stdio[name]
        for name in (
            "uv_stdout_maximum_bytes",
            "uv_stderr_maximum_bytes",
            "bwrap_subtree_stdout_maximum_bytes",
            "bwrap_subtree_stderr_maximum_bytes",
            "all_descendant_stdio_maximum_bytes",
        )
    ] == [65_536, 65_536, 65_536, 65_536, 262_144]
    assert "at-most-4,096-byte reads" in stdio["wiring_and_enforcement"]
    assert (
        "Success requires every one of the four streams exactly empty"
        in (stdio["wiring_and_enforcement"])
    )

    hard = supervision["hard_resource_ceiling_enforcement"]
    assert hard["exact_limits"] == {
        "wall_seconds": 43_200,
        "cpu_seconds": 345_600,
        "restricted_storage_bytes": 32_000_000_000,
        "rss_bytes": 17_179_869_184,
        "gpu_visibility_or_use": 0,
    }
    assert "at-most-0.05-second sample" in hard["first_breach_rule"]
    assert "Equality to a non-GPU limit is not a breach" in hard["first_breach_rule"]
    assert "SIGTERM once" in hard["whole_tree_termination"]
    assert "exactly 2.0 monotonic seconds" in hard["whole_tree_termination"]
    assert "SIGKILL once" in hard["whole_tree_termination"]
    assert "HARD_RESOURCE_CEILING_BREACHED" in hard["whole_tree_termination"]
    assert "never RESOURCE_MARGIN_MISSED" in hard["whole_tree_termination"]
    assert "outer process" in supervision["outer_claim_boundary"]
    assert "never derives, creates, consumes" in supervision["outer_claim_boundary"]


def test_d150_claim_is_exact_atomic_single_use_and_machine_local() -> None:
    contract = _load()
    package = contract["future_d149_implementation_package"]
    attempt = contract["future_d150_formal_one_use_boundary"]
    assert attempt["claim_id"] == "GLOBAL_V3_G4_GIN300_CAPABILITY_ATTEMPT_1"
    assert attempt["current_claim_status"] == (
        "NOT_CREATED_D148_HAS_ZERO_EXECUTION_AUTHORITY"
    )
    assert attempt["future_public_terminal_path"] == package["public_result_path"]
    assert attempt["future_terminal_presence_at_d148_freeze"] is False
    assert (
        "exact 14-path D149 implementation package"
        in (attempt["creation_preconditions"])
    )
    assert (
        "exact 11 stage/HEAD/worktree input blobs"
        in (attempt["creation_preconditions"])
    )
    assert (
        "Any known mismatch is a pre-consumption failure"
        in (attempt["creation_preconditions"])
    )
    assert (
        "outside claim/result machine inputs"
        in (attempt["external_d149_integration_gate"])
    )
    assert "not a claim/result field" not in attempt["external_d149_integration_gate"]
    assert "does not grant an argument" in attempt["external_d149_integration_gate"]

    claim = attempt["claim_contract"]
    assert claim["schema_version"] == (
        "cypshift.openadmet_cyp_2026.global_v3_g4_gin300_capability_claim.v1"
    )
    assert claim["maximum_bytes"] == 65_536
    assert claim["exact_keys_in_order"] == [
        "schema_version",
        "claim_id",
        "nonce",
        "d148_commit",
        "d148_contract_sha256",
        "runtime_manifest_sha256",
        "d149_commit",
        "implementation_hashes",
        "implementation_hashes_sha256",
        "fixed_roots",
        "public_result_path",
        "object_identities",
        "tool_identities",
        "resource_limits",
        "allowed_statuses",
        "created_at_utc",
    ]
    assert claim["implementation_hash_keys_in_order"] == (
        package["implementation_and_lock_paths"] + package["public_test_paths"]
    )
    assert len(claim["implementation_hash_keys_in_order"]) == 7
    roots = contract["network_fetch_offline_sandbox_and_cleanup"]["private_roots"]
    assert claim["fixed_root_keys_in_order"] == [
        "attempt_root",
        "runtime_root",
        "wheel_cache_root",
        "object_root",
        "claim_root",
        "publication_staging_root",
        "transactional_claim_staging_path",
    ]
    assert claim["fixed_roots_exact_values"] == {
        key: roots[key] for key in claim["fixed_root_keys_in_order"]
    }
    assert len(set(claim["fixed_roots_exact_values"].values())) == 7

    objects = claim["object_identities_exact_values"]
    assert list(objects) == claim["object_identity_keys_in_order"]
    assert objects["runtime_manifest_sha256"] == RUNTIME_MANIFEST_SHA256
    assert objects["wheel_count"] == 96
    assert objects["wheel_total_size_bytes"] == 539_395_366
    assert objects["snap_size_bytes"] == 7_452_448
    assert objects["dgl_expected_size_bytes"] == 7_454_321
    assert objects["dgl_sha256_at_claim"] is None
    assert objects["molfeat_metadata_size_bytes"] == 606
    assert objects["molfeat_model_size_bytes"] == 7_467_310
    assert "first streamed D150 body SHA-256" in objects["dgl_first_hash_rule"]
    assert claim["resource_limits_exact_values"] == {
        "wall_seconds": 43_200,
        "cpu_seconds": 345_600,
        "restricted_storage_bytes": 32_000_000_000,
        "rss_bytes": 17_179_869_184,
        "gpu_hours": 0,
        "seal_wall_seconds": 5.0,
        "seal_cpu_seconds": 5.0,
        "seal_staging_bytes": 2_097_152,
        "seal_rss_bytes": 268_435_456,
    }
    assert (
        list(claim["resource_limits_exact_values"])
        == (claim["resource_limit_keys_in_order"])
    )
    assert (
        "No CI run id or lane count enters the claim/result"
        in (claim["top_level_value_rules"])
    )
    assert (
        "No random, time, host, PID, path, or mutable input"
        in (claim["nonce_derivation"])
    )
    assert "0444 and staged root 0555" in claim["atomic_consumption"]
    assert "RENAME_NOREPLACE" in claim["atomic_consumption"]
    assert "sole consumption instant" in claim["atomic_consumption"]
    assert "outer never removes a valid tombstone" in claim["collision_and_crash"]

    chronology = attempt["supervision_claim_cleanup_seal_chronology"]
    assert len(chronology) == 8
    assert chronology[0].startswith("1. Outer reaches mandatory lineage_authenticated")
    assert chronology[1].startswith("2. With both mandatory checkpoints")
    assert chronology[2].startswith("3. The stdlib child authenticates itself")
    assert chronology[3].startswith("4. Child derives and stages the exact claim")
    assert chronology[4].startswith("5. The same supervised child fetches")
    assert chronology[5].startswith("6. Child performs best-effort mutable cleanup")
    assert chronology[6].startswith("7. Outer handles return/crash")
    assert chronology[7].startswith("8. Only after cleanup facts are complete")
    operations = attempt["sole_authorized_operations_after_consumption"]
    for required in (
        "Fetch exactly 96 wheels",
        "one interpreter archive",
        "one checksum sidecar",
        "three checkpoint/model objects",
        "one 606-byte MolFeat provenance-metadata object",
        "two uncached 3,908-row converted-SNAP GIN probes",
        "180 model-double fit identities",
        "140,688 prediction rows per root",
        "exactly six real CatBoost fits",
        "4,692 validation predictions",
        "exactly 48 candidate-model fallback predictions",
    ):
        assert required in operations
    for forbidden in (
        "code edit",
        "dependency resolution",
        "alternate checkpoint",
        "retry",
        "resume",
        "result-dependent tolerance",
        "official/private/protected input",
        "metric",
        "selection",
        "submission",
        "portal credential",
        "upload",
    ):
        assert forbidden in attempt["forbidden_after_consumption"]
    assert (
        "internal and nonpublishable"
        in (attempt["preconsumption_and_postconsumption_failures"])
    )
    assert (
        "claim_consumed=true"
        in (attempt["preconsumption_and_postconsumption_failures"])
    )
    assert attempt["attempt_limit"] == 1
    assert attempt["retry_limit"] == 0
    assert attempt["resume_allowed"] is False
    assert attempt["move_or_overwrite_allowed"] is False


def test_d150_result_schema_bindings_parity_and_accounting_are_exact() -> None:
    contract = _load()
    result = contract["future_d150_result_contract"]
    assert result["path"] == (
        "benchmarks/openadmet_cyp_2026/global_v3_g4_gin300_capability_result.json"
    )
    assert result["schema_version"] == (
        "cypshift.openadmet_cyp_2026.global_v3_g4_gin300_capability_result.v1"
    )
    assert result["maximum_result_bytes"] == 1_048_576
    assert (
        "no BOM, duplicate key, NaN, Infinity, or negative zero"
        in (result["canonical_encoding"])
    )
    assert "mode 0444" in result["canonical_encoding"]
    assert "Git records the integrated file" in result["canonical_encoding"]
    top = result["exact_top_level_keys_in_order"]
    assert top == [
        "schema_version",
        "recorded_at_utc",
        "experiment_id",
        "capability_contract_sha256",
        "d148_commit",
        "d149_commit",
        "implementation_lineage",
        "status",
        "claim",
        "rights_and_objects",
        "tensor_graph_parity",
        "synthetic_capability",
        "resource_projection",
        "supervision",
        "cleanup",
        "accounting",
        "failure",
        "live_seal_mode_octal",
        "next_gate",
    ]
    assert len(top) == len(set(top)) == 19
    nested = result["exact_nested_keys_in_order"]
    assert set(nested) == {
        "implementation_lineage",
        "claim",
        "rights_and_objects",
        "tensor_graph_parity",
        "synthetic_capability",
        "resource_projection",
        "supervision",
        "cleanup",
        "accounting",
        "failure",
    }
    assert all(len(keys) == len(set(keys)) for keys in nested.values())
    assert nested["implementation_lineage"][-1] == "runtime_manifest_sha256"
    assert nested["claim"] == [
        "claim_id",
        "claim_consumed",
        "claim_sha256",
        "nonce",
        "tombstone_retained",
    ]
    assert nested["rights_and_objects"][-3:] == [
        "retained_runtime_tree_regular_bytes",
        "unknown_overlap_disclosed",
        "nonredistribution_passed",
    ]
    assert len(nested["tensor_graph_parity"]) == 12
    assert len(nested["accounting"]) == 24
    assert nested["failure"] == ["phase", "code", "detail_count"]
    assert (
        "No field is caller-supplied" in result["top_level_and_lineage_value_binding"]
    )
    assert "no claim-root bytes" in result["claim_value_binding"]
    assert "There is no third state" in result["claim_value_binding"]
    assert "return_code is null only" in result["supervision_field_semantics"]
    assert (
        "explicitly exempt from the generic nonnegative-count rule"
        in (result["supervision_field_semantics"])
    )

    parity = result["accepted_parity_value_binding"]
    assert "embedding_bytes_exact are true" in parity["primary_exact"]
    assert "numeric_fallback_used is false" in parity["primary_exact"]
    assert "pairwise max_abs values are exact JSON 0.0" in parity["primary_exact"]
    assert "parity_fallback_predictions is 0" in parity["primary_exact"]
    assert "embedding_bytes_exact is false" in parity["predeclared_numeric_fallback"]
    assert "<=0.0000001 with rtol zero" in (parity["predeclared_numeric_fallback"])
    assert (
        "prediction_fallback_bytes_exact is true"
        in (parity["predeclared_numeric_fallback"])
    )
    assert (
        "parity_fallback_predictions is 48" in (parity["predeclared_numeric_fallback"])
    )
    assert "mutually exclusive" in parity["rule"]

    success = result["accepted_success_nested_value_binding"]
    assert set(success) == {
        "rights_and_objects",
        "synthetic_capability",
        "resource_projection",
        "supervision",
        "cleanup",
        "failure_and_status",
    }
    assert NOTICES_SHA256 in success["rights_and_objects"]
    assert "molecules=3908" in success["synthetic_capability"]
    assert "model_double_fits_per_root=180" in success["synthetic_capability"]
    assert "scaled_gin_rows=7816" in success["synthetic_capability"]
    assert "all_20_percent_margins_passed=true" in success["resource_projection"]
    assert (
        "hard_ceiling_trigger and hard_ceiling_observed_value are null"
        in (success["supervision"])
    )
    assert "runtime_retained=true" in success["cleanup"]
    assert "failure.phase=null" in success["failure_and_status"]

    accounting = result["success_exact_accounting"]
    expected_counts = {
        "runtime_artifacts_fetched": 98,
        "runtime_bytes_fetched": 566_804_721,
        "checkpoint_model_objects_fetched": 3,
        "checkpoint_model_bytes_fetched": 22_374_079,
        "provenance_metadata_objects_fetched": 1,
        "provenance_metadata_bytes_fetched": 606,
        "http_redirects_followed": 2,
        "runtime_environments_created": 1,
        "checkpoint_objects_deserialized": 3,
        "parity_processes": 3,
        "graphs_built": 7_840,
        "gin_rows_built": 7_840,
        "synthetic_roots": 2,
        "model_double_fits": 360,
        "model_double_predictions": 281_376,
        "real_catboost_fits": 6,
        "real_catboost_validation_predictions": 4_692,
        "official_inputs_opened": 0,
        "official_target_values_opened": 0,
        "model_quality_metrics": 0,
        "claims_consumed": 1,
        "result_files_published": 1,
        "gpu_hours": 0,
    }
    assert all(accounting[key] == value for key, value in expected_counts.items())
    assert accounting["runtime_bytes_fetched"] == 539_395_366 + 27_409_290 + 65
    assert accounting["checkpoint_model_bytes_fetched"] == (
        7_452_448 + 7_454_321 + 7_467_310
    )
    assert accounting["graphs_built"] == 3 * 8 + 2 * 3_908
    assert accounting["gin_rows_built"] == 3 * 8 + 2 * 3_908
    assert accounting["model_double_predictions"] == 2 * 140_688
    assert accounting["real_catboost_validation_predictions"] == 6 * 782
    assert accounting["parity_fallback_predictions_by_branch"] == {
        "primary_exact": 0,
        "predeclared_numeric_fallback": 48,
    }
    assert "Any different count or byte total" in accounting["rule"]

    terminal = contract["terminal_classification"]
    expected_statuses = [
        terminal["failed"]["status"],
        terminal["ineligible"]["status"],
        terminal["resource_infeasible"]["status"],
        terminal["capability_success"]["status"],
    ]
    assert result["allowed_statuses"] == expected_statuses
    assert list(result["exact_next_gate_by_status"]) == [
        terminal["capability_success"]["status"],
        terminal["ineligible"]["status"],
        terminal["resource_infeasible"]["status"],
        terminal["failed"]["status"],
    ]
    assert set(result["exact_next_gate_by_status"]) == set(expected_statuses)
    assert "must equal the one exact string selected" in result["next_gate_rule"]
    rules = result["field_and_nullability_rules"]
    for required in (
        "no key is omitted",
        "claim_consumed=false",
        "claim_consumed=true",
        "retained_runtime_tree_sha256",
        "Every non-success requires runtime_retained=false",
        "No absolute/private path",
        "exception text",
        "prediction",
        "SMILES",
        "row identity",
        "unrestricted log",
    ):
        assert required in rules

    failure = result["failure_payload"]
    assert failure["phases"][0] is None
    assert failure["codes"][0] is None
    pairs = failure["allowed_phase_code_pairs"]
    assert set(pairs) == set(failure["phases"][1:])
    assert {code for codes in pairs.values() for code in codes} == set(
        failure["codes"][1:]
    )
    assert len(failure["non_publishable_internal_outcomes"]) == 6
    assert set(failure["non_publishable_internal_outcomes"]).isdisjoint(
        failure["codes"]
    )
    assert (
        "Never publish exception/repr/message/path/line/traceback" in (failure["rule"])
    )
    assert (
        "RESOURCE_MARGIN_MISSED maps only to resource-infeasible" in (failure["rule"])
    )
    assert "HARD_RESOURCE_CEILING_BREACHED" in failure["rule"]


def test_cleanup_rights_sealing_and_collision_semantics_fail_closed() -> None:
    contract = _load()
    package = contract["future_d149_implementation_package"]
    install = package["runtime_install_contract"]
    wheel_rights = install["wheel_rights_inspection"]
    for required in (
        "Across every member in the entire safety-validated wheel",
        "case-insensitively collect any basename beginning LICENSE",
        "Zero bundled notice members is accepted if and only if",
        "nonempty frozen canonical_license_ids/SPDX assignment",
        "nonempty exact metadata_evidence",
        "notice_obligation that requires retaining every notice file supplied",
        "zero members actually supplied",
        "not a waiver of any redistribution duty",
    ):
        assert required in wheel_rights
    manifest = _load(RUNTIME_MANIFEST)
    for package_record in manifest["packages"]:
        license_record = package_record["license"]
        assert license_record["canonical_license_ids"]
        assert license_record["spdx_expression"]
        assert license_record["metadata_evidence"]
        assert license_record["notice_obligation"].startswith("Retain every license")
    assert "PYTHON.json" in install["interpreter_rights_inspection"]
    assert (
        "fail on an unclassified/missing bundled component notice"
        in (install["interpreter_rights_inspection"])
    )
    binding = install["runtime_rights_inventory_binding"]
    for key in (
        "runtime_manifest_sha256",
        "wheel_notice_inventory_sha256",
        "wheel_notice_file_count",
        "wheel_notice_bytes",
        "interpreter_notice_inventory_sha256",
        "interpreter_notice_file_count",
        "interpreter_notice_bytes",
    ):
        assert key in binding
    retained = install["retained_runtime_tree_inventory"]
    assert retained["record_keys_in_order"] == [
        "path",
        "kind",
        "mode_octal",
        "uid",
        "gid",
        "size_bytes",
        "sha256",
        "symlink_target",
    ]
    assert "fchmods it to exactly 0555" in retained["read_only_seal"]
    assert "otherwise 0444" in retained["read_only_seal"]
    assert "rehash the sealed tree twice" in retained["read_only_seal"]
    assert "No entry may be created" in retained["read_only_seal"]
    assert "including the `.` root record" in retained["canonical_digest"]

    cleanup = contract["network_fetch_offline_sandbox_and_cleanup"]["cleanup"]
    assert set(cleanup) == {
        "child_handoff",
        "outer_authoritative_cleanup",
        "object_view_success_reduction",
        "non_success_object_view_deletion",
        "consumed_claim_retention",
        "success_retention",
        "retained_snap_layout_and_seal",
        "pre_completion_retention_revocation",
        "failure_retention",
        "absence_durability_rule",
        "cleanup_aggregate_inventory_digest",
        "preseal_verification",
        "staging_lifecycle",
    }
    assert (
        "outer authenticates any bounded aggregate child/crash payload"
        in (cleanup["outer_authoritative_cleanup"])
    )
    assert (
        "retain only the exact recursively sealed installed runtime_root"
        in (cleanup["outer_authoritative_cleanup"])
    )
    assert (
        "retain only the permanent claim_root tombstone"
        in (cleanup["outer_authoritative_cleanup"])
    )
    assert "DGL/MolFeat" in cleanup["object_view_success_reduction"]
    assert (
        "never be deleted, moved, overwritten, reset, or reused"
        in (cleanup["consumed_claim_retention"])
    )
    assert (
        "verified SNAP checkpoint in its exact sealed object-root layout"
        in (cleanup["success_retention"])
    )
    assert (
        "Retain no DGL checkpoint or MolFeat checkpoint"
        in (cleanup["success_retention"])
    )
    assert "file is single-link, nonsymlink" in cleanup["retained_snap_layout_and_seal"]
    assert "fchmods to 0444" in cleanup["retained_snap_layout_and_seal"]
    assert "0555" in cleanup["retained_snap_layout_and_seal"]
    assert (
        "only after common-seal promotion"
        in (cleanup["pre_completion_retention_revocation"])
    )
    assert (
        "never permitted after a valid completion receipt"
        in (cleanup["pre_completion_retention_revocation"])
    )
    assert (
        "fsync that root's already authenticated parent"
        in (cleanup["absence_durability_rule"])
    )
    for digest_key in (
        "claim_tombstone_retained",
        "attempt_root_absent",
        "wheel_cache_absent",
        "child_payload_staging_absent_before_seal",
        "runtime_retained",
        "snap_retained",
        "other_objects_absent",
        "retained_runtime_tree_sha256",
        "retained_runtime_tree_entry_count",
        "retained_runtime_tree_regular_bytes",
        "snap_sha256",
    ):
        assert digest_key in cleanup["cleanup_aggregate_inventory_digest"]

    result = contract["future_d150_result_contract"]
    seal = result["common_seal"]
    assert seal["shared_envelope"] == {
        "maximum_total_attempts": 2,
        "maximum_wall_seconds_total": 5.0,
        "maximum_cpu_seconds_total": 5.0,
        "maximum_staging_allocated_bytes": 2_097_152,
        "maximum_outer_rss_bytes": 268_435_456,
    }
    assert "0444" in seal["first_attempt"]
    assert "RENAME_NOREPLACE" in seal["first_attempt"]
    assert "no post-promotion result mutation" in seal["first_attempt"]
    assert (
        "only when the first proposed status was already non-success"
        in (seal["single_fallback"])
    )
    assert "never downgrades a proposed success" in seal["single_fallback"]
    assert "No fallback" in seal["no_fallback_cases"]
    assert "may never be staged, committed, integrated" in seal["no_fallback_cases"]
    assert "claim_consumed=false" in seal["preconsumption_failure"]
    assert "internal and nonpublishable" in seal["preconsumption_failure"]
    assert "retains/authenticates the tombstone" in seal["postconsumption_failure"]
    assert "four-case rule" in result["presence_and_collision"]
    assert "live untracked seal mode is 0444" in result["presence_and_collision"]
    assert "filesystem 0644 or retained 0444" in result["presence_and_collision"]
    assert (
        "only after the exact formal command exits zero"
        in (result["d150_operator_integration_gate"])
    )
    assert (
        "standalone schema test cannot override this gate"
        in (result["d150_operator_integration_gate"])
    )


def test_d148_accounting_is_transparent_public_only_and_zero_execution() -> None:
    contract = _load()
    accounting = contract["current_d148_accounting"]
    nonzero = {
        "contracts_created": 1,
        "third_party_notice_files_created": 1,
        "runtime_manifest_files_created": 1,
        "public_static_test_files_created": 1,
        "checkpoint_network_requests": 6,
        "checkpoint_head_requests": 6,
        "provenance_metadata_head_requests": 1,
        "provenance_metadata_get_requests": 1,
        "provenance_metadata_body_bytes": 606,
        "interpreter_artifact_head_requests": 2,
        "runtime_pypi_release_json_distinct_resources": 95,
        "runtime_spdx_license_json_distinct_resources": 9,
        "runtime_pytorch_cpu_simple_index_distinct_resources": 1,
        "runtime_interpreter_github_release_or_tag_metadata_resources_at_least": 1,
        "runtime_interpreter_checksum_sidecar_get_requests": 1,
        "runtime_interpreter_checksum_sidecar_body_bytes": 65,
        "runtime_build_project_license_get_requests": 1,
        "runtime_build_project_license_body_bytes": 1_495,
        "runtime_torch_wheel_head_requests_at_least": 2,
        "exact_small_provenance_checksum_license_body_bytes": 2_166,
        "public_source_requests_at_least": 15,
    }
    false_flags = {
        "runtime_interpreter_github_release_or_tag_metadata_exact_total_retained",
        "runtime_torch_wheel_head_request_exact_total_retained",
        "runtime_public_http_transaction_exact_total_retained",
        "runtime_public_metadata_response_bytes_exact_total_retained",
        "public_source_request_exact_total_retained",
        "public_source_response_bytes_exact_total_retained",
    }
    strings = {"scope", "exact_small_body_bytes_formula"}
    assert set(accounting) == set(nonzero) | false_flags | strings | {
        "runtime_environments_created",
        "interpreter_archives_downloaded_or_extracted",
        "runtime_wheels_downloaded_or_installed",
        "checkpoint_body_get_requests",
        "artifact_body_bytes_from_d148_head_checks",
        "runtime_torch_wheel_body_bytes",
        "checkpoint_files_fetched_or_retained",
        "checkpoint_bytes_fetched_or_read",
        "checkpoint_tensors_deserialized_or_executed",
        "implementation_files_created",
        "claims_created_or_consumed",
        "parity_processes_executed",
        "graphs_built",
        "gin_feature_rows_built",
        "synthetic_feature_rows_built",
        "official_inputs_opened",
        "official_structure_rows_opened",
        "official_target_values_opened",
        "baseline_prediction_rows_opened",
        "model_fits",
        "predictions",
        "development_metrics",
        "bootstrap_replicates",
        "selection_tokens",
        "contenders_locked",
        "confirmatory_truth_values_opened",
        "blinded_test_rows_opened",
        "tdi_rows_opened",
        "submission_rows_generated",
        "validator_calls",
        "leaderboard_observations_used_for_selection",
        "portal_credentials_opened",
        "live_uploads",
        "gpu_hours",
    }
    assert accounting["scope"].startswith("Incremental D148 activity only.")
    assert "fetched zero checkpoint/model" in accounting["scope"]
    assert (
        "Raw runtime-evidence HTTP transaction/retry/cache totals"
        in (accounting["scope"])
    )
    assert "were not instrumented and are not guessed" in accounting["scope"]
    assert "33 temporarily persisted public checkpoint files" in accounting["scope"]
    assert (
        "7,452,448-byte SNAP checkpoint opened only for hashing"
        in (accounting["scope"])
    )
    assert all(accounting[key] == value for key, value in nonzero.items())
    assert all(accounting[key] is False for key in false_flags)
    for key, value in accounting.items():
        if key in set(nonzero) | false_flags | strings:
            continue
        assert type(value) is int
        assert value == 0
    assert accounting["exact_small_provenance_checksum_license_body_bytes"] == (
        accounting["provenance_metadata_body_bytes"]
        + accounting["runtime_interpreter_checksum_sidecar_body_bytes"]
        + accounting["runtime_build_project_license_body_bytes"]
    )

    terminal = contract["terminal_classification"]
    assert terminal["precedence"] == [
        (
            "G3_G4_GIN300_FAILED for malformed lineage, claim, implementation, "
            "runtime, schema, topology, accounting, operational, publication, or "
            "cleanup integrity"
        ),
        (
            "G3_G4_GIN300_INELIGIBLE_PRETRAINED_PROVENANCE_OR_PARITY_FAILED "
            "for rights, notice, object, hash, tensor, graph, embedding, Linux "
            "parity, or nonredistribution failure after integrity is established"
        ),
        (
            "G3_G4_GIN300_RESOURCE_INFEASIBLE_PREFIT for a complete valid "
            "capability whose frozen 20-percent-margin resource gate misses"
        ),
        (
            "G3_3_EXP_G4_GIN300_CAPABILITY_ACCEPTED only when every prior gate "
            "and every resource maximum passes"
        ),
    ]
    assert (
        "Capability-only engineering evidence"
        in (terminal["capability_success"]["authority"])
    )
    assert (
        "does not authorize an official row now"
        in (terminal["capability_success"]["authority"])
    )
    assert terminal["reserved_later_status"] == {
        "status": "G3_G4_GIN300_RESOURCE_ABORTED",
        "rule": (
            "Reserved exclusively for a later hard claim-bound official "
            "label-free feature or official development resource breach. The "
            "D148-D150 capability sequence may not emit this status."
        ),
    }
    lower_next = contract["next_gate"].lower()
    for prohibited_now in (
        "artifact body",
        "checkpoint",
        "deserialization",
        "graph",
        "embedding",
        "synthetic root",
        "catboost fit",
        "prediction",
        "resource projection",
        "claim",
        "official row",
        "metric",
        "submission",
        "portal",
        "upload",
    ):
        assert prohibited_now in lower_next
