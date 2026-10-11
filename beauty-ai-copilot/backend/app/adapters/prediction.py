"""Beauty prediction adapters.

* FixturePredictionAdapter — reads fixed-seed fixture predictions. It is NOT computer-vision
  inference and the UI labels it as such.
* RealPredictionAdapter — interface only. It stays unconfigured until an authorized model and
  evaluation data are supplied; calling it raises IntegrationUnavailable instead of faking output.
"""
from __future__ import annotations

from typing import Protocol

from app.config import get_settings
from app.errors import IntegrationUnavailable
from app.services import fixtures


class PredictionAdapter(Protocol):
    mode: str

    def predict_batch(self, model_id: str, sample_ids: list[str]) -> dict[str, dict]: ...


class FixturePredictionAdapter:
    mode = "synthetic_fixture"

    def predict_batch(self, model_id: str, sample_ids: list[str]) -> dict[str, dict]:
        data = fixtures.load_json(fixtures.predictions_path(model_id))["predictions"]
        return {sid: data[sid] for sid in sample_ids}


class RealPredictionAdapter:
    mode = "real"

    def predict_batch(self, model_id: str, sample_ids: list[str]) -> dict[str, dict]:
        raise IntegrationUnavailable(
            "real_prediction_unconfigured",
            "Real prediction mode requires an authorized model endpoint and consented evaluation data. None is configured.")


def get_prediction_adapter() -> PredictionAdapter:
    return FixturePredictionAdapter() if get_settings().prediction_mode == "synthetic_fixture" else RealPredictionAdapter()
