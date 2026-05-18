import json
from pathlib import Path
from typing import Any, Dict


DEFAULT_MEMORY = {
    "disagreement_penalty": {
        "direction": 0.60,
        "confidence": 0.60,
        "evidence": 0.60,
        "risk": 0.60,
        "horizon": 0.60,
    },
    "source_reliability": {},
    "type_reliability": {},
    "reviews": [],
}


class ReviewMemory:
    def __init__(self, path: str = "data/review_memory.json"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.data = self.load()

    def load(self) -> Dict[str, Any]:
        if not self.path.exists():
            return DEFAULT_MEMORY.copy()

        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return DEFAULT_MEMORY.copy()

    def save(self):
        self.path.write_text(
            json.dumps(self.data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def get_disagreement_penalty(self, disagreement_type: str) -> float:
        return self.data.get("disagreement_penalty", {}).get(disagreement_type, 0.60)

    def add_review(
        self,
        ticker: str,
        date: str,
        uncertainty_result: Dict[str, Any],
    ):
        disagreement = uncertainty_result.get("disagreement", {})
        decision = uncertainty_result.get("adaptive_decision", {})
        evidences = uncertainty_result.get("evidences", [])

        record = {
            "ticker": ticker,
            "date": date,
            "disagreement_total": disagreement.get("total"),
            "disagreement_type": disagreement.get("main_type"),
            "final_action": decision.get("final_action"),
            "final_position": decision.get("final_position"),
            "risk_level": decision.get("risk_level"),
            "evidences": evidences,
        }

        self.data["reviews"].append(record)

        # 先做最小版：记录最近 100 条，避免文件无限增长
        self.data["reviews"] = self.data["reviews"][-100:]

        self.save()