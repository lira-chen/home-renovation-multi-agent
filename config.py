# -*- coding: utf-8 -*-
"""
全局配置：API key、模型、路径、参数。整个多 Agent 系统都从这里读，别在别处硬编码 key。

API key 只从 .env 文件（或系统环境变量）读取，不硬编码、不提交到 GitHub。
首次使用：复制 .env.example 为 .env，填上你的 key。
"""
import os

ROOT = os.path.dirname(os.path.abspath(__file__))


def _load_env(path):
    """极简 .env 加载器（不依赖 python-dotenv）：读 KEY=VALUE 行，设进环境变量。"""
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k, v = k.strip(), v.strip().strip('"').strip("'")
            if k and k not in os.environ:
                os.environ[k] = v


# 先加载项目里的 .env（如果有），再读 key
_load_env(os.path.join(ROOT, ".env"))

# ==== API Keys（只从环境变量读，不写死，防泄露）====
DEEPSEEK_KEY = os.environ.get("DEEPSEEK_KEY", "")
SILICONFLOW_KEY = os.environ.get("SILICONFLOW_KEY", "")

# ==== 模型 ====
LLM_MODEL = "deepseek-chat"
EMBED_MODEL = "BAAI/bge-large-zh-v1.5"
BGE_QUERY_INSTRUCTION = "为这个句子生成表示以用于检索相关文章："  # BGE 检索时 query 要加这个前缀才准

# ==== 路径（都基于本文件所在目录，跨目录运行也不会找不到文件）====
DOC_PATH = os.path.join(ROOT, "sample.txt")
PRICE_TABLE_PATH = os.path.join(ROOT, "price_table.json")
TRACE_DIR = os.path.join(ROOT, "trace")

# ==== 参数 ====
CHUNK_SIZE = 200      # 切段字数
TOP_K = 3             # 检索返回条数
LLM_TEMPERATURE = 0.1
MAX_FOLLOWUP_ROUNDS = 3   # 信息补全最多追问几轮

# 需求里必填的字段（问不出来就触发信息补全）
REQUIRED_FIELDS = ["户型", "面积_平米", "预算_元"]
