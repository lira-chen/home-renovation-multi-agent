# -*- coding: utf-8 -*-
"""
跑评测，输出量化指标（这就是能写进简历/README 的"硬数字"）：
    1. JSON 解析成功率      —— 容错层能不能救回坏 JSON
    2. RAG 召回率           —— 检索准不准
    3. 报价确定性           —— 报价是否完全来自本地价格库、可复现
    4. 端到端链路成功率     —— 完整跑下来不崩的比例

运行（在项目根目录）：
    C:/Users/86189/miniconda3/envs/dl/python.exe eval/run_eval.py

注意：第 2、4 项要调线上 API（embedding / LLM），会花 token 和时间。
"""
import os
import sys

# 让脚本能 import 到项目根目录的 config / agents / orchestrator
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents import json_utils
from agents.retrieval_agent import DocumentStore
from agents import quote_agent
from orchestrator import run_pipeline
from eval.test_cases import MALFORMED_JSON_CASES, RETRIEVAL_CASES, END_TO_END_CASES


def eval_json_robustness():
    """容错层：能本地修复的算对，本地修不了但能兜底不崩也算'容错通过'。"""
    repaired = 0
    for text, expect in MALFORMED_JSON_CASES:
        obj, _ = json_utils.parse_json_response(text)
        got = "error" not in obj
        repaired += (got == expect)
    return repaired, len(MALFORMED_JSON_CASES)


def eval_retrieval(store):
    correct = 0
    for q, kw in RETRIEVAL_CASES:
        hits = store.retrieve(q)
        if any(kw in text for _, text in hits):
            correct += 1
    return correct, len(RETRIEVAL_CASES)


def eval_quote_deterministic():
    """报价必须：单价来自价格库、合计=小计之和、无未匹配项目。返回 (通过项, 总项)。"""
    table = quote_agent.load_price_table()
    plan = {"空间": [{"名称": "客厅", "施工项目": ["墙面涂刷", "地面找平", "地砖铺贴"]}]}
    req = {"面积_平米": 100}
    quote = quote_agent.quote(req, plan, table)

    checks, total = 0, 0.0
    ok = True
    for line in quote["明细"]:
        key = line["项目"]
        if key not in table or table[key]["单价"] != line["单价"]:
            ok = False
        total += line["小计"]
    if abs(total - quote["合计"]) > 0.01:
        ok = False
    if quote["未匹配项目"]:
        ok = False
    return (1 if ok else 0), 1


def eval_end_to_end():
    """端到端：跑完整链路，统计结构完整（无 error 标记、报价有数字）的比例。"""
    ok = 0
    for s in END_TO_END_CASES:
        try:
            r = run_pipeline(s, followup_fn=lambda missing, req: {})
            good = (isinstance(r["requirements"], dict) and "error" not in r["requirements"]
                    and isinstance(r["plan"], dict) and "error" not in r["plan"]
                    and isinstance(r["quote"].get("合计"), (int, float))
                    and isinstance(r["construction"], dict) and "error" not in r["construction"])
            ok += good
            print(f"  [端到端] {'OK' if good else 'FAIL'} {s[:30]}...")
        except Exception as e:
            print(f"  [端到端] FAIL 异常：{e}")
    return ok, len(END_TO_END_CASES)


def main():
    print("=" * 56)
    print("家装多 Agent 系统 —— 评测报告")
    print("=" * 56)

    # 1. JSON 容错
    a, b = eval_json_robustness()
    print(f"\n[1] JSON 解析成功率（容错层）：{a}/{b} = {a / b * 100:.0f}%")

    # 2. RAG 召回
    print("[2] 检索中（调 embedding API）...")
    store = DocumentStore()
    a, b = eval_retrieval(store)
    print(f"    RAG 召回率：{a}/{b} = {a / b * 100:.0f}%")

    # 3. 报价确定性
    a, b = eval_quote_deterministic()
    print(f"\n[3] 报价确定性（单价来自价格库、合计正确、无未匹配）：{'通过' if a == b else '未通过'}")

    # 4. 端到端
    print("\n[4] 端到端链路（调 LLM API，较慢）...")
    a, b = eval_end_to_end()
    print(f"    端到端链路成功率：{a}/{b} = {a / b * 100:.0f}%")

    print("\n" + "=" * 56)
    print("评测完成。以上数字可写进 README。")
    print("=" * 56)


if __name__ == "__main__":
    main()
