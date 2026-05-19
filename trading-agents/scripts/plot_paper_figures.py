import csv
import json
from pathlib import Path

import matplotlib.pyplot as plt


DATA_DIR = Path("data")
ABLATION_PATH = DATA_DIR / "ablation_results.json"
ABLATION_CACHE_PATH = DATA_DIR / "ablation_cache" / "000630_cn_2026-05-15_ablation_results.json"
SUMMARY_PATH = DATA_DIR / "backtest_summary_4stocks.csv"
RESULTS_PATH = DATA_DIR / "backtest_results_4stocks.csv"


COLORS = {
    "ours-full": "#2A6FBB",
    "wo-cw-rag": "#7A8A99",
    "wo-dadm": "#D97904",
    "wo-rm": "#8B5FBF",
    "wo-rmse": "#8B5FBF",
}

LABELS = {
    "ours-full": "Ours-full",
    "wo-cw-rag": "w/o CW-RAG",
    "wo-dadm": "w/o DADM",
    "wo-rm": "w/o RM",
    "wo-rmse": "w/o RM",
}

MODE_ORDER = ["ours-full", "wo-cw-rag", "wo-dadm", "wo-rmse", "wo-rm"]


def setup_style():
    plt.rcParams.update({
        "figure.dpi": 160,
        "savefig.dpi": 320,
        "font.family": "DejaVu Sans",
        "axes.edgecolor": "#333333",
        "axes.labelcolor": "#222222",
        "axes.titleweight": "bold",
        "axes.grid": True,
        "grid.color": "#D8DEE6",
        "grid.linewidth": 0.8,
        "grid.alpha": 0.8,
        "legend.frameon": False,
        "xtick.color": "#222222",
        "ytick.color": "#222222",
    })


def save_bar(filename, labels, values, title, ylabel, percent=False):
    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    colors = [COLORS.get(k, "#4C78A8") for k in labels]
    text_labels = [LABELS.get(k, k) for k in labels]
    bars = ax.bar(text_labels, values, color=colors, width=0.62)
    ax.set_title(title, pad=12)
    ax.set_ylabel(ylabel)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.axhline(0, color="#333333", linewidth=0.8)
    for bar, value in zip(bars, values):
        label = f"{value:.2%}" if percent else f"{value:.3f}"
        va = "bottom" if value >= 0 else "top"
        offset = 0.003 if percent else 0.01
        y = value + offset if value >= 0 else value - offset
        ax.text(bar.get_x() + bar.get_width() / 2, y, label, ha="center", va=va, fontsize=9)
    fig.tight_layout()
    fig.savefig(DATA_DIR / filename, bbox_inches="tight")
    plt.close(fig)


def read_summary():
    with SUMMARY_PATH.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def normalize_ablation_item(item):
    if "uncertainty_analysis" in item:
        item = item["uncertainty_analysis"]
    return item


def read_ablation():
    path = ABLATION_CACHE_PATH if ABLATION_CACHE_PATH.exists() else ABLATION_PATH
    data = json.loads(path.read_text(encoding="utf-8"))
    ordered = {}
    for mode in MODE_ORDER:
        if mode in data:
            output_mode = "wo-rm" if mode == "wo-rmse" else mode
            ordered[output_mode] = normalize_ablation_item(data[mode])
    for mode, item in data.items():
        output_mode = "wo-rm" if mode == "wo-rmse" else mode
        if output_mode not in ordered:
            ordered[output_mode] = normalize_ablation_item(item)
    return ordered


def plot_ablation():
    data = read_ablation()
    modes = list(data.keys())
    disagreement = [float(data[m]["disagreement"]["total"]) for m in modes]
    position = [float(data[m]["adaptive_decision"]["final_position"]) for m in modes]
    save_bar(
        "fig_paper_disagreement.png",
        modes,
        disagreement,
        "Disagreement Score by Model",
        "Disagreement score",
        percent=False,
    )
    save_bar(
        "fig_paper_position.png",
        modes,
        position,
        "Risk-adjusted Position by Model",
        "Suggested position",
        percent=True,
    )


def plot_summary():
    rows = read_summary()
    modes = [r["mode"] for r in rows]
    total_return = [float(r["total_return"]) for r in rows]
    max_drawdown = [float(r["max_drawdown"]) for r in rows]
    sharpe = [float(r["sharpe_like"]) for r in rows]
    save_bar(
        "fig_paper_total_return_4stocks.png",
        modes,
        total_return,
        "Backtest Total Return",
        "Total return",
        percent=True,
    )
    save_bar(
        "fig_paper_max_drawdown_4stocks.png",
        modes,
        max_drawdown,
        "Backtest Maximum Drawdown",
        "Maximum drawdown",
        percent=True,
    )
    save_bar(
        "fig_paper_sharpe_like_4stocks.png",
        modes,
        sharpe,
        "Sharpe-like Risk-adjusted Return",
        "Sharpe-like",
        percent=False,
    )


def plot_equity_curve():
    rows = []
    with RESULTS_PATH.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        return
    modes = list(dict.fromkeys(r["mode"] for r in rows))
    fig, ax = plt.subplots(figsize=(7.6, 4.4))
    for mode in modes:
        vals = [float(r["strategy_return"]) for r in rows if r["mode"] == mode]
        equity = []
        current = 1.0
        for ret in vals:
            current *= 1.0 + ret
            equity.append(current)
        ax.plot(
            range(1, len(equity) + 1),
            equity,
            linewidth=2.2 if mode == "ours-full" else 1.7,
            color=COLORS.get(mode, "#4C78A8"),
            label=LABELS.get(mode, mode),
        )
    ax.set_title("Normalized Strategy Equity Curve", pad=12)
    ax.set_xlabel("Backtest sample")
    ax.set_ylabel("Normalized equity")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.legend(ncol=2)
    fig.tight_layout()
    fig.savefig(DATA_DIR / "fig_paper_equity_curve_4stocks.png", bbox_inches="tight")
    plt.close(fig)


def main():
    setup_style()
    plot_ablation()
    plot_summary()
    plot_equity_curve()


if __name__ == "__main__":
    main()
