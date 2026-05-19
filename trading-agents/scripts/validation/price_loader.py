from datetime import datetime, timedelta
from typing import Optional

import pandas as pd


def normalize_cn_ticker(ticker: str) -> str:
    code = ticker.replace(".SZ", "").replace(".SS", "").replace(".SH", "").replace(".BJ", "")

    if code.startswith(("0", "2", "3")):
        return f"{code}.SZ"
    if code.startswith(("6", "9")):
        return f"{code}.SS"
    if code.startswith(("8", "4")):
        return f"{code}.BJ"

    return ticker


def get_holding_return_yfinance(
    ticker: str,
    date: str,
    holding_days: int = 5,
) -> Optional[float]:
    """
    使用 yfinance 获取分析日到 holding_days 后的持有期收益率。
    """
    try:
        import yfinance as yf
    except ImportError:
        raise ImportError("请先安装 yfinance：pip install yfinance")

    yf_ticker = normalize_cn_ticker(ticker)

    start_dt = datetime.strptime(date, "%Y-%m-%d")
    end_dt = start_dt + timedelta(days=holding_days + 15)

    df = yf.download(
        yf_ticker,
        start=start_dt.strftime("%Y-%m-%d"),
        end=end_dt.strftime("%Y-%m-%d"),
        progress=False,
        auto_adjust=True,
        group_by="column",
    )

    if df is None or df.empty:
        return None

    # 兼容 yfinance 返回 MultiIndex 的情况
    if isinstance(df.columns, pd.MultiIndex):
        if "Close" in df.columns.get_level_values(0):
            close_df = df["Close"]
            if isinstance(close_df, pd.DataFrame):
                closes = close_df.iloc[:, 0]
            else:
                closes = close_df
        else:
            return None
    else:
        if "Close" not in df.columns:
            return None
        closes = df["Close"]

    closes = closes.dropna()

    if len(closes) < 2:
        return None

    # 保险转换成 float
    entry_price = float(closes.iloc[0].item() if hasattr(closes.iloc[0], "item") else closes.iloc[0])

    exit_index = min(holding_days, len(closes) - 1)
    exit_price = float(closes.iloc[exit_index].item() if hasattr(closes.iloc[exit_index], "item") else closes.iloc[exit_index])

    return exit_price / entry_price - 1