# Trading-Agents-OpenClaw：面向金融不确定性的多智能体投研决策系统

本项目基于 [`trading-agents-openclaw`](https://github.com/DWLng/trading-agents-openclaw) 进行二次开发，面向金融投研场景中常见的多源信息冲突、智能体观点分歧、证据可信度不一致和决策风险暴露问题，构建了一个带有 **不确定性诊断、风险自适应决策、证据可信度加权和复盘记忆校准** 的多智能体金融决策系统。

原始项目能够完成股票的技术面、基本面、新闻面、情绪面、多空辩论和交易计划生成。本项目在此基础上进一步增加了三个核心创新模块：

1. **分歧感知的多智能体金融决策机制**
2. **证据可信度加权 RAG 机制**
3. **复盘记忆驱动的自我校准机制**

系统最终可以生成飞书投研文档，并输出：

- 综合分歧指数
- 主要分歧类型
- 证据可信度
- 冲突证据
- 风险自适应建议
- 建议仓位
- 复盘记忆更新结果
- 消融实验与回测验证结果

---

## 1. 项目主要改进

### 1.1 分歧感知的多智能体金融决策机制

原始 TradingAgents 流程中，不同分析智能体会分别给出技术面、基本面、新闻面、情绪面和交易建议，但系统没有显式量化智能体之间的分歧。

本项目新增 `uncertainty/disagreement.py`，将不同智能体的输出结构化为 `AgentOutput`，并从以下五个维度计算多智能体分歧：

- **方向分歧**：不同智能体对买入、持有、卖出的判断差异
- **置信度分歧**：不同智能体信心程度差异
- **证据分歧**：不同证据源之间的看多、看空、中性冲突
- **风险分歧**：不同智能体对风险暴露的判断差异
- **时间尺度分歧**：短期、中期、长期判断不一致

最终形成综合分歧指数：

```text
D = λ1Ddirection + λ2Dconfidence + λ3Devidence + λ4Drisk + λ5Dhorizon
```

该分歧指数会进一步影响最终仓位和风险控制策略。

---

### 1.2 风险自适应决策机制

新增 `uncertainty/adaptive_decision.py`，根据综合分歧指数和主要分歧类型，动态调整最终交易建议和仓位。

当多智能体之间出现较高分歧时，系统不会直接给出激进交易建议，而是通过风险惩罚参数降低仓位暴露。

示例：

```text
综合分歧指数：0.466
主要分歧类型：direction
风险自适应建议：buy
建议仓位：20.57%
```

在缓存版消融实验中，关闭分歧诊断后，系统无法识别智能体冲突，仓位上升：

```text
Ours-full：建议仓位 20.57%
w/o DADM：建议仓位 30.00%
```

这说明分歧诊断机制能够在高不确定性场景下抑制过度仓位暴露。

---

### 1.3 证据可信度加权 RAG

新增 `uncertainty/evidence.py`，将 TradingAgents 产生的报告进一步结构化为证据对象 `Evidence`。

每条证据包含：

```text
evidence_id
source
evidence_type
stance
credibility_score
conflict_ids
```

系统从以下因素综合计算证据可信度：

- 来源权威性
- 证据类型可靠性
- 文本质量
- 跨源一致性
- 历史可靠性

示例输出：

```text
证据可信度明细：
• market_report：方向 看空，可信度 0.762
• fundamentals_report：方向 中性，可信度 0.827
• sentiment_report：方向 看空，可信度 0.543
• news_report：方向 看多，可信度 0.495
• final_trade_decision：方向 看空，可信度 0.802
```

系统还会检测冲突证据，例如：

```text
market_report 与 news_report 冲突
sentiment_report 与 news_report 冲突
final_trade_decision 与 news_report 冲突
```

该机制用于提升系统对多源金融信息的可信度建模能力。

---

### 1.4 复盘记忆驱动的自我校准机制

新增 `uncertainty/review_memory.py` 和 `review_update.py`，实现复盘记忆功能。

系统每次分析后，会将以下内容写入：

```text
data/review_memory.json
```

包括：

- 股票代码
- 分析日期
- 综合分歧指数
- 主要分歧类型
- 最终动作
- 建议仓位
- 证据可信度
- 智能体输出

后续可以通过真实收益反馈更新系统参数：

```powershell
python review_update.py --ticker 000630 --return-rate -0.05 --max-drawdown 0.08
```

复盘更新会调整：

- 分歧惩罚参数
- 证据源可信度
- 证据类型可信度
- 智能体权重

从而实现：

```text
历史复盘结果 → 参数校准 → 影响下一次证据评分和仓位控制
```

---

## 2. 新增代码结构

```text
trading-agents/scripts/
├── run_analysis.py                 # 主分析入口，集成不确定性增强层
├── report_generator.py             # 飞书报告生成器，新增不确定性诊断展示
├── review_update.py                # 复盘记忆更新脚本
├── run_backtest.py                 # 多模式回测验证脚本
├── run_ablation_from_cache.py      # 基于缓存的严格消融实验脚本
├── plot_backtest.py                # 回测结果图表生成脚本
├── plot_ablation.py                # 消融结果图表生成脚本
├── uncertainty/
│   ├── __init__.py
│   ├── disagreement.py             # 多维分歧诊断
│   ├── adaptive_decision.py        # 风险自适应决策
│   ├── evidence.py                 # 证据可信度加权
│   └── review_memory.py            # 复盘记忆自我校准
└── validation/
    ├── __init__.py
    └── price_loader.py             # 真实历史价格收益获取
```

---

## 3. 环境准备

进入项目目录后，建议先激活虚拟环境：

```powershell
cd C:\Users\31231\OneDrive\Desktop\学习\trading-agents-openclaw
.\.venv\Scripts\Activate.ps1
```

进入脚本目录：

```powershell
cd trading-agents\scripts
```

如果需要真实历史价格收益验证，需要安装：

```powershell
pip install yfinance
```

如果需要生成图表，需要安装：

```powershell
pip install matplotlib
```

如果安装较慢，可以使用清华源：

```powershell
pip install yfinance matplotlib -i https://pypi.tuna.tsinghua.edu.cn/simple
```

---

## 4. 快速开始

### 4.1 运行完整模型并生成飞书文档

```powershell
python run_analysis.py --ticker 000630 --market cn --output-mode feishu-doc --skip-mx --timeout 1200 --retries 0
```

成功后终端会输出飞书文档链接：

```text
📄 飞书文档已生成/更新：https://...
```

---

### 4.2 输出飞书消息格式

```powershell
python run_analysis.py --ticker 000630 --market cn --output-mode feishu-msg --skip-mx --timeout 1200 --retries 0
```

---

### 4.3 输出 JSON

```powershell
python run_analysis.py --ticker 000630 --market cn --output-mode json --skip-mx --timeout 1200 --retries 0
```

---

## 5. 输出模式说明

`run_analysis.py` 支持多种输出模式：

```text
feishu-doc：生成或更新飞书文档
feishu-msg：输出飞书消息格式摘要
json：输出完整 JSON，适合程序读取
raw：只输出最终交易决策
```

示例：

```powershell
python run_analysis.py --ticker 000630 --market cn --output-mode feishu-msg --skip-mx --timeout 1200 --retries 0
```

---

## 6. 消融实验

为了验证不同模块的作用，系统支持以下消融开关。

### 6.1 完整模型 Ours-full

```powershell
python run_analysis.py --ticker 000630 --market cn --output-mode feishu-doc --skip-mx --timeout 1200 --retries 0
```

### 6.2 去掉证据可信度加权 Ours-w/o CW-RAG

```powershell
python run_analysis.py --ticker 000630 --market cn --output-mode feishu-doc --skip-mx --timeout 1200 --retries 0 --disable-evidence-weight
```

### 6.3 去掉分歧诊断 Ours-w/o DADM

```powershell
python run_analysis.py --ticker 000630 --market cn --output-mode feishu-doc --skip-mx --timeout 1200 --retries 0 --disable-disagreement
```

### 6.4 去掉复盘记忆 Ours-w/o RMSE

```powershell
python run_analysis.py --ticker 000630 --market cn --output-mode feishu-doc --skip-mx --timeout 1200 --retries 0 --disable-review-memory
```

---

## 7. 基于缓存的严格消融实验

直接重复运行四个模型会导致 TradingAgents 底层大模型输出波动。为了更严格控制变量，本项目新增缓存版消融实验脚本：

```text
run_ablation_from_cache.py
```

该脚本只运行一次 TradingAgents 原始分析，然后在同一份 `raw_result` 上分别运行四种不确定性配置。

### 7.1 首次运行并生成缓存

```powershell
python run_ablation_from_cache.py --ticker 000630 --market cn --date 2026-05-15 --holding-days 5 --allow-short
```

### 7.2 使用缓存快速复现实验

```powershell
python run_ablation_from_cache.py --ticker 000630 --market cn --date 2026-05-15 --holding-days 5 --allow-short --use-cache
```

缓存文件保存在：

```text
data/ablation_cache/
```

示例输出：

```text
📦 使用缓存 raw_result: data\ablation_cache\000630_cn_2026-05-15_raw_result.json
真实持有期收益: 000630 | 2026-05-15 | 5日 | -3.22%
🧪 运行消融配置: ours-full
🧪 运行消融配置: wo-cw-rag
🧪 运行消融配置: wo-dadm
🧪 运行消融配置: wo-rmse
✅ 缓存版消融实验完成
```

---

## 8. 真实收益验证

项目支持使用历史价格计算真实持有期收益率。价格数据由 `validation/price_loader.py` 通过 `yfinance` 获取。

安装依赖：

```powershell
pip install yfinance
```

真实 5 日持有期收益验证示例：

```powershell
python run_ablation_from_cache.py --ticker 000630 --market cn --date 2026-05-15 --holding-days 5 --allow-short --use-cache
```

示例结果：

```text
真实持有期收益: 000630 | 2026-05-15 | 5日 | -3.22%

ours-full: action=buy, position=20.57%, strategy_return=-0.66%, disagreement=0.466, avg_credibility=0.673
wo-cw-rag: action=buy, position=20.42%, strategy_return=-0.66%, disagreement=0.473, avg_credibility=0.770
wo-dadm: action=buy, position=30.00%, strategy_return=-0.96%, disagreement=0.000, avg_credibility=0.673
wo-rmse: action=buy, position=21.63%, strategy_return=-0.70%, disagreement=0.465, avg_credibility=0.635
```

该结果说明，在真实下跌区间中，关闭分歧诊断后模型仓位上升至 30%，导致亏损扩大。完整模型通过分歧感知降低仓位，从而降低下跌风险暴露。

---

## 9. 普通回测脚本

除了缓存版消融实验，也可以使用 `run_backtest.py` 进行多模式回测。

### 9.1 手动指定持有期收益

```powershell
python run_backtest.py --tickers 000630 --market cn --dates 2026-05-15 --holding-return -0.05 --allow-short
```

### 9.2 使用真实历史价格收益

```powershell
python run_backtest.py --tickers 000630 --market cn --dates 2026-05-15 --holding-days 5 --allow-short
```

### 9.3 多日期验证

```powershell
python run_backtest.py --tickers 000630 --market cn --dates 2026-04-15 2026-04-22 2026-04-29 2026-05-06 2026-05-15 --holding-days 5 --allow-short
```

输出文件：

```text
data/backtest_results.csv
data/backtest_summary.csv
```

---

## 10. 图表生成

回测或消融实验完成后，可以生成图表：

```powershell
copy data\ablation_cache\000630_cn_2026-05-15_ablation_results.csv data\backtest_results.csv
python plot_backtest.py
```

生成图表：

```text
data/fig_disagreement.png
data/fig_position.png
data/fig_strategy_return.png
data/fig_evidence_disagreement.png
data/fig_risk_disagreement.png
```

推荐用于论文展示的图：

```text
图 5-1 不同模型综合分歧指数对比
图 5-2 不同模型建议仓位对比
图 5-3 单案例模拟策略收益对比
```

---

## 11. 复盘记忆更新

当获得某只股票后续真实收益后，可以更新复盘记忆：

```powershell
python review_update.py --ticker 000630 --return-rate -0.05 --max-drawdown 0.08
```

输出示例：

```text
✅ 复盘记忆已更新
股票：000630
后续收益率：-5.00%
最大回撤：8.00%

分歧惩罚参数更新：
- 分歧类型：direction
- 旧参数：0.625
- 新参数：0.650
- 原因：最大回撤较高，提高风险惩罚

证据可信度更新：
- market_report | source 0.750 → 0.710 | type 0.750 → 0.710

智能体权重更新：
- Market Analyst | 0.700 → 0.740
```

---

## 12. 飞书文档新增展示内容

飞书报告中新增“不确定性诊断与风险自适应决策”章节，包含：

```text
综合分歧指数
主要分歧类型
触发控制动作
风险自适应建议
建议仓位
风险等级

分歧来源明细：
方向分歧
置信度分歧
证据分歧
风险分歧
时间尺度分歧

证据可信度明细：
market_report
fundamentals_report
sentiment_report
news_report
final_trade_decision
```

示例：

```text
综合分歧指数：0.466
主要分歧类型：direction
风险自适应建议：买入
建议仓位：20.57%

分歧来源明细：
• 方向分歧：0.965
• 证据分歧：0.366
• 风险分歧：0.250
```

---

## 13. 实验结果示例

基于缓存控制变量的消融实验结果如下：

| 模型 | 综合分歧指数 | 建议仓位 | 策略收益 | 平均证据可信度 |
|---|---:|---:|---:|---:|
| Ours-full | 0.466 | 20.57% | -0.66% | 0.673 |
| Ours-w/o CW-RAG | 0.473 | 20.42% | -0.66% | 0.770 |
| Ours-w/o DADM | 0.000 | 30.00% | -0.96% | 0.673 |
| Ours-w/o RMSE | 0.465 | 21.63% | -0.70% | 0.635 |

实验结论：

- 关闭分歧诊断后，综合分歧指数被置为 0，系统无法感知智能体冲突。
- 关闭分歧诊断后，建议仓位上升至 30%，风险暴露显著提高。
- 在真实 5 日收益为 -3.22% 的下跌区间中，w/o DADM 亏损扩大至 -0.96%。
- 完整模型通过分歧感知和复盘记忆校准，将仓位控制在 20.57%，亏损相对更小。

---

## 14. 注意事项

### 14.1 不要提交本地敏感文件

以下文件或目录不应提交到 GitHub：

```text
openclaw.json
data/
log.txt
.venv-wsl/
TradingAgents-Kimi/
```

尤其是：

```text
openclaw.json
```

其中可能包含 API Key。

### 14.2 JSON 输出编码

Windows PowerShell 默认编码可能导致 emoji 输出失败。因此本项目在 `json` 模式下使用：

```python
json.dumps(result, ensure_ascii=True, indent=2)
```

以保证回测脚本稳定读取。

### 14.3 消融实验建议使用缓存版

为了避免大语言模型生成波动影响结果，建议正式实验使用：

```text
run_ablation_from_cache.py
```

而不是重复运行四次 `run_analysis.py`。

---

## 15. 项目链接

本项目二次开发仓库：

```text
https://github.com/zhanghongzhen-sjtu/trading-agents-openclaw
```

原始项目：

```text
https://github.com/DWLng/trading-agents-openclaw
```

---

## 16. 免责声明

本项目仅用于学术研究和金融智能体系统实验，不构成任何投资建议。股票分析结果、交易方向和建议仓位仅供研究参考，实际投资应结合个人风险承受能力和专业判断。