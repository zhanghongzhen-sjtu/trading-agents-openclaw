import csv
from pathlib import Path
from collections import defaultdict
import matplotlib.pyplot as plt


DATA_DIR = Path("data")
FILE_000630 = DATA_DIR / "backtest_results_000630.csv"
FILE_MULTI = DATA_DIR / "backtest_results_multi_stock.csv"

MERGED_RESULTS = DATA_DIR / "backtest_results_4stocks.csv"
MERGED_SUMMARY = DATA_DIR / "backtest_summary_4stocks.csv"

MODES = ["ours-full", "wo-cw-rag", "wo-dadm", "wo-rmse"]


def read_csv(path: Path):
    rows = []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows


def save_csv(path: Path, rows):
    if not rows:
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"已生成: {path}")


def to_float(row, key, default=0.0):
    try:
        return float(row.get(key, default))
    except Exception:
        return default


def mean(values):
    return sum(values) / len(values) if values else 0.0


def merge_rows(rows1, rows2):
    merged = []
    seen = set()

    for row in rows1 + rows2:
        key = (row["ticker"], row["date"], row["mode"])
        if key not in seen:
            seen.add(key)
            merged.append(row)

    merged.sort(key=lambda x: (x["ticker"], x["date"], x["mode"]))
    return merged


def max_drawdown(returns):
    equity = 1.0
    peak = 1.0
    max_dd = 0.0

    for r in returns:
        equity *= 1 + r
        peak = max(peak, equity)
        dd = (peak - equity) / peak
        max_dd = max(max_dd, dd)

    return max_dd


def summarize(rows):
    summary = []

    for mode in MODES:
        mode_rows = [r for r in rows if r["mode"] == mode]
        returns = [to_float(r, "strategy_return") for r in mode_rows]
        excess_stock = [to_float(r, "excess_vs_stock") for r in mode_rows]
        excess_market = [to_float(r, "excess_vs_market") for r in mode_rows]

        if not returns:
            continue

        total_return = 1.0
        for r in returns:
            total_return *= 1 + r
        total_return -= 1

        avg_return = mean(returns)
        vol = mean([(r - avg_return) ** 2 for r in returns]) ** 0.5
        sharpe_like = avg_return / vol if vol > 1e-9 else 0.0
        win_rate = sum(1 for r in returns if r > 0) / len(returns)

        summary.append({
            "mode": mode,
            "num_trades": len(returns),
            "total_return": total_return,
            "avg_return": avg_return,
            "volatility": vol,
            "sharpe_like": sharpe_like,
            "win_rate": win_rate,
            "max_drawdown": max_drawdown(returns),
            "avg_excess_vs_stock": mean(excess_stock),
            "avg_excess_vs_market": mean(excess_market),
        })

    return summary


def save_summary(path: Path, summary):
    fieldnames = [
        "mode",
        "num_trades",
        "total_return",
        "avg_return",
        "volatility",
        "sharpe_like",
        "win_rate",
        "max_drawdown",
        "avg_excess_vs_stock",
        "avg_excess_vs_market",
    ]

    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(summary)

    print(f"已生成: {path}")


def plot_bar(summary, key, title, ylabel, filename, percent=True):
    labels = [r["mode"] for r in summary]
    values = [float(r[key]) for r in summary]

    plt.figure(figsize=(9, 5))
    bars = plt.bar(labels, values)

    plt.title(title)
    plt.xlabel("Mode")
    plt.ylabel(ylabel)

    for bar, value in zip(bars, values):
        text = f"{value:.2%}" if percent else f"{value:.3f}"
        plt.text(
            bar.get_x() + bar.get_width() / 2,
            value,
            text,
            ha="center",
            va="bottom" if value >= 0 else "top",
            fontsize=9,
        )

    plt.tight_layout()
    out_path = DATA_DIR / filename
    plt.savefig(out_path, dpi=200)
    plt.close()
    print(f"已生成图表: {out_path}")


def plot_model_vs_market(rows):
    date_mode_returns = defaultdict(list)
    date_market_returns = defaultdict(list)

    for row in rows:
        date_mode_returns[(row["date"], row["mode"])].append(to_float(row, "strategy_return"))
        date_market_returns[row["date"]].append(to_float(row, "market_benchmark_return"))

    dates = sorted({r["date"] for r in rows})

    plt.figure(figsize=(10, 6))

    for mode in MODES:
        ys = [mean(date_mode_returns[(d, mode)]) for d in dates]
        plt.plot(dates, ys, marker="o", label=mode)

    market_ys = [mean(date_market_returns[d]) for d in dates]
    plt.plot(dates, market_ys, marker="o", linestyle="--", label="CSI300")

    plt.title("Average Strategy Return by Date (4 Stocks vs Market)")
    plt.xlabel("Date")
    plt.ylabel("Return")
    plt.xticks(rotation=30)
    plt.legend()
    plt.tight_layout()

    out_path = DATA_DIR / "fig_line_model_vs_market_4stocks.png"
    plt.savefig(out_path, dpi=200)
    plt.close()
    print(f"已生成图表: {out_path}")


def plot_normalized_stocks_vs_market(rows):
    ticker_date_return = {}
    date_market_return = {}

    for row in rows:
        key = (row["ticker"], row["date"])
        ticker_date_return[key] = to_float(row, "stock_return")
        date_market_return[row["date"]] = to_float(row, "market_benchmark_return")

    tickers = sorted({ticker for ticker, _ in ticker_date_return.keys()})
    dates = sorted({date for _, date in ticker_date_return.keys()})

    plt.figure(figsize=(10, 6))

    for ticker in tickers:
        nav = 1.0
        ys = []
        for d in dates:
            nav *= 1 + ticker_date_return.get((ticker, d), 0.0)
            ys.append(nav)
        plt.plot(dates, ys, marker="o", label=ticker)

    market_nav = 1.0
    market_ys = []
    for d in dates:
        market_nav *= 1 + date_market_return.get(d, 0.0)
        market_ys.append(market_nav)

    plt.plot(dates, market_ys, marker="o", linestyle="--", label="CSI300")

    plt.title("Normalized Stock Changes vs Market (4 Stocks)")
    plt.xlabel("Date")
    plt.ylabel("Normalized Net Value")
    plt.xticks(rotation=30)
    plt.legend()
    plt.tight_layout()

    out_path = DATA_DIR / "fig_line_normalized_stocks_vs_market_4stocks.png"
    plt.savefig(out_path, dpi=200)
    plt.close()
    print(f"已生成图表: {out_path}")


def main():
    if not FILE_000630.exists():
        print(f"缺少文件: {FILE_000630}")
        return

    if not FILE_MULTI.exists():
        print(f"缺少文件: {FILE_MULTI}")
        return

    rows_000630 = read_csv(FILE_000630)
    rows_multi = read_csv(FILE_MULTI)

    merged = merge_rows(rows_000630, rows_multi)
    save_csv(MERGED_RESULTS, merged)

    summary = summarize(merged)
    save_summary(MERGED_SUMMARY, summary)

    plot_bar(summary, "total_return", "Backtest Total Return by Mode (4 Stocks)", "Total Return", "fig_total_return_4stocks.png", percent=True)
    plot_bar(summary, "max_drawdown", "Backtest Max Drawdown by Mode (4 Stocks)", "Max Drawdown", "fig_max_drawdown_4stocks.png", percent=True)
    plot_bar(summary, "sharpe_like", "Backtest Sharpe-like by Mode (4 Stocks)", "Sharpe-like", "fig_sharpe_like_4stocks.png", percent=False)
    plot_bar(summary, "avg_excess_vs_market", "Average Excess Return vs Market by Mode (4 Stocks)", "Avg Excess Return vs Market", "fig_excess_vs_market_4stocks.png", percent=True)

    plot_model_vs_market(merged)
    plot_normalized_stocks_vs_market(merged)

    print("\n✅ 四股票合并与重绘完成")


if __name__ == "__main__":
    main()