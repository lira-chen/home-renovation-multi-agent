# -*- coding: utf-8 -*-
"""
家装规范智能问答 —— RAG v2（加引用溯源 + 评测）

在 v1 基础上新增两样，让"玩具"变成"能写进简历的成品"：
    1. 引用溯源：检索时记住每段是"第几段"，回答时让模型标注 [来源N]，方便人工审核
    2. 评测集：准备一批问答，算"检索准确率"，得出一个能写进简历的数字

运行：C:/Users/86189/miniconda3/envs/dl/python.exe rag_v2.py
"""

import os
import numpy as np
import requests

# ============ 配置 ============
import config  # key 统一从 .env 读，避免硬编码泄露
DEEPSEEK_KEY = config.DEEPSEEK_KEY
SILICONFLOW_KEY = config.SILICONFLOW_KEY
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DOC_PATH = os.path.join(SCRIPT_DIR, "sample.txt")
EMBED_MODEL = "BAAI/bge-large-zh-v1.5"
BGE_QUERY_INSTRUCTION = "为这个句子生成表示以用于检索相关文章："  # BGE 要求 query 加这个前缀，检索才准
LLM_MODEL = "deepseek-chat"
CHUNK_SIZE = 200
TOP_K = 3

# ============ 基础函数（和 v1 一样，复用即可） ============
def load_doc(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def split_text(text, chunk_size=CHUNK_SIZE):
    """进阶版切段：先按句号/换行断句，再合并到约 chunk_size，绝不在句子中间硬切"""
    # 1) 断句：遇到句末标点或换行就切一刀
    sentences = []
    cur = ""
    for ch in text:
        cur += ch
        if ch in "。！？；\n":
            sentences.append(cur.strip())
            cur = ""
    if cur.strip():
        sentences.append(cur.strip())
    sentences = [s for s in sentences if s]   # 去掉空串

    # 2) 合并：贪心地把句子塞进约 chunk_size 的段里，绝不切开一个句子
    chunks = []
    buf = ""
    for s in sentences:
        if len(buf) + len(s) <= chunk_size:
            buf += s
        else:
            if buf:
                chunks.append(buf)
            buf = s
    if buf:
        chunks.append(buf)
    return chunks

def embed(texts):
    url = "https://api.siliconflow.cn/v1/embeddings"
    headers = {"Authorization": f"Bearer {SILICONFLOW_KEY}"}
    r = requests.post(url, json={"model": EMBED_MODEL, "input": texts}, headers=headers)
    r.raise_for_status()
    return [d["embedding"] for d in r.json()["data"]]

def cosine_sim(a, b):
    a, b = np.array(a), np.array(b)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9))

def call_deepseek(prompt):
    url = "https://api.deepseek.com/chat/completions"
    headers = {"Authorization": f"Bearer {DEEPSEEK_KEY}"}
    r = requests.post(url, json={
        "model": LLM_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
    }, headers=headers)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]

# ============ 新增 1：检索时带上"来源编号" ============
def vector_retrieve(chunks, chunk_vecs, query, k=TOP_K):
    """向量检索：看"意思像不像"（语义，BGE 加指令前缀）"""
    qv = embed([BGE_QUERY_INSTRUCTION + query])[0]
    sims = [cosine_sim(qv, v) for v in chunk_vecs]
    top_idx = np.argsort(sims)[-k:][::-1]
    return [(i, chunks[i]) for i in top_idx]

def keyword_retrieve(chunks, query, k=TOP_K):
    """关键词检索：看"字面重不重叠"（BM25 的极简替身，无需分词）"""
    query_chars = set(query)
    scores = []
    for chunk in chunks:
        overlap = sum(1 for ch in query_chars if ch in chunk)
        scores.append(overlap / len(query_chars))
    top_idx = np.argsort(scores)[-k:][::-1]
    return [(i, chunks[i]) for i in top_idx if scores[i] > 0]

def hybrid_retrieve(chunks, chunk_vecs, query, k=TOP_K):
    """混合检索：向量 + 关键词两条腿，用 RRF 融合"""
    vec_hits = vector_retrieve(chunks, chunk_vecs, query, k=k)
    kw_hits = keyword_retrieve(chunks, query, k=k)
    rrf = {}
    for rank, (i, _) in enumerate(vec_hits):
        rrf[i] = rrf.get(i, 0) + 1.0 / (60 + rank)
    for rank, (i, _) in enumerate(kw_hits):
        rrf[i] = rrf.get(i, 0) + 1.0 / (60 + rank)
    top = sorted(rrf.items(), key=lambda x: -x[1])[:k]
    return [(i, chunks[i]) for i, _ in top]

# 对外统一用混合检索
def retrieve_with_source(chunks, chunk_vecs, query, k=TOP_K):
    """检索入口：混合检索（向量 + 关键词），返回 (段号, 段落内容)"""
    return hybrid_retrieve(chunks, chunk_vecs, query, k=k)

# ============ 新增 2：回答时标注引用来源 ============
def answer_with_citation(chunks, chunk_vecs, query):
    """回答 + 标注依据的是哪个片段"""
    hits = retrieve_with_source(chunks, chunk_vecs, query)
    # 给每段贴个 [来源N] 标签
    numbered = "\n\n".join(f"[来源{i}] {text}" for i, text in hits)
    prompt = f"""请只根据下面提供的文档片段回答问题。如果文档中没有相关信息，就说"文档中没有提到"。
回答时，请在相关句子末尾用 [来源N] 标注你依据的是哪个片段。

文档片段：
{numbered}

问题：{query}
"""
    answer = call_deepseek(prompt)
    return answer, hits

# ============ 新增 3：评测集 ============
# 每个 (问题, 关键词) —— 关键词是正确答案所在段里独有的词，用来判断"检索找没找到"
EVAL_SET = [
    ("墙面防水高度不低于多少？", "1800"),
    ("插座回路电线截面积至少多少？", "2.5"),
    ("瓷砖空鼓面积不能超过多少？", "15%"),
    ("闭水试验蓄水时间不少于多久？", "24 小时"),
    ("墙面涂料应几底几面？", "一底两面"),
    ("环境温度低于多少度不宜涂料施工？", "5 摄氏度"),
    ("找平处理平整度误差不超过多少？", "3 毫米"),
    ("强弱电交叉处应做什么处理？", "屏蔽"),
]
def eval_retrieval(chunks, chunk_vecs):
    correct = 0
    for question, keyword in EVAL_SET:
        hits = retrieve_with_source(chunks, chunk_vecs, question)
        if any(keyword in text for _, text in hits):
            correct += 1
    return correct / len(EVAL_SET)

# ============ 主流程 ============
if __name__ == "__main__":
    text = load_doc(DOC_PATH)
    chunks = split_text(text)
    chunk_vecs = embed(chunks)
    print(f"已切 {len(chunks)} 段，已向量化\n")

    # 1) 先跑评测，看检索准不准
    acc = eval_retrieval(chunks, chunk_vecs)
    print(f"检索准确率: {acc*100:.1f}%  ({len(EVAL_SET)} 个问题)\n")

    # 2) 再演示带引用的问答
    print("===== 带引用溯源的问答 =====\n")
    while True:
        q = input("你问: ").strip()
        if q.lower() == "q":
            break
        answer, hits = answer_with_citation(chunks, chunk_vecs, q)
        print("\n回答:", answer)
        print("依据的片段:")
        for i, text in hits:
            print(f"  [来源{i}] {text[:50]}...")
        print()
