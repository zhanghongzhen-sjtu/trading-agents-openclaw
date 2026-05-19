#!/usr/bin/env python3
"""
回测结果图表生成脚本

输入：
data/backtest_results.csv
data/backtest_summary.csv

输出：
data/fig_strategy_return.png
data/fig_position.png
data/fig_disagreement.png
data/fig_risk_evidence.png
"""

import csv
from pathlib import Path

import matplotlib.pyplot as plt


RESULT_PATH = Path("data/backtest_results.csv")
SUMMARY_PATH = Path("data/backtest_summary.csv")
OUT_DIR = Path("data")


MODEL_NAME_MAP = {
    "ours-full": "Ours-full",
    "wo-cw-rag": "w/o CW-RAG",
    "wo-dadm": "w/o DADM",
    "wo-rmse": "w/o RMSE",
}


def read_csv(path: Path):
    if not path.exists():
        raise FileNotFoundError(f"找不到文件：{path}")

    with path.open("r", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def to_float(x, default=0.0):
    try:
        return float(x)
    except Exception:
        return default


def plot_bar(rows, metric, title, ylabel, filename, percent=False):
    labels = [MODEL_NAME_MAP.get(r["mode"], r["mode"]) for r in rows]
    values = [to_float(r.get(metric, 0)) for r in rows]

    if percent:
        plot_values = [v * 100 for v in values]
    else:
        plot_values = values

    plt.figure(figsize=(9, 5))
    bars = plt.bar(labels, plot_values)

    plt.title(title)
    plt.ylabel(ylabel)
    plt.xticks(rotation=15, ha="right")

    for bar, value in zip(bars, plot_values):
        plt.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height(),
            f"{value:.2f}" + ("%" if percent else ""),
            ha="center",
            va="bottom",
            fontsize=9,
        )

    plt.tight_layout()
    output_path = OUT_DIR / filename
    plt.savefig(output_path, dpi=200)
    plt.close()

    print(f"已生成：{output_path}")


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    rows = read_csv(RESULT_PATH)

    # 图 1：策略收益对比
    plot_bar(
        rows,
        metric="strategy_return",
        title="Single-case Simulation: Strategy Return",
        ylabel="Strategy Return (%)",
        filename="fig_strategy_return.png",
        percent=True,
    )

    # 图 2：建议仓位对比
    plot_bar(
        rows,
        metric="position",
        title="Ablation Study: Suggested Position",
        ylabel="Position (%)",
        filename="fig_position.png",
        percent=True,
    )

    # 图 3：综合分歧指数对比
    plot_bar(
        rows,
        metric="disagreement_total",
        title="Ablation Study: Total Disagreement",
        ylabel="Disagreement Score",
        filename="fig_disagreement.png",
        percent=False,
    )

    # 图 4：证据分歧对比
    plot_bar(
        rows,
        metric="evidence_disagreement",
        title="Ablation Study: Evidence Disagreement",
        ylabel="Evidence Disagreement",
        filename="fig_evidence_disagreement.png",
        percent=False,
    )

    # 图 5：风险分歧对比
    plot_bar(
        rows,
        metric="risk_disagreement",
        title="Ablation Study: Risk Disagreement",
        ylabel="Risk Disagreement",
        filename="fig_risk_disagreement.png",
        percent=False,
    )

    print("✅ 图表生成完成")


if __name__ == "__main__":
    main()