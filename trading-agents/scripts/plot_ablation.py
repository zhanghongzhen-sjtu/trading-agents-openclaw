#!/usr/bin/env python3
"""
消融实验结果可视化脚本

用法：
python plot_ablation.py

输入：
data/ablation_results.json

输出：
data/ablation_comparison.png
data/ablation_results.csv
"""

import json
import csv
from pathlib import Path

import matplotlib.pyplot as plt


RESULT_PATH = Path("data/ablation_results.json")
CSV_PATH = Path("data/ablation_results.csv")
FIG_PATH = Path("data/ablation_comparison.png")


def load_results():
    if not RESULT_PATH.exists():
        raise FileNotFoundError(f"未找到 {RESULT_PATH}，请先运行四种消融实验")

    return json.loads(RESULT_PATH.read_text(encoding="utf-8"))


def save_csv(results):
    rows = []

    for model_name, item in results.items():
        disagreement = item.get("disagreement", {})
        decision = item.get("adaptive_decision", {})
        evidences = item.get("evidences", [])

        avg_credibility = 0.0
        if evidences:
            avg_credibility = sum(e.get("credibility_score", 0) for e in evidences) / len(evidences)

        rows.append({
            "model": model_name,
            "disagreement_total": disagreement.get("total", 0),
            "direction_disagreement": disagreement.get("direction", 0),
            "evidence_disagreement": disagreement.get("evidence", 0),
            "risk_disagreement": disagreement.get("risk", 0),
            "horizon_disagreement": disagreement.get("horizon", 0),
            "final_position": decision.get("final_position", 0),
            "avg_credibility": avg_credibility,
            "final_action": decision.get("final_action", ""),
            "risk_level": decision.get("risk_level", ""),
        })

    CSV_PATH.parent.mkdir(parents=True, exist_ok=True)

    with CSV_PATH.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    return rows


def plot_metric(rows, metric, title, ylabel, output_path):
    labels = [r["model"] for r in rows]
    values = [float(r[metric]) for r in rows]

    plt.figure(figsize=(10, 5))
    plt.bar(labels, values)
    plt.title(title)
    plt.ylabel(ylabel)
    plt.xticks(rotation=20, ha="right")
    plt.tight_layout()
    plt.savefig(output_path, dpi=200)
    plt.close()


def main():
    results = load_results()
    rows = save_csv(results)

    FIG_PATH.parent.mkdir(parents=True, exist_ok=True)

    plot_metric(
        rows,
        "disagreement_total",
        "Ablation Study: 综合分歧指数对比",
        "Disagreement Score",
        Path("data/ablation_disagreement.png"),
    )

    plot_metric(
        rows,
        "final_position",
        "Ablation Study: 建议仓位对比",
        "Final Position",
        Path("data/ablation_position.png"),
    )

    plot_metric(
        rows,
        "avg_credibility",
        "Ablation Study: 平均证据可信度对比",
        "Average Evidence Credibility",
        Path("data/ablation_credibility.png"),
    )

    print("✅ 消融实验图表已生成")
    print(f"- CSV: {CSV_PATH}")
    print("- 图1: data/ablation_disagreement.png")
    print("- 图2: data/ablation_position.png")
    print("- 图3: data/ablation_credibility.png")


if __name__ == "__main__":
    main()