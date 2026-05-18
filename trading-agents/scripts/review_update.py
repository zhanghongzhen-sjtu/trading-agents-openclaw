#!/usr/bin/env python3
"""
复盘记忆更新脚本
================

用途：
根据某只股票后续真实收益，对 review_memory.json 中的分歧惩罚参数、
证据源可信度、证据类型可信度和智能体权重进行自我校准。

示例：
python review_update.py --ticker 000630 --return-rate -0.05 --max-drawdown 0.08
"""

import argparse

from uncertainty.review_memory import ReviewMemory


def parse_args():
    parser = argparse.ArgumentParser(description="复盘更新记忆参数")
    parser.add_argument("--ticker", required=True, help="股票代码，例如 000630")
    parser.add_argument("--return-rate", type=float, required=True, help="后续收益率，例如 -0.05 表示亏损 5%")
    parser.add_argument("--max-drawdown", type=float, default=0.0, help="最大回撤，例如 0.08 表示最大回撤 8%")
    parser.add_argument("--threshold", type=float, default=0.55, help="高分歧阈值，默认 0.55")
    parser.add_argument("--step", type=float, default=0.05, help="参数调整步长，默认 0.05")
    return parser.parse_args()


def main():
    args = parse_args()

    memory = ReviewMemory()

    try:
        feedback = memory.apply_feedback(
            ticker=args.ticker,
            return_rate=args.return_rate,
            max_drawdown=args.max_drawdown,
            threshold=args.threshold,
            step=args.step,
        )
    except ValueError as e:
        print(f"❌ {e}")
        return

    print("✅ 复盘记忆已更新")
    print(f"股票：{args.ticker}")
    print(f"后续收益率：{args.return_rate:.2%}")
    print(f"最大回撤：{args.max_drawdown:.2%}")

    penalty = feedback.get("penalty_update", {})
    print("\n分歧惩罚参数更新：")
    print(f"- 分歧类型：{penalty.get('disagreement_type')}")
    print(f"- 旧参数：{penalty.get('old_penalty', 0):.3f}")
    print(f"- 新参数：{penalty.get('new_penalty', 0):.3f}")
    print(f"- 原因：{penalty.get('reason')}")

    print("\n证据可信度更新：")
    for item in feedback.get("evidence_updates", []):
        print(
            f"- {item.get('evidence_id')} | "
            f"source {item.get('old_source_reliability'):.3f} → {item.get('new_source_reliability'):.3f} | "
            f"type {item.get('old_type_reliability'):.3f} → {item.get('new_type_reliability'):.3f}"
        )

    print("\n智能体权重更新：")
    for item in feedback.get("agent_updates", []):
        print(
            f"- {item.get('agent_name')} | "
            f"{item.get('old_weight'):.3f} → {item.get('new_weight'):.3f} | "
            f"{item.get('reason')}"
        )


if __name__ == "__main__":
    main()