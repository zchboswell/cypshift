#!/usr/bin/env python3
"""Deterministic CPU mechanics for the frozen G2-4 EXP-M1 design."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Final, Literal, cast

import numpy as np

SCRIPT: Final = Path(__file__).resolve()
ROOT: Final = SCRIPT.parents[2]
CONTRACT: Final = (
    ROOT / "benchmarks" / "openadmet_cyp_2026" / "global_v2_m1_synthetic_contract.json"
)
PARENT: Final = (
    ROOT / "benchmarks" / "openadmet_cyp_2026" / "global_v2_m1_screen_contract.json"
)
CONTRACT_SHA256: Final = (
    "f80a6e8d7735a67ddebf636958aea0b56e738afbc3d10bcea2450ec168048df7"
)
PARENT_SHA256: Final = (
    "63516e0f3b9b87cd24911d39d753de0dabac458413d05a6ac83a27d97b1c2cc0"
)
ENDPOINTS: Final = ("CYP1A2", "CYP2C9", "CYP2D6", "CYP3A4")
LOSSES: Final = ("CENTRAL_MAE", "INTERVAL_DEAD_ZONE")
MODEL_SEEDS: Final = (20260824, 20260825, 20260826)
REPEAT_SEEDS: Final = (20260810, 20260811, 20260812)
OUTER_FOLDS: Final = tuple(range(5))
INNER_FOLDS: Final = tuple(range(4))
FEATURE_WIDTH: Final = 2248
MORGAN_WIDTH: Final = 2048
DESCRIPTOR_WIDTH: Final = 200
MODEL_DOUBLE_FITS: Final = 2430
OFFICIAL_ZERO_FIELDS: Final = (
    "official_target_values_opened",
    "official_features_opened",
    "official_structures_opened",
    "official_model_fits",
    "official_predictions_generated",
    "development_metric_evaluations",
    "confirmatory_truth_values_opened",
    "historical_row_level_artifacts_opened",
    "blinded_test_rows_opened",
    "tdi_rows_opened",
    "external_records_opened",
    "submission_rows_generated",
    "official_metric_calls",
    "leaderboard_observations_used_for_selection",
    "live_uploads",
    "execution_claims_created_or_consumed",
)

SystemId = Literal["SHARED", "INDEPENDENT", "PERMUTED"]
Stage = Literal["INNER", "OUTER"]
LossId = Literal["CENTRAL_MAE", "INTERVAL_DEAD_ZONE"]


class M1Error(RuntimeError):
    """Fail-closed contract or mechanics error."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise M1Error(message)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_path(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def json_bytes(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def csv_bytes(fieldnames: tuple[str, ...], rows: list[dict[str, object]]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode()


def static_contract() -> tuple[dict[str, Any], dict[str, Any]]:
    require(sha256_path(CONTRACT) == CONTRACT_SHA256, "synthetic contract drift")
    require(sha256_path(PARENT) == PARENT_SHA256, "M1 parent contract drift")
    contract = cast(dict[str, Any], json.loads(CONTRACT.read_text(encoding="utf-8")))
    parent = cast(dict[str, Any], json.loads(PARENT.read_text(encoding="utf-8")))
    require(
        contract["parents"]["m1_screen_contract"]["sha256"] == PARENT_SHA256,
        "parent binding drift",
    )
    require(
        parent["fit_and_prediction_budget"]["exact_new_neural_fits"]
        == MODEL_DOUBLE_FITS,
        "fit budget drift",
    )
    return contract, parent


def scoped_seed(namespace: str, *fields: object) -> int:
    payload = "|".join(("cypshift-m1-v1", namespace, *(str(field) for field in fields)))
    return int.from_bytes(hashlib.sha256(payload.encode()).digest()[:8], "big") % (
        2**63
    )


@dataclass(frozen=True, order=True)
class FitIdentity:
    stage: Stage
    system: SystemId
    repeat_seed: int
    outer_fold: int
    inner_fold: int | None
    loss_id: LossId
    model_seed: int
    endpoint: str | None

    @property
    def architecture_namespace(self) -> str:
        if self.system in {"SHARED", "PERMUTED"}:
            return "SHARED_ARCH"
        require(self.endpoint in ENDPOINTS, "independent endpoint missing")
        return f"INDEPENDENT|{self.endpoint}"

    @property
    def initialization_seed(self) -> int:
        return scoped_seed(
            self.architecture_namespace,
            self.repeat_seed,
            self.outer_fold,
            self.inner_fold if self.inner_fold is not None else "OUTER",
            self.loss_id,
            self.model_seed,
        )

    def key(self) -> tuple[object, ...]:
        return (
            self.stage,
            self.system,
            self.repeat_seed,
            self.outer_fold,
            -1 if self.inner_fold is None else self.inner_fold,
            self.loss_id,
            self.model_seed,
            self.endpoint or "SHARED",
        )


def shared_loss_token(repeat_seed: int, outer_fold: int) -> LossId:
    index = REPEAT_SEEDS.index(repeat_seed) * 5 + outer_fold
    if index < 5:
        return "CENTRAL_MAE"
    if index < 10:
        return "INTERVAL_DEAD_ZONE"
    return "CENTRAL_MAE"  # exact tie resolves lexicographically


def independent_loss_token(repeat_seed: int, outer_fold: int, endpoint: str) -> LossId:
    require(endpoint in ENDPOINTS, "unknown endpoint")
    index = (REPEAT_SEEDS.index(repeat_seed) * 5 + outer_fold) * 4 + ENDPOINTS.index(
        endpoint
    )
    category = index // 20
    return "CENTRAL_MAE" if category in {0, 2} else "INTERVAL_DEAD_ZONE"


def enumerate_fit_identities(
    *, reverse_execution_order: bool = False
) -> list[FitIdentity]:
    identities: list[FitIdentity] = []
    for repeat_seed in REPEAT_SEEDS:
        for outer_fold in OUTER_FOLDS:
            selected = shared_loss_token(repeat_seed, outer_fold)
            for inner_fold in INNER_FOLDS:
                for loss_id in LOSSES:
                    for model_seed in MODEL_SEEDS:
                        identities.append(
                            FitIdentity(
                                "INNER",
                                "SHARED",
                                repeat_seed,
                                outer_fold,
                                inner_fold,
                                cast(LossId, loss_id),
                                model_seed,
                                None,
                            )
                        )
                        for endpoint in ENDPOINTS:
                            identities.append(
                                FitIdentity(
                                    "INNER",
                                    "INDEPENDENT",
                                    repeat_seed,
                                    outer_fold,
                                    inner_fold,
                                    cast(LossId, loss_id),
                                    model_seed,
                                    endpoint,
                                )
                            )
                for model_seed in MODEL_SEEDS:
                    identities.append(
                        FitIdentity(
                            "INNER",
                            "PERMUTED",
                            repeat_seed,
                            outer_fold,
                            inner_fold,
                            selected,
                            model_seed,
                            None,
                        )
                    )
            for model_seed in MODEL_SEEDS:
                identities.append(
                    FitIdentity(
                        "OUTER",
                        "SHARED",
                        repeat_seed,
                        outer_fold,
                        None,
                        selected,
                        model_seed,
                        None,
                    )
                )
                identities.append(
                    FitIdentity(
                        "OUTER",
                        "PERMUTED",
                        repeat_seed,
                        outer_fold,
                        None,
                        selected,
                        model_seed,
                        None,
                    )
                )
                for loss_id in LOSSES:
                    for endpoint in ENDPOINTS:
                        identities.append(
                            FitIdentity(
                                "OUTER",
                                "INDEPENDENT",
                                repeat_seed,
                                outer_fold,
                                None,
                                cast(LossId, loss_id),
                                model_seed,
                                endpoint,
                            )
                        )
    require(len(identities) == MODEL_DOUBLE_FITS, "fit identity count differs")
    require(len(set(identities)) == MODEL_DOUBLE_FITS, "duplicate fit identity")
    if reverse_execution_order:
        identities.reverse()
    return identities


def deterministic_best_epoch(identity: FitIdentity) -> int:
    require(identity.stage == "INNER", "best epoch requires inner identity")
    return 1 + scoped_seed("BEST_EPOCH", *identity.key()) % 300


def outer_epoch(identity: FitIdentity) -> int:
    require(identity.stage == "OUTER", "outer epoch requires outer identity")
    epochs = sorted(
        deterministic_best_epoch(
            FitIdentity(
                "INNER",
                identity.system,
                identity.repeat_seed,
                identity.outer_fold,
                inner_fold,
                identity.loss_id,
                identity.model_seed,
                identity.endpoint,
            )
        )
        for inner_fold in INNER_FOLDS
    )
    return (epochs[1] + epochs[2]) // 2


def _identity_digest(identity: FitIdentity, epoch: int, kind: str) -> str:
    return sha256_bytes(
        json_bytes(
            {
                "contract": CONTRACT_SHA256,
                "identity": asdict(identity),
                "epoch": epoch,
                "kind": kind,
            }
        )
    )


FIT_FIELDS: Final = (
    "stage",
    "system",
    "repeat_seed",
    "outer_fold",
    "inner_fold",
    "loss_id",
    "model_seed",
    "endpoint",
    "epoch",
    "fit_receipt_sha256",
)
SELECTION_FIELDS: Final = (
    "scope",
    "repeat_seed",
    "outer_fold",
    "endpoint",
    "loss_id",
    "selection_receipt_sha256",
)


def model_double_files(*, reverse_execution_order: bool = False) -> dict[str, bytes]:
    """Traverse every frozen fit identity and emit canonical mechanics receipts."""

    static_contract()
    fit_rows: list[dict[str, object]] = []
    for identity in enumerate_fit_identities(
        reverse_execution_order=reverse_execution_order
    ):
        epoch = (
            deterministic_best_epoch(identity)
            if identity.stage == "INNER"
            else outer_epoch(identity)
        )
        fit_rows.append(
            {
                **asdict(identity),
                "inner_fold": ""
                if identity.inner_fold is None
                else identity.inner_fold,
                "endpoint": identity.endpoint or "",
                "epoch": epoch,
                "fit_receipt_sha256": _identity_digest(identity, epoch, "MODEL_DOUBLE"),
            }
        )
    fit_rows.sort(key=lambda row: tuple(str(row[field]) for field in FIT_FIELDS[:-1]))

    selections: list[dict[str, object]] = []
    for repeat_seed in REPEAT_SEEDS:
        for outer_fold in OUTER_FOLDS:
            shared = shared_loss_token(repeat_seed, outer_fold)
            shared_row = {
                "scope": "SHARED",
                "repeat_seed": repeat_seed,
                "outer_fold": outer_fold,
                "endpoint": "",
                "loss_id": shared,
            }
            selections.append(
                {
                    **shared_row,
                    "selection_receipt_sha256": sha256_bytes(json_bytes(shared_row)),
                }
            )
            for endpoint in ENDPOINTS:
                independent = independent_loss_token(repeat_seed, outer_fold, endpoint)
                row = {
                    "scope": "INDEPENDENT",
                    "repeat_seed": repeat_seed,
                    "outer_fold": outer_fold,
                    "endpoint": endpoint,
                    "loss_id": independent,
                }
                selections.append(
                    {**row, "selection_receipt_sha256": sha256_bytes(json_bytes(row))}
                )

    preprocessing = {
        "schema_version": "cypshift.openadmet_cyp_2026.m1_preprocessing_receipt.v1",
        "contract_sha256": CONTRACT_SHA256,
        "contexts": 75,
        "input_columns": FEATURE_WIDTH,
        "target_values_opened": 0,
        "system_specific_transforms": 0,
    }
    predictions = {
        "schema_version": "cypshift.openadmet_cyp_2026.m1_model_double_predictions.v1",
        "contract_sha256": CONTRACT_SHA256,
        "inner_raw_rows": 57600,
        "inner_seed_averaged_rows": 19200,
        "outer_raw_rows": 11520,
        "outer_seed_averaged_rows": 3840,
        "canonical_identity_digest": sha256_bytes(
            b"".join(row["fit_receipt_sha256"].encode() for row in fit_rows)
        ),
        "scientific_interpretation": "Synthetic mechanics only; no model-quality interpretation.",
    }
    return {
        "feature_preprocessing_receipt.json": json_bytes(preprocessing),
        "model_double_fit_receipts.csv": csv_bytes(FIT_FIELDS, fit_rows),
        "loss_selection_receipts.csv": csv_bytes(SELECTION_FIELDS, selections),
        "prediction_receipts.json": json_bytes(predictions),
    }


@dataclass(frozen=True)
class PreprocessingReceipt:
    medians_sha256: str
    means_sha256: str
    scales_sha256: str
    train_rows: int
    prediction_rows: int
    columns: int


def _little_f8_bytes(array: np.ndarray[Any, Any]) -> bytes:
    return np.ascontiguousarray(array, dtype="<f8").tobytes()


def preprocess_features(
    raw: np.ndarray[Any, Any], train_indices: np.ndarray[Any, Any]
) -> tuple[np.ndarray[Any, Any], PreprocessingReceipt]:
    """Fit target-blind descriptor imputation and scaling on training rows only."""

    matrix = np.asarray(raw, dtype=np.float64)
    indices = np.asarray(train_indices, dtype=np.int64)
    require(
        matrix.ndim == 2 and matrix.shape[1] == FEATURE_WIDTH, "feature shape differs"
    )
    require(indices.ndim == 1 and indices.size > 0, "training indices differ")
    require(np.unique(indices).size == indices.size, "duplicate training index")
    require(
        indices.min() >= 0 and indices.max() < matrix.shape[0],
        "training index out of range",
    )
    require(np.isfinite(matrix[:, :MORGAN_WIDTH]).all(), "Morgan feature is nonfinite")
    train = matrix[indices].copy()
    descriptor_train = train[:, MORGAN_WIDTH:]
    require(
        not np.all(~np.isfinite(descriptor_train), axis=0).any(),
        "all-nonfinite descriptor",
    )
    medians = np.nanmedian(
        np.where(np.isfinite(descriptor_train), descriptor_train, np.nan), axis=0
    )
    imputed = matrix.copy()
    descriptor = imputed[:, MORGAN_WIDTH:]
    invalid = ~np.isfinite(descriptor)
    descriptor[invalid] = np.broadcast_to(medians, descriptor.shape)[invalid]
    require(np.isfinite(imputed).all(), "imputation left nonfinite value")
    means = np.mean(imputed[indices], axis=0, dtype=np.float64)
    scales = np.std(imputed[indices], axis=0, dtype=np.float64, ddof=0)
    scales[scales == 0.0] = 1.0
    transformed = np.ascontiguousarray((imputed - means) / scales, dtype=np.float32)
    receipt = PreprocessingReceipt(
        medians_sha256=sha256_bytes(_little_f8_bytes(medians)),
        means_sha256=sha256_bytes(_little_f8_bytes(means)),
        scales_sha256=sha256_bytes(_little_f8_bytes(scales)),
        train_rows=int(indices.size),
        prediction_rows=int(matrix.shape[0]),
        columns=int(matrix.shape[1]),
    )
    return transformed, receipt


def permute_label_bundles(
    rows: list[dict[str, object]],
    *,
    repeat_seed: int,
    outer_fold: int,
    inner_fold: int | None,
    endpoint: str,
    loss_id: LossId,
) -> list[dict[str, object]]:
    """Apply the frozen training-only intact-bundle permutation."""

    require(endpoint in ENDPOINTS, "unknown permutation endpoint")
    eligible = [row for row in rows if bool(row["eligible"])]
    require(len(eligible) > 0, "empty permutation population")
    source = sorted(
        eligible, key=lambda row: (str(row["component"]), str(row["molecule_id"]))
    )
    scope = "OUTER" if inner_fold is None else str(inner_fold)
    destination = sorted(
        eligible,
        key=lambda row: (
            sha256_bytes(
                f"20260829|{repeat_seed}|{outer_fold}|{scope}|{endpoint}|{loss_id}|{row['component']}|{row['molecule_id']}".encode()
            ),
            str(row["component"]),
            str(row["molecule_id"]),
        ),
    )
    bundle_fields = (
        "central",
        "lower",
        "upper",
        "std",
        "raw_missingness",
        "assay_source",
        "provenance",
    )
    output = [dict(row) for row in rows]
    by_identity = {
        (str(row["component"]), str(row["molecule_id"])): row for row in output
    }
    for source_row, destination_row in zip(source, destination, strict=True):
        target = by_identity[
            (str(destination_row["component"]), str(destination_row["molecule_id"]))
        ]
        for field in bundle_fields:
            target[field] = source_row[field]
    before = sorted(tuple(row[field] for field in bundle_fields) for row in source)
    after = sorted(
        tuple(row[field] for field in bundle_fields)
        for row in output
        if bool(row["eligible"])
    )
    require(before == after, "permutation changed label-bundle multiset")
    if len(eligible) > 1:
        require(
            any(
                str(a["molecule_id"]) != str(b["molecule_id"])
                for a, b in zip(source, destination, strict=True)
            ),
            "permutation is identity",
        )
    return output


@dataclass(frozen=True)
class TorchFitResult:
    epochs_completed: int
    best_epoch: int
    parameter_sha256: str
    prediction_sha256: str
    prediction_rows: int
    prediction_columns: int
    final_validation_objective: float | None


def configure_torch_runtime(*, threads: int = 4, interop_threads: int = 1) -> Any:
    """Apply the exact deterministic CPU settings before tensor work."""

    import torch

    require(torch.__version__ == "2.13.0+cpu", "PyTorch version differs")
    require(not torch.cuda.is_available(), "CUDA device is visible")
    require(os.environ.get("PYTHONHASHSEED") == "0", "PYTHONHASHSEED differs")
    for name in (
        "OMP_NUM_THREADS",
        "MKL_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
        "NUMEXPR_NUM_THREADS",
    ):
        require(os.environ.get(name) == str(threads), f"{name} differs")
    require(os.environ.get("OMP_DYNAMIC") == "FALSE", "OMP_DYNAMIC differs")
    require(os.environ.get("MKL_DYNAMIC") == "FALSE", "MKL_DYNAMIC differs")
    torch.use_deterministic_algorithms(True, warn_only=False)
    torch.set_deterministic_debug_mode("error")
    torch.set_num_threads(threads)
    torch.set_num_interop_threads(interop_threads)
    torch.set_float32_matmul_precision("highest")
    torch.set_flush_denormal(True)
    torch.backends.mkldnn.enabled = False
    return torch


def build_model(system: SystemId, *, endpoint: str | None = None) -> Any:
    """Construct the exact parent-frozen shared or independent architecture."""

    import torch

    require(system in {"SHARED", "INDEPENDENT", "PERMUTED"}, "unknown system")
    if system == "INDEPENDENT":
        require(endpoint in ENDPOINTS, "independent endpoint missing")
    else:
        require(endpoint is None, "shared endpoint must be absent")

    class ExactMLP(torch.nn.Module):
        def __init__(self, outputs: int) -> None:
            super().__init__()
            self.trunk = torch.nn.Sequential(
                torch.nn.Linear(FEATURE_WIDTH, 512),
                torch.nn.ReLU(),
                torch.nn.Dropout(0.1),
                torch.nn.Linear(512, 256),
                torch.nn.ReLU(),
                torch.nn.Dropout(0.1),
            )
            self.heads = torch.nn.ModuleList(
                [
                    torch.nn.Sequential(
                        torch.nn.Linear(256, 64),
                        torch.nn.ReLU(),
                        torch.nn.Dropout(0.1),
                        torch.nn.Linear(64, 1),
                    )
                    for _ in range(outputs)
                ]
            )

        def forward(self, features: Any) -> Any:
            latent = self.trunk(features)
            return torch.cat([head(latent) for head in self.heads], dim=1)

    return ExactMLP(1 if system == "INDEPENDENT" else 4)


def _masked_objective(
    torch: Any,
    predictions: Any,
    central: Any,
    lower: Any,
    upper: Any,
    *,
    loss_id: LossId,
) -> Any:
    if loss_id == "CENTRAL_MAE":
        eligible = torch.isfinite(central)
        cells = torch.abs(predictions - central)
    else:
        eligible = (
            torch.isfinite(central)
            & torch.isfinite(lower)
            & torch.isfinite(upper)
            & (lower <= upper)
        )
        cells = torch.clamp(lower - predictions, min=0.0) + torch.clamp(
            predictions - upper, min=0.0
        )
    endpoint_losses = []
    for endpoint_index in range(predictions.shape[1]):
        mask = eligible[:, endpoint_index]
        if bool(torch.any(mask)):
            endpoint_losses.append(torch.mean(cells[mask, endpoint_index]))
    require(bool(endpoint_losses), "minibatch has no eligible endpoint")
    return torch.stack(endpoint_losses).mean()


def _state_digest(model: Any) -> str:
    payload = bytearray()
    for name, tensor in sorted(model.state_dict().items()):
        array = np.ascontiguousarray(tensor.detach().cpu().numpy(), dtype="<f4")
        encoded_name = name.encode()
        encoded_shape = json_bytes(list(array.shape)).rstrip(b"\n")
        payload.extend(len(encoded_name).to_bytes(8, "big"))
        payload.extend(encoded_name)
        payload.extend(len(encoded_shape).to_bytes(8, "big"))
        payload.extend(encoded_shape)
        payload.extend(array.tobytes())
    return sha256_bytes(bytes(payload))


def _prediction_digest(predictions: np.ndarray[Any, Any]) -> str:
    array = np.ascontiguousarray(predictions, dtype="<f8")
    return sha256_bytes(array.tobytes())


def fit_torch_model(
    *,
    identity: FitIdentity,
    train_features: np.ndarray[Any, Any],
    train_central: np.ndarray[Any, Any],
    train_lower: np.ndarray[Any, Any],
    train_upper: np.ndarray[Any, Any],
    prediction_features: np.ndarray[Any, Any],
    epochs: int,
    validation: tuple[
        np.ndarray[Any, Any],
        np.ndarray[Any, Any],
        np.ndarray[Any, Any],
        np.ndarray[Any, Any],
    ]
    | None = None,
    patience: int = 25,
) -> TorchFitResult:
    """Fit one exact architecture; callers enforce capability boundaries."""

    import torch

    require(1 <= epochs <= 300, "epoch budget differs")
    train_x = np.ascontiguousarray(train_features, dtype=np.float32)
    predict_x = np.ascontiguousarray(prediction_features, dtype=np.float32)
    require(
        train_x.ndim == 2 and train_x.shape[1] == FEATURE_WIDTH,
        "training feature shape differs",
    )
    require(
        predict_x.ndim == 2 and predict_x.shape[1] == FEATURE_WIDTH,
        "prediction feature shape differs",
    )
    endpoint_indices = list(range(4))
    if identity.system == "INDEPENDENT":
        require(identity.endpoint in ENDPOINTS, "independent endpoint differs")
        endpoint_indices = [ENDPOINTS.index(cast(str, identity.endpoint))]

    def targets(value: np.ndarray[Any, Any]) -> Any:
        array = np.asarray(value, dtype=np.float32)
        require(array.shape == (train_x.shape[0], 4), "training target shape differs")
        return torch.from_numpy(np.ascontiguousarray(array[:, endpoint_indices]))

    torch.manual_seed(identity.initialization_seed)
    model = build_model(identity.system, endpoint=identity.endpoint)
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=0.001,
        weight_decay=0.0001,
        betas=(0.9, 0.999),
        eps=1e-8,
        amsgrad=False,
    )
    x_tensor = torch.from_numpy(train_x)
    central_tensor = targets(train_central)
    lower_tensor = targets(train_lower)
    upper_tensor = targets(train_upper)
    best_state: dict[str, Any] | None = None
    best_value = math.inf
    best_epoch = 0
    stale = 0
    final_validation: float | None = None
    epochs_completed = 0
    for epoch in range(1, epochs + 1):
        model.train()
        shuffle_seed = scoped_seed("EPOCH_SHUFFLE", *identity.key(), epoch)
        order = np.random.Generator(np.random.PCG64(shuffle_seed)).permutation(
            train_x.shape[0]
        )
        for start in range(0, train_x.shape[0], 128):
            batch = torch.from_numpy(
                np.ascontiguousarray(order[start : start + 128], dtype=np.int64)
            )
            optimizer.zero_grad(set_to_none=True)
            prediction = model(x_tensor[batch])
            loss = _masked_objective(
                torch,
                prediction,
                central_tensor[batch],
                lower_tensor[batch],
                upper_tensor[batch],
                loss_id=identity.loss_id,
            )
            require(bool(torch.isfinite(loss)), "nonfinite training objective")
            loss.backward()
            optimizer.step()
        epochs_completed = epoch
        if validation is not None:
            val_x, val_central, val_lower, val_upper = validation
            val_x_tensor = torch.from_numpy(
                np.ascontiguousarray(val_x, dtype=np.float32)
            )
            val_targets = [
                torch.from_numpy(
                    np.ascontiguousarray(
                        np.asarray(value, dtype=np.float32)[:, endpoint_indices]
                    )
                )
                for value in (val_central, val_lower, val_upper)
            ]
            model.eval()
            with torch.inference_mode():
                value = float(
                    _masked_objective(
                        torch,
                        model(val_x_tensor),
                        val_targets[0],
                        val_targets[1],
                        val_targets[2],
                        loss_id=identity.loss_id,
                    ).item()
                )
            require(math.isfinite(value), "nonfinite validation objective")
            final_validation = value
            if value < best_value:
                best_value = value
                best_epoch = epoch
                best_state = {
                    name: tensor.detach().clone()
                    for name, tensor in model.state_dict().items()
                }
                stale = 0
            else:
                stale += 1
                if stale >= patience:
                    break
    if validation is not None:
        require(best_state is not None and best_epoch > 0, "finite checkpoint absent")
        model.load_state_dict(best_state)
    else:
        best_epoch = epochs
    model.eval()
    with torch.inference_mode():
        predictions = (
            model(torch.from_numpy(predict_x)).detach().cpu().numpy().astype(np.float64)
        )
    require(np.isfinite(predictions).all(), "nonfinite prediction")
    return TorchFitResult(
        epochs_completed=epochs_completed,
        best_epoch=best_epoch,
        parameter_sha256=_state_digest(model),
        prediction_sha256=_prediction_digest(predictions),
        prediction_rows=int(predictions.shape[0]),
        prediction_columns=int(predictions.shape[1]),
        final_validation_objective=final_validation,
    )
