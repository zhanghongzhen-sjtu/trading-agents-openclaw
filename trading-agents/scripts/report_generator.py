#!/usr/bin/env python3
"""
投研报告生成器
==============
将 TradingAgents 的分析结果转换为飞书文档 block 格式，生成专业详实的投研报告。

设计原则：
- 详实：保留 Analyst 完整报告，不过度截断
- 专业：标准投研报告结构，数据来源清晰
- 易读：善用标题层级、分割线、引用块
- 色彩：决策评级用颜色区分（绿/黄/红）
- 完整：包含长期/中期/短期逻辑、行业分析、竞品对比
"""

from datetime import datetime
from typing import Dict, List, Any

from feishu_doc_client import (
    text_block,
    heading1_block,
    heading2_block,
    heading3_block,
    divider_block,
    bullet_block,
    quote_block,
    FEISHU_COLORS,
)

# 飞书单个 text_run content 上限约 10000 字符，为安全起见分段
_MAX_TEXT_PER_BLOCK = 8000


def _clean_text(text: str) -> str:
    """清理文本中的 markdown 标记，保留内容。幂等操作。"""
    if not text:
        return ""
    text = text.strip()
    # 移除 markdown 标记但保留内容结构
    # 使用双重替换确保幂等性（即使已清理过也不会出问题）
    text = text.replace("**", "").replace("*", "")
    # 保留标题标记的空格，让结构清晰
    text = text.replace("# ", "").replace("## ", "").replace("### ", "")
    return text


def _split_long_text(text: str, max_len: int = _MAX_TEXT_PER_BLOCK) -> List[str]:
    """
    将长文本按段落分割为多个 chunk，每个 chunk 不超过 max_len 字符。
    优先在段落边界处分割。
    """
    if not text:
        return ["暂无数据"]

    text = _clean_text(text)
    if len(text) <= max_len:
        return [text]

    chunks = []
    paragraphs = text.split("\n")
    current_chunk = ""

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        # 如果单段就超长，直接截断
        if len(para) > max_len:
            if current_chunk:
                chunks.append(current_chunk.strip())
                current_chunk = ""
            # 将超长段落按句子分割
            sentences = para.split("。")
            temp = ""
            for sent in sentences:
                if len(temp) + len(sent) + 1 > max_len:
                    if temp:
                        chunks.append(temp.strip() + "。")
                    temp = sent + "。"
                else:
                    temp += sent + "。"
            if temp:
                chunks.append(temp.strip())
            continue

        # 正常段落，尝试加入当前 chunk
        if len(current_chunk) + len(para) + 1 > max_len:
            if current_chunk:
                chunks.append(current_chunk.strip())
            current_chunk = para
        else:
            current_chunk = (current_chunk + "\n" + para).strip()

    if current_chunk:
        chunks.append(current_chunk.strip())

    return chunks if chunks else ["暂无数据"]


def _add_text_section(blocks: List[Dict], text: str, max_len: int = _MAX_TEXT_PER_BLOCK):
    """将长文本分段加入 blocks。"""
    for chunk in _split_long_text(text, max_len):
        blocks.append(text_block(chunk))


def _extract_rating(decision: str) -> tuple:
    """从决策文本中提取评级和 emoji。"""
    decision_lower = decision.lower()
    ratings = [
        ("买入", "🟢 买入", "green"),
        ("增持", "🟢 增持", "green"),
        ("buy", "🟢 Buy", "green"),
        ("overweight", "🟢 Overweight", "green"),
        ("持有", "🟡 持有", "yellow"),
        ("hold", "🟡 Hold", "yellow"),
        ("减持", "🔴 减持", "red"),
        ("underweight", "🔴 Underweight", "red"),
        ("卖出", "🔴 卖出", "red"),
        ("sell", "🔴 Sell", "red"),
    ]
    for keyword, display, color in ratings:
        if keyword in decision_lower:
            return display, color
    return "⚪ 观望", "default"


def _build_info_table_lines(ticker: str, date: str, rating_display: str) -> str:
    """构建信息摘要表格文本（使用等宽字体对齐）。"""
    lines = [
        "┌──────────┬─────────────────────────────┐",
        f"│ 标的     │ {ticker:<27} │",
        f"│ 分析日期 │ {date:<27} │",
        f"│ 决策评级 │ {rating_display:<27} │",
        "└──────────┴─────────────────────────────┘",
    ]
    return "\n".join(lines)

def _build_uncertainty_summary(result: Dict[str, Any]) -> str:
    """构建不确定性诊断摘要。"""
    uncertainty = result.get("uncertainty_analysis", {})
    disagreement = uncertainty.get("disagreement", {})
    adaptive_decision = uncertainty.get("adaptive_decision", {})

    if not disagreement or not adaptive_decision:
        return "暂无不确定性诊断数据。"

    total = disagreement.get("total", 0)
    main_type = disagreement.get("main_type", "N/A")

    direction = disagreement.get("direction", 0)
    confidence = disagreement.get("confidence", 0)
    evidence = disagreement.get("evidence", 0)
    risk = disagreement.get("risk", 0)
    horizon = disagreement.get("horizon", 0)

    control_action = adaptive_decision.get("control_action", "N/A")
    final_action = adaptive_decision.get("final_action", "N/A")
    final_position = adaptive_decision.get("final_position", 0)
    risk_level = adaptive_decision.get("risk_level", "N/A")
    explanation = adaptive_decision.get("explanation", "")

    action_map = {
        "normal": "正常执行",
        "second_round_debate": "触发二轮辩论",
        "retrieve_again_and_filter": "证据重检索与可信度过滤",
        "risk_arbitration_reduce_position": "风险仲裁与仓位折减",
        "ask_for_more_evidence_reduce_overconfidence": "要求补充证据并降低过度自信权重",
        "split_short_mid_long_strategy": "拆分短线与中长期策略",
        "risk_veto_or_hold": "风险优先，观望或否决交易",
    }

    final_action_map = {
        "buy": "买入",
        "hold": "持有/观望",
        "sell": "卖出/减仓",
    }

    risk_level_map = {
        "low": "低",
        "medium": "中",
        "high": "高",
    }

    lines = [
        f"综合分歧指数：{total:.3f}",
        f"主要分歧类型：{main_type}",
        f"触发控制动作：{action_map.get(control_action, control_action)}",
        f"风险自适应建议：{final_action_map.get(final_action, final_action)}",
        f"建议仓位：{final_position:.2%}",
        f"风险等级：{risk_level_map.get(risk_level, risk_level)}",
        "",
        "分歧来源明细：",
        f"• 方向分歧：{direction:.3f}",
        f"• 置信度分歧：{confidence:.3f}",
        f"• 证据分歧：{evidence:.3f}",
        f"• 风险分歧：{risk:.3f}",
        f"• 时间尺度分歧：{horizon:.3f}",
    ]

    evidences = uncertainty.get("evidences", [])
    if evidences:
        lines.append("")
        lines.append("证据可信度明细：")

        for e in evidences:
            evidence_id = e.get("evidence_id", "N/A")
            stance = e.get("stance", "N/A")
            score = e.get("credibility_score", 0)
            conflicts = e.get("conflict_ids", [])

            stance_map = {
                "bullish": "看多",
                "bearish": "看空",
                "neutral": "中性",
            }

            conflict_text = "无" if not conflicts else "、".join(conflicts)

            lines.append(
                f"• {evidence_id}：方向 {stance_map.get(stance, stance)}，"
                f"可信度 {score:.3f}，冲突证据：{conflict_text}"
            )

    if explanation:
        lines.extend(["", f"系统解释：{explanation}"])

    return "\n".join(lines)

def _extract_time_horizon_logic(decision: str, market_report: str, fundamentals_report: str) -> Dict[str, str]:
    """从分析结果中提取长期/中期/短期逻辑。"""
    combined = f"{decision}\n{market_report}\n{fundamentals_report}"
    lines = combined.split("\n")

    horizon = {"长期逻辑": "", "中期逻辑": "", "短期逻辑": ""}

    for line in lines:
        line_lower = line.lower()
        # 长期逻辑
        if any(kw in line_lower for kw in ["长期", "战略", "基本面趋势", "行业格局", "护城河", "商业模式", "5年", "3年"]):
            horizon["长期逻辑"] += line.strip() + "\n"
        # 中期逻辑
        elif any(kw in line_lower for kw in ["中期", "季度", "业绩", "营收趋势", "毛利", "产品周期", "6个月", "1年"]):
            horizon["中期逻辑"] += line.strip() + "\n"
        # 短期逻辑
        elif any(kw in line_lower for kw in ["短期", "技术面", "均线", "支撑", "压力", "量价", "macd", "rsi", "周", "月"]):
            horizon["短期逻辑"] += line.strip() + "\n"

    # 清理，保留前300字符
    for k in horizon:
        if not horizon[k].strip():
            horizon[k] = "暂无明确数据支撑"
        else:
            horizon[k] = horizon[k].strip()[:300]

    return horizon


def _extract_key_data_from_mx(mx_text: str) -> List[str]:
    """从妙想数据中提取关键数据点。"""
    if not mx_text:
        return []

    key_points = []
    for line in mx_text.split("\n"):
        line = line.strip()
        if not line or line.startswith("==="):
            continue
        # 提取包含关键数据的行
        if any(kw in line for kw in ["PE", "PB", "ROE", "营收", "利润", "毛利率", "净利率", "市值"]):
            key_points.append(line[:150])

    return key_points[:10]


def generate_report_blocks(result: Dict[str, Any], history: List[Dict[str, str]] = None) -> List[Dict[str, Any]]:
    """
    生成飞书文档 block 列表。

    Args:
        result: TradingAgents 分析结果字典
        history: 历史分析记录列表 [{"date": "...", "rating": "..."}, ...]

    Returns:
        飞书文档 block 列表
    """
    ticker = result.get("ticker", "")
    date = result.get("date", "")
    decision = result.get("final_trade_decision", "")
    investment_plan = result.get("investment_plan", "")
    trader_plan = result.get("trader_investment_plan", "")
    mx_context = result.get("mx_context", "")

    rating_display, rating_color = _extract_rating(decision)
    color_map = {"green": 5, "yellow": 4, "red": 9, "default": 0}
    rating_color_value = color_map.get(rating_color, 0)

    blocks: List[Dict[str, Any]] = []

    # =================================================================
    # 报告头
    # =================================================================
    blocks.append(heading1_block(f"投研报告：{ticker}"))
    blocks.append(divider_block())

    # 信息摘要表格
    blocks.append(text_block(_build_info_table_lines(ticker, date, rating_display)))
    blocks.append(text_block(""))

    # =================================================================
    # 执行摘要
    # =================================================================
    blocks.append(heading2_block("执行摘要"))
    blocks.append(divider_block())

    # 核心观点
    core_view = decision.split("\n")[0] if decision else "暂无"
    blocks.append(quote_block(f"核心观点：{core_view[:500]}"))
    blocks.append(text_block(""))
    
    # =================================================================
    # 不确定性诊断与风险自适应决策
    # =================================================================
    blocks.append(heading3_block("不确定性诊断与风险自适应决策"))
    blocks.append(text_block(_build_uncertainty_summary(result)))
    blocks.append(text_block(""))

    # 关键数据速览
    blocks.append(heading3_block("关键数据速览"))
    key_data_lines = []
    combined_text = f"{investment_plan}\n{trader_plan}\n{decision}"

    for keyword in ["目标价", "目标价位", "Target Price", "price target"]:
        if keyword in combined_text:
            for line in combined_text.split("\n"):
                if keyword in line and len(line) < 120:
                    key_data_lines.append(f"• {_clean_text(line)[:100]}")
                    break

    for keyword in ["止损", "止损位", "Stop Loss", "stop loss"]:
        if keyword in combined_text:
            for line in combined_text.split("\n"):
                if keyword in line and len(line) < 120:
                    key_data_lines.append(f"• {_clean_text(line)[:100]}")
                    break

    for keyword in ["仓位", "持仓", "Position", "仓位建议"]:
        if keyword in combined_text:
            for line in combined_text.split("\n"):
                if keyword in line and len(line) < 120:
                    key_data_lines.append(f"• {_clean_text(line)[:100]}")
                    break

    for keyword in ["周期", "持有周期", "Time Horizon", "horizon"]:
        if keyword in combined_text:
            for line in combined_text.split("\n"):
                if keyword in line and len(line) < 120:
                    key_data_lines.append(f"• {_clean_text(line)[:100]}")
                    break

    if key_data_lines:
        blocks.append(text_block("\n".join(key_data_lines)))
    else:
        blocks.append(text_block("• 详见下方交易计划章节"))
    blocks.append(text_block(""))

    # =================================================================
    # 投资逻辑分析（长期/中期/短期）
    # =================================================================
    blocks.append(heading2_block("投资逻辑分析"))
    blocks.append(divider_block())

    market_report = result.get("market_report", "")
    fundamentals_report = result.get("fundamentals_report", "")
    horizon = _extract_time_horizon_logic(decision, market_report, fundamentals_report)

    blocks.append(heading3_block("长期逻辑（1年以上）"))
    _add_text_section(blocks, horizon.get("长期逻辑", "暂无数据"))
    blocks.append(text_block(""))

    blocks.append(heading3_block("中期逻辑（3-12个月）"))
    _add_text_section(blocks, horizon.get("中期逻辑", "暂无数据"))
    blocks.append(text_block(""))

    blocks.append(heading3_block("短期逻辑（1-3个月）"))
    _add_text_section(blocks, horizon.get("短期逻辑", "暂无数据"))
    blocks.append(text_block(""))

    # =================================================================
    # 技术面分析
    # =================================================================
    blocks.append(heading2_block("技术面分析"))
    blocks.append(divider_block())
    if market_report:
        _add_text_section(blocks, market_report)
    else:
        blocks.append(text_block("暂无技术面数据。可能原因：API 连接超时或数据源暂时不可用。"))
    blocks.append(text_block(""))

    # =================================================================
    # 基本面分析
    # =================================================================
    blocks.append(heading2_block("基本面分析"))
    blocks.append(divider_block())
    if fundamentals_report:
        _add_text_section(blocks, fundamentals_report)
    else:
        blocks.append(text_block("暂无基本面数据。可能原因：API 连接超时或数据源暂时不可用。"))
    blocks.append(text_block(""))

    # =================================================================
    # 行业分析（新增）
    # =================================================================
    blocks.append(heading2_block("行业分析"))
    blocks.append(divider_block())
    if mx_context:
        # 从妙想数据中提取行业分析部分
        industry_section = _extract_section_from_mx(mx_context, "行业分析", "同行业对比")
        if industry_section:
            _add_text_section(blocks, industry_section)
        else:
            blocks.append(text_block("妙想数据中未找到行业分析信息。"))
    else:
        blocks.append(text_block("妙想数据未获取到，暂无行业分析。"))
    blocks.append(text_block(""))

    # =================================================================
    # 同行业竞品对比（新增）
    # =================================================================
    blocks.append(heading2_block("同行业竞品对比"))
    blocks.append(divider_block())
    if mx_context:
        peer_section = _extract_section_from_mx(mx_context, "同行业对比", "机构观点")
        if peer_section:
            _add_text_section(blocks, peer_section)
        else:
            blocks.append(text_block("妙想数据中未找到竞品对比信息。"))
    else:
        blocks.append(text_block("妙想数据未获取到，暂无竞品对比。"))
    blocks.append(text_block(""))

    # =================================================================
    # 舆情与新闻
    # =================================================================
    blocks.append(heading2_block("舆情与新闻"))
    blocks.append(divider_block())
    sentiment_report = result.get("sentiment_report", "")
    news_report = result.get("news_report", "")

    if sentiment_report:
        blocks.append(heading3_block("市场情绪"))
        _add_text_section(blocks, sentiment_report)
        blocks.append(text_block(""))

    if news_report:
        blocks.append(heading3_block("关键新闻"))
        _add_text_section(blocks, news_report)
        blocks.append(text_block(""))

    if not sentiment_report and not news_report:
        blocks.append(text_block("暂无舆情与新闻数据。可能原因：API 连接超时或数据源暂时不可用。"))
        blocks.append(text_block(""))

    # =================================================================
    # 投资辩论
    # =================================================================
    blocks.append(heading2_block("投资辩论"))
    blocks.append(divider_block())
    blocks.append(text_block("Bull Researcher 与 Bear Researcher 基于分析师报告进行的多轮辩论结论："))
    blocks.append(text_block(""))

    if investment_plan:
        blocks.append(heading3_block("辩论结论"))
        _add_text_section(blocks, investment_plan)
    else:
        blocks.append(text_block("暂无辩论记录。"))
    blocks.append(text_block(""))

    # =================================================================
    # 交易计划
    # =================================================================
    blocks.append(heading2_block("交易计划"))
    blocks.append(divider_block())

    if trader_plan:
        _add_text_section(blocks, trader_plan)
    elif investment_plan:
        _add_text_section(blocks, investment_plan)
    else:
        blocks.append(text_block("暂无交易计划。"))
    blocks.append(text_block(""))

    # =================================================================
    # 风险提示
    # =================================================================
    blocks.append(heading2_block("风险提示"))
    blocks.append(divider_block())

    # 从决策文本中提取风险相关内容
    risk_lines = []
    for line in decision.split("\n"):
        line_lower = line.lower()
        if any(kw in line_lower for kw in ["风险", "risk", " downside", "下行", "波动", "不确定", "谨慎"]):
            if len(line) < 200:
                risk_lines.append(line.strip())

    if risk_lines:
        for line in risk_lines[:10]:
            blocks.append(bullet_block(_clean_text(line)[:150]))
    else:
        blocks.append(bullet_block("投资有风险，入市需谨慎。"))
        blocks.append(bullet_block("市场波动可能导致实际收益与预期不符。"))
        blocks.append(bullet_block("宏观经济和政策变化可能影响股票表现。"))
    blocks.append(text_block(""))

    # =================================================================
    # 历史分析记录
    # =================================================================
    if history:
        blocks.append(heading2_block("历史分析记录"))
        blocks.append(divider_block())
        blocks.append(text_block("本股票的历次分析评级变化："))
        blocks.append(text_block(""))

        for record in reversed(history[-10:]):
            record_date = record.get("date", "")
            record_rating = record.get("rating", "")
            record_rating_short = _extract_rating(record_rating)[0]
            blocks.append(text_block(f"• {record_date}  |  {record_rating_short}"))

        blocks.append(text_block(""))

    # =================================================================
    # 免责声明
    # =================================================================
    blocks.append(divider_block())
    blocks.append(quote_block(
        "免责声明：本分析由 TradingAgents AI 投研系统生成，仅供研究参考，不构成投资建议。"
        "投资者应独立判断并自行承担投资风险。过往表现不代表未来收益。"
    ))
    blocks.append(text_block(
        f"\n报告生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  "
        f"|  数据源：东方财富妙想 / yfinance  "
        f"|  LLM：MiniMax-M2.7-highspeed / MiniMax-M2.5"
    ))

    return blocks


def generate_update_header_blocks(ticker: str, date: str, decision: str, analysis_index: int) -> List[Dict[str, Any]]:
    """
    为已有文档生成本次分析的更新头（用于在文档开头插入新的分析）。

    Args:
        analysis_index: 第几次分析（1=首次，2=第二次，...）
    """
    rating_display, _ = _extract_rating(decision)

    blocks = [
        divider_block(),
        heading2_block(f"第 {analysis_index} 次分析  ({date})"),
        text_block(f"决策评级：{rating_display}"),
        text_block(""),
    ]
    return blocks


def _extract_section_from_mx(mx_text: str, section_name: str, next_section_name: str = "") -> str:
    """从妙想数据中提取指定章节的内容。"""
    if not mx_text:
        return ""

    start_marker = f"=== {section_name} ==="
    end_marker = f"=== {next_section_name} ===" if next_section_name else ""

    start_idx = mx_text.find(start_marker)
    if start_idx == -1:
        return ""

    start_idx += len(start_marker)
    if end_marker:
        end_idx = mx_text.find(end_marker, start_idx)
        if end_idx == -1:
            end_idx = len(mx_text)
        section = mx_text[start_idx:end_idx].strip()
    else:
        section = mx_text[start_idx:].strip()

    # 限制长度
    return section[:2000]
