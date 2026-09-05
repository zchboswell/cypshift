"""Gated first TDI release; no test reads until full-development models exist.

Run under an independent 900-second process-group deadline. A hash-pinned,
independent two-seed audit is mandatory; this driver never audits itself.
"""

from __future__ import annotations

import argparse
import csv
import fcntl
import io
import json
import pickle
import signal
import subprocess
import warnings
from pathlib import Path
from typing import Any

import competition_tdi_runner as runner
import numpy as np
from competition_data import balanced_group_folds
from competition_features import featurize_binary_morgan
from competition_tdi_data import load_tdi_development
from competition_tdi_metrics import ENDPOINTS
from sklearn.exceptions import ConvergenceWarning

ROOT = Path(__file__).resolve().parents[2]
TEST_SHA256 = "a342f8444a8dcb531ca12f3685293f0bd6c36ae9073f491e44a9bc1cc4b741f9"
AUDIT_SCRIPT_SHA256 = "f344bc6ab97d544607b2a8982769f36d588519640aa9e6721631bcb42f2bd6a3"
AUDIT_PLAN_SHA256 = "d2afa3fee8beda18f0024b650e5e85b41ce3c1334938cc7c8c809c98d543b786"
PRODUCTION = {
    "schema": "cypshift.phase3.tdi_production_recipe.v1",
    "selection_seed": 20260905,
    "selection_folds": 3,
    "cpu_core_hours": 2.0,
    "occupied_wall_seconds": 900,
    "maximum_fits": {"logistic": 8, "selected": 14},
    "test_sha256": TEST_SHA256,
    "test_rows": 750,
    "reserved_numeric_targets_opened": 0,
}


def authenticated_json(path: Path, expected: str) -> dict[str, Any]:
    raw = path.read_bytes()
    if runner.digest(raw) != expected:
        raise ValueError("JSON receipt differs")
    return json.loads(raw)


def authorize(
    audit_path: Path,
    audit_sha256: str,
    data: Any,
    recipe: dict[str, Any],
) -> tuple[str, dict[str, Any]]:
    """Trust only the explicitly pinned independent audit; recheck its evidence."""
    audit = authenticated_json(audit_path, audit_sha256)
    if (
        audit.get("schema") != "cypshift.phase3.tdi_audit.v1"
        or audit.get("status") != "complete"
        or audit.get("independent_artifact_audit_passed") is not True
        or audit.get("production_eligible") is not True
        or audit.get("reserved_numeric_targets_opened") != 0
        or audit.get("recipe_sha256") != runner.file_hash(runner.RECIPE)
        or audit.get("data_manifest_sha256") != recipe["data_manifest_sha256"]
        or audit.get("tdi_manifest_sha256") != recipe["tdi_bundle_manifest_sha256"]
    ):
        raise ValueError("Independent two-seed production authority is incomplete")
    repeats = audit.get("repeats", [])
    if len(repeats) != 2:
        raise ValueError("Both independently audited repeats are required")
    evidence = []
    for expected_seed, entry in zip((20260905, 20260906), repeats, strict=True):
        result_path = Path(entry["result"]["path"])
        result = authenticated_json(result_path, entry["result"]["sha256"])
        experiment = authenticated_json(
            result_path.with_name("experiment.json"), result["experiment_sha256"]
        )
        if (
            result.get("seed") != expected_seed
            or entry.get("seed") != expected_seed
            or result.get("status") != "complete"
            or result.get("completed_fits") != 80
            or entry.get("experiment_sha256") != result["experiment_sha256"]
            or experiment.get("recipe_sha256") != audit["recipe_sha256"]
            or experiment.get("data_manifest_sha256") != audit["data_manifest_sha256"]
            or experiment.get("tdi_manifest_sha256") != audit["tdi_manifest_sha256"]
            or experiment.get("runtime") != recipe["runtime"]
            or result.get("reserved_numeric_targets_opened") != 0
        ):
            raise ValueError("Audited repeat identity differs")
        for key in ("names", "molecule_ids", "groups"):
            if (
                result[key] != list(getattr(data, key))
                or experiment[key] != result[key]
            ):
                raise ValueError("Audited development identities differ")
        outer, inner = runner.balanced_nested_folds(
            data.groups, data.original_direct_training_mask, expected_seed
        )
        if (
            result["outer_fold"] != outer.tolist()
            or result["inner_fold"] != inner.tolist()
        ):
            raise ValueError("Audited evaluation folds differ")
        arrays = {}
        for name in (*runner.LEARNERS, "selected"):
            spec = result["classes"][name]
            if (
                not Path(spec["path"])
                .resolve()
                .is_relative_to(result_path.parent.resolve())
            ):
                raise ValueError("Audited predictions escaped their run")
            arrays[name] = runner.read_array(spec)
        recomputed = runner.seed_evidence(data, arrays)
        if any(result[key] != value for key, value in recomputed.items()):
            raise ValueError("Audited metrics or decision differ from actual OOF")
        checked = authenticated_json(
            Path(entry["audit"]["path"]), entry["audit"]["sha256"]
        )
        if (
            checked.get("schema") != "cypshift.private.tdi_independent_audit.v1"
            or checked.get("status") != "passed"
            or checked.get("seed") != expected_seed
            or checked.get("fits") != 0
            or checked.get("reserved_numeric_targets_opened") != 0
            or checked.get("script_sha256") != AUDIT_SCRIPT_SHA256
            or checked.get("plan_sha256") != AUDIT_PLAN_SHA256
            or checked.get("result_sha256") != entry["result"]["sha256"]
            or checked.get("experiment_sha256") != result["experiment_sha256"]
            or checked.get("execution_commit") != experiment["execution_git_commit"]
            or checked.get("recipe_sha256") != audit["recipe_sha256"]
            or checked.get("data_manifest_sha256") != audit["data_manifest_sha256"]
            or checked.get("tdi_bundle_manifest_sha256") != audit["tdi_manifest_sha256"]
            or checked.get("independently_replayed_estimators") != 80
            or checked.get("threshold_cells_verified") != 20
            or checked.get("evidence") != recomputed
        ):
            raise ValueError(
                "Independent replay audit does not authenticate this repeat"
            )
        evidence.append(result)
    decision = runner.combine_evidence(*evidence)
    chosen = decision["recommended_procedure"]
    if (
        chosen not in PRODUCTION["maximum_fits"]
        or audit.get("recommended_procedure") != chosen
    ):
        raise ValueError("No matching useful two-seed production procedure")
    return chosen, audit


def support_preflight(data: Any) -> tuple[np.ndarray, list[dict[str, Any]]]:
    folds = balanced_group_folds(
        data.groups, data.original_direct_training_mask, 3, 20260905
    )
    report = []
    for fold in range(3):
        for col, endpoint in enumerate(ENDPOINTS):
            for role, population in (
                ("train", folds != fold),
                ("assessment", folds == fold),
            ):
                rows = np.flatnonzero(population & data.mask[:, col])
                counts = [
                    int(np.sum(data.labels[rows, col] == value)) for value in (0, 1)
                ]
                families = [
                    len({data.groups[i] for i in rows if data.labels[i, col] == value})
                    for value in (0, 1)
                ]
                if min(counts, default=0) == 0 or (
                    role == "assessment" and min(families) < 2
                ):
                    raise ValueError(
                        "Production grouped class support failed before fitting"
                    )
                report.append(
                    {
                        "fold": fold,
                        "endpoint": endpoint,
                        "role": role,
                        "class_counts": counts,
                        "class_families": families,
                    }
                )
    return folds, report


def selection(
    data: Any,
    features: np.ndarray,
    output: Path,
    procedure: str,
    fit: Any,
) -> dict[str, Any]:
    """Six or twelve family-disjoint fits; full-development OOF thresholds only."""
    if (output / "selection.json").exists():
        raise FileExistsError("Production selection is immutable")
    if procedure not in PRODUCTION["maximum_fits"]:
        raise ValueError("Unqualified production procedure")
    if (
        features.dtype != np.uint8
        or features.shape != (len(data.names), 4096)
        or not np.isin(features, [0, 1]).all()
    ):
        raise ValueError("Production feature layout differs")
    folds, support = support_preflight(data)
    learners = ("logistic",) if procedure == "logistic" else runner.LEARNERS
    endpoints, receipts = [], []
    for col in range(2):
        choices, arrays = {}, {}
        for learner in learners:
            probability = np.full(len(data.names), np.nan)
            for fold in range(3):
                train = np.flatnonzero((folds != fold) & data.mask[:, col])
                predict = np.flatnonzero(folds == fold)
                pred, receipt = fit(
                    learner=learner,
                    endpoint=col,
                    train=train,
                    predict=predict,
                    identity={"role": "production_selection", "fold": fold},
                )
                if pred.shape != (len(predict),) or not np.isfinite(pred).all():
                    raise ValueError("Production selection probabilities incomplete")
                probability[predict] = pred
                receipts.append(receipt)
            eligible = data.mask[:, col]
            choices[learner] = runner.select_threshold(
                probability[eligible], data.labels[eligible, col]
            )
            arrays[learner] = runner.array_receipt(
                output / f"selection-{col}-{learner}.npy", probability
            )
        if procedure == "logistic":
            if not choices["logistic"]["supported"]:
                raise ValueError(
                    "Production logistic OOF cannot select a nonconstant threshold"
                )
            chosen = "logistic"
        else:
            chosen = runner.choose_learner(choices)
        endpoints.append(
            {
                "endpoint": col,
                "learner": chosen,
                "threshold": choices[chosen]["threshold"],
                "threshold_choices": choices,
                "oof": arrays,
            }
        )
    result = {
        "folds": folds.tolist(),
        "support": support,
        "endpoints": endpoints,
        "fit_receipts": receipts,
    }
    runner.publish(output / "selection.json", runner.canonical(result))
    return result


def fit_final(
    output: Path,
    features: np.ndarray,
    data: Any,
    endpoint: int,
    learner: str,
    identity: dict[str, Any],
    budget: Any,
) -> dict[str, Any]:
    """Fit all eligible development rows and retain a fresh, authenticated model.

    No assessment/test rows are accepted by this helper. The evaluator's stricter
    family-disjoint training/prediction boundary remains unchanged.
    """
    train = np.flatnonzero(data.mask[:, endpoint])
    if set(data.labels[train, endpoint]) != {0, 1}:
        raise ValueError("Final estimator lacks both classes")
    targets = np.asarray(data.labels[train, endpoint], dtype=np.int8)
    inputs = {
        **identity,
        "role": "production_final",
        "endpoint": endpoint,
        "learner": learner,
        "training_indices": train.tolist(),
        "training_targets_sha256": runner.digest(targets.tobytes()),
        "parameters": runner.model_parameters(learner),
    }
    key = runner.digest(runner.canonical(inputs))
    directory = output / "fits" / key
    directory.mkdir(parents=True, exist_ok=False)
    runner.publish(directory / "inputs.json", runner.canonical(inputs))
    with budget.fit(directory):
        model = runner.new_estimator(learner)
        x = runner.model_inputs(features, train, learner)
        with warnings.catch_warnings():
            warnings.simplefilter("error", ConvergenceWarning)
            model.fit(x, targets)
        before = runner.positive_probability(model, x)
        path = directory / ("model.pkl" if learner == "logistic" else "model.cbm")
        if learner == "logistic":
            runner.publish(path, pickle.dumps(model, protocol=pickle.HIGHEST_PROTOCOL))
            resolved = model.get_params()
            resolved["n_iter_"] = np.asarray(model.n_iter_).tolist()
        else:
            temporary = directory / "model.partial"
            model.save_model(str(temporary))
            runner.publish(path, temporary.read_bytes())
            temporary.unlink()
            resolved = model.get_all_params()
        checkpoint = {"path": str(path.resolve()), "sha256": runner.file_hash(path)}
        fresh = runner.load_model(checkpoint, learner)
        after = runner.positive_probability(fresh, x)
        if not np.allclose(before, after, atol=1e-12, rtol=0):
            raise ValueError("Final model fresh reload probabilities differ")
        receipt = {
            "key": key,
            "inputs": inputs,
            "inputs_sha256": runner.file_hash(directory / "inputs.json"),
            "checkpoint": checkpoint,
            "resolved_parameters": resolved,
            "classes": np.asarray(model.classes_).tolist(),
            "training_probability": runner.array_receipt(
                directory / "training-probability.npy", after
            ),
            "maximum_reload_absolute_error": float(np.max(np.abs(before - after))),
        }
        runner.publish(directory / "receipt.json", runner.canonical(receipt))
    return {
        "path": str((directory / "receipt.json").resolve()),
        "sha256": runner.file_hash(directory / "receipt.json"),
    }


def parse_test(
    test_raw: bytes, expected_sha256: str, expected_rows: int = 750
) -> list[dict[str, str]]:
    """Authenticate the label-free file before any molecular featurization."""
    if runner.digest(test_raw) != expected_sha256:
        raise ValueError("Blinded test source receipt differs")
    rows = list(csv.reader(io.StringIO(test_raw.decode("utf-8")), strict=True))
    if not rows or set(rows[0]) != {"SMILES", "Molecule_Name"} or len(rows[0]) != 2:
        raise ValueError("Blinded test schema differs")
    if len(rows) != expected_rows + 1 or any(len(row) != 2 for row in rows[1:]):
        raise ValueError("Blinded test row count/layout differs")
    names = [row[rows[0].index("Molecule_Name")] for row in rows[1:]]
    if len(set(names)) != expected_rows or any(
        not cell or cell.strip() != cell for row in rows[1:] for cell in row
    ):
        raise ValueError("Blinded test identities are invalid")
    return [dict(zip(rows[0], row, strict=True)) for row in rows[1:]]


def serialize_csv(
    test_raw: bytes, classes: np.ndarray, expected_sha256: str, expected_rows: int = 750
) -> bytes:
    """Preserve exact organizer identities/order; reject constant predictions."""
    rows = parse_test(test_raw, expected_sha256, expected_rows)
    if (
        classes.shape != (expected_rows, 2)
        or not np.isin(classes, [0, 1]).all()
        or any(len(np.unique(classes[:, col])) != 2 for col in range(2))
    ):
        raise ValueError("TDI predictions must be complete binary and nonconstant")
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(["SMILES", "Molecule_Name", *ENDPOINTS])
    for row, pred in zip(rows, classes, strict=True):
        writer.writerow(
            [
                row["SMILES"],
                row["Molecule_Name"],
                *map(int, pred),
            ]
        )
    return stream.getvalue().encode()


def predict_test(
    test_raw: bytes,
    output: Path,
    selected: dict[str, Any],
    finals: list[dict[str, Any]],
    expected_sha256: str,
    expected_rows: int = 750,
) -> dict[str, Any]:
    rows = parse_test(test_raw, expected_sha256, expected_rows)
    features = featurize_binary_morgan([row["SMILES"] for row in rows])
    feature_receipt = runner.array_receipt(output / "blinded-features.npy", features)
    probability = np.empty((expected_rows, 2), dtype=np.float64)
    for col, (decision, spec) in enumerate(
        zip(selected["endpoints"], finals, strict=True)
    ):
        receipt = authenticated_json(Path(spec["path"]), spec["sha256"])
        if (
            receipt["inputs"]["endpoint"] != col
            or receipt["inputs"]["learner"] != decision["learner"]
        ):
            raise ValueError("Final model endpoint or learner differs")
        model = runner.load_model(receipt["checkpoint"], decision["learner"])
        probability[:, col] = runner.positive_probability(
            model,
            runner.model_inputs(
                features, np.arange(expected_rows), decision["learner"]
            ),
        )
    thresholds = np.array([item["threshold"] for item in selected["endpoints"]])
    classes = (probability >= thresholds).astype(np.int8)
    probability_receipt = runner.array_receipt(
        output / "blinded-probability.npy", probability
    )
    # Persist invalid predictions diagnostically before the strict CSV check.
    classes_receipt = runner.array_receipt(output / "blinded-class.npy", classes)
    raw = serialize_csv(test_raw, classes, expected_sha256, expected_rows)
    runner.publish(output / "submission.csv", raw)
    return {
        "features": feature_receipt,
        "probability": probability_receipt,
        "classes": classes_receipt,
        "submission": {
            "path": str((output / "submission.csv").resolve()),
            "sha256": runner.digest(raw),
        },
    }


class ProductionBudget(runner.Budget):
    """Reuse fit accounting; a distinct accounting seed prevents evaluation mixing."""

    def __init__(self, root: Path, output: Path) -> None:
        super().__init__(root, output, -20260905)
        self.cpu_allowance = (
            min(
                2 - self.prior["seed_cpu_core_hours"],
                1000 - self.prior["program_cpu_core_hours"],
            )
            * 3600
        )
        self.wall_allowance = 900 - self.prior["seed_occupied_wall_seconds"]
        self.remaining()


def core_validate(
    core_python: Path, test: Path, output: Path, expected_test_sha256: str
) -> dict[str, Any]:
    code = "from dataclasses import asdict;from pathlib import Path;import json,sys;sys.path.insert(0,sys.argv[1]);from cypshift.competition_submission import validate_submission;print(json.dumps(asdict(validate_submission(Path(sys.argv[2]).read_bytes(),Path(sys.argv[3]).read_bytes(),'tdi',expected_test_sha256=sys.argv[4])),sort_keys=True))"
    command = [
        str(core_python.resolve()),
        "-c",
        code,
        str(ROOT / "src"),
        str(test.resolve()),
        str((output / "submission.csv").resolve()),
        expected_test_sha256,
    ]
    result = subprocess.run(
        command, check=True, capture_output=True, text=True, timeout=30
    )
    receipt = json.loads(result.stdout)
    if (
        receipt["submission_sha256"] != runner.file_hash(output / "submission.csv")
        or receipt["test_sha256"] != expected_test_sha256
        or receipt["rows"] != 750
        or receipt["track"] != "tdi"
    ):
        raise ValueError("Core validator receipt differs")
    runner.publish(output / "validator.json", runner.canonical(receipt))
    return receipt


def produce(
    compiled: Path,
    tdi_bundle: Path,
    audit: Path,
    audit_sha256: str,
    test: Path,
    core_python: Path,
    output: Path,
) -> dict[str, Any]:
    if not (
        output.resolve().parent
        == compiled.resolve().parent
        == tdi_bundle.resolve().parent
    ) or output.resolve().is_relative_to(ROOT):
        raise ValueError(
            "Production must use the shared private phase3 accounting root"
        )
    recipe = json.loads(runner.RECIPE.read_bytes())
    runner.validate_recipe(recipe)
    if (
        runner.file_hash(compiled / "manifest.json") != recipe["data_manifest_sha256"]
        or runner.file_hash(tdi_bundle / "manifest.json")
        != recipe["tdi_bundle_manifest_sha256"]
    ):
        raise ValueError("Production development bundle receipts differ")
    resources = runner.resource_receipt()
    with (output.parent / "compute.lock").open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        runner.freeze_interrupted_fits(output.parent)
        output.mkdir(exist_ok=False)
        budget = ProductionBudget(output.parent, output)
        previous = signal.getsignal(signal.SIGALRM)

        def deadline(signum: int, frame: Any) -> None:
            raise TimeoutError("TDI production occupied wall exhausted")

        signal.signal(signal.SIGALRM, deadline)
        signal.setitimer(signal.ITIMER_REAL, budget.remaining()[0])
        status = "failed"
        try:
            budget.limit()
            source = runner.source_identity(recipe)
            for relative in (
                "research/maplight-fixed/competition_tdi_production.py",
                "src/cypshift/competition_submission.py",
            ):
                committed = subprocess.check_output(
                    ["git", "show", f"{source['execution_git_commit']}:{relative}"],
                    cwd=ROOT,
                )
                if runner.digest(committed) != runner.file_hash(ROOT / relative):
                    raise ValueError("Production source differs from committed code")
                source[relative] = runner.digest(committed)
            data = load_tdi_development(compiled, tdi_bundle)
            procedure, authority = authorize(audit, audit_sha256, data, recipe)
            features = featurize_binary_morgan(data.raw_smiles)
            feature_spec = runner.array_receipt(output / "features.npy", features)
            identity = {
                "schema": "cypshift.phase3.tdi_production_experiment.v1",
                "recipe": PRODUCTION,
                "source": source,
                "resources": resources,
                "procedure": procedure,
                "audit": {"path": str(audit.resolve()), "sha256": audit_sha256},
                "features": feature_spec,
                "names": list(data.names),
                "molecule_ids": list(data.molecule_ids),
                "groups": list(data.groups),
                "data_manifest_sha256": recipe["data_manifest_sha256"],
                "tdi_manifest_sha256": recipe["tdi_bundle_manifest_sha256"],
            }
            runner.publish(output / "experiment.json", runner.canonical(identity))

            def fit(**kwargs: Any) -> Any:
                kwargs["identity"] = {
                    "experiment_sha256": runner.file_hash(output / "experiment.json"),
                    **kwargs["identity"],
                }
                return runner.fit_estimator(
                    output, features, data, budget=budget, **kwargs
                )

            selected = selection(data, features, output, procedure, fit)
            final_identity = {
                "experiment_sha256": runner.file_hash(output / "experiment.json"),
                "selection_sha256": runner.file_hash(output / "selection.json"),
            }
            finals = [
                fit_final(
                    output,
                    features,
                    data,
                    item["endpoint"],
                    item["learner"],
                    final_identity,
                    budget,
                )
                for item in selected["endpoints"]
            ]
            runner.publish(output / "final-models.json", runner.canonical(finals))
            # This is deliberately the first blinded file read, after all fits and
            # thresholds are fixed. No geometry or class-balance selection follows.
            prediction = predict_test(
                test.read_bytes(), output, selected, finals, TEST_SHA256
            )
            validator = core_validate(core_python, test, output, TEST_SHA256)
            budget.remaining()
            result = {
                "schema": "cypshift.phase3.tdi_release.v1",
                "status": "complete",
                "submission_ready": True,
                "uploaded": False,
                "procedure": procedure,
                "completed_fits": len(selected["fit_receipts"]) + len(finals),
                "audit_sha256": audit_sha256,
                "experiment_sha256": runner.file_hash(output / "experiment.json"),
                "selection_sha256": runner.file_hash(output / "selection.json"),
                "final_models": finals,
                "prediction": prediction,
                "validator": validator,
                "reserved_numeric_targets_opened": 0,
            }
            if result["completed_fits"] != PRODUCTION["maximum_fits"][procedure]:
                raise ValueError("Production fit count differs")
            runner.publish(output / "result.json", runner.canonical(result))
            status = "complete"
            return result
        except BaseException as exc:
            runner.publish(
                output / "failure.json",
                runner.canonical(
                    {
                        "status": "failed",
                        "type": type(exc).__name__,
                        "message": str(exc),
                        "submission_ready": False,
                    }
                ),
            )
            raise
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, previous)
            budget.finish(status)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("compiled", "tdi-bundle", "audit", "test", "core-python", "output"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--audit-sha256", required=True)
    args = parser.parse_args()
    result = produce(
        args.compiled,
        args.tdi_bundle,
        args.audit,
        args.audit_sha256,
        args.test,
        args.core_python,
        args.output,
    )
    print(
        json.dumps(
            {
                "status": result["status"],
                "submission": result["prediction"]["submission"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
