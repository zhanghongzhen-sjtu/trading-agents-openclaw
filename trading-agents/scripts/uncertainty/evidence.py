from dataclasses import dataclass, field
from typing import List, Literal

Stance = Literal["bullish", "neutral", "bearish"]


@dataclass
class Evidence:
    evidence_id: str
    ticker: str
    source: str
    evidence_type: str
    content: str
    stance: Stance = "neutral"
    relevance_score: float = 0.5
    credibility_score: float = 0.5
    conflict_ids: List[str] = field(default_factory=list)


SOURCE_AUTHORITY = {
    "market_report": 0.75,
    "fundamentals_report": 0.90,
    "sentiment_report": 0.60,
    "news_report": 0.70,
    "final_trade_decision": 0.85,
    "mx_context": 0.80,
    "unknown": 0.50,
}


TYPE_RELIABILITY = {
    "market": 0.75,
    "fundamental": 0.90,
    "sentiment": 0.55,
    "news": 0.70,
    "decision": 0.85,
    "mx": 0.80,
    "unknown": 0.50,
}


def clamp(x: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, x))


def infer_stance_from_decision(decision: str) -> Stance:
    if decision == "buy":
        return "bullish"
    if decision == "sell":
        return "bearish"
    return "neutral"


def estimate_text_quality(text: str) -> float:
    """
    简单估计文本质量：
    文本越完整、包含数据越多，质量越高。
    """
    if not text:
        return 0.30

    length_score = min(len(text) / 3000, 1.0)

    data_keywords = [
        "%", "同比", "环比", "营收", "利润", "ROE", "PE", "PB",
        "均线", "RSI", "MACD", "成交量", "现金流", "毛利率",
        "市盈率", "市净率", "目标价", "止损"
    ]
    keyword_hits = sum(1 for kw in data_keywords if kw in text)
    keyword_score = min(keyword_hits / 8, 1.0)

    return clamp(0.45 * length_score + 0.55 * keyword_score)


def compute_consistency(e: Evidence, all_evidences: List[Evidence]) -> float:
    """
    跨源一致性：
    同方向证据越多，一致性越高。
    """
    if not all_evidences:
        return 0.5

    same = 0
    opposite = 0

    for other in all_evidences:
        if other.evidence_id == e.evidence_id:
            continue

        if e.stance == "neutral" or other.stance == "neutral":
            continue

        if e.stance == other.stance:
            same += 1
        else:
            opposite += 1

    total = same + opposite
    if total == 0:
        return 0.5

    return clamp(same / total)


def score_evidence(
    e: Evidence,
    all_evidences: List[Evidence],
    historical_reliability: float = 0.5,
    alpha: float = 0.25,
    beta: float = 0.20,
    gamma: float = 0.20,
    delta: float = 0.20,
    eta: float = 0.15,
) -> Evidence:
    """
    证据可信度 =
    来源权威性 + 文本质量/时效替代项 + 跨源一致性 + 类型可靠性 + 历史有效性
    """
    source_score = SOURCE_AUTHORITY.get(e.source, SOURCE_AUTHORITY["unknown"])
    quality_score = estimate_text_quality(e.content)
    consistency_score = compute_consistency(e, all_evidences)
    type_score = TYPE_RELIABILITY.get(e.evidence_type, TYPE_RELIABILITY["unknown"])

    e.credibility_score = clamp(
        alpha * source_score
        + beta * quality_score
        + gamma * consistency_score
        + delta * type_score
        + eta * historical_reliability
    )

    return e


def detect_conflicts(evidences: List[Evidence]) -> List[Evidence]:
    for i, ei in enumerate(evidences):
        for j, ej in enumerate(evidences):
            if i >= j:
                continue

            opposite = (
                (ei.stance == "bullish" and ej.stance == "bearish")
                or (ei.stance == "bearish" and ej.stance == "bullish")
            )

            if opposite:
                ei.conflict_ids.append(ej.evidence_id)
                ej.conflict_ids.append(ei.evidence_id)

    return evidences