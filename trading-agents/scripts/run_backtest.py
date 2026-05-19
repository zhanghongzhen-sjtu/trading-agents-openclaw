#!/usr/bin/env python3
"""
多模式消融回测脚本
==================

用途：
调用 run_analysis.py 的不同消融模式，模拟持仓收益，并输出对比结果。

示例：
python run_backtest.py --tickers 000630 --market cn --dates 2026-05-01 2026-05-08 2026-05-15
"""
import os
import argparse
import csv
import json
import subprocess
import sys
from pathlib import Path
from statistics import mean, pstdev


MODES = {
    "ours-full": [],
    "wo-cw-rag": ["--disable-evidence-weight"],
    "wo-dadm": ["--disable-disagreement"],
    "wo-rmse": ["--disable-review-memory"],
}


def parse_args():
    parser = argparse.ArgumentParser(description="消融实验回测脚本")
    parser.add_argument("--tickers", nargs="+", required=True, help="股票代码列表，例如 000630 600519")
    parser.add_argument("--market", default="cn", choices=["cn", "us"], help="市场类型")
    parser.add_argument("--dates", nargs="+", required=True, help="回测日期列表，例如 2026-05-01 2026-05-08")
    parser.add_argument("--holding-return", type=float, default=None, help="临时测试用：手动指定持有期收益率，例如 -0.05")
    parser.add_argument("--allow-short", action="store_true", help="允许卖出信号按做空收益计算")
    parser.add_argument("--timeout", type=int, default=1200)
    return parser.parse_args()


def run_analysis(ticker: str, date: str, market: str, mode_name: str, mode_args: list, timeout: int):
    cmd = [
        sys.executable,
        "run_analysis.py",
        "--ticker", ticker,
        "--date", date,
        "--market", market,
        "--output-mode", "json",
        "--skip-mx",
        "--timeout", str(timeout),
        "--retries", "0",
        "--disable-review-memory",
    ]

    # 如果当前模式不是 wo-rmse，去掉默认 disable-review-memory
    if mode_name != "wo-rmse":
        cmd.remove("--disable-review-memory")

    cmd.extend(mode_args)

    print(f"运行: {mode_name} | {ticker} | {date}", file=sys.stderr)

    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"

    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout + 60,
    )

    if proc.returncode != 0:
        print(proc.stderr[-1000:], file=sys.stderr)
        raise RuntimeError(f"run_analysis.py 执行失败: {ticker} {date} {mode_name}")

    text = proc.stdout.strip()

    # stdout 可能有额外文本，尝试从最后一个 JSON 开始解析
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        raise RuntimeError("未找到 JSON 输出")

    return json.loads(text[start:end + 1])


def calc_strategy_return(action: str, position: float, holding_return: float, allow_short: bool = False) -> float:
    action = (action or "").lower()

    if action == "buy":
        return position * holding_return

    if action == "hold":
        return 0.0

    if action == "sell":
        if allow_short:
            return -position * holding_return
        return 0.0

    return 0.0


def max_drawdown(returns):
    equity = 1.0
    peak = 1.0
    max_dd = 0.0

    for r in returns:
        equity *= (1 + r)
        peak = max(peak, equity)
        dd = (peak - equity) / peak
        max_dd = max(max_dd, dd)

    return max_dd


def summarize(rows):
    summary = []

    for mode in MODES:
        mode_returns = [r["strategy_return"] for r in rows if r["mode"] == mode]

        if not mode_returns:
            continue

        total_return = 1.0
        for r in mode_returns:
            total_return *= (1 + r)
        total_return -= 1

        avg_return = mean(mode_returns)
        vol = pstdev(mode_returns) if len(mode_returns) > 1 else 0.0
        sharpe = avg_return / vol if vol > 1e-9 else 0.0
        win_rate = sum(1 for r in mode_returns if r > 0) / len(mode_returns)
        mdd = max_drawdown(mode_returns)

        summary.append({
            "mode": mode,
            "num_trades": len(mode_returns),
            "total_return": total_return,
            "avg_return": avg_return,
            "volatility": vol,
            "sharpe_like": sharpe,
            "win_rate": win_rate,
            "max_drawdown": mdd,
        })

    return summary


def write_csv(path: Path, rows: list):
    path.parent.mkdir(parents=True, exist_ok=True)

    if not rows:
        return

    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main():
    args = parse_args()

    if args.holding_return is None:
        print("当前最小版需要先用 --holding-return 手动指定持有期收益率。")
        print("例如：python run_backtest.py --tickers 000630 --market cn --dates 2026-05-15 --holding-return -0.05")
        return

    rows = []

    for ticker in args.tickers:
        for date in args.dates:
            for mode_name, mode_args in MODES.items():
                result = run_analysis(
                    ticker=ticker,
                    date=date,
                    market=args.market,
                    mode_name=mode_name,
                    mode_args=mode_args,
                    timeout=args.timeout,
                )

                uncertainty = result.get("uncertainty_analysis", {})
                decision = uncertainty.get("adaptive_decision", {})
                disagreement = uncertainty.get("disagreement", {})

                action = decision.get("final_action", "hold")
                position = decision.get("final_position", 0.0)

                strategy_return = calc_strategy_return(
                action=action,
                position=position,
                holding_return=args.holding_return,
                allow_short=args.allow_short,
            )

                rows.append({
                    "ticker": ticker,
                    "date": date,
                    "mode": mode_name,
                    "action": action,
                    "position": position,
                    "holding_return": args.holding_return,
                    "strategy_return": strategy_return,
                    "disagreement_total": disagreement.get("total", 0),
                    "evidence_disagreement": disagreement.get("evidence", 0),
                    "risk_disagreement": disagreement.get("risk", 0),
                })

    summary = summarize(rows)

    write_csv(Path("data/backtest_results.csv"), rows)
    write_csv(Path("data/backtest_summary.csv"), summary)

    print("✅ 回测完成")
    print("明细: data/backtest_results.csv")
    print("汇总: data/backtest_summary.csv")

    print("\n汇总结果：")
    for item in summary:
        print(
            f"{item['mode']}: "
            f"累计收益={item['total_return']:.2%}, "
            f"最大回撤={item['max_drawdown']:.2%}, "
            f"胜率={item['win_rate']:.2%}, "
            f"Sharpe-like={item['sharpe_like']:.3f}"
        )


if __name__ == "__main__":
    main()