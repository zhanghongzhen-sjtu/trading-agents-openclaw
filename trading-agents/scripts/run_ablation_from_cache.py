#!/usr/bin/env python3
"""
基于原始结果缓存的消融实验脚本
================================

用途：
1. TradingAgents 原始分析只运行一次；
2. 将原始 result 保存为缓存；
3. 在同一份 raw_result 上运行四种 uncertainty 消融配置；
4. 输出机制指标和模拟收益结果。

示例：

# 手动指定持有期收益率
python run_ablation_from_cache.py --ticker 000630 --market cn --date 2026-05-15 --holding-return -0.05 --allow-short

# 自动使用缓存，不重复跑 TradingAgents
python run_ablation_from_cache.py --ticker 000630 --market cn --date 2026-05-15 --holding-return -0.05 --allow-short --use-cache

# 若已经接入 validation.price_loader.py，也可以用真实价格收益
python run_ablation_from_cache.py --ticker 000630 --market cn --date 2026-05-15 --holding-days 5 --allow-short
"""

import argparse
import csv
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from statistics import mean, pstdev
from typing import Dict, Any, List, Optional


from run_analysis import run_tradingagents, run_uncertainty_layer


try:
    from validation.price_loader import get_holding_return_yfinance
except Exception:
    get_holding_return_yfinance = None


MODES = {
    "ours-full": {
        "use_evidence_weight": True,
        "use_disagreement": True,
        "use_review_memory": True,
    },
    "wo-cw-rag": {
        "use_evidence_weight": False,
        "use_disagreement": True,
        "use_review_memory": True,
    },
    "wo-dadm": {
        "use_evidence_weight": True,
        "use_disagreement": False,
        "use_review_memory": True,
    },
    "wo-rmse": {
        "use_evidence_weight": True,
        "use_disagreement": True,
        "use_review_memory": False,
    },
}


def parse_args():
    parser = argparse.ArgumentParser(description="基于缓存的消融实验脚本")
    parser.add_argument("--ticker", required=True, help="股票代码，例如 000630")
    parser.add_argument("--market", default="cn", choices=["auto", "cn", "us"], help="市场类型")
    parser.add_argument("--date", default=None, help="分析日期 yyyy-mm-dd，默认前天")
    parser.add_argument("--timeout", type=int, default=1200, help="TradingAgents 超时秒数")
    parser.add_argument("--retries", type=int, default=0, help="失败重试次数")

    parser.add_argument("--use-cache", action="store_true", help="如果缓存存在，直接读取缓存，不重新跑 TradingAgents")
    parser.add_argument("--refresh-cache", action="store_true", help="强制重新运行 TradingAgents 并覆盖缓存")

    parser.add_argument("--holding-return", type=float, default=None, help="手动指定持有期收益率，例如 -0.05")
    parser.add_argument("--holding-days", type=int, default=5, help="自动获取真实价格收益时的持有期交易日数量")
    parser.add_argument("--allow-short", action="store_true", help="允许 sell 按做空收益计算")

    return parser.parse_args()


def resolve_date(date: Optional[str]) -> str:
    if date:
        return date
    return (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d")


def resolve_market(ticker: str, market: str) -> str:
    if market != "auto":
        return market

    code = ticker.replace(".SZ", "").replace(".SS", "").replace(".SH", "").replace(".BJ", "")

    if (code.isdigit() and len(code) == 6) or any("\u4e00" <= c <= "\u9fff" for c in ticker):
        return "cn"

    return "us"


def get_cache_path(ticker: str, date: str, market: str) -> Path:
    safe_ticker = ticker.replace("/", "_").replace("\\", "_")
    return Path("data") / "ablation_cache" / f"{safe_ticker}_{market}_{date}_raw_result.json"


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, obj: Dict[str, Any]):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def get_raw_result(args, ticker: str, date: str, market: str) -> Dict[str, Any]:
    cache_path = get_cache_path(ticker, date, market)

    if args.use_cache and cache_path.exists() and not args.refresh_cache:
        print(f"📦 使用缓存 raw_result: {cache_path}", file=sys.stderr)
        return load_json(cache_path)

    print("🚀 未使用缓存，开始运行 TradingAgents 原始分析...", file=sys.stderr)

    raw_result = run_tradingagents(
        ticker=ticker,
        trade_date=date,
        market=market,
        mx_text="",
        timeout=args.timeout,
        max_retries=args.retries,
    )

    if raw_result.get("error"):
        raise RuntimeError(f"TradingAgents 原始分析失败: {raw_result.get('message') or raw_result}")

    raw_result.pop("uncertainty_analysis", None)

    save_json(cache_path, raw_result)
    print(f"✅ 原始结果已缓存: {cache_path}", file=sys.stderr)

    return raw_result


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


def get_holding_return(args, ticker: str, date: str) -> float:
    if args.holding_return is not None:
        print(f"使用手动持有期收益: {args.holding_return:.2%}", file=sys.stderr)
        return args.holding_return

    if get_holding_return_yfinance is None:
        raise RuntimeError("未找到 validation.price_loader.get_holding_return_yfinance，请先实现 price_loader 或使用 --holding-return")

    value = get_holding_return_yfinance(
        ticker=ticker,
        date=date,
        holding_days=args.holding_days,
    )

    if value is None:
        raise RuntimeError(f"无法获取真实持有期收益: {ticker} {date}")

    print(f"真实持有期收益: {ticker} | {date} | {args.holding_days}日 | {value:.2%}", file=sys.stderr)
    return value


def avg_credibility(evidences: List[Dict[str, Any]]) -> float:
    if not evidences:
        return 0.0
    return sum(float(e.get("credibility_score", 0.0)) for e in evidences) / len(evidences)


def max_drawdown(returns: List[float]) -> float:
    equity = 1.0
    peak = 1.0
    max_dd = 0.0

    for r in returns:
        equity *= 1 + r
        peak = max(peak, equity)
        dd = (peak - equity) / peak
        max_dd = max(max_dd, dd)

    return max_dd


def summarize(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    summary = []

    for mode in MODES:
        mode_returns = [float(r["strategy_return"]) for r in rows if r["mode"] == mode]

        if not mode_returns:
            continue

        total_return = 1.0
        for r in mode_returns:
            total_return *= 1 + r
        total_return -= 1

        avg_return = mean(mode_returns)
        vol = pstdev(mode_returns) if len(mode_returns) > 1 else 0.0
        sharpe_like = avg_return / vol if vol > 1e-9 else 0.0
        win_rate = sum(1 for r in mode_returns if r > 0) / len(mode_returns)

        summary.append({
            "mode": mode,
            "num_trades": len(mode_returns),
            "total_return": total_return,
            "avg_return": avg_return,
            "volatility": vol,
            "sharpe_like": sharpe_like,
            "win_rate": win_rate,
            "max_drawdown": max_drawdown(mode_returns),
        })

    return summary


def write_csv(path: Path, rows: List[Dict[str, Any]]):
    path.parent.mkdir(parents=True, exist_ok=True)

    if not rows:
        return

    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main():
    args = parse_args()

    ticker = args.ticker.strip()
    date = resolve_date(args.date)
    market = resolve_market(ticker, args.market)

    raw_result = get_raw_result(args, ticker, date, market)
    holding_return = get_holding_return(args, ticker, date)

    rows = {}
    csv_rows = []

    for mode_name, cfg in MODES.items():
        print(f"🧪 运行消融配置: {mode_name}", file=sys.stderr)

        uncertainty_result = run_uncertainty_layer(
            ticker=ticker,
            result=dict(raw_result),
            use_evidence_weight=cfg["use_evidence_weight"],
            use_disagreement=cfg["use_disagreement"],
            use_review_memory=cfg["use_review_memory"],
        )

        decision = uncertainty_result.get("adaptive_decision", {})
        disagreement = uncertainty_result.get("disagreement", {})
        evidences = uncertainty_result.get("evidences", [])

        action = decision.get("final_action", "hold")
        position = float(decision.get("final_position", 0.0))

        strategy_return = calc_strategy_return(
            action=action,
            position=position,
            holding_return=holding_return,
            allow_short=args.allow_short,
        )

        row = {
            "ticker": ticker,
            "date": date,
            "market": market,
            "mode": mode_name,
            "action": action,
            "position": position,
            "holding_return": holding_return,
            "strategy_return": strategy_return,
            "disagreement_total": disagreement.get("total", 0.0),
            "direction_disagreement": disagreement.get("direction", 0.0),
            "evidence_disagreement": disagreement.get("evidence", 0.0),
            "risk_disagreement": disagreement.get("risk", 0.0),
            "horizon_disagreement": disagreement.get("horizon", 0.0),
            "main_type": disagreement.get("main_type", ""),
            "avg_credibility": avg_credibility(evidences),
        }

        csv_rows.append(row)

        rows[mode_name] = {
            "row": row,
            "uncertainty_analysis": uncertainty_result,
        }

    out_dir = Path("data") / "ablation_cache"
    out_dir.mkdir(parents=True, exist_ok=True)

    result_json = out_dir / f"{ticker}_{market}_{date}_ablation_results.json"
    result_csv = out_dir / f"{ticker}_{market}_{date}_ablation_results.csv"
    summary_csv = out_dir / f"{ticker}_{market}_{date}_ablation_summary.csv"

    save_json(result_json, rows)
    write_csv(result_csv, csv_rows)
    write_csv(summary_csv, summarize(csv_rows))

    print("✅ 缓存版消融实验完成")
    print(f"明细 JSON: {result_json}")
    print(f"明细 CSV:  {result_csv}")
    print(f"汇总 CSV:  {summary_csv}")

    print("\n结果摘要：")
    for r in csv_rows:
        print(
            f"{r['mode']}: "
            f"action={r['action']}, "
            f"position={r['position']:.2%}, "
            f"strategy_return={r['strategy_return']:.2%}, "
            f"disagreement={float(r['disagreement_total']):.3f}, "
            f"avg_credibility={float(r['avg_credibility']):.3f}"
        )


if __name__ == "__main__":
    main()