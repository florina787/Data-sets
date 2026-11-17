"""Champion-challenger model registry with explicit promotion criteria, human approval and rollback."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from flowwealth.contracts import utcnow


@dataclass(frozen=True)
class PromotionCriteria:
    min_holdout_ic_t: float = 2.0          # statistical evidence on untouched holdout
    min_wf_folds_positive_frac: float = 0.75
    min_net_sharpe: float = 0.0            # must survive realistic costs
    must_beat_baselines_net: bool = True
    min_net_sharpe_margin_vs_champion: float = 0.1
    max_drawdown_floor: float = -0.25      # net max drawdown must be better than this
    max_ece: float | None = 0.05           # only if the model emits probabilities
    min_holdout_dates: int = 120


@dataclass
class ModelCard:
    model_id: str            # name@version
    horizon: str
    evidence: dict           # holdout_ic_t, wf_folds_positive_frac, net_sharpe, net_max_dd, ece, n_dates, baseline_net_sharpes
    dataset_version: str
    stage: str = "challenger"
    registered_at: str = field(default_factory=lambda: utcnow().isoformat())


class ModelRegistry:
    def __init__(self, path: Path, criteria: PromotionCriteria = PromotionCriteria()):
        self.path, self.criteria = Path(path), criteria
        self.state = json.loads(self.path.read_text()) if self.path.exists() else {"models": {}, "champion": {}, "log": []}

    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.state, indent=2))

    def _log(self, event: str, **kw):
        self.state["log"].append({"at": utcnow().isoformat(), "event": event, **kw})

    def register(self, card: ModelCard) -> None:
        if card.model_id in self.state["models"]:
            raise ValueError(f"{card.model_id} already registered; bump the version")
        self.state["models"][card.model_id] = asdict(card)
        self._log("register", model_id=card.model_id)
        self._save()

    def champion(self, horizon: str) -> str | None:
        return self.state["champion"].get(horizon, {}).get("current")

    def evaluate(self, model_id: str) -> dict:
        c, m = self.criteria, self.state["models"][model_id]
        e = m["evidence"]
        reasons = []
        if (e.get("holdout_ic_t") or 0) < c.min_holdout_ic_t:
            reasons.append(f"holdout IC t-stat {e.get('holdout_ic_t')} < {c.min_holdout_ic_t}")
        if (e.get("wf_folds_positive_frac") or 0) < c.min_wf_folds_positive_frac:
            reasons.append("walk-forward IC not consistently positive")
        if (e.get("net_sharpe") is None) or e["net_sharpe"] < c.min_net_sharpe:
            reasons.append(f"net Sharpe {e.get('net_sharpe')} below {c.min_net_sharpe} after costs")
        if c.must_beat_baselines_net and any(e.get("net_sharpe", -9) <= b for b in e.get("baseline_net_sharpes", {}).values() if b is not None):
            reasons.append("does not beat simple baselines net of costs")
        if (e.get("net_max_dd") or -1) < c.max_drawdown_floor:
            reasons.append(f"net max drawdown {e.get('net_max_dd')} worse than {c.max_drawdown_floor}")
        if c.max_ece is not None and e.get("ece") is not None and e["ece"] > c.max_ece:
            reasons.append(f"calibration error {e['ece']:.3f} > {c.max_ece}")
        if (e.get("n_dates") or 0) < c.min_holdout_dates:
            reasons.append("holdout too short")
        champ = self.champion(m["horizon"])
        if champ:
            ce = self.state["models"][champ]["evidence"]
            if e.get("net_sharpe", -9) < (ce.get("net_sharpe") or 0) + c.min_net_sharpe_margin_vs_champion:
                reasons.append(f"not better than champion {champ} by required margin")
        return {"model_id": model_id, "eligible": not reasons, "reasons": reasons, "criteria": asdict(c)}

    def promote(self, model_id: str, approved_by: str | None) -> dict:
        verdict = self.evaluate(model_id)
        if not verdict["eligible"]:
            self._log("promotion_refused", model_id=model_id, reasons=verdict["reasons"])
            self._save()
            raise PermissionError("; ".join(verdict["reasons"]))
        if not approved_by:
            raise PermissionError("human approval required for production model changes")
        h = self.state["models"][model_id]["horizon"]
        slot = self.state["champion"].setdefault(h, {"current": None, "history": []})
        if slot["current"]:
            self.state["models"][slot["current"]]["stage"] = "retired"
            slot["history"].append(slot["current"])
        slot["current"] = model_id
        self.state["models"][model_id]["stage"] = "champion"
        self._log("promote", model_id=model_id, horizon=h, approved_by=approved_by)
        self._save()
        return verdict

    def rollback(self, horizon: str, approved_by: str) -> str | None:
        slot = self.state["champion"].get(horizon)
        if not slot or not slot["history"]:
            raise ValueError("no previous champion to roll back to")
        bad, prev = slot["current"], slot["history"].pop()
        self.state["models"][bad]["stage"] = "rolled_back"
        self.state["models"][prev]["stage"] = "champion"
        slot["current"] = prev
        self._log("rollback", horizon=horizon, from_model=bad, to_model=prev, approved_by=approved_by)
        self._save()
        return prev
