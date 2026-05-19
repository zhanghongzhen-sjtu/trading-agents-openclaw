import csv
from pathlib import Path
from collections import defaultdict
import matplotlib.pyplot as plt


DATA_PATH = Path("data/backtest_results.csv")
OUT_DIR = Path("data")
OUT_DIR.mkdir(parents=True, exist_ok=True)

MODES = ["ours-full", "wo-cw-rag", "wo-dadm", "wo-rmse"]


def load_rows(path: Path):
    rows = []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append({
                "ticker": row["ticker"],
                "date": row["date"],
                "mode": row["mode"],
                "action": row["action"],
                "position": float(row["position"]),
                "stock_return": float(row["stock_return"]),
                "market_benchmark": row["market_benchmark"],
                "market_benchmark_return": float(row["market_benchmark_return"]),
                "holding_return": float(row["holding_return"]),
                "strategy_return": float(row["strategy_return"]),
                "excess_vs_stock": float(row["excess_vs_stock"]),
                "excess_vs_market": float(row["excess_vs_market"]),
                "disagreement_total": float(row["disagreement_total"]),
                "evidence_disagreement": float(row["evidence_disagreement"]),
                "risk_disagreement": float(row["risk_disagreement"]),
            })
    return rows


def mean(values):
    return sum(values) / len(values) if values else 0.0


def plot_model_returns_vs_market(rows):
    """
    图1：
    四模型在各日期上的平均策略收益折线图，
    并叠加大盘收益折线。
    """
    grouped = defaultdict(list)
    market_grouped = defaultdict(list)

    for row in rows:
        grouped[(row["date"], row["mode"])].append(row["strategy_return"])
        market_grouped[row["date"]].append(row["market_benchmark_return"])

    dates = sorted({row["date"] for row in rows})

    plt.figure(figsize=(10, 6))

    for mode in MODES:
        ys = []
        for d in dates:
            ys.append(mean(grouped[(d, mode)]))
        plt.plot(dates, ys, marker="o", label=mode)

    market_ys = [mean(market_grouped[d]) for d in dates]
    plt.plot(dates, market_ys, marker="o", linestyle="--", label="CSI300")

    plt.title("Average Strategy Return by Date (Models vs Market)")
    plt.xlabel("Date")
    plt.ylabel("Return")
    plt.xticks(rotation=30)
    plt.legend()
    plt.tight_layout()

    out_path = OUT_DIR / "fig_line_model_vs_market.png"
    plt.savefig(out_path, dpi=200)
    plt.close()
    print(f"已生成图表: {out_path}")


def plot_normalized_stocks_vs_market(rows):
    """
    图2：
    各股票真实持有期收益归一化后的累计走势，
    并与大盘进行对比。
    """
    ticker_grouped = defaultdict(list)
    for row in rows:
        # 只需要每个 ticker/date 一份真实收益即可
        ticker_grouped[row["ticker"]].append((row["date"], row["stock_return"]))

    dates = sorted({row["date"] for row in rows})

    # 取每个日期一份大盘收益（虽然每条记录里都有，但内容相同）
    market_by_date = {}
    for row in rows:
        if row["date"] not in market_by_date:
            market_by_date[row["date"]] = row["market_benchmark_return"]

    plt.figure(figsize=(10, 6))

    # 每只股票画一条归一化曲线
    for ticker, items in ticker_grouped.items():
        items = sorted(set(items), key=lambda x: x[0])
        nav = 1.0
        ys = []
        xs = []
        for d, ret in items:
            nav *= (1 + ret)
            xs.append(d)
            ys.append(nav)
        plt.plot(xs, ys, marker="o", label=ticker)

    # 大盘归一化曲线
    market_nav = 1.0
    market_xs = []
    market_ys = []
    for d in dates:
        market_nav *= (1 + market_by_date[d])
        market_xs.append(d)
        market_ys.append(market_nav)

    plt.plot(market_xs, market_ys, marker="o", linestyle="--", label="CSI300")

    plt.title("Normalized Stock Changes vs Market")
    plt.xlabel("Date")
    plt.ylabel("Normalized Net Value")
    plt.xticks(rotation=30)
    plt.legend()
    plt.tight_layout()

    out_path = OUT_DIR / "fig_line_normalized_stocks_vs_market.png"
    plt.savefig(out_path, dpi=200)
    plt.close()
    print(f"已生成图表: {out_path}")


def main():
    if not DATA_PATH.exists():
        print(f"未找到文件: {DATA_PATH}")
        return

    rows = load_rows(DATA_PATH)

    plot_model_returns_vs_market(rows)
    plot_normalized_stocks_vs_market(rows)


if __name__ == "__main__":
    main()