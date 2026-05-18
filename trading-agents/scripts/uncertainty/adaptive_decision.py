from dataclasses import dataclass
from typing import List, Literal

from .disagreement import AgentOutput, DisagreementResult

FinalAction = Literal["buy", "hold", "sell"]


@dataclass
class DecisionResult:
    ticker: str
    final_action: FinalAction
    final_position: float
    disagreement_score: float
    disagreement_type: str
    control_action: str
    risk_level: str
    explanation: str


def majority_action(outputs: List[AgentOutput]) -> str:
    scores = {"buy": 0.0, "hold": 0.0, "sell": 0.0}

    for o in outputs:
        scores[o.decision] += o.confidence

    return max(scores.items(), key=lambda kv: kv[1])[0]


def average_position(outputs: List[AgentOutput]) -> float:
    if not outputs:
        return 0.0

    return sum(o.suggested_position for o in outputs) / len(outputs)


def diagnose_control_action(
    disagreement: DisagreementResult,
    theta2: float = 0.55,
    theta3: float = 0.75,
) -> str:
    if disagreement.total >= theta3:
        return "risk_veto_or_hold"

    if disagreement.total < theta2:
        return "normal"

    mapping = {
        "direction": "second_round_debate",
        "evidence": "retrieve_again_and_filter",
        "risk": "risk_arbitration_reduce_position",
        "confidence": "ask_for_more_evidence_reduce_overconfidence",
        "horizon": "split_short_mid_long_strategy",
    }

    return mapping.get(disagreement.main_type, "reduce_position")


def apply_adaptive_decision(
    ticker: str,
    outputs: List[AgentOutput],
    disagreement: DisagreementResult,
    rho: float = 0.6,
    p_min: float = 0.10,
) -> DecisionResult:
    base_action = majority_action(outputs)
    p0 = average_position(outputs)

    control_action = diagnose_control_action(disagreement)

    if control_action == "risk_veto_or_hold":
        final_action = "hold"
        final_position = 0.0
        risk_level = "high"
    else:
        adjusted_position = p0 * (1 - rho * disagreement.total)
        final_position = max(0.0, min(1.0, adjusted_position))

        if final_position < p_min:
            final_action = "hold"
        else:
            final_action = base_action

        risk_level = "medium" if disagreement.total >= 0.55 else "low"

    explanation = (
        f"综合分歧指数为 {disagreement.total:.3f}，"
        f"主要分歧类型为 {disagreement.main_type}，"
        f"触发控制动作为 {control_action}。"
    )

    return DecisionResult(
        ticker=ticker,
        final_action=final_action,
        final_position=final_position,
        disagreement_score=disagreement.total,
        disagreement_type=disagreement.main_type,
        control_action=control_action,
        risk_level=risk_level,
        explanation=explanation,
    )