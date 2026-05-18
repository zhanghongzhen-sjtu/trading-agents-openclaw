#!/usr/bin/env python3
"""
复盘记忆更新脚本
================

用途：
根据某只股票后续真实收益，对 review_memory.json 中的分歧惩罚参数进行自我校准。

示例：
python review_update.py --ticker 000630 --return-rate -0.05 --max-drawdown 0.08
"""

import argparse
import json
from pathlib import Path


MEMORY_PATH = Path("data/review_memory.json")


def clamp(x: float, low: float = 0.2, high: float = 1.0) -> float:
    return max(low, min(high, x))


def parse_args():
    parser = argparse.ArgumentParser(description="复盘更新分歧惩罚参数")
    parser.add_argument("--ticker", required=True, help="股票代码，例如 000630")
    parser.add_argument("--return-rate", type=float, required=True, help="后续收益率，例如 -0.05 表示亏损 5%")
    parser.add_argument("--max-drawdown", type=float, default=0.0, help="最大回撤，例如 0.08 表示最大回撤 8%")
    parser.add_argument("--threshold", type=float, default=0.55, help="高分歧阈值，默认 0.55")
    parser.add_argument("--step", type=float, default=0.05, help="惩罚参数调整步长，默认 0.05")
    return parser.parse_args()


def load_memory() -> dict:
    if not MEMORY_PATH.exists():
        raise FileNotFoundError(f"未找到记忆文件：{MEMORY_PATH}")

    return json.loads(MEMORY_PATH.read_text(encoding="utf-8"))


def save_memory(memory: dict):
    MEMORY_PATH.write_text(
        json.dumps(memory, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


def find_latest_review(memory: dict, ticker: str) -> dict | None:
    reviews = memory.get("reviews", [])

    for record in reversed(reviews):
        if str(record.get("ticker", "")).upper() == ticker.upper():
            return record

    return None


def update_penalty(memory: dict, review: dict, return_rate: float, max_drawdown: float, threshold: float, step: float):
    disagreement_total = review.get("disagreement_total", 0) or 0
    disagreement_type = review.get("disagreement_type", "direction") or "direction"

    penalty_map = memory.setdefault("disagreement_penalty", {})
    old_penalty = penalty_map.get(disagreement_type, 0.60)

    reason = "无调整"
    new_penalty = old_penalty

    if disagreement_total >= threshold and return_rate < 0:
        new_penalty = clamp(old_penalty + step)
        reason = "高分歧后亏损，提高该分歧类型惩罚"

    elif disagreement_total >= threshold and return_rate > 0:
        new_penalty = clamp(old_penalty - step / 2)
        reason = "高分歧后盈利，适度降低该分歧类型惩罚"

    elif max_drawdown >= 0.08:
        new_penalty = clamp(old_penalty + step / 2)
        reason = "最大回撤较高，提高风险惩罚"

    penalty_map[disagreement_type] = new_penalty

    review["review_feedback"] = {
        "realized_return": return_rate,
        "max_drawdown": max_drawdown,
        "old_penalty": old_penalty,
        "new_penalty": new_penalty,
        "update_reason": reason,
    }

    return disagreement_type, old_penalty, new_penalty, reason


def main():
    args = parse_args()

    memory = load_memory()
    review = find_latest_review(memory, args.ticker)

    if not review:
        print(f"❌ 未找到股票 {args.ticker} 的历史分析记录")
        return

    dtype, old_p, new_p, reason = update_penalty(
        memory=memory,
        review=review,
        return_rate=args.return_rate,
        max_drawdown=args.max_drawdown,
        threshold=args.threshold,
        step=args.step,
    )

    save_memory(memory)

    print("✅ 复盘记忆已更新")
    print(f"股票：{args.ticker}")
    print(f"分歧类型：{dtype}")
    print(f"旧惩罚参数：{old_p:.3f}")
    print(f"新惩罚参数：{new_p:.3f}")
    print(f"更新原因：{reason}")


if __name__ == "__main__":
    main()