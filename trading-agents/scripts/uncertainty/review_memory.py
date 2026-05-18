import json
from pathlib import Path
from typing import Any, Dict, List, Optional


DEFAULT_MEMORY = {
    "disagreement_penalty": {
        "direction": 0.60,
        "confidence": 0.60,
        "evidence": 0.60,
        "risk": 0.60,
        "horizon": 0.60,
    },
    "source_reliability": {
        "market_report": 0.75,
        "fundamentals_report": 0.85,
        "sentiment_report": 0.60,
        "news_report": 0.70,
        "final_trade_decision": 0.85,
    },
    "type_reliability": {
        "market": 0.75,
        "fundamental": 0.85,
        "sentiment": 0.60,
        "news": 0.70,
        "decision": 0.85,
    },
    "agent_weights": {
        "Market Analyst": 0.70,
        "Fundamentals Analyst": 0.75,
        "Sentiment Analyst": 0.60,
        "News Analyst": 0.65,
        "Risk Manager": 0.80,
    },
    "reviews": [],
}


def clamp(x: float, low: float = 0.2, high: float = 1.0) -> float:
    return max(low, min(high, x))


class ReviewMemory:
    def __init__(self, path: str = "data/review_memory.json"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.data = self.load()

    def load(self) -> Dict[str, Any]:
        if not self.path.exists():
            return json.loads(json.dumps(DEFAULT_MEMORY))

        try:
            loaded = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return json.loads(json.dumps(DEFAULT_MEMORY))

        return self._merge_default(loaded)

    def _merge_default(self, loaded: Dict[str, Any]) -> Dict[str, Any]:
        merged = json.loads(json.dumps(DEFAULT_MEMORY))

        for key, value in loaded.items():
            if isinstance(value, dict) and isinstance(merged.get(key), dict):
                merged[key].update(value)
            else:
                merged[key] = value

        return merged

    def save(self):
        self.path.write_text(
            json.dumps(self.data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def get_disagreement_penalty(self, disagreement_type: str) -> float:
        return self.data.get("disagreement_penalty", {}).get(disagreement_type, 0.60)

    def get_source_reliability(self, source: str) -> float:
        return self.data.get("source_reliability", {}).get(source, 0.50)

    def get_type_reliability(self, evidence_type: str) -> float:
        return self.data.get("type_reliability", {}).get(evidence_type, 0.50)

    def get_agent_weight(self, agent_name: str) -> float:
        return self.data.get("agent_weights", {}).get(agent_name, 0.60)

    def add_review(
        self,
        ticker: str,
        date: str,
        uncertainty_result: Dict[str, Any],
    ):
        disagreement = uncertainty_result.get("disagreement", {})
        decision = uncertainty_result.get("adaptive_decision", {})
        evidences = uncertainty_result.get("evidences", [])
        agent_outputs = uncertainty_result.get("agent_outputs", [])

        record = {
            "ticker": ticker,
            "date": date,
            "disagreement_total": disagreement.get("total"),
            "disagreement_type": disagreement.get("main_type"),
            "final_action": decision.get("final_action"),
            "final_position": decision.get("final_position"),
            "risk_level": decision.get("risk_level"),
            "agent_outputs": agent_outputs,
            "evidences": evidences,
            "review_feedback": None,
        }

        self.data["reviews"].append(record)
        self.data["reviews"] = self.data["reviews"][-200:]
        self.save()

    def find_latest_review(self, ticker: str) -> Optional[Dict[str, Any]]:
        for record in reversed(self.data.get("reviews", [])):
            if str(record.get("ticker", "")).upper() == ticker.upper():
                return record
        return None

    def update_disagreement_penalty(
        self,
        disagreement_type: str,
        old_action: str,
        return_rate: float,
        max_drawdown: float,
        disagreement_total: float,
        threshold: float = 0.55,
        step: float = 0.05,
    ) -> Dict[str, Any]:
        penalty_map = self.data.setdefault("disagreement_penalty", {})
        old_penalty = penalty_map.get(disagreement_type, 0.60)
        new_penalty = old_penalty
        reason = "未达到调整条件"

        bad_outcome = False
        good_outcome = False

        if old_action == "buy":
            bad_outcome = return_rate < 0
            good_outcome = return_rate > 0
        elif old_action == "sell":
            bad_outcome = return_rate > 0
            good_outcome = return_rate < 0
        elif old_action == "hold":
            bad_outcome = abs(return_rate) > 0.06
            good_outcome = abs(return_rate) <= 0.03

        if disagreement_total >= threshold and bad_outcome:
            new_penalty = clamp(old_penalty + step)
            reason = "高分歧后决策结果不佳，提高该分歧类型惩罚"
        elif disagreement_total >= threshold and good_outcome:
            new_penalty = clamp(old_penalty - step / 2)
            reason = "高分歧后决策结果较好，适度降低该分歧类型惩罚"
        elif max_drawdown >= 0.08:
            new_penalty = clamp(old_penalty + step / 2)
            reason = "最大回撤较高，提高风险惩罚"

        penalty_map[disagreement_type] = new_penalty

        return {
            "disagreement_type": disagreement_type,
            "old_penalty": old_penalty,
            "new_penalty": new_penalty,
            "reason": reason,
        }

    def update_source_and_type_reliability(
        self,
        evidences: List[Dict[str, Any]],
        return_rate: float,
        step: float = 0.04,
    ) -> List[Dict[str, Any]]:
        updates = []

        source_map = self.data.setdefault("source_reliability", {})
        type_map = self.data.setdefault("type_reliability", {})

        for e in evidences:
            source = e.get("source", "unknown")
            evidence_type = e.get("evidence_type", "unknown")
            stance = e.get("stance", "neutral")

            if stance == "bullish":
                evidence_correct = return_rate > 0
            elif stance == "bearish":
                evidence_correct = return_rate < 0
            else:
                evidence_correct = abs(return_rate) <= 0.03

            old_source = source_map.get(source, 0.50)
            old_type = type_map.get(evidence_type, 0.50)

            if evidence_correct:
                new_source = clamp(old_source + step)
                new_type = clamp(old_type + step)
                reason = "证据方向与后续走势一致，提高可信度"
            else:
                new_source = clamp(old_source - step)
                new_type = clamp(old_type - step)
                reason = "证据方向与后续走势不一致，降低可信度"

            source_map[source] = new_source
            type_map[evidence_type] = new_type

            updates.append({
                "evidence_id": e.get("evidence_id"),
                "source": source,
                "evidence_type": evidence_type,
                "stance": stance,
                "old_source_reliability": old_source,
                "new_source_reliability": new_source,
                "old_type_reliability": old_type,
                "new_type_reliability": new_type,
                "reason": reason,
            })

        return updates

    def update_agent_weights(
        self,
        agent_outputs: List[Dict[str, Any]],
        return_rate: float,
        step: float = 0.04,
    ) -> List[Dict[str, Any]]:
        updates = []
        agent_map = self.data.setdefault("agent_weights", {})

        for agent in agent_outputs:
            name = agent.get("agent_name", "unknown")
            decision = agent.get("decision", "hold")

            if decision == "buy":
                correct = return_rate > 0
            elif decision == "sell":
                correct = return_rate < 0
            else:
                correct = abs(return_rate) <= 0.03

            old_weight = agent_map.get(name, 0.60)

            if correct:
                new_weight = clamp(old_weight + step)
                reason = "智能体方向与后续走势一致，提高权重"
            else:
                new_weight = clamp(old_weight - step)
                reason = "智能体方向与后续走势不一致，降低权重"

            agent_map[name] = new_weight

            updates.append({
                "agent_name": name,
                "decision": decision,
                "old_weight": old_weight,
                "new_weight": new_weight,
                "reason": reason,
            })

        return updates

    def apply_feedback(
        self,
        ticker: str,
        return_rate: float,
        max_drawdown: float,
        threshold: float = 0.55,
        step: float = 0.05,
    ) -> Dict[str, Any]:
        review = self.find_latest_review(ticker)

        if not review:
            raise ValueError(f"未找到股票 {ticker} 的历史分析记录")

        disagreement_total = review.get("disagreement_total", 0) or 0
        disagreement_type = review.get("disagreement_type", "direction") or "direction"
        final_action = review.get("final_action", "hold") or "hold"
        evidences = review.get("evidences", [])
        agent_outputs = review.get("agent_outputs", [])

        penalty_update = self.update_disagreement_penalty(
            disagreement_type=disagreement_type,
            old_action=final_action,
            return_rate=return_rate,
            max_drawdown=max_drawdown,
            disagreement_total=disagreement_total,
            threshold=threshold,
            step=step,
        )

        evidence_updates = self.update_source_and_type_reliability(
            evidences=evidences,
            return_rate=return_rate,
            step=step * 0.8,
        )

        agent_updates = self.update_agent_weights(
            agent_outputs=agent_outputs,
            return_rate=return_rate,
            step=step * 0.8,
        )

        feedback = {
            "realized_return": return_rate,
            "max_drawdown": max_drawdown,
            "penalty_update": penalty_update,
            "evidence_updates": evidence_updates,
            "agent_updates": agent_updates,
        }

        review["review_feedback"] = feedback
        self.save()

        return feedback