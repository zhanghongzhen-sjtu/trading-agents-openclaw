import csv
from pathlib import Path
import matplotlib.pyplot as plt


DATA_PATH = Path("data/backtest_summary.csv")
OUT_DIR = Path("data")
OUT_DIR.mkdir(parents=True, exist_ok=True)


def read_summary_csv(path: Path):
    rows = []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append({
                "mode": row["mode"],
                "num_trades": int(row["num_trades"]),
                "total_return": float(row["total_return"]),
                "avg_return": float(row["avg_return"]),
                "volatility": float(row["volatility"]),
                "sharpe_like": float(row["sharpe_like"]),
                "win_rate": float(row["win_rate"]),
                "max_drawdown": float(row["max_drawdown"]),
                "avg_excess_vs_stock": float(row.get("avg_excess_vs_stock", 0.0)),
                "avg_excess_vs_market": float(row.get("avg_excess_vs_market", 0.0)),
            })
    return rows


def plot_bar(rows, key, title, ylabel, filename, percent=False):
    modes = [r["mode"] for r in rows]
    values = [r[key] for r in rows]

    plt.figure(figsize=(8, 5))
    bars = plt.bar(modes, values)

    plt.title(title)
    plt.ylabel(ylabel)
    plt.xlabel("Mode")

    for bar, v in zip(bars, values):
        if percent:
            text = f"{v:.2%}"
        else:
            text = f"{v:.3f}"
        plt.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height(),
            text,
            ha="center",
            va="bottom"
        )

    plt.tight_layout()
    out_path = OUT_DIR / filename
    plt.savefig(out_path, dpi=200)
    plt.close()
    print(f"已生成图表: {out_path}")


def main():
    if not DATA_PATH.exists():
        print(f"未找到文件: {DATA_PATH}")
        return

    rows = read_summary_csv(DATA_PATH)

    plot_bar(
        rows,
        key="total_return",
        title="Backtest Total Return by Mode",
        ylabel="Total Return",
        filename="fig_total_return.png",
        percent=True,
    )

    plot_bar(
        rows,
        key="max_drawdown",
        title="Backtest Max Drawdown by Mode",
        ylabel="Max Drawdown",
        filename="fig_max_drawdown.png",
        percent=True,
    )

    plot_bar(
        rows,
        key="win_rate",
        title="Backtest Win Rate by Mode",
        ylabel="Win Rate",
        filename="fig_win_rate.png",
        percent=True,
    )

    plot_bar(
        rows,
        key="sharpe_like",
        title="Backtest Sharpe-like by Mode",
        ylabel="Sharpe-like",
        filename="fig_sharpe_like.png",
        percent=False,
    )

    plot_bar(
        rows,
        key="avg_excess_vs_stock",
        title="Average Excess Return vs Stock by Mode",
        ylabel="Avg Excess Return vs Stock",
        filename="fig_excess_vs_stock.png",
        percent=True,
    )

    plot_bar(
        rows,
        key="avg_excess_vs_market",
        title="Average Excess Return vs Market by Mode",
        ylabel="Avg Excess Return vs Market",
        filename="fig_excess_vs_market.png",
        percent=True,
    )


if __name__ == "__main__":
    main()