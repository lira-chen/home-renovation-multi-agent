# -*- coding: utf-8 -*-
"""
家装规范智能问答 —— 最简 RAG（入门版）

整个 RAG 就 4 步，对应下面 4 个核心函数：
    1. split_text  → 把文档切成小段
    2. embed       → 每段文字转成向量（一串数字）
    3. retrieve    → 问题也转向量，找出最相似的几段
    4. answer      → 把"相关段落 + 问题"拼成 prompt，让 DeepSeek 回答

你的任务：填好带 TODO 的地方，然后跑通它。

运行前准备：
    1. 注册 https://siliconflow.cn 拿 embedding key（免费）
    2. 填好下面的两个 key
    3. 依赖（大概率已装好）：pip install requests numpy
"""

import os
import numpy as np
import requests

# ============ 配置区（key 统一从 .env 读，别硬编码） ============
import config
DEEPSEEK_KEY = config.DEEPSEEK_KEY
SILICONFLOW_KEY = config.SILICONFLOW_KEY

DOC_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sample.txt")  # 自动定位到脚本所在文件夹
EMBED_MODEL = "BAAI/bge-large-zh-v1.5"   # 向量模型，不用改
LLM_MODEL = "deepseek-chat"               # 生成模型，不用改
CHUNK_SIZE = 300      # 每段多少字（可改着玩）
TOP_K = 3             # 检索最相似的几段（可改着玩）

# ============ 0. 读文档 ============
def load_doc(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

# ============ 1. 切段 —— 【TODO-1：你要写】 ============
def split_text(text, chunk_size=CHUNK_SIZE):
    """把一大段文本切成一个个小段，返回 list[str]"""
    # 最简单：每隔 chunk_size 个字切一刀
    #   提示：range(0, len(text), chunk_size)
    # 进阶：别在句子中间硬切——先按句号/换行断句，再合并到约 chunk_size
    return [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]

# ============ 2. 向量化 —— 已写好，你看懂就行 ============
def embed(texts):
    """把文字转成向量（一串数字），意思相近的句子，向量也相近"""
    url = "https://api.siliconflow.cn/v1/embeddings"
    headers = {"Authorization": f"Bearer {SILICONFLOW_KEY}"}
    r = requests.post(url, json={"model": EMBED_MODEL, "input": texts}, headers=headers)
    r.raise_for_status()
    return [d["embedding"] for d in r.json()["data"]]

def cosine_sim(a, b):
    """两个向量的余弦相似度：越接近 1 越像"""
    a, b = np.array(a), np.array(b)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9))

# ============ 3. 检索 —— 【TODO-2：你要写】 ============
def retrieve(chunks, chunk_vecs, query, k=TOP_K):
    """给定问题，找出最相关的 k 段，返回 list[str]"""
    # 步骤提示：
    #   1) query 转成向量：qv = embed([query])[0]
    #   2) 算 qv 和每一段向量的余弦相似度，得到列表 sims
    #   3) np.argsort(sims) 从小到大排序，取最后 k 个（最大），再倒序
    #   4) 返回这些下标对应的段落
    qv = embed([query])[0]
    sims = [cosine_sim(qv, cv) for cv in chunk_vecs]
    top_k_indices = np.argsort(sims)[-k:][::-1]
    return [chunks[i] for i in top_k_indices]
# ============ 4. 生成 —— 【TODO-3：你要写 prompt】 ============
def answer(chunks, chunk_vecs, query):
    """检索到相关段落，拼成 prompt，让 DeepSeek 回答"""
    contexts = retrieve(chunks, chunk_vecs, query)
    # TODO-3: 拼 prompt。要求包含三样：
    #   1) 检索到的几段内容 contexts
    #   2) 明确告诉模型"只根据这些片段回答，没有就说文档里没有"
    #   3) 用户的问题 query
    prompt = (f"根据以下文档内容回答问题，如果文档信息没有请回答没有相关信息。\n\n"
              f"文档内容：\n" + "\n".join(contexts) + f"\n\n用户问题：{query}\n\n请给出回答：")
    return call_deepseek(prompt)

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

# ============ 主流程 ============
if __name__ == "__main__":
    text = load_doc(DOC_PATH)
    chunks = split_text(text)
    chunk_vecs = embed(chunks)
    print(f"已切 {len(chunks)} 段，已向量化")

    print("\n开始提问（输入 q 退出）:")
    while True:
        q = input("\n你问: ").strip()
        if q.lower() == "q":
            break
        print("回答:", answer(chunks, chunk_vecs, q))
