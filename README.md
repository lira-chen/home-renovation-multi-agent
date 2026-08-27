# 家装多 Agent 系统（Multi-Agent Home Renovation Pipeline）

一个面向真实业务的多 Agent 装修链路：**需求收集 → 信息补全 → 规范检索 → 方案生成 → 报价核算 → 施工对接**。
不是单个 RAG 问答，而是多个 Agent 之间**用结构化 JSON 传递数据、编排成一条完整业务链路**。

## 为什么做这个

装修需求是一句话（"90 平三居室，预算 20 万，现代简约"），但落地要经过：把话说清楚 → 查施工规范 → 出方案 → 算钱 → 对接施工队。每一步是一个 Agent，串起来就是可复现的业务流水线。

对应岗位能力点：
- **Agent 任务编排**：orchestrator.py 串联 6 步，控制信息补全的循环
- **模块间结构化数据传递（JSON）**：Agent 之间只传 JSON，不传自然语言
- **数据知识工程**：本地价格库 `price_table.json`、规范文档 `sample.txt`

## 架构

```
用户输入（自然语言）
      │
      ▼
┌──────────────────┐
│ ① 需求收集 Agent   │  LLM 解析 → requirements.json（含"缺失字段"）
└────────┬─────────┘
         │ 缺关键字段？→ 追问（信息补全，最多 3 轮）
         ▼
┌──────────────────┐
│ ② 检索 Agent       │  混合检索（向量+关键词 RRF）→ 规范依据 [来源N]
└────────┬─────────┘
         ▼
┌──────────────────┐
│ ③ 方案生成 Agent   │  LLM → plan.json
└────────┬─────────┘
     ┌───┴────────────┐
     ▼                ▼
┌──────────────┐  ┌────────────────┐
│ ④ 报价 Agent   │  │ ⑤ 施工对接 Agent │
│ 纯本地价格库   │  │ LLM → 施工要点   │
└──────────────┘  └────────────────┘
     │
     ▼
全链路轨迹落盘 trace/run_xxx.jsonl
```

## 各 Agent 的输入 / 输出（JSON Schema）

| Agent | 输入 | 输出 | 是否调 LLM |
|---|---|---|---|
| 需求收集 | 自然语言 | `requirements.json`（户型/面积/预算/风格/是否毛坯/装修范围/缺失字段） | 是（NLU） |
| 检索 | 需求 JSON | `[(来源号, 规范段落)]` | 否（只用 embedding） |
| 方案生成 | 需求 + 规范依据 | `plan.json`（整体说明 + 各空间施工项目 + 规范依据） | 是（生成） |
| 报价 | 需求 + 方案 + 价格库 | `quote.json`（明细 + 未匹配 + 合计） | **否（纯本地计算）** |
| 施工对接 | 需求 + 方案 + 规范依据 | `construction.json`（施工要点 + 验收标准 + 安全提示） | 是（生成） |

### requirements.json 示例
```json
{
  "户型": "三室两厅",
  "面积_平米": 90,
  "预算_元": 200000,
  "风格": "现代简约",
  "是否毛坯": "是",
  "装修范围": ["全屋"],
  "特殊需求": "",
  "缺失字段": []
}
```

### quote.json 示例（报价 Agent 输出，数字全来自价格库）
```json
{
  "明细": [{"项目": "墙面涂刷", "单位": "㎡", "数量": 225.0, "单价": 30, "小计": 6750.0}],
  "未匹配项目": [],
  "合计": 6750.0,
  "说明": "单价来自本地价格库（price_table.json）..."
}
```

## 三个核心设计（对应真实业务里的"脏活"）

### 1. JSON 容错层（`agents/json_utils.py`）
LLM 吐出的 JSON 经常不合法（代码块围栏、尾逗号、夹带说明、截断）。容错层做 4 道保险：
剥围栏 → 截取 `{...}` → 修尾逗号 → 解析失败把报错回喂模型重试（最多 2 次），仍失败返回 `{"error": ...}`，**链路不崩**。

### 2. 全链路轨迹落盘（`orchestrator.py` 的 TraceLogger）
每一步的 `输入/原始LLM输出/解析结果` 追加写进 `trace/run_时间戳.jsonl`，方便 debug、复现、做评测。

### 3. 报价不靠大模型（`agents/quote_agent.py`）
报价 Agent **不调用 LLM**。单价只读 `price_table.json`，工程量按面积 × 系数估算（标注需现场量房），
合计 = 各小计之和。可复现、可审计——LLM 只会编数，报价必须可查。

## 运行

**首次使用**：复制 `.env.example` 为 `.env`，填上你的 API key（`.env` 已被 gitignore，不会提交到 GitHub）。

```bash
# 依赖（已装则跳过）
pip install -r requirements.txt

# 命令行跑完整链路
C:/Users/86189/miniconda3/envs/dl/python.exe orchestrator.py

# 网页界面
C:/Users/86189/miniconda3/envs/dl/python.exe -m streamlit run app.py

# 跑评测，输出量化指标
C:/Users/86189/miniconda3/envs/dl/python.exe eval/run_eval.py
```

## 评测指标

`eval/run_eval.py` 输出 4 个硬数字：
1. **JSON 解析成功率**（容错层）
2. **RAG 召回率**（检索准不准，8 题）
3. **报价确定性**（单价来自价格库、合计正确、无未匹配）
4. **端到端链路成功率**（完整跑通不崩的比例）

本次实测（sample.txt + 8 题检索集 + 2 个端到端样例）：
- JSON 解析成功率 6/6 = **100%**
- RAG 召回率 8/8 = **100%**
- 报价确定性 **通过**
- 端到端链路成功率 2/2 = **100%**

## 数据来源说明（诚实标注）

> 本项目演示的是**多 Agent 链路**，不是真实生产数据。数据来源如实说明：

- `sample.txt`：**示例文档**，章节结构对照 GB 50327-2001《住宅装饰装修工程施工规范》十六章，**内容为编写示例、非标准原文**（勿当国标原文使用）。可换成真国标全文（用 `pdf2txt.py` 把 PDF 转文本）。
- `price_table.json`：本地价格库，单价为 2024-2025 年中等档次**市场参考价**（人工+辅料，主材另计），**非官方/非实时报价**，真实报价需按地区、档次、时点调整。报价 Agent 的作用是演示"数字来自价格库、不靠大模型"这条链路，而非给真实装修报价。

## 目录结构

```
rag_project/
├── config.py                # 全局配置（key、模型、路径、参数）
├── sample.txt               # 规范文档（检索数据源）
├── price_table.json         # 本地价格库（报价数据源）
├── orchestrator.py          # 编排器 + 轨迹落盘 + 命令行入口
├── app.py                   # Streamlit 网页
├── agents/
│   ├── llm.py               # 共享 LLM / embedding / 切段
│   ├── json_utils.py        # JSON 容错层
│   ├── requirement_agent.py # 需求收集
│   ├── retrieval_agent.py   # 检索（混合检索）
│   ├── plan_agent.py        # 方案生成
│   ├── quote_agent.py       # 报价（纯本地）
│   └── construction_agent.py# 施工对接
├── eval/
│   ├── test_cases.py        # 测试数据
│   └── run_eval.py          # 评测脚本
├── rag_v2.py                # 单 Agent RAG（历史教程，本系统的检索来源）
├── pdf2txt.py               # PDF → 文本
└── trace/                   # 运行时生成的轨迹（已 gitignore）
```

## API key 与安全

key **不硬编码在代码里**，统一从 `.env` 文件读（`config.py` 只读环境变量）。流程：
1. 复制 `.env.example` 为 `.env`
2. 填入你的 key：
   - `DEEPSEEK_KEY`：https://platform.deepseek.com/
   - `SILICONFLOW_KEY`：https://siliconflow.cn/
3. `.env` 已在 `.gitignore` 里，`git push` 不会带上它

> 提醒：如果 key 曾经出现在聊天记录或旧提交里，建议去平台**重置一次**，旧 key 作废最稳妥。

## 部署到 Streamlit Cloud（网页上线）

代码推上 GitHub 后，几步就能上线成公开网页：

1. 打开 https://share.streamlit.io ，用 **GitHub 账号登录**（和仓库同一个号）。
2. 点 **Create app**（或 New app）→ 选仓库 `home-renovation-multi-agent`、分支 `main`、主文件 `app.py`。
3. 展开 **Advanced settings** → 填 **Secrets**（这里就是云端版的 `.env`，**不会**公开）：
   ```
   DEEPSEEK_KEY = "sk-你的deepseek密钥"
   SILICONFLOW_KEY = "sk-你的硅基流动密钥"
   ```
4. 点 **Deploy**，等 1-2 分钟构建，得到公开网址。

> 原理：`app.py` 开头会把 Streamlit 的 `st.secrets` 注入到环境变量，`config.py` 照常读 `os.environ`，所以云端和本地用的是同一套代码，key 只存在云端 Secrets 里、不进仓库。

## 关系说明

`rag_v2.py` 是本项目早期的单 Agent RAG 教程产物；本系统的检索能力由 `agents/retrieval_agent.py` 承载，
是从 `rag_v2.py` 抽取并封装的。多 Agent 系统（`orchestrator.py`）才是正式作品。
