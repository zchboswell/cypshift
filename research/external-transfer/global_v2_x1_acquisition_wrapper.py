#!/usr/bin/env python3
"""Single-use acquisition and offline execution wrapper for EXP-X1.

The networked parent performs one exact HTTPS GET.  Archive verification,
listing, extraction, SQLite access, chemistry, topology, and support compilation
run in a fresh user/network namespace with no network interface.
"""

from __future__ import annotations

import argparse
import hashlib
import http.client
import os
import resource
import shutil
import subprocess
import sys
import tarfile
import time
from collections.abc import Mapping
from pathlib import Path, PurePosixPath
from typing import Any, Final, cast
from urllib.parse import urlsplit

SCRIPT: Final = Path(__file__).resolve()
ROOT: Final = SCRIPT.parents[2]
if str(SCRIPT.parent) not in sys.path:
    sys.path.insert(0, str(SCRIPT.parent))

import global_v2_x1_compiler as base  # noqa: E402
import global_v2_x1_real_source_adapter as adapter  # noqa: E402

ACCEPTANCE: Final = (
    ROOT
    / "benchmarks/openadmet_cyp_2026/global_v2_x1_real_source_adapter_acceptance.json"
)
ACCEPTANCE_SCHEMA: Final = (
    "cypshift.openadmet_cyp_2026.global_v2_x1_real_source_adapter_acceptance.v1"
)
DRIVER: Final = SCRIPT.with_name("run_global_v2_x1_official_shaped_synthetic.py")
FOCUSED_TESTS: Final = (
    ROOT / "tests/test_openadmet_global_v2_x1_real_source_adapter.py"
)
UNSHARE: Final = Path("/usr/bin/unshare")
ARCHIVE_MEMBER_BASENAME: Final = "chembl_37.db"
MAXIMUM_EXTRACTED_BYTES: Final = 80 * 1024**3
BUFFER_BYTES: Final = 4 * 1024**2
CONSUMED_STATUS: Final = "immutable_consumed_claim_adapter_accepted"


class X1AcquisitionError(adapter.X1AdapterError):
    """The one-shot acquisition, extraction, or resource boundary failed."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise X1AcquisitionError(message)


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    _require(isinstance(value, Mapping), f"{label} is not an object")
    return cast(Mapping[str, Any], value)


def _is_digest(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def derive_consumed_claim(
    *,
    tracked_claim_path: Path = adapter.CLAIM,
    acceptance_path: Path = ACCEPTANCE,
) -> dict[str, Any]:
    """Bind exact integrated adapter bytes before the claim can be consumed."""

    _require(
        base.sha256_path(tracked_claim_path) == adapter.CLAIM_SHA256,
        "tracked acquisition claim differs",
    )
    claim = base.read_json(tracked_claim_path)
    future = _mapping(claim.get("future_consumption_bindings"), "future bindings")
    _require(
        claim.get("status")
        == "immutable_unconsumed_claim_adapter_acceptance_required"
        and claim.get("consumed") is False
        and claim.get("maximum_consumptions") == 1
        and all(value is None for value in future.values()),
        "tracked acquisition claim state differs",
    )
    acceptance = base.read_json(acceptance_path)
    acceptance_sha = base.sha256_path(acceptance_path)
    bindings = _mapping(acceptance.get("source_bindings"), "acceptance source bindings")
    accounting = _mapping(acceptance.get("accounting"), "acceptance accounting")
    _require(
        acceptance.get("schema_version") == ACCEPTANCE_SCHEMA
        and acceptance.get("status") == adapter.SYNTHETIC_STATUS
        and acceptance.get("claim_template_sha256") == adapter.CLAIM_SHA256
        and bindings.get("accepted_compiler_sha256") == base.sha256_path(base.SCRIPT)
        and bindings.get("real_source_adapter_sha256") == base.sha256_path(adapter.SCRIPT)
        and bindings.get("acquisition_wrapper_sha256") == base.sha256_path(SCRIPT)
        and bindings.get("official_shaped_synthetic_driver_sha256")
        == base.sha256_path(DRIVER)
        and bindings.get("focused_tests_sha256") == base.sha256_path(FOCUSED_TESTS)
        and acceptance.get("roots") == 2
        and acceptance.get("physical_sqlite_hashes_differ") is True
        and acceptance.get("physical_r2b_hashes_differ") is True
        and acceptance.get("relative_terminal_maps_byte_identical") is True
        and acceptance.get("private_roots_retained") == 0
        and acceptance.get("mutable_roots_retained") == 0
        and acceptance.get("focused_tests_passed", 0) > 0
        and acceptance.get("adversarial_boundaries_passed") is True
        and _is_digest(acceptance.get("terminal_tree_sha256"))
        and accounting.get("target_values_parsed") == 0
        and accounting.get("official_model_fits") == 0
        and accounting.get("official_predictions_generated") == 0
        and accounting.get("live_uploads") == 0,
        "adapter synthetic acceptance differs",
    )
    implementation = {
        "real_source_adapter_sha256": base.sha256_path(adapter.SCRIPT),
        "acquisition_wrapper_sha256": base.sha256_path(SCRIPT),
        "official_shaped_synthetic_driver_sha256": base.sha256_path(DRIVER),
        "official_shaped_synthetic_acceptance_sha256": acceptance_sha,
        "adapter_acceptance_receipt_sha256": acceptance_sha,
    }
    consumed = dict(claim)
    consumed.update(
        {
            "status": CONSUMED_STATUS,
            "consumed": True,
            "future_consumption_bindings": implementation,
        }
    )
    return consumed


def publish_consumed_claim(attempt_root: Path, claim: Mapping[str, Any]) -> Path:
    path = attempt_root / "consumed_claim.json"
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o400)
    try:
        with os.fdopen(descriptor, "wb", closefd=True) as stream:
            stream.write(base.json_bytes(dict(claim)))
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    return path


def download_once(*, url: str, destination: Path, expected_sha256: str) -> int:
    """Issue exactly one non-redirecting, non-resumable HTTPS request."""

    parsed = urlsplit(url)
    _require(
        parsed.scheme == "https"
        and parsed.hostname is not None
        and parsed.username is None
        and parsed.password is None
        and parsed.fragment == "",
        "archive URL boundary differs",
    )
    _require(not destination.exists() and not destination.is_symlink(), "archive path exists")
    _require(destination.parent.is_dir(), "archive parent is absent")
    temporary = destination.with_name(f".{destination.name}.partial")
    _require(not temporary.exists() and not temporary.is_symlink(), "partial archive exists")
    request_path = parsed.path or "/"
    if parsed.query:
        request_path = f"{request_path}?{parsed.query}"
    connection = http.client.HTTPSConnection(parsed.hostname, parsed.port or 443, timeout=300)
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o400)
    digest = hashlib.sha256()
    size = 0
    try:
        connection.request(
            "GET",
            request_path,
            headers={
                "Accept": "application/octet-stream",
                "Accept-Encoding": "identity",
                "Connection": "close",
                "User-Agent": "cypshift-exp-x1-acquisition-v1",
            },
        )
        response = connection.getresponse()
        _require(response.status == 200, f"archive HTTP status differs: {response.status}")
        _require(
            response.getheader("Content-Encoding") in {None, "identity"},
            "archive content encoding differs",
        )
        with os.fdopen(descriptor, "wb", closefd=True) as stream:
            descriptor = -1
            while True:
                block = response.read(BUFFER_BYTES)
                if not block:
                    break
                stream.write(block)
                digest.update(block)
                size += len(block)
            stream.flush()
            os.fsync(stream.fileno())
        _require(size > 0 and digest.hexdigest() == expected_sha256, "archive SHA-256 differs")
        os.replace(temporary, destination)
        os.chmod(destination, 0o400)
        return size
    except BaseException:
        if descriptor >= 0:
            os.close(descriptor)
        temporary.unlink(missing_ok=True)
        raise
    finally:
        connection.close()


def secure_extract_database(
    *, archive_path: Path, extract_root: Path, expected_archive_sha256: str
) -> tuple[Path, dict[str, Any]]:
    """Verify the complete archive before safely extracting its sole SQLite DB."""

    base._regular_readonly(archive_path, "ChEMBL archive")
    _require(
        base.sha256_path(archive_path) == expected_archive_sha256,
        "archive checksum differs before listing",
    )
    _require(not extract_root.exists() and not extract_root.is_symlink(), "extract root exists")
    try:
        with tarfile.open(archive_path, mode="r:gz") as archive:
            names: set[str] = set()
            database_members: list[tarfile.TarInfo] = []
            total_size = 0
            member_count = 0
            for member in archive:
                member_count += 1
                path = PurePosixPath(member.name)
                _require(
                    member.name not in names
                    and not path.is_absolute()
                    and path.parts
                    and all(part not in {"", ".", ".."} for part in path.parts),
                    "unsafe or duplicate archive member",
                )
                names.add(member.name)
                _require(member.isdir() or member.isreg(), "non-regular archive member")
                _require(member.size >= 0, "negative archive member size")
                if member.isreg():
                    total_size += member.size
                    _require(
                        total_size <= MAXIMUM_EXTRACTED_BYTES,
                        "archive expanded-size ceiling exceeded",
                    )
                    if path.name == ARCHIVE_MEMBER_BASENAME:
                        database_members.append(member)
            _require(len(database_members) == 1, "archive database member cardinality differs")
            database_member = database_members[0]
            extract_root.mkdir(mode=0o700, parents=True)
            destination = extract_root / ARCHIVE_MEMBER_BASENAME
            descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o400)
            digest = hashlib.sha256()
            written = 0
            try:
                source = archive.extractfile(database_member)
                _require(source is not None, "cannot open archive database member")
                with source, os.fdopen(descriptor, "wb", closefd=True) as stream:
                    descriptor = -1
                    while True:
                        block = source.read(BUFFER_BYTES)
                        if not block:
                            break
                        stream.write(block)
                        digest.update(block)
                        written += len(block)
                    stream.flush()
                    os.fsync(stream.fileno())
            except BaseException:
                if descriptor >= 0:
                    os.close(descriptor)
                raise
            _require(written == database_member.size, "extracted database size differs")
            os.chmod(destination, 0o400)
            os.chmod(extract_root, 0o500)
    except BaseException:
        base.cleanup(extract_root)
        raise
    return destination, {
        "archive_sha256": expected_archive_sha256,
        "archive_member_count": member_count,
        "expanded_regular_bytes": total_size,
        "database_member": database_member.name,
        "database_bytes": written,
        "database_sha256": digest.hexdigest(),
    }


def _tree_bytes(root: Path) -> int:
    if not root.exists():
        return 0
    return sum(path.stat().st_size for path in root.rglob("*") if path.is_file())


def _offline_run(*, attempt_root: Path, challenge_root: Path) -> Path:
    claim_path = attempt_root / "consumed_claim.json"
    claim = base.read_json(claim_path)
    expected_claim = derive_consumed_claim()
    _require(claim == expected_claim, "consumed claim differs")
    adapter.validate_consumed_claim(claim)
    paths = _mapping(claim.get("paths"), "claim paths")
    source = _mapping(claim.get("source"), "claim source")
    archive_path = Path(cast(str, paths["archive_path"]))
    extract_root = Path(cast(str, paths["extract_root"]))
    private_root = Path(cast(str, paths["private_root"]))
    terminal_root = Path(cast(str, paths["terminal_root"]))
    _require(attempt_root == Path(cast(str, paths["attempt_root"])), "offline attempt root differs")
    database, archive_receipt = secure_extract_database(
        archive_path=archive_path,
        extract_root=extract_root,
        expected_archive_sha256=cast(str, source["archive_sha256"]),
    )
    compilation, projection = adapter.compile_source(
        database_path=database,
        challenge_root=challenge_root,
        private_root=private_root,
        synthetic=False,
        consumed_claim=claim,
    )
    peak_storage = _tree_bytes(attempt_root)
    claim_sha = base.sha256_path(claim_path)
    files = adapter.terminal_files(
        compilation,
        projection,
        synthetic=False,
        consumed_claim_sha256=claim_sha,
    )
    base.cleanup(private_root)
    base.publish_files(terminal_root, files)
    offline_receipt = {
        "schema_version": "cypshift.openadmet_cyp_2026.global_v2_x1_offline_receipt.v1",
        "consumed_claim_sha256": claim_sha,
        "archive": archive_receipt,
        "peak_restricted_storage_bytes": peak_storage,
        "process_concurrency": 1,
        "network_namespace": "fresh-empty",
    }
    receipt_path = attempt_root / "offline_receipt.json"
    receipt_path.write_bytes(base.json_bytes(offline_receipt))
    os.chmod(receipt_path, 0o400)
    return terminal_root


def _unshare_available() -> None:
    _require(UNSHARE.is_file() and os.access(UNSHARE, os.X_OK), "unshare is unavailable")
    probe = subprocess.run(
        [str(UNSHARE), "--user", "--map-root-user", "--net", "--", "/bin/true"],
        check=False,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    _require(probe.returncode == 0, "fresh user/network namespace is unavailable")


def run_official_attempt(
    *,
    tracked_claim_path: Path = adapter.CLAIM,
    acceptance_path: Path = ACCEPTANCE,
) -> Path:
    """Consume the exact claim once, download once, compile once, and clean."""

    consumed = derive_consumed_claim(
        tracked_claim_path=tracked_claim_path, acceptance_path=acceptance_path
    )
    _unshare_available()
    paths = _mapping(consumed.get("paths"), "claim paths")
    source = _mapping(consumed.get("source"), "claim source")
    challenge = _mapping(consumed.get("challenge_source"), "claim challenge source")
    resources = _mapping(consumed.get("resource_falsifier"), "resource falsifier")
    attempt_root = Path(cast(str, paths["attempt_root"]))
    archive_path = Path(cast(str, paths["archive_path"]))
    receipt_root = Path(cast(str, paths["receipt_root"]))
    challenge_root = Path(cast(str, challenge["root"]))
    repository = ROOT.resolve(strict=True)
    parent = attempt_root.parent.resolve(strict=True)
    _require(
        attempt_root == parent / attempt_root.name
        and repository not in attempt_root.parents
        and not attempt_root.exists()
        and not attempt_root.is_symlink()
        and not receipt_root.exists()
        and not receipt_root.is_symlink()
        and challenge_root.is_dir(),
        "fixed acquisition paths are unavailable",
    )
    required_free = int(float(resources["maximum_restricted_storage_gb"]) * 1024**3)
    _require(shutil.disk_usage(parent).free >= required_free, "storage reservation is unavailable")
    started = time.monotonic()
    usage_before = resource.getrusage(resource.RUSAGE_CHILDREN)
    attempt_root.mkdir(mode=0o700)
    (attempt_root / "source").mkdir(mode=0o700)
    claim_path = publish_consumed_claim(attempt_root, consumed)
    claim_sha = base.sha256_path(claim_path)
    final: dict[str, Any]
    try:
        archive_bytes = download_once(
            url=cast(str, source["archive_url"]),
            destination=archive_path,
            expected_sha256=cast(str, source["archive_sha256"]),
        )
        process = subprocess.run(
            [
                str(UNSHARE),
                "--user",
                "--map-root-user",
                "--net",
                "--",
                sys.executable,
                str(SCRIPT),
                "--offline-attempt-root",
                str(attempt_root),
                "--offline-challenge-root",
                str(challenge_root),
            ],
            check=False,
            stdin=subprocess.DEVNULL,
        )
        _require(process.returncode == 0, "offline acquisition compilation failed")
        offline = base.read_json(attempt_root / "offline_receipt.json")
        terminal = base.read_json(Path(cast(str, paths["terminal_root"])) / "manifest.json")
        usage_after = resource.getrusage(resource.RUSAGE_CHILDREN)
        cpu_seconds = (
            usage_after.ru_utime
            + usage_after.ru_stime
            - usage_before.ru_utime
            - usage_before.ru_stime
        )
        wall_seconds = time.monotonic() - started
        peak_rss_bytes = int(usage_after.ru_maxrss * 1024)
        peak_storage = int(offline["peak_restricted_storage_bytes"])
        resource_pass = (
            cpu_seconds / 3600 <= float(resources["cpu_core_hours"])
            and wall_seconds / 3600 <= float(resources["wall_hours"])
            and peak_storage <= required_free
            and peak_rss_bytes <= float(resources["maximum_peak_rss_gib"]) * 1024**3
        )
        support_pass = terminal.get("status") == adapter.OFFICIAL_ACCEPTED_STATUS
        status = (
            adapter.OFFICIAL_ACCEPTED_STATUS
            if resource_pass and support_pass
            else (
                "G2_5C_X1_RESOURCE_REJECTED"
                if not resource_pass
                else adapter.OFFICIAL_REJECTED_STATUS
            )
        )
        final = {
            "schema_version": "cypshift.openadmet_cyp_2026.global_v2_x1_acquisition_receipt.v1",
            "status": status,
            "consumed_claim_sha256": claim_sha,
            "archive_bytes": archive_bytes,
            "offline_receipt": offline,
            "terminal_manifest_sha256": base.sha256_path(
                Path(cast(str, paths["terminal_root"])) / "manifest.json"
            ),
            "support_counts": terminal["counts"],
            "support_decision": terminal["status"],
            "resources": {
                "wall_seconds": wall_seconds,
                "cpu_core_hours": cpu_seconds / 3600,
                "peak_rss_bytes": peak_rss_bytes,
                "peak_restricted_storage_bytes": peak_storage,
                "process_concurrency": 1,
                "gpu_hours": 0,
                "pass": resource_pass,
            },
            "accounting": terminal["accounting"],
            "cleanup_complete": True,
        }
    except BaseException as exc:
        final = {
            "schema_version": "cypshift.openadmet_cyp_2026.global_v2_x1_acquisition_receipt.v1",
            "status": "G2_5C_X1_ACQUISITION_FAILED",
            "consumed_claim_sha256": claim_sha,
            "failure_category": type(exc).__name__,
            "cleanup_complete": True,
        }
    base.cleanup(attempt_root)
    _require(not attempt_root.exists(), "restricted attempt cleanup failed")
    base.publish_files(receipt_root, {"receipt.json": base.json_bytes(final)})
    return receipt_root / "receipt.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline-attempt-root", type=Path)
    parser.add_argument("--offline-challenge-root", type=Path)
    parser.add_argument("--run-official", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.offline_attempt_root is not None or args.offline_challenge_root is not None:
        _require(
            args.offline_attempt_root is not None
            and args.offline_challenge_root is not None
            and not args.run_official,
            "offline argument set differs",
        )
        terminal = _offline_run(
            attempt_root=args.offline_attempt_root.resolve(),
            challenge_root=args.offline_challenge_root.resolve(),
        )
        print(terminal)
        return 0
    _require(args.run_official, "explicit --run-official is required")
    print(run_official_attempt())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "ACCEPTANCE",
    "ACCEPTANCE_SCHEMA",
    "CONSUMED_STATUS",
    "DRIVER",
    "FOCUSED_TESTS",
    "SCRIPT",
    "X1AcquisitionError",
    "derive_consumed_claim",
    "download_once",
    "publish_consumed_claim",
    "run_official_attempt",
    "secure_extract_database",
]
