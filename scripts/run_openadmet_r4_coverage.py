#!/usr/bin/env python3
"""Run the single receipt-bound official R4 transformation coverage gate."""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from rdkit import rdBase

from cypshift.openadmet_transformation_compiler import (
    compile_transformation_geometry,
)
from cypshift.openadmet_transformation_coverage import (
    load_transformation_projection,
)
from cypshift.openadmet_transformation_io import (
    canonical_json_bytes,
    strict_json_object,
)
from cypshift.openadmet_transformation_projection import (
    _cleanup_stage,
    project_openadmet_transformation_inputs,
)
from cypshift.openadmet_transformation_publication import (
    TERMINAL_CODES,
    TransformationPublicationResult,
    publish_transformation_coverage,
    publish_transformation_failure,
)
from cypshift.openadmet_transformation_serialization import (
    serialize_transformation_results,
)
from cypshift.openadmet_transformation_support import (
    compile_transformation_support,
)
from cypshift.openadmet_transformation_types import TransformationIntegrityError

REPOSITORY_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
EXPECTED_R2B_MANIFEST: Final[str] = (
    "08dcf61cded99fae046bff49b57b0c4a12082cd8714c779ac44a351bf1a0c8c8"
)
EXPECTED_R3A_MANIFEST: Final[str] = (
    "a472b6abf35a1bc3944e2a5baddafbf83ba4c3bb5f269c0993032f300eeb405b"
)
EXPECTED_TOPOLOGY: Final[str] = (
    "6c4e66ecec4791ac5ddcdbb7bde44bd98e05456dbf27b80688550e6675b2aabf"
)
EXPECTED_SOURCE_RECEIPTS: Final[dict[str, dict[str, Any]]] = {
    "direct_observations.csv": {
        "sha256": "00b1ac95cc73dda2699f2f05bc33200d1119a197d7a92ae900cde78d722f00b7",
        "rows": 19620,
    },
    "group_folds.csv": {
        "sha256": "91678d68b2f9ac3913f6b679dd284f82ba2a040d803de83655bf89906f31f774",
        "rows": 73575,
    },
    "public_episodes.csv": {
        "sha256": "471804773631623235a7d554a1d8e297c5b098089f96390c85f622a82b619a7a",
        "rows": 1122,
    },
    "masks.csv": {
        "sha256": "0b437aa5c43286833f4b2ccbf97c36afbfa6e940dcf20d1e2a2728a324fe3240",
        "rows": 1122,
    },
    "structure.csv": {
        "sha256": "3d54edc618eeca8414afc1a0180fec2f58299aa581cb7f427ac96d923ee37c36",
        "rows": 4905,
    },
}
EXPECTED_COUNTS: Final[dict[str, int]] = {
    "direct_observations": 19620,
    "group_folds": 73575,
    "public_episodes": 1122,
    "masks": 1122,
    "structure": 4905,
}
EXPECTED_REPOSITORY_RECEIPTS: Final[dict[str, str]] = {
    "uv.lock": "33d9382256de7992ce9ff7a7edc125d4771546a25ef3be5f1160627846d2c9b6",
    "src/cypshift/chemistry.py": "21d8df35f001c790290d3ef2c836c9f459015b5db0f48c8f6e44436f9181103a",
    "src/cypshift/schema.py": "42a65b149e103ea28ff7db3c54d3fbd5944d0b9866f8425d28a5c979a44b4c8e",
    "src/cypshift/openadmet_validation.py": "75ded69bcd6d109879adef842e3f6905362990b26711529033bd615ef7355def",
    "src/cypshift/openadmet_validation_contract.py": "b92ea93ba924b337260226b851654cfcf6edd2164c5e68933b461c048b9491e5",
    "src/cypshift/openadmet_transformation_io.py": "820a83b3563bc4f8dbb7de2b13ad0c8fdf9032db8d9bbcb75a6962ffc53a3ee9",
    "src/cypshift/openadmet_transformation_projection.py": "0e094712f4f7e10f878ea3ac6a1907f2ad42a25db3c70fbefec70b3ab2aca73a",
    "src/cypshift/openadmet_transformation_coverage.py": "d60af6a251aa0f69cdee3f3f70a47b2107ec4f6d6c7d189ca641c3873f107472",
    "src/cypshift/openadmet_transformation_types.py": "d9fc616f25a4c6b6cc8b2bbd538920218ae51b116fd32c2f0c01ff395657b64b",
    "src/cypshift/openadmet_transformation_mmp.py": "43fe5ff18ecf2f355f1dead9e8a8393cba2e384ee44ef3293f14773c2e956c43",
    "src/cypshift/openadmet_transformation_stereo.py": "838d66f48bcdd75ccfb1fa5cd8de1654bdf7632e82f62f1252554f7483736ff1",
    "src/cypshift/openadmet_transformations.py": "2ac5ea0004402df82bbb26024089a1b0b2fe258346a71c7b89bd1512672eaaed",
    "src/cypshift/openadmet_transformation_compiler.py": "559d4b88dd5657f166e05d3ba341fa0f5fb8021ba19fdbee62ec5469bdfda5c8",
    "src/cypshift/openadmet_transformation_support.py": "9d08b5c0e23d41958a2d1924a6b17b7ef1bb54dbd4ed74946d317e94c57f03ec",
    "src/cypshift/openadmet_transformation_serialization.py": "460678f949267d8f711a833008f287750a8b63b89e729afdbc8913ce70b21e28",
    "src/cypshift/openadmet_transformation_publication.py": "7f52bfbc06aa5f721d2d5493c03db3b3982e07946bc4817a412345644d9de3fa",
    "benchmarks/openadmet_cyp_2026/transformation_coverage_contract_v5.json": "63d12cb376760c65eabd3d94d3f3939b0591e4019e1332075df0a4c10a4b4954",
    "benchmarks/openadmet_cyp_2026/transformation_coverage_contract_v6.json": "a0743c43cdafbcfd736cf94c57fe21488266d1f6df6ef73311c26ccda795f95d",
    "benchmarks/openadmet_cyp_2026/validation_contract.json": "ada8beff0b6f42baeb61c91df1cbb75ef832ce2b1b87b0d0bcbf253c94326ab3",
    "benchmarks/openadmet_cyp_2026/global_experiment_contract.json": "d728684cc3794bbe01ea44342202944a378968f097cb8f5490852b63721a6285",
    "benchmarks/openadmet_cyp_2026/global_experiment_contract_v4.json": "a37a316ceab297deb89d4458169d38d1c73d2edb39ab96ea4c77459a56b01254",
    "benchmarks/openadmet_cyp_2026/global_experiment_contract_v5.json": "596d9a246b130c00f07abfcaf73b369038b874ce556be5e6354df10e1d5ad6e2",
}


class R4RunnerError(RuntimeError):
    """The official run refused or failed closed."""


@dataclass(frozen=True, slots=True)
class OfficialPaths:
    """Exact official leaf paths after manifest authentication."""

    direct: Path
    folds: Path
    public: Path
    masks: Path
    topology: Path
    structure: Path


def run_official_r4(
    *,
    r2b_root: Path,
    r3a_root: Path,
    terminal_output: Path,
    expected_runner_sha256: str,
) -> TransformationPublicationResult:
    """Execute the one deterministic official R4 coverage path."""

    runtime = _pre_input_gate(terminal_output, expected_runner_sha256)
    private_root: Path | None = None
    stage = "authentication"
    try:
        paths = _authenticate_official_inputs(r2b_root, r3a_root)
        private_root = Path(
            tempfile.mkdtemp(prefix=".r4-official-", dir=terminal_output.parent)
        )
        projection = private_root / "projection"
        stage = "projection"
        project_openadmet_transformation_inputs(
            direct_observations_path=paths.direct,
            group_folds_path=paths.folds,
            public_episodes_path=paths.public,
            masks_path=paths.masks,
            structure_path=paths.structure,
            output_directory=projection,
            expected_receipts=EXPECTED_SOURCE_RECEIPTS,
            expected_counts=EXPECTED_COUNTS,
        )
        stage = "consumption"
        bundle = load_transformation_projection(projection)
        _validate_cardinalities(bundle)
        stage = "geometry"
        geometry = compile_transformation_geometry(bundle)
        if len(geometry.episodes) != 1818:
            raise R4RunnerError("geometry episode count differs")
        stage = "support"
        support = compile_transformation_support(bundle, geometry)
        stage = "serialization"
        serialization = serialize_transformation_results(geometry, support)
        if serialization.episode_transformations_csv.count(b"\n") - 1 != 1818:
            raise R4RunnerError("serialized episode count differs")
        stage = "post_gate"
        _post_input_gate(expected_runner_sha256, runtime["code_commit"])
        stage = "cleanup"
        _remove_private(private_root)
        private_root = None
        stage = "publication"
        return publish_transformation_coverage(
            destination=terminal_output,
            bundle=bundle,
            geometry=geometry,
            support=support,
            runtime=runtime,
        )
    except Exception as exc:
        codes = _failure_codes(stage, exc)
        if private_root is not None:
            try:
                _remove_private(private_root)
            except Exception as cleanup_exc:
                raise R4RunnerError(
                    "private cleanup failed; refusing terminal publication"
                ) from cleanup_exc
        try:
            _post_input_gate(expected_runner_sha256, runtime["code_commit"])
        except Exception:
            codes.add("P1")
        return publish_transformation_failure(
            destination=terminal_output,
            terminal_codes=sorted(codes),
            runtime=runtime,
        )


def _pre_input_gate(
    terminal_output: Path, expected_runner_sha256: str
) -> dict[str, Any]:
    _destination_preflight(terminal_output)
    _runtime_preflight()
    _renameat2_preflight()
    head = _git_head_clean()
    _verify_repository_receipts()
    if not _sha256(expected_runner_sha256):
        raise R4RunnerError("invalid expected runner receipt")
    if _file_sha256(Path(__file__)) != expected_runner_sha256:
        raise R4RunnerError("runner receipt differs")
    return {
        "python_version": "3.12.3",
        "rdkit_version": "2026.03.5",
        "platform": "Linux x86_64 CPU",
        "device": "CPU",
        "seed": 0,
        "code_commit": head,
    }


def _post_input_gate(expected_runner_sha256: str, expected_head: Any) -> None:
    if not isinstance(expected_head, str) or _git_head_clean() != expected_head:
        raise R4RunnerError("checkout changed during run")
    _verify_repository_receipts()
    if _file_sha256(Path(__file__)) != expected_runner_sha256:
        raise R4RunnerError("runner changed during run")


def _destination_preflight(destination: Path) -> None:
    if ".." in destination.parts or destination.exists() or destination.is_symlink():
        raise R4RunnerError("terminal destination is not fresh")
    parent = destination.parent
    if not parent.is_dir() or parent.is_symlink():
        raise R4RunnerError("terminal parent must be an existing real directory")
    for value in (parent, *parent.parents):
        if value.is_symlink():
            raise R4RunnerError("terminal parent contains a symlink")
    resolved = destination.resolve(strict=False)
    repository = REPOSITORY_ROOT.resolve()
    if resolved == repository or repository in resolved.parents:
        raise R4RunnerError("terminal destination must be outside Git")


def _runtime_preflight() -> None:
    version = (
        f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    )
    if (
        version != "3.12.3"
        or rdBase.rdkitVersion != "2026.03.5"
        or platform.system() != "Linux"
        or platform.machine() != "x86_64"
        or os.name != "posix"
    ):
        raise R4RunnerError("runtime differs")


def _renameat2_preflight() -> None:
    try:
        renameat2 = ctypes.CDLL(None, use_errno=True).renameat2
    except (AttributeError, OSError) as exc:
        raise R4RunnerError("renameat2 unavailable") from exc
    if renameat2 is None:
        raise R4RunnerError("renameat2 unavailable")


def _git_head_clean() -> str:
    head = _git("rev-parse", "HEAD").strip()
    if re.fullmatch(r"[0-9a-f]{40}", head) is None:
        raise R4RunnerError("git head differs")
    if _git("status", "--porcelain", "--untracked-files=all"):
        raise R4RunnerError("checkout is dirty")
    return head


def _git(*args: str) -> str:
    try:
        result = subprocess.run(
            ("git", *args),
            cwd=REPOSITORY_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise R4RunnerError("git preflight failed") from exc
    return result.stdout.strip()


def _verify_repository_receipts() -> None:
    for relative, expected in EXPECTED_REPOSITORY_RECEIPTS.items():
        if _file_sha256(REPOSITORY_ROOT / relative) != expected:
            raise R4RunnerError(f"repository receipt differs: {relative}")


def _authenticate_official_inputs(r2b_root: Path, r3a_root: Path) -> OfficialPaths:
    _trusted_root(r2b_root, "R2B")
    _trusted_root(r3a_root, "R3A")
    r2b_manifest = _fixed_json(
        r2b_root / "manifest.json", EXPECTED_R2B_MANIFEST, "R2B manifest"
    )
    r3a_manifest = _fixed_json(
        r3a_root / "feature_input_manifest.json",
        EXPECTED_R3A_MANIFEST,
        "R3A manifest",
    )
    if r2b_manifest.get("schema_version") != (
        "cypshift.openadmet_cyp_2026.validation_artifacts.v1"
    ):
        raise R4RunnerError("R2B manifest schema differs")
    if r3a_manifest.get("schema_version") != (
        "cypshift.openadmet_cyp_2026.feature_input.v1"
    ):
        raise R4RunnerError("R3A manifest schema differs")
    paths = OfficialPaths(
        r2b_root / "direct_observations.csv",
        r2b_root / "group_folds.csv",
        r2b_root / "campaign_episodes_public.csv",
        r2b_root / "episode_label_masks.csv",
        r2b_root / "topology_viability.json",
        r3a_root / "feature_input.csv",
    )
    if _file_sha256(paths.topology) != EXPECTED_TOPOLOGY:
        raise R4RunnerError("topology receipt differs")
    return paths


def _trusted_root(root: Path, label: str) -> None:
    if ".." in root.parts or not root.is_dir() or root.is_symlink():
        raise R4RunnerError(f"{label} root is not trusted")
    for value in (root, *root.parents):
        if value.is_symlink():
            raise R4RunnerError(f"{label} root contains a symlink")
    resolved = root.resolve()
    repository = REPOSITORY_ROOT.resolve()
    if resolved == repository or repository in resolved.parents:
        raise R4RunnerError(f"{label} root must be outside Git")


def _fixed_json(path: Path, expected: str, label: str) -> dict[str, Any]:
    data = _read_regular(path, label)
    if hashlib.sha256(data).hexdigest() != expected:
        raise R4RunnerError(f"{label} receipt differs")
    value = strict_json_object(data, label)
    if canonical_json_bytes(value) != data:
        raise R4RunnerError(f"{label} is not canonical")
    return value


def _read_regular(path: Path, label: str) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise R4RunnerError(f"{label} is not a regular file")
    return path.read_bytes()


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(_read_regular(path, str(path))).hexdigest()


def _validate_cardinalities(bundle: Any) -> None:
    expected = (4905, 19620, 73575, 1818, 6, 5)
    observed = (
        len(bundle.molecules),
        len(bundle.direct_availability),
        len(bundle.folds),
        len(bundle.episodes),
        len(bundle.input_receipts),
        len(bundle.source_receipts),
    )
    if observed != expected:
        raise R4RunnerError("official projection cardinality differs")


def _remove_private(root: Path) -> None:
    if root.is_symlink() or not root.is_dir():
        raise R4RunnerError("private root differs")
    projection = root / "projection"
    if projection.is_symlink():
        raise R4RunnerError("private projection is a symlink")
    if projection.exists():
        if not projection.is_dir():
            raise R4RunnerError("private projection differs")
        _cleanup_stage(projection)
    shutil.rmtree(root)
    if root.exists() or root.is_symlink():
        raise R4RunnerError("private cleanup incomplete")


def _failure_codes(stage: str, exc: Exception) -> set[str]:
    if isinstance(exc, TransformationIntegrityError):
        codes = {code for code in exc.codes if code in TERMINAL_CODES}
        return codes or {"V4"}
    return {
        "authentication": {"P6"},
        "projection": {"P6"},
        "consumption": {"P6"},
        "geometry": {"V4"},
        "support": {"V4"},
        "serialization": {"P6"},
        "post_gate": {"P1"},
        "cleanup": {"P5"},
        "publication": {"P2"},
    }.get(stage, {"P1"})


def _sha256(value: str) -> bool:
    return re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--r2b-root", type=Path, required=True)
    parser.add_argument("--r3a-root", type=Path, required=True)
    parser.add_argument("--terminal-output", type=Path, required=True)
    parser.add_argument("--expected-runner-sha256", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    result = run_official_r4(
        r2b_root=args.r2b_root,
        r3a_root=args.r3a_root,
        terminal_output=args.terminal_output,
        expected_runner_sha256=args.expected_runner_sha256,
    )
    print(f"{result.status} {result.output_directory}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
