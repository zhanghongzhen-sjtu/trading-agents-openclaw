from pathlib import Path
import hashlib


_real_md5 = hashlib.md5


def _md5_compat(*args, **kwargs):
    kwargs.pop("usedforsecurity", None)
    return _real_md5(*args, **kwargs)


hashlib.md5 = _md5_compat

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Image,
    KeepTogether,
    ListFlowable,
    ListItem,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "2.pdf"
DATA = ROOT / "trading-agents" / "scripts" / "data"


def styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "title",
            parent=base["Normal"],
            fontName="Times-Bold",
            fontSize=14,
            leading=20,
            alignment=TA_CENTER,
            spaceAfter=24,
        ),
        "major": ParagraphStyle(
            "major",
            parent=base["Normal"],
            fontName="Times-Roman",
            fontSize=14,
            leading=21,
            alignment=TA_CENTER,
            spaceAfter=18,
        ),
        "h1": ParagraphStyle(
            "h1",
            parent=base["Normal"],
            fontName="Times-Bold",
            fontSize=14,
            leading=21,
            leftIndent=1.25 * cm,
            spaceBefore=14,
            spaceAfter=8,
        ),
        "h2": ParagraphStyle(
            "h2",
            parent=base["Normal"],
            fontName="Times-Bold",
            fontSize=14,
            leading=21,
            leftIndent=1.25 * cm,
            spaceBefore=10,
            spaceAfter=6,
        ),
        "body": ParagraphStyle(
            "body",
            parent=base["Normal"],
            fontName="Times-Roman",
            fontSize=14,
            leading=21,
            firstLineIndent=1.25 * cm,
            alignment=TA_JUSTIFY,
            spaceAfter=4,
        ),
        "plain": ParagraphStyle(
            "plain",
            parent=base["Normal"],
            fontName="Times-Roman",
            fontSize=14,
            leading=21,
            alignment=TA_LEFT,
            spaceAfter=4,
        ),
        "eq": ParagraphStyle(
            "eq",
            parent=base["Normal"],
            fontName="Courier",
            fontSize=11,
            leading=16,
            leftIndent=1.25 * cm,
            spaceBefore=4,
            spaceAfter=8,
        ),
        "caption": ParagraphStyle(
            "caption",
            parent=base["Normal"],
            fontName="Times-Roman",
            fontSize=12,
            leading=16,
            alignment=TA_CENTER,
            spaceAfter=10,
        ),
        "ref": ParagraphStyle(
            "ref",
            parent=base["Normal"],
            fontName="Times-Roman",
            fontSize=12,
            leading=16,
            leftIndent=0.6 * cm,
            firstLineIndent=-0.6 * cm,
            spaceAfter=3,
        ),
    }


S = styles()


def p(text, style="body"):
    return Paragraph(text, S[style])


def heading(text, level=1):
    return Paragraph(text, S["h1" if level == 1 else "h2"])


def table(data, widths):
    t = Table(data, colWidths=widths, repeatRows=1)
    t.setStyle(
        TableStyle(
            [
                ("FONT", (0, 0), (-1, -1), "Times-Roman", 10),
                ("FONT", (0, 0), (-1, 0), "Times-Bold", 10),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.black),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EEF2F6")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return t


def fig(filename, caption, width=14.2 * cm):
    path = DATA / filename
    img = Image(str(path), width=width, height=width * 0.58)
    return KeepTogether([img, p(caption, "caption")])


def bullets(items):
    return ListFlowable(
        [ListItem(p(x, "plain"), leftIndent=0) for x in items],
        bulletType="1",
        start="1",
        leftIndent=1.25 * cm,
    )


def build():
    story = []
    story.append(p("Disagreement-Aware Multi-Agent Investment Research Decision System under Financial Uncertainty", "title"))
    story.append(p("ABSTRACT", "major"))
    story.append(p("Master thesis: XX p, 6 figures, 4 tables, 24 sources.", "plain"))
    story.append(p("LARGE LANGUAGE MODEL, MULTI-AGENT SYSTEM, FINANCIAL DECISION-MAKING, RETRIEVAL-AUGMENTED GENERATION, EVIDENCE CREDIBILITY, DISAGREEMENT DIAGNOSIS, RISK CONTROL, REVIEW MEMORY", "plain"))
    story.append(p("This thesis studies a multi-agent investment research decision system for financial markets under uncertainty. The work is based on the Trading-Agents-OpenClaw project and improves it with credibility-weighted retrieval-augmented generation, multi-dimensional disagreement diagnosis, and review-memory-driven self-calibration. Experiments show that the full model reduces position exposure in high-conflict cases and produces smaller losses and drawdowns than three ablated variants."))

    story.append(PageBreak())
    story.append(p("CONTENTS", "major"))
    for line in ["1 Introduction", "2 Related Work", "3 System Design", "4 Core Method", "5 Implementation and Experiments", "6 Conclusion", "References"]:
        story.append(p(line, "plain"))

    story.append(PageBreak())
    story.append(heading("1 Introduction"))
    story.append(p("Financial markets are dynamic systems in which structured data and unstructured information interact. Prices are affected by corporate fundamentals, technical patterns, liquidity, macro policy, investor sentiment, and unexpected events. Classical financial analysis and quantitative trading methods are useful when assumptions are stable, but they are often weak at interpreting heterogeneous text evidence and explaining conflicting signals."))
    story.append(p("Large language models can read reports, summarize news, call tools, and produce natural-language reasoning. TradingAgents applies this idea to investment research by simulating a trading firm with market analysts, fundamental analysts, news analysts, bull and bear researchers, risk managers, and traders. The Trading-Agents-OpenClaw project extends this workflow with local scripts, data integration, reporting, and review functions."))
    story.append(heading("1.1 Contributions", 2))
    story.append(bullets([
        "A credibility-weighted RAG mechanism for financial evidence.",
        "A disagreement diagnosis mechanism for direction, confidence, evidence, risk, and horizon conflict.",
        "A risk-adaptive decision mechanism that maps disagreement to position reduction.",
        "A review memory mechanism that records decisions and feedback for later calibration.",
        "An implementation and ablation evaluation based on Trading-Agents-OpenClaw.",
    ]))

    story.append(heading("2 Related Work"))
    story.append(p("Financial language models such as FinBERT, BloombergGPT, and FinGPT demonstrate the value of domain-specific language modeling for financial text. Agent frameworks such as ReAct, AutoGen, CAMEL, Generative Agents, Reflexion, Self-Refine, and Voyager show how LLMs can be connected with tools, memory, and feedback. RAG improves factual grounding, but standard RAG ranks documents mainly by relevance; financial systems also need credibility and conflict handling."))
    story.append(p("Financial strategies are commonly evaluated by return, volatility, drawdown, win rate, and risk-adjusted return. FinRL and related work emphasize reproducible backtesting and practical trading constraints. This thesis follows this evaluation logic but focuses on LLM multi-agent risk control rather than pure price prediction."))

    story.append(heading("3 System Design"))
    story.append(p("The system contains five layers: data collection, evidence processing, multi-agent analysis, uncertainty-aware decision control, and review memory. The natural-language outputs of the original agents are preserved, but key fields are extracted into structured records: action, confidence, evidence identifiers, suggested position, risk points, and time horizon."))
    story.append(table([
        ["Module", "Project file", "Function"],
        ["Analysis entry", "run_analysis.py", "Runs multi-agent analysis"],
        ["Disagreement", "uncertainty/disagreement.py", "Computes disagreement"],
        ["Adaptive decision", "uncertainty/adaptive_decision.py", "Controls final action and position"],
        ["Evidence", "uncertainty/evidence.py", "Scores evidence credibility"],
        ["Review memory", "review_memory.py, review_update.py", "Stores feedback and updates calibration"],
    ], [4.0 * cm, 5.0 * cm, 6.0 * cm]))
    story.append(p("Table 1 - Mapping between thesis modules and project files", "caption"))

    story.append(heading("4 Core Method"))
    story.append(p("Evidence credibility is computed from source authority, freshness, cross-source consistency, data quality, and historical reliability. The normalized weight constraints avoid the formula errors shown in the previous draft."))
    story.append(p("C(e_j) = alpha_s S_j + alpha_t T_j + alpha_c C_j + alpha_q Q_j + alpha_h H_j", "eq"))
    story.append(p("alpha_s + alpha_t + alpha_c + alpha_q + alpha_h = 1,   alpha_k >= 0", "eq"))
    story.append(p("Initial setting: alpha_s=0.25, alpha_t=0.20, alpha_c=0.20, alpha_q=0.20, alpha_h=0.15.", "eq"))
    story.append(p("Total disagreement combines direction, confidence, evidence, risk, and horizon disagreement."))
    story.append(p("D = lambda_1 D_dir + lambda_2 D_conf + lambda_3 D_evd + lambda_4 D_risk + lambda_5 D_hor", "eq"))
    story.append(p("lambda_1 + lambda_2 + lambda_3 + lambda_4 + lambda_5 = 1,   lambda_k >= 0", "eq"))
    story.append(p("The final position is reduced when disagreement is high:"))
    story.append(p("p = min(p_max, max(0, p_0(1 - gamma D)m_a))", "eq"))

    story.append(heading("5 Implementation and Experiments"))
    story.append(p("Four configurations are compared: Ours-full, w/o CW-RAG, w/o DADM, and w/o RMSE. Cached raw outputs are used to reduce randomness from repeated LLM calls."))
    story.append(table([
        ["Model", "Total disagreement", "Direction", "Evidence", "Position"],
        ["Ours-full", "0.466", "0.965", "0.366", "20.57%"],
        ["w/o CW-RAG", "0.473", "0.965", "0.403", "20.42%"],
        ["w/o DADM", "0.000", "0.000", "0.000", "30.00%"],
        ["w/o RMSE", "0.465", "0.965", "0.366", "21.63%"],
    ], [3.4 * cm, 3.0 * cm, 2.6 * cm, 2.6 * cm, 2.6 * cm]))
    story.append(p("Table 2 - Mechanism-level ablation result", "caption"))
    story.append(fig("fig_paper_disagreement.png", "Figure 1 - Disagreement score comparison"))
    story.append(fig("fig_paper_position.png", "Figure 2 - Suggested position comparison"))
    story.append(table([
        ["Model", "Samples", "Total return", "Volatility", "Max drawdown", "Sharpe-like"],
        ["Ours-full", "20", "-0.59%", "0.72%", "2.01%", "-0.037"],
        ["w/o CW-RAG", "20", "-4.37%", "0.58%", "4.37%", "-0.383"],
        ["w/o DADM", "20", "-7.33%", "0.95%", "7.68%", "-0.394"],
        ["w/o RMSE", "20", "-9.71%", "1.51%", "9.71%", "-0.330"],
    ], [3.1 * cm, 2.0 * cm, 2.5 * cm, 2.4 * cm, 2.5 * cm, 2.4 * cm]))
    story.append(p("Table 3 - Four-stock backtest summary", "caption"))
    story.append(fig("fig_paper_total_return_4stocks.png", "Figure 3 - Total return in the four-stock backtest"))
    story.append(fig("fig_paper_max_drawdown_4stocks.png", "Figure 4 - Maximum drawdown in the four-stock backtest"))
    story.append(fig("fig_paper_equity_curve_4stocks.png", "Figure 5 - Normalized strategy equity curve"))
    story.append(fig("fig_paper_sharpe_like_4stocks.png", "Figure 6 - Sharpe-like score comparison"))
    story.append(p("The full model still has a small negative return in this short sample, but it has the lowest loss and the smallest maximum drawdown. This supports the hypothesis that uncertainty-aware control may not guarantee profit, but can reduce risk exposure when agent opinions conflict."))

    story.append(heading("6 Conclusion"))
    story.append(p("This thesis designed and implemented a disagreement-aware multi-agent investment research decision system based on Trading-Agents-OpenClaw. The experiments show that disabling disagreement diagnosis causes the system to ignore agent conflict and increase position size. The complete system achieves the smallest loss and drawdown among the compared configurations."))
    story.append(p("The work is limited by the small backtest sample, heuristic evidence weights, and rule-based review memory. Future work should extend the system to larger stock pools, portfolio allocation, stronger risk measures such as VaR and CVaR, and more rigorous benchmarks for financial LLM agents."))

    story.append(PageBreak())
    story.append(p("REFERENCES", "major"))
    refs = [
        "Markowitz, H. Portfolio Selection. The Journal of Finance, 1952.",
        "Fama, E.F. Efficient Capital Markets: A Review of Theory and Empirical Work. The Journal of Finance, 1970.",
        "Sharpe, W.F. Mutual Fund Performance. The Journal of Business, 1966.",
        "Lo, A.W. The Adaptive Markets Hypothesis. The Journal of Portfolio Management, 2004.",
        "Moskowitz, T.J., Ooi, Y.H., Pedersen, L.H. Time Series Momentum. Journal of Financial Economics, 2012.",
        "Devlin, J. et al. BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding. NAACL, 2019.",
        "Araci, D. FinBERT: Financial Sentiment Analysis with Pre-trained Language Models. arXiv:1908.10063, 2019.",
        "Wu, S. et al. BloombergGPT: A Large Language Model for Finance. arXiv:2303.17564, 2023.",
        "Yang, H., Liu, X.-Y., Wang, C.D. FinGPT: Open-Source Financial Large Language Models. arXiv:2306.06031, 2023.",
        "Lewis, P. et al. Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks. NeurIPS, 2020.",
        "Yao, S. et al. ReAct: Synergizing Reasoning and Acting in Language Models. ICLR, 2023.",
        "Wu, Q. et al. AutoGen: Enabling Next-Gen LLM Applications via Multi-Agent Conversation. arXiv:2308.08155, 2023.",
        "Li, G. et al. CAMEL: Communicative Agents for Mind Exploration of Large Language Model Society. arXiv:2303.17760, 2023.",
        "Park, J.S. et al. Generative Agents: Interactive Simulacra of Human Behavior. UIST, 2023.",
        "Shinn, N. et al. Reflexion: Language Agents with Verbal Reinforcement Learning. NeurIPS, 2023.",
        "Madaan, A. et al. Self-Refine: Iterative Refinement with Self-Feedback. NeurIPS, 2023.",
        "Wang, G. et al. Voyager: An Open-Ended Embodied Agent with Large Language Models. arXiv:2305.16291, 2023.",
        "Xiao, Y. et al. TradingAgents: Multi-Agents LLM Financial Trading Framework. arXiv:2412.20138, 2024.",
        "Liu, X.-Y. et al. FinRL: Deep Reinforcement Learning Framework to Automate Trading in Quantitative Finance. ICAIF, 2021.",
        "Liu, X.-Y. et al. FinRL: A Deep Reinforcement Learning Library for Automated Stock Trading. arXiv:2011.09607, 2020.",
        "Yang, H. et al. Deep Reinforcement Learning for Automated Stock Trading: An Ensemble Strategy. ICAIF, 2020.",
        "Sezer, O.B. et al. Financial Time Series Forecasting with Deep Learning: A Systematic Literature Review. Applied Soft Computing, 2020.",
        "Ozbayoglu, A.M. et al. Deep Learning for Financial Applications: A Survey. Applied Soft Computing, 2020.",
        "Trading-Agents-OpenClaw project repository and local implementation files, 2026.",
    ]
    for idx, ref in enumerate(refs, 1):
        story.append(p(f"{idx}. {ref}", "ref"))

    doc = SimpleDocTemplate(
        str(OUT),
        pagesize=A4,
        rightMargin=1 * cm,
        leftMargin=3 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )
    doc.build(story)


if __name__ == "__main__":
    build()
