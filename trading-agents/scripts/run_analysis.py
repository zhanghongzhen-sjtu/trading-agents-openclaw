#!/usr/bin/env python3
"""
TradingAgents 飞书遥控执行脚本
==============================
被 OpenClaw trading agent 调用，执行股票分析并输出到飞书文档或飞书消息。

用法:
    # 飞书文档模式（默认）：生成/更新飞书文档报告
    python3 run_analysis.py --ticker 贵州茅台 --date 2025-04-18

    # 飞书消息模式：直接发送消息到聊天
    python3 run_analysis.py --ticker 贵州茅台 --output-mode feishu-msg

    # JSON 模式
    python3 run_analysis.py --ticker AAPL --output-mode json

输出:
    - 飞书文档: 专业投研报告，同一股票自动更新到同一份文档
    - 飞书消息: 简洁的 Markdown 摘要
    - 文件: 完整分析报告保存到 ~/.tradingagents/logs/
"""

import argparse
import json
import os
import subprocess
import sys
import textwrap
from datetime import datetime, timedelta
from pathlib import Path
from uncertainty.disagreement import AgentOutput, compute_disagreement
from uncertainty.adaptive_decision import apply_adaptive_decision
from uncertainty.evidence import Evidence, infer_stance_from_decision, score_evidence, detect_conflicts
from uncertainty.review_memory import ReviewMemory
# 将脚本目录加入路径，以便导入 feishu_doc_client 等模块
# 将脚本目录加入路径，以便导入 feishu_doc_client 等模块
SCRIPT_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT = SCRIPT_DIR.parent.parent.resolve()

sys.path.insert(0, str(SCRIPT_DIR))

# 自动加入 MX Skills 路径，避免换终端后找不到 mx_data
sys.path.insert(0, str(PROJECT_ROOT / "mx-skills"))
sys.path.insert(0, str(PROJECT_ROOT / "mx-skills" / "mx-data"))
sys.path.insert(0, str(PROJECT_ROOT / "mx-skills" / "mx-xuangu"))
sys.path.insert(0, str(PROJECT_ROOT / "mx-skills" / "mx-search"))


def load_minimax_key_from_openclaw() -> str:
    """从 OpenClaw 配置中读取 MiniMax API Key。"""
    try:
        config_path = Path.home() / ".openclaw" / "openclaw.json"
        if not config_path.exists():
            return ""
        with open(config_path) as f:
            cfg = json.load(f)
        return cfg.get("models", {}).get("providers", {}).get("minimax", {}).get("apiKey", "")
    except Exception:
        return ""
    
def load_deepseek_key_from_openclaw() -> str:
    """从 OpenClaw 配置中读取 DeepSeek API Key。"""
    try:
        config_path = Path.home() / ".openclaw" / "openclaw.json"
        if not config_path.exists():
            return ""

        with open(config_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)

        return (
            cfg.get("models", {})
               .get("providers", {})
               .get("deepseek", {})
               .get("apiKey", "")
        )
    except Exception:
        return ""

# MX API Key（子进程环境变量注入，确保 fetch_mx_data 可用）
_MX_KEY = "YOUR_MX_APIKEY"
os.environ.setdefault("MX_APIKEY", _MX_KEY)

# TradingAgents 项目路径（可通过环境变量 TRADINGAGENTS_PROJECT 覆盖）
TA_PROJECT = Path(
    os.environ.get(
        "TRADINGAGENTS_PROJECT",
        SCRIPT_DIR / "TradingAgents-Kimi"
    )
).resolve()
TA_VENV_PYTHON = TA_PROJECT / ".venv" / "bin" / "python3"
PYTHON = str(TA_VENV_PYTHON) if TA_VENV_PYTHON.exists() else sys.executable


def fetch_mx_data(ticker: str, market: str) -> dict:
    """调用妙想skill获取补充数据。"""
    try:
        from mx_integration import MXIntegration, format_mx_data_for_report
        mx = MXIntegration()
        # A股使用中文名称，美股用ticker
        stock_name = ticker
        if market == "cn":
            # 尝试获取中文名称
            code = ticker.replace(".SZ", "").replace(".SS", "").replace(".BJ", "").replace(".SH", "")
            if code.isdigit() and len(code) == 6:
                stock_name = code
        mx_results = mx.comprehensive_analysis(stock_name)
        mx_text = format_mx_data_for_report(mx_results)
        return {
            "raw": mx_results,
            "formatted_text": mx_text,
            "error": None,
        }
    except Exception as e:
        print(f"[MX] 妙想数据获取失败: {e}", file=sys.stderr)
        return {
            "raw": {},
            "formatted_text": "",
            "error": str(e),
        }


def build_analysis_script(ticker: str, trade_date: str, market: str, mx_text: str = "") -> str:
    """生成内联的 TradingAgents 分析脚本。"""
    output_language = "Chinese" if market == "cn" else "English"
    data_vendor = "mx,tencent,akshare,yfinance"
    llm_provider = "deepseek"
    deep_model = "deepseek-chat"
    quick_model = "deepseek-chat"

    # A股 ticker 转换为 yfinance 格式
    ticker_for_ta = ticker
    if market == "cn":
        code = ticker.replace(".SZ", "").replace(".SS", "").replace(".BJ", "").replace(".SH", "")
        if code.isdigit() and len(code) == 6:
            if code.startswith(("6", "9")):
                ticker_for_ta = f"{code}.SS"
            elif code.startswith(("0", "2", "3")):
                ticker_for_ta = f"{code}.SZ"
            elif code.startswith(("8", "4")):
                ticker_for_ta = f"{code}.BJ"

    # 将妙想数据作为额外上下文嵌入
    mx_context_section = ""
    if mx_text and mx_text.strip():
        mx_context_section = f'''
# 妙想Skill获取的补充数据
MX_CONTEXT = """
{mx_text[:5000]}
"""
'''

    script = f'''
import json
import os
import sys

sys.path.insert(0, r"{TA_PROJECT}")
os.environ.setdefault("DEEPSEEK_API_KEY", os.getenv("DEEPSEEK_API_KEY", ""))
os.environ.setdefault("MX_APIKEY", os.getenv("MX_APIKEY", "YOUR_MX_APIKEY"))

from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG

{mx_context_section}

config = DEFAULT_CONFIG.copy()
config["llm_provider"] = "{llm_provider}"
config["deep_think_llm"] = "{deep_model}"
config["quick_think_llm"] = "{quick_model}"
config["output_language"] = "{output_language}"
config["data_vendors"] = {{
    "core_stock_apis": "{data_vendor}",
    "technical_indicators": "{data_vendor}",
    "fundamental_data": "{data_vendor}",
    "news_data": "{data_vendor}",
}}
config["max_debate_rounds"] = 1
config["max_risk_discuss_rounds"] = 1
config["checkpoint_enabled"] = False
config["memory_log_path"] = os.path.expanduser("~/.tradingagents/memory/trading_memory.md")
config["memory_log_max_entries"] = 100

ta = TradingAgentsGraph(debug=False, config=config)
final_state, decision = ta.propagate("{ticker_for_ta}", "{trade_date}")

result = {{
    "ticker": "{ticker}",
    "date": "{trade_date}",
    "market": "{market}",
    "final_trade_decision": decision,
    "market_report": final_state.get("market_report", ""),
    "sentiment_report": final_state.get("sentiment_report", ""),
    "news_report": final_state.get("news_report", ""),
    "fundamentals_report": final_state.get("fundamentals_report", ""),
    "raw_state": {{k: str(v)[:3000] for k, v in final_state.items() if v}},
    "investment_plan": final_state.get("investment_plan", ""),
    "trader_investment_plan": final_state.get("trader_investment_plan", ""),
}}

# 如果有妙想数据，附加到结果中
try:
    mx_data = MX_CONTEXT.strip() if 'MX_CONTEXT' in dir() else ""
    if mx_data:
        result["mx_context"] = mx_data
except:
    pass

print("<<<TRADINGAGENTS_RESULT>>>")
print(json.dumps(result, ensure_ascii=False, indent=2))
print("<<<TRADINGAGENTS_END>>>")
'''
    return script


def run_tradingagents(ticker: str, trade_date: str, market: str, mx_text: str = "", timeout: int = 1200, max_retries: int = 2) -> dict:
    """运行 TradingAgents 并返回结构化结果。失败自动重试。"""
    script = build_analysis_script(ticker, trade_date, market, mx_text)

    api_key = os.environ.get("DEEPSEEK_API_KEY") or load_deepseek_key_from_openclaw()

    env = os.environ.copy()
    env["PYTHONPATH"] = str(TA_PROJECT)
    env["PYTHONUNBUFFERED"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env["DEEPSEEK_API_KEY"] = api_key
    env["MX_APIKEY"] = os.environ.get("MX_APIKEY", "YOUR_MX_APIKEY")

    last_error = None
    for attempt in range(max_retries + 1):
        if attempt > 0:
            print(f"🔄 第 {attempt + 1} 次尝试...", file=sys.stderr)

        try:
            proc = subprocess.run(
                [PYTHON, "-c", script],
                capture_output=True,
                text=True,
                timeout=timeout,
                env=env,
                cwd=str(TA_PROJECT),
                encoding="utf-8",
                errors="replace",
            )
        except subprocess.TimeoutExpired:
            last_error = f"分析超时（{timeout}秒）"
            print(f"⏰ {last_error}，尝试 {attempt + 1}/{max_retries + 1}", file=sys.stderr)
            continue

        # 成功获取结果，处理输出
        # 检测 MiniMax 额度耗尽
        combined_output = (proc.stdout or "") + (proc.stderr or "")
        if "MiniMaxQuotaExhausted" in combined_output or "额度已耗尽" in combined_output:
            print("⚠️ MiniMax Coding Plan 额度已耗尽！", file=sys.stderr)
            print("请选择：", file=sys.stderr)
            print("  1. 等待额度重置（通常次日自动恢复）", file=sys.stderr)
            print("  2. 切换到其他模型", file=sys.stderr)
            return {
                "error": True,
                "error_type": "quota_exhausted",
                "ticker": ticker,
                "date": trade_date,
                "message": "MiniMax Coding Plan 额度已耗尽，请等待额度重置或切换模型",
            }

        # 将子进程输出打印到 stderr，便于 Agent 通过 process log 查看进度
        if proc.stderr:
            print(proc.stderr, file=sys.stderr, flush=True)
        if proc.stdout:
            print(proc.stdout, file=sys.stderr, flush=True)

        stdout = proc.stdout
        stderr = proc.stderr

        start = stdout.find("<<<TRADINGAGENTS_RESULT>>>")
        end = stdout.find("<<<TRADINGAGENTS_END>>>")

        if start != -1 and end != -1:
            json_str = stdout[start + len("<<<TRADINGAGENTS_RESULT>>>"):end].strip()
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                pass

        for line in stdout.splitlines():
            line = line.strip()
            if line.startswith("{") and line.endswith("}"):
                try:
                    return json.loads(line)
                except json.JSONDecodeError:
                    continue

        # 解析失败，重试
        last_error = "输出解析失败"
        print(f"⚠️ {last_error}，尝试 {attempt + 1}/{max_retries}", file=sys.stderr)

    # 所有重试均失败
    return {
        "error": True,
        "ticker": ticker,
        "date": trade_date,
        "message": last_error or "分析失败",
    }


def format_feishu_message(result: dict) -> str:
    """将分析结果格式化为飞书友好的 Markdown 消息。"""
    if result.get("error"):
        error_msg = (
            result.get("message")
            or result.get("stderr")
            or result.get("error_type")
            or "无错误信息"
        )

        return textwrap.dedent(f"""\
             **TradingAgents 分析失败**

            - 股票: {result.get('ticker', 'N/A')}
            - 日期: {result.get('date', 'N/A')}
            - 返回码: {result.get('returncode', 'N/A')}

            **错误信息:**
            ```
            {str(error_msg)[:1000]}
            ```
        """)

    ticker = result.get("ticker", "")
    date = result.get("date", "")
    decision = result.get("final_trade_decision", "")
    investment_plan = result.get("investment_plan", "")
    trader_plan = result.get("trader_investment_plan", "")

    rating = "HOLD"
    for r in ["Buy", "Overweight", "Hold", "Underweight", "Sell",
              "买入", "增持", "持有", "减持", "卖出"]:
        if r.lower() in decision.lower():
            rating = r
            break

    emoji_map = {
        "Buy": "🟢", "买入": "🟢",
        "Overweight": "🟢", "增持": "🟢",
        "Hold": "🟡", "持有": "🟡",
        "Underweight": "🔴", "减持": "🔴",
        "Sell": "🔴", "卖出": "🔴",
    }
    rating_emoji = emoji_map.get(rating, "⚪")

    def summarize(text: str, max_len: int = 300) -> str:
        if not text:
            return "暂无数据"
        text = text.replace("#", "").replace("*", "").strip()
        return text[:max_len] + ("..." if len(text) > max_len else "")

    tech = summarize(result.get('market_report', ''), 200)
    sentiment = summarize(result.get('sentiment_report', ''), 150)
    news = summarize(result.get('news_report', ''), 150)
    fundamental = summarize(result.get('fundamentals_report', ''), 200)
    plan = summarize(trader_plan or investment_plan, 250)
    final = summarize(decision, 300)

    uncertainty = result.get("uncertainty_analysis", {})
    disagreement = uncertainty.get("disagreement", {})
    adaptive_decision = uncertainty.get("adaptive_decision", {})

    uncertainty_summary = ""
    if disagreement and adaptive_decision:
        uncertainty_summary = textwrap.dedent(f"""\
        
        **不确定性诊断与风险自适应决策**
        - 综合分歧指数：{disagreement.get("total", 0):.3f}
        - 主要分歧类型：{disagreement.get("main_type", "N/A")}
        - 触发控制动作：{adaptive_decision.get("control_action", "N/A")}
        - 风险自适应建议：{adaptive_decision.get("final_action", "N/A")}
        - 建议仓位：{adaptive_decision.get("final_position", 0):.2%}
        - 风险等级：{adaptive_decision.get("risk_level", "N/A")}
        """)



    msg = textwrap.dedent(f"""\
{rating_emoji} **{ticker} 投研分析完成**  |  {date}

| 项目 | 内容 |
|------|------|
| 标的 | **{ticker}** |
| 决策 | **{rating}** |

**核心观点**
{final}
{uncertainty_summary}
**交易计划**
{plan}

**技术面** | {tech}
**基本面** | {fundamental}
**情绪面** | {sentiment}
**新闻面** | {news}

---
💡 *完整报告见飞书文档或日志: ~/.tradingagents/logs/{ticker}/*
    """)

    return msg

def append_blocks_in_batches(client, doc_id: str, blocks: list, batch_size: int = 40):
    """飞书 docx API 一次 children 最多 50 个，这里分批写入。"""
    if not blocks:
        return

    for i in range(0, len(blocks), batch_size):
        batch = blocks[i:i + batch_size]
        client.append_blocks(doc_id, batch)


def output_to_feishu_doc(result: dict) -> str:
    """
    将分析结果输出到飞书文档。
    同一股票会自动更新到同一份文档。

    Returns:
        飞书文档 URL
    """
    from feishu_doc_manager import get_or_create_doc, record_analysis, get_doc_history
    from feishu_doc_client import FeishuDocClient
    from report_generator import generate_report_blocks, generate_update_header_blocks

    ticker = result.get("ticker", "")
    date = result.get("date", "")
    decision = result.get("final_trade_decision", "")

    # 1. 获取或创建文档
    doc = get_or_create_doc(ticker, ticker_name=ticker)
    doc_id = doc["document_id"]
    doc_url = doc["url"]
    is_new = doc["is_new"]

    client = FeishuDocClient(account_id="trading")

    # 2. 生成报告 blocks
    history = get_doc_history(ticker)
    report_blocks = generate_report_blocks(result, history=history)

    if is_new:
        # 新文档：分批写入所有 blocks，避免超过飞书单次 50 个 children 限制
        append_blocks_in_batches(client, doc_id, report_blocks, batch_size=40)
    else:
        # 已有文档：先清除旧内容，再写入新内容
        # 这样避免 index=0 插入导致的编码错乱问题
        existing_blocks = client.list_blocks(doc_id)

        # 保留第一个 block（页面 block），删除其余内容 blocks
        if len(existing_blocks) > 1:
            # 反向删除，避免 index 变化问题
            for block in reversed(existing_blocks[1:]):
                block_id = block.get("block_id")
                if block_id:
                    try:
                        client.delete_block(doc_id, block_id)
                    except Exception:
                        pass  # 忽略删除失败（可能是页面类型 block）

        # 生成更新头（第 N 次分析）
        import feishu_doc_manager as dm
        full_registry = dm.get_all_registry()
        norm_ticker = ticker.upper().replace(".SZ", "").replace(".SS", "").replace(".BJ", "").replace(".SH", "")
        analysis_count = full_registry.get(norm_ticker, {}).get("analysis_count", 0)
        header_blocks = generate_update_header_blocks(ticker, date, decision, analysis_count + 1)

        all_blocks = header_blocks + report_blocks

        # 关键修改：这里也必须分批写入，不能直接 client.append_blocks(doc_id, all_blocks)
        append_blocks_in_batches(client, doc_id, all_blocks, batch_size=40)

    # 3. 记录分析到注册表
    record_analysis(ticker, date, decision, doc_id)

    return doc_url


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="TradingAgents 飞书遥控执行脚本")
    parser.add_argument("--ticker", required=True, help="股票代码或名称（如 贵州茅台、AAPL）")
    parser.add_argument("--date", default=None, help="分析日期 yyyy-mm-dd，默认前天")
    parser.add_argument("--market", default="auto", choices=["auto", "cn", "us"], help="市场类型")
    parser.add_argument(
        "--output-mode",
        default="feishu-doc",
        choices=["feishu-doc", "feishu-msg", "json", "raw"],
        help="输出模式：feishu-doc=飞书文档（默认）, feishu-msg=飞书消息, json=原始JSON, raw=纯文本"
    )
    parser.add_argument("--skip-mx", action="store_true", help="跳过妙想数据采集（调试用）")
    parser.add_argument("--timeout", type=int, default=1200, help="子进程超时秒数（默认1200）")
    parser.add_argument("--retries", type=int, default=2, help="失败重试次数（默认2）")
    return parser.parse_args()


def infer_decision_from_text(text: str) -> str:
    text_lower = (text or "").lower()

    bearish_words = [
        "sell", "underweight", "reduce", "减持", "卖出", "看空",
        "谨慎", "下行", "风险", "承压", "走弱", "回撤"
    ]

    bullish_words = [
        "buy", "overweight", "increase", "买入", "增持", "看多",
        "利好", "突破", "走强", "改善", "增长", "上行"
    ]

    bearish_score = sum(1 for w in bearish_words if w in text_lower)
    bullish_score = sum(1 for w in bullish_words if w in text_lower)

    if bullish_score > bearish_score:
        return "buy"
    if bearish_score > bullish_score:
        return "sell"
    return "hold"


def infer_confidence_from_text(text: str) -> float:
    text_lower = (text or "").lower()

    strong_words = ["强烈", "明确", "显著", "high confidence", "strong", "确定"]
    weak_words = ["可能", "不确定", "谨慎", "有限", "低", "uncertain", "low confidence"]

    confidence = 0.60

    if any(w in text_lower for w in strong_words):
        confidence += 0.15

    if any(w in text_lower for w in weak_words):
        confidence -= 0.10

    return max(0.35, min(0.90, confidence))


def infer_position_from_decision(decision: str, confidence: float) -> float:
    if decision == "buy":
        return 0.30 + 0.40 * confidence
    if decision == "sell":
        return 0.05
    return 0.10 + 0.20 * confidence


def run_uncertainty_layer(ticker: str, result: dict):


    market_report = result.get("market_report", "")
    fundamentals_report = result.get("fundamentals_report", "")
    sentiment_report = result.get("sentiment_report", "")
    news_report = result.get("news_report", "")
    investment_plan = result.get("investment_plan", "")
    trader_plan = result.get("trader_investment_plan", "")
    final_decision = result.get("final_trade_decision", "")

    market_decision = infer_decision_from_text(market_report)
    market_conf = infer_confidence_from_text(market_report)

    fundamental_decision = infer_decision_from_text(fundamentals_report)
    fundamental_conf = infer_confidence_from_text(fundamentals_report)

    sentiment_decision = infer_decision_from_text(sentiment_report)
    sentiment_conf = infer_confidence_from_text(sentiment_report)

    news_decision = infer_decision_from_text(news_report)
    news_conf = infer_confidence_from_text(news_report)

    risk_decision = infer_decision_from_text(final_decision + "\n" + trader_plan + "\n" + investment_plan)
    risk_conf = infer_confidence_from_text(final_decision + "\n" + trader_plan + "\n" + investment_plan)
    
    evidences = [
        Evidence(
            evidence_id="market_report",
            ticker=ticker,
            source="market_report",
            evidence_type="market",
            content=market_report,
            stance=infer_stance_from_decision(market_decision),
            relevance_score=0.85,
        ),
        Evidence(
            evidence_id="fundamentals_report",
            ticker=ticker,
            source="fundamentals_report",
            evidence_type="fundamental",
            content=fundamentals_report,
            stance=infer_stance_from_decision(fundamental_decision),
            relevance_score=0.90,
        ),
        Evidence(
            evidence_id="sentiment_report",
            ticker=ticker,
            source="sentiment_report",
            evidence_type="sentiment",
            content=sentiment_report,
            stance=infer_stance_from_decision(sentiment_decision),
            relevance_score=0.70,
        ),
        Evidence(
            evidence_id="news_report",
            ticker=ticker,
            source="news_report",
            evidence_type="news",
            content=news_report,
            stance=infer_stance_from_decision(news_decision),
            relevance_score=0.75,
        ),
        Evidence(
            evidence_id="final_trade_decision",
            ticker=ticker,
            source="final_trade_decision",
            evidence_type="decision",
            content=final_decision + "\n" + trader_plan + "\n" + investment_plan,
            stance=infer_stance_from_decision(risk_decision),
            relevance_score=0.95,
        ),
    ]

    evidences = [score_evidence(e, evidences) for e in evidences]
    evidences = detect_conflicts(evidences)

    evidence_stance = {
        e.evidence_id: e.stance
        for e in evidences
    }

    evidence_weight = {
        e.evidence_id: e.credibility_score
        for e in evidences
    }
    
    outputs = [
        AgentOutput(
            agent_name="Market Analyst",
            role="market",
            decision=market_decision,
            confidence=market_conf,
            evidence_ids=["market_report"],
            suggested_position=infer_position_from_decision(market_decision, market_conf),
            horizon="short",
            reasoning_summary=market_report[:300],
        ),
        AgentOutput(
            agent_name="Fundamentals Analyst",
            role="fundamental",
            decision=fundamental_decision,
            confidence=fundamental_conf,
            evidence_ids=["fundamentals_report"],
            suggested_position=infer_position_from_decision(fundamental_decision, fundamental_conf),
            horizon="mid",
            reasoning_summary=fundamentals_report[:300],
        ),
        AgentOutput(
            agent_name="Sentiment Analyst",
            role="sentiment",
            decision=sentiment_decision,
            confidence=sentiment_conf,
            evidence_ids=["sentiment_report"],
            suggested_position=infer_position_from_decision(sentiment_decision, sentiment_conf),
            horizon="short",
            reasoning_summary=sentiment_report[:300],
        ),
        AgentOutput(
            agent_name="News Analyst",
            role="news",
            decision=news_decision,
            confidence=news_conf,
            evidence_ids=["news_report"],
            suggested_position=infer_position_from_decision(news_decision, news_conf),
            horizon="short",
            reasoning_summary=news_report[:300],
        ),
        AgentOutput(
            agent_name="Risk Manager",
            role="risk",
            decision=risk_decision if risk_decision != "buy" else "hold",
            confidence=risk_conf,
            evidence_ids=["final_trade_decision"],
            suggested_position=0.10 if risk_decision in ["sell", "hold"] else 0.25,
            horizon="short",
            reasoning_summary=(final_decision + "\n" + trader_plan)[:300],
        ),
    ]

    disagreement = compute_disagreement(
        outputs=outputs,
        evidence_stance=evidence_stance,
        evidence_weight=evidence_weight,
    )

    memory = ReviewMemory()
    rho = memory.get_disagreement_penalty(disagreement.main_type)

    decision = apply_adaptive_decision(
        ticker=ticker,
        outputs=outputs,
        disagreement=disagreement,
        rho=rho,
    )

    return {
        "agent_outputs": [o.__dict__ for o in outputs],
        "evidences": [
            {
                "evidence_id": e.evidence_id,
                "source": e.source,
                "evidence_type": e.evidence_type,
                "stance": e.stance,
                "credibility_score": e.credibility_score,
                "conflict_ids": e.conflict_ids,
            }
            for e in evidences
        ],
        "evidence_stance": evidence_stance,
        "evidence_weight": evidence_weight,
        "disagreement": disagreement.__dict__,
        "adaptive_decision": decision.__dict__,
    }





def main():
    args = parse_args()

    ticker = args.ticker.strip()
    date = args.date
    if not date:
        date = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d")

    market = args.market
    if market == "auto":
        code = ticker.replace(".SZ", "").replace(".SS", "").replace(".BJ", "").replace(".SH", "")
        if (code.isdigit() and len(code) == 6) or any('\u4e00' <= c <= '\u9fff' for c in ticker):
            market = "cn"
        else:
            market = "us"

    # 检查 MiniMax API Key
    # 检查 DeepSeek API Key
    api_key = os.environ.get("DEEPSEEK_API_KEY") or load_deepseek_key_from_openclaw()
    if not api_key:
        print("错误: 未找到 DeepSeek API Key")
        print("请先在环境变量 DEEPSEEK_API_KEY 或 C:\\Users\\31231\\.openclaw\\openclaw.json 的 models.providers.deepseek.apiKey 中配置")
        sys.exit(1)

    if not (TA_PROJECT / "tradingagents" / "graph" / "trading_graph.py").exists():
        print(f"❌ 错误: TradingAgents 项目未找到于 {TA_PROJECT}")
        sys.exit(1)

    print(f"🚀 启动分析: {ticker} @ {date} (市场: {market})", file=sys.stderr)

    # Step 1: 获取妙想数据
    mx_text = ""
    if not args.skip_mx:
        print("📊 正在获取妙想数据...", file=sys.stderr)
        mx_data = fetch_mx_data(ticker, market)
        mx_text = mx_data.get("formatted_text", "")
        if mx_data.get("error"):
            print(f"⚠️ 妙想数据获取失败: {mx_data['error']}", file=sys.stderr)
        else:
            print(f"✅ 妙想数据获取成功 ({len(mx_text)} 字符)", file=sys.stderr)

    # Step 2: 运行 TradingAgents 分析
    result = run_tradingagents(ticker, date, market, mx_text, timeout=args.timeout, max_retries=args.retries)

    # Step 2.5: 不确定性诊断与风险自适应决策测试
    uncertainty_result = run_uncertainty_layer(ticker, result)
    result["uncertainty_analysis"] = uncertainty_result
    memory = ReviewMemory()
    memory.add_review(ticker, date, uncertainty_result)
    print("\n========== 不确定性诊断测试 ==========", file=sys.stderr)
    print(json.dumps(uncertainty_result, ensure_ascii=False, indent=2), file=sys.stderr)
    print("=====================================\n", file=sys.stderr)

    # Step 3: 将妙想数据合并到结果中
    if mx_text:
        result["mx_context"] = mx_text

    if args.output_mode == "json":
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.output_mode == "raw":
        print(result.get("final_trade_decision", ""))
    elif args.output_mode == "feishu-msg":
        print(format_feishu_message(result))
    else:
        # feishu-doc 模式
        if result.get("error"):
            print(format_feishu_message(result))
            sys.exit(1)
        try:
            doc_url = output_to_feishu_doc(result)
            print(f"📄 飞书文档已生成/更新：{doc_url}")
        except Exception as e:
            print(f"❌ 飞书文档生成失败: {e}")
            print("回退到消息模式：")
            print(format_feishu_message(result))
            sys.exit(1)


if __name__ == "__main__":
    main()
