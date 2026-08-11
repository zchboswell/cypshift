"""Deterministic static report for a completed reference run."""

from __future__ import annotations

import html
import json
from collections.abc import Mapping, Sequence
from hashlib import sha256
from pathlib import Path
from typing import Any

from cypshift.audit import AUDIT_SCHEMA_VERSION
from cypshift.baseline import MODEL_SCHEMA_VERSION, RUN_MANIFEST_SCHEMA_VERSION

REPORT_SCHEMA_VERSION = "cypshift.report.v1"


class ReportError(ValueError):
    """Raised when a run cannot be safely rendered as a report."""


def generate_report(run_directory: Path, output_directory: Path) -> Path:
    """Validate a completed run and write a new static HTML report."""

    output_path = output_directory / "report.html"
    if output_path.exists():
        raise ReportError(f"refusing to overwrite existing artifact: {output_path}")

    audit = _read_json(run_directory / "audit.json")
    model = _read_json(run_directory / "model.json")
    manifest = _read_json(run_directory / "run_manifest.json")
    if audit.get("schema_version") != AUDIT_SCHEMA_VERSION:
        raise ReportError("unsupported audit schema")
    if model.get("schema_version") != MODEL_SCHEMA_VERSION:
        raise ReportError("unsupported model schema")
    if manifest.get("schema_version") != RUN_MANIFEST_SCHEMA_VERSION:
        raise ReportError("unsupported run manifest schema")
    _validate_artifact_hashes(run_directory, manifest)

    content = render_report(audit, model, manifest).encode("utf-8")
    output_directory.mkdir(parents=True, exist_ok=True)
    try:
        with output_path.open("xb") as handle:
            handle.write(content)
    except OSError as exc:
        raise ReportError(f"cannot write {output_path}: {exc}") from exc
    return output_path


def render_report(
    audit: Mapping[str, Any],
    model: Mapping[str, Any],
    manifest: Mapping[str, Any],
) -> str:
    """Render validated reference records into deterministic standalone HTML."""

    audit_summary = _mapping(audit, "summary")
    model_summary = _mapping(model, "fit_summary")
    configuration = _mapping(manifest, "resolved_configuration")
    run_summary = _mapping(manifest, "summary")
    software = _mapping(manifest, "software")

    facts = [
        ("Report schema", REPORT_SCHEMA_VERSION),
        ("Model", model.get("method")),
        ("Split scope", configuration.get("split_scope")),
        ("Seed", configuration.get("seed")),
        ("Validation fraction", configuration.get("validation_fraction")),
        ("Accepted molecules", audit_summary.get("molecules_accepted")),
        ("Quarantined molecules", audit_summary.get("molecules_quarantined")),
        ("Observed contexts", model_summary.get("contexts_observed")),
        ("Supported model contexts", model_summary.get("contexts_supported")),
        (
            "Unsupported model contexts",
            model_summary.get("contexts_unsupported"),
        ),
        ("Training measurements used", model_summary.get("measurements_used")),
        ("Predictions", run_summary.get("predictions")),
        ("LLM adjudication used", configuration.get("llm_adjudication_used")),
    ]
    software_rows = [(name, version) for name, version in sorted(software.items())]

    warning_counts = _mapping(audit_summary, "warning_counts")
    warning_rows = [
        (warning, count) for warning, count in sorted(warning_counts.items())
    ]
    issue_rows = []
    for issue in _sequence(audit, "issues"):
        issue_record = _as_mapping(issue, "audit issue")
        warnings = issue_record.get("warnings")
        warning_text = ", ".join(str(value) for value in warnings or [])
        issue_rows.append(
            (
                issue_record.get("molecule_id"),
                issue_record.get("status"),
                warning_text,
            )
        )

    assay_rows = []
    for context in _sequence(audit, "assay_context_counts"):
        record = _as_mapping(context, "assay context")
        assay_rows.append(
            tuple(
                record.get(field)
                for field in (
                    "endpoint",
                    "isoform",
                    "nadph_condition",
                    "probe",
                    "readout",
                    "count",
                )
            )
        )

    unsupported_rows = []
    for context in _sequence(model, "unsupported_contexts"):
        record = _as_mapping(context, "unsupported context")
        unsupported_rows.append(
            tuple(
                record.get(field)
                for field in (
                    "endpoint",
                    "isoform",
                    "nadph_condition",
                    "probe",
                    "readout",
                    "unit",
                    "reason",
                    "observed_measurement_count",
                    "training_measurement_count",
                )
            )
        )

    hash_rows = []
    for kind in ("input_hashes", "output_hashes"):
        for name, digest in sorted(_mapping(manifest, kind).items()):
            hash_rows.append((kind.removesuffix("_hashes"), name, digest))

    body = "\n".join(
        [
            "<!doctype html>",
            '<html lang="en">',
            "<head>",
            '<meta charset="utf-8">',
            '<meta name="viewport" content="width=device-width, initial-scale=1">',
            "<title>cypshift reference run report</title>",
            f"<style>{_STYLE}</style>",
            "</head>",
            "<body>",
            "<main>",
            '<p class="eyebrow">cypshift / auditable reference</p>',
            "<h1>CYP prediction run report</h1>",
            (
                '<p class="lede">This report verifies a deterministic reference '
                "run and its provenance. The endpoint-context median is a baseline, "
                "not evidence of biological performance; use it only with validated "
                "data, endpoints, and evaluation.</p>"
            ),
            _section("Run summary", _table(("Field", "Value"), facts)),
            _section(
                "Chemistry audit",
                _table(("Warning", "Count"), warning_rows)
                + _table(("Molecule", "Status", "Warnings"), issue_rows),
            ),
            _section(
                "Assay contexts",
                _table(
                    (
                        "Endpoint",
                        "Isoform",
                        "NADPH",
                        "Probe",
                        "Readout",
                        "Count",
                    ),
                    assay_rows,
                ),
            ),
            _section(
                "Unsupported model contexts",
                '<p class="note">Observed contexts without an uncensored numeric '
                "training value are recorded here and omitted from predictions.</p>"
                + _table(
                    (
                        "Endpoint",
                        "Isoform",
                        "NADPH",
                        "Probe",
                        "Readout",
                        "Unit",
                        "Reason",
                        "Observed",
                        "Training",
                    ),
                    unsupported_rows,
                ),
            ),
            _section("Software", _table(("Component", "Version"), software_rows)),
            _section(
                "Artifact integrity",
                '<p class="note">All listed artifacts were hash-verified before '
                "this report was rendered.</p>"
                + _table(("Role", "Artifact", "SHA-256"), hash_rows),
            ),
            _section(
                "Limitations",
                "<ul>"
                "<li>The fixture split is a deterministic pipeline test only.</li>"
                "<li>The endpoint-context median is not a competitive model.</li>"
                "<li>Censored values are preserved but excluded from this fit.</li>"
                "<li>Unsupported assay contexts are omitted and listed explicitly.</li>"
                "<li>The provisional standardization policy requires launch-day review.</li>"
                "<li>No uncertainty, calibration, TDI classifier, or LLM is used.</li>"
                "</ul>",
            ),
            "</main>",
            "</body>",
            "</html>",
            "",
        ]
    )
    return body


def _validate_artifact_hashes(
    run_directory: Path, manifest: Mapping[str, Any]
) -> None:
    for section in ("input_hashes", "output_hashes"):
        for name, expected in _mapping(manifest, section).items():
            if not isinstance(name, str) or not isinstance(expected, str):
                raise ReportError(f"invalid {section} entry")
            if Path(name).name != name:
                raise ReportError(f"artifact name must be a basename: {name!r}")
            path = run_directory / name
            actual = _file_hash(path)
            if actual != expected:
                raise ReportError(f"artifact hash mismatch: {name}")


def _read_json(path: Path) -> dict[str, Any]:
    try:
        with path.open(encoding="utf-8") as handle:
            value = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise ReportError(f"cannot read {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ReportError(f"{path.name} must contain a JSON object")
    return value


def _file_hash(path: Path) -> str:
    digest = sha256()
    try:
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
    except OSError as exc:
        raise ReportError(f"cannot hash {path}: {exc}") from exc
    return digest.hexdigest()


def _mapping(value: Mapping[str, Any], field: str) -> Mapping[str, Any]:
    return _as_mapping(value.get(field), field)


def _as_mapping(value: Any, description: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise ReportError(f"{description} must be an object")
    return value


def _sequence(value: Mapping[str, Any], field: str) -> Sequence[Any]:
    candidate = value.get(field)
    if not isinstance(candidate, list):
        raise ReportError(f"{field} must be an array")
    return candidate


def _section(title: str, content: str) -> str:
    return f"<section><h2>{html.escape(title)}</h2>{content}</section>"


def _table(headers: Sequence[str], rows: Sequence[Sequence[Any]]) -> str:
    header = "".join(f"<th>{html.escape(value)}</th>" for value in headers)
    body = "".join(
        "<tr>"
        + "".join(f"<td>{html.escape(_display(value))}</td>" for value in row)
        + "</tr>"
        for row in rows
    )
    if not rows:
        body = f'<tr><td colspan="{len(headers)}">None</td></tr>'
    return (
        '<div class="table-wrap"><table><thead><tr>'
        + header
        + "</tr></thead><tbody>"
        + body
        + "</tbody></table></div>"
    )


def _display(value: Any) -> str:
    if value is True:
        return "yes"
    if value is False:
        return "no"
    if value is None:
        return "not recorded"
    return str(value)


_STYLE = """
:root { color-scheme: light; font-family: Inter, ui-sans-serif, system-ui, sans-serif; }
body { margin: 0; background: #f4f5f2; color: #20251f; }
main { max-width: 960px; margin: 0 auto; padding: 56px 24px 80px; }
.eyebrow { color: #49634d; font-size: 0.78rem; font-weight: 700; letter-spacing: .12em; text-transform: uppercase; }
h1 { font-size: clamp(2rem, 6vw, 4rem); letter-spacing: -.045em; line-height: 1; margin: 10px 0 18px; }
h2 { font-size: 1.25rem; margin: 0 0 14px; }
.lede { color: #4e574d; font-size: 1.08rem; line-height: 1.65; max-width: 760px; }
section { background: #fff; border: 1px solid #dfe3dc; border-radius: 12px; margin-top: 24px; padding: 24px; }
.table-wrap { overflow-x: auto; margin-top: 12px; }
table { border-collapse: collapse; font-size: .9rem; width: 100%; }
th, td { border-bottom: 1px solid #e7e9e4; padding: 10px 12px; text-align: left; vertical-align: top; }
th { color: #49634d; font-size: .74rem; letter-spacing: .06em; text-transform: uppercase; }
td:last-child { overflow-wrap: anywhere; }
.note, li { color: #596057; line-height: 1.55; }
ul { margin: 0; padding-left: 20px; }
""".strip()
