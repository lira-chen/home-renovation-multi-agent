# -*- coding: utf-8 -*-
"""共享底层能力：调 LLM、向量化、切段。各个 Agent 都从这里拿基础函数。"""
import numpy as np
import requests

import config


def call_llm(messages, temperature=None, json_mode=False):
    """调 DeepSeek 对话接口，返回文本。json_mode=True 时要求模型只输出 JSON。"""
    if not config.DEEPSEEK_KEY:
        raise RuntimeError("未配置 DEEPSEEK_KEY：复制 .env.example 为 .env 并填入你的 key")
    if temperature is None:
        temperature = config.LLM_TEMPERATURE
    url = "https://api.deepseek.com/chat/completions"
    headers = {"Authorization": f"Bearer {config.DEEPSEEK_KEY}"}
    payload = {"model": config.LLM_MODEL, "messages": messages, "temperature": temperature}
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    r = requests.post(url, json=payload, headers=headers, timeout=60)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def embed(texts):
    """把文字转成向量（SiliconFlow 的 BGE 模型），返回 list[list[float]]。"""
    if not config.SILICONFLOW_KEY:
        raise RuntimeError("未配置 SILICONFLOW_KEY：复制 .env.example 为 .env 并填入你的 key")
    url = "https://api.siliconflow.cn/v1/embeddings"
    headers = {"Authorization": f"Bearer {config.SILICONFLOW_KEY}"}
    r = requests.post(url, json={"model": config.EMBED_MODEL, "input": texts}, headers=headers, timeout=60)
    r.raise_for_status()
    return [d["embedding"] for d in r.json()["data"]]


def cosine_sim(a, b):
    """两个向量的余弦相似度，越接近 1 越像。"""
    a, b = np.array(a), np.array(b)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9))


def split_text(text, chunk_size=config.CHUNK_SIZE):
    """按句末标点/换行断句，再贪心合并到约 chunk_size，绝不切开句子。"""
    sentences, cur = [], ""
    for ch in text:
        cur += ch
        if ch in "。！？；\n":
            sentences.append(cur.strip())
            cur = ""
    if cur.strip():
        sentences.append(cur.strip())
    sentences = [s for s in sentences if s]

    chunks, buf = [], ""
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
