from dataclasses import dataclass, field
from typing import Dict, List, Literal
import math
import statistics

Decision = Literal["buy", "hold", "sell"]
Horizon = Literal["short", "mid", "long"]


@dataclass
class AgentOutput:
    agent_name: str
    role: str
    decision: Decision
    confidence: float
    evidence_ids: List[str] = field(default_factory=list)
    risk_points: List[str] = field(default_factory=list)
    suggested_position: float = 0.0
    horizon: Horizon = "short"
    reasoning_summary: str = ""


@dataclass
class DisagreementResult:
    direction: float
    confidence: float
    evidence: float
    risk: float
    horizon: float
    total: float
    main_type: str


def _entropy_distribution(counts: Dict[str, float], num_classes: int) -> float:
    total = sum(counts.values())
    if total <= 0:
        return 0.0

    ent = 0.0
    for v in counts.values():
        if v <= 0:
            continue
        p = v / total
        ent -= p * math.log(p)

    return ent / math.log(num_classes)


def compute_direction_disagreement(outputs: List[AgentOutput]) -> float:
    counts = {"buy": 0.0, "hold": 0.0, "sell": 0.0}

    for o in outputs:
        counts[o.decision] += max(o.confidence, 0.05)

    return _entropy_distribution(counts, 3)


def compute_confidence_disagreement(outputs: List[AgentOutput]) -> float:
    if len(outputs) <= 1:
        return 0.0

    vals = [o.confidence for o in outputs]
    return statistics.pstdev(vals)


def compute_evidence_disagreement(
    outputs: List[AgentOutput],
    evidence_stance: Dict[str, str],
    evidence_weight: Dict[str, float],
) -> float:
    w_buy = 0.0
    w_sell = 0.0
    w_hold = 0.0
    used = set()

    for o in outputs:
        for eid in o.evidence_ids:
            if eid in used:
                continue

            used.add(eid)
            stance = evidence_stance.get(eid, "neutral")
            weight = evidence_weight.get(eid, 0.5)

            if stance == "bullish":
                w_buy += weight
            elif stance == "bearish":
                w_sell += weight
            else:
                w_hold += weight

    denom = w_buy + w_sell + w_hold + 1e-9
    return min(w_buy, w_sell) / denom


def compute_risk_disagreement(outputs: List[AgentOutput]) -> float:
    risk_outputs = [
        o for o in outputs
        if "risk" in o.role.lower() or "risk" in o.agent_name.lower()
    ]

    return_outputs = [o for o in outputs if o not in risk_outputs]

    if not risk_outputs or not return_outputs:
        return 0.0

    p_risk = sum(o.suggested_position for o in risk_outputs) / len(risk_outputs)
    p_return = sum(o.suggested_position for o in return_outputs) / len(return_outputs)

    return abs(p_return - p_risk)


def compute_horizon_disagreement(outputs: List[AgentOutput]) -> float:
    counts = {"short": 0.0, "mid": 0.0, "long": 0.0}

    for o in outputs:
        counts[o.horizon] += max(o.confidence, 0.05)

    return _entropy_distribution(counts, 3)


def _diagnose_main_type(values: Dict[str, float]) -> str:
    return max(values.items(), key=lambda kv: kv[1])[0]


def compute_disagreement(
    outputs: List[AgentOutput],
    evidence_stance: Dict[str, str],
    evidence_weight: Dict[str, float],
    lambdas: Dict[str, float] | None = None,
) -> DisagreementResult:
    if lambdas is None:
        lambdas = {
            "direction": 0.28,
            "confidence": 0.17,
            "evidence": 0.22,
            "risk": 0.23,
            "horizon": 0.10,
        }

    d_direction = compute_direction_disagreement(outputs)
    d_confidence = compute_confidence_disagreement(outputs)
    d_evidence = compute_evidence_disagreement(outputs, evidence_stance, evidence_weight)
    d_risk = compute_risk_disagreement(outputs)
    d_horizon = compute_horizon_disagreement(outputs)

    values = {
        "direction": d_direction,
        "confidence": d_confidence,
        "evidence": d_evidence,
        "risk": d_risk,
        "horizon": d_horizon,
    }

    total = sum(lambdas[k] * values[k] for k in values)

    return DisagreementResult(
        direction=d_direction,
        confidence=d_confidence,
        evidence=d_evidence,
        risk=d_risk,
        horizon=d_horizon,
        total=total,
        main_type=_diagnose_main_type(values),
    )