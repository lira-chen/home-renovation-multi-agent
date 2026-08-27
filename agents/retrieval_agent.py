# -*- coding: utf-8 -*-
"""检索 Agent：把 sample.txt 切段、向量化，对外提供混合检索。

这是把 rag_v2.py 里的检索能力抽出来封装成独立模块，供方案生成 / 施工对接 Agent 调用。
"""
import numpy as np

import config
from agents import llm


class DocumentStore:
    """持有文档 + 向量，只对外暴露 retrieve()。初始化时切段并向量化。"""

    def __init__(self, path=config.DOC_PATH, chunk_size=config.CHUNK_SIZE):
        with open(path, encoding="utf-8") as f:
            text = f.read()
        self.chunks = llm.split_text(text, chunk_size)
        self.chunk_vecs = llm.embed(self.chunks)

    def vector_retrieve(self, query, k=config.TOP_K):
        """向量检索：看语义像不像。"""
        qv = llm.embed([config.BGE_QUERY_INSTRUCTION + query])[0]
        sims = [llm.cosine_sim(qv, v) for v in self.chunk_vecs]
        top = np.argsort(sims)[-k:][::-1]
        return [(int(i), self.chunks[i]) for i in top]

    def keyword_retrieve(self, query, k=config.TOP_K):
        """关键词检索：看字面重不重叠（BM25 极简替身，无需分词）。"""
        qchars = set(query)
        scores = []
        for c in self.chunks:
            overlap = sum(1 for ch in qchars if ch in c)
            scores.append(overlap / len(qchars))
        top = np.argsort(scores)[-k:][::-1]
        return [(int(i), self.chunks[i]) for i in top if scores[i] > 0]

    def retrieve(self, query, k=config.TOP_K):
        """混合检索：向量 + 关键词两条腿，用 RRF 融合，返回 [(段号, 段落)]。"""
        vec = self.vector_retrieve(query, k)
        kw = self.keyword_retrieve(query, k)
        rrf = {}
        for rank, (i, _) in enumerate(vec):
            rrf[i] = rrf.get(i, 0) + 1.0 / (60 + rank)
        for rank, (i, _) in enumerate(kw):
            rrf[i] = rrf.get(i, 0) + 1.0 / (60 + rank)
        top = sorted(rrf.items(), key=lambda x: -x[1])[:k]
        return [(i, self.chunks[i]) for i, _ in top]
