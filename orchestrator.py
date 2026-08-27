# -*- coding: utf-8 -*-
"""
编排器：把 5 个 Agent 串成一条链路，并做全链路轨迹落盘。

链路：需求收集 → 信息补全 → 检索 → 方案生成 → 报价 → 施工对接
Agent 之间只传 JSON，不传自然语言；每一步的输入/输出都落盘到 trace/run_xxx.jsonl。

运行：
    C:/Users/86189/miniconda3/envs/dl/python.exe orchestrator.py
"""
import os
import json
import time

import config
from agents.retrieval_agent import DocumentStore
from agents import requirement_agent, plan_agent, quote_agent, construction_agent


class TraceLogger:
    """轨迹落盘：每步的 输入/输出/原始LLM输出 追加写到一行 JSON。"""

    def __init__(self):
        os.makedirs(config.TRACE_DIR, exist_ok=True)
        self.run_id = time.strftime("%Y%m%d_%H%M%S")
        self.path = os.path.join(config.TRACE_DIR, f"run_{self.run_id}.jsonl")

    def log(self, step, input=None, raw=None, output=None):
        line = {
            "step": step,
            "time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "input": input,
            "raw": raw,
            "output": output,
        }
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(line, ensure_ascii=False) + "\n")


def ask_followup(missing, req):
    """命令行追问缺失字段，返回补充信息 dict。"""
    prompts = {
        "户型": "户型（几室几厅）",
        "面积_平米": "面积（平方米，数字）",
        "预算_元": "预算（元，数字）",
    }
    answers = {}
    print("\n[信息补全] 还缺几个关键信息，麻烦补一下：")
    for field in missing:
        val = input(f"  {prompts.get(field, field)}：").strip()
        if val:
            answers[field] = int(val) if field in ("面积_平米", "预算_元") and val.isdigit() else val
    return answers


def run_pipeline(user_input, followup_fn=ask_followup, trace=None,
                 max_rounds=config.MAX_FOLLOWUP_ROUNDS):
    """跑完整链路，返回结果 dict。followup_fn(missing, req) 用于补缺失字段（网页里可换实现）。"""
    trace = trace or TraceLogger()
    store = DocumentStore()
    table = quote_agent.load_price_table()

    # 1. 需求收集
    req = requirement_agent.collect(user_input, trace)

    # 2. 信息补全：缺关键字段就追问，直到齐全或达到轮次上限
    for _ in range(max_rounds):
        missing = req.get("缺失字段", []) if isinstance(req, dict) else list(config.REQUIRED_FIELDS)
        missing = [m for m in missing if m in config.REQUIRED_FIELDS]
        if not missing:
            break
        extra = followup_fn(missing, req)
        if not extra:
            break
        combined = json.dumps({"原需求": req, "补充": extra}, ensure_ascii=False)
        req = requirement_agent.collect(combined, trace)
    if isinstance(req, dict):
        req.setdefault("缺失字段", [])

    # 3. 检索：方案和施工都要规范依据
    query = json.dumps(req, ensure_ascii=False)
    citations = store.retrieve(query, k=config.TOP_K)
    trace.log("检索", input=query, raw=None,
              output=[{"来源": i, "内容": t[:80]} for i, t in citations])

    # 4. 方案生成
    plan = plan_agent.generate(req, citations, trace)

    # 5. 报价（纯本地）
    quote = quote_agent.quote(req, plan, table, trace)

    # 6. 施工对接
    construction = construction_agent.generate(req, plan, citations, trace)

    return {
        "requirements": req,
        "plan": plan,
        "quote": quote,
        "construction": construction,
        "citations": citations,
        "trace_file": trace.path,
    }


def print_result(result):
    q = result["quote"]
    print("\n" + "=" * 56)
    print("【装修需求】")
    print(json.dumps(result["requirements"], ensure_ascii=False, indent=2))
    print("\n【装修方案】")
    print(json.dumps(result["plan"], ensure_ascii=False, indent=2))
    print("\n【报价（本地价格库计算，不靠大模型）】")
    for line in q.get("明细", []):
        print(f"  {line['项目']:<6} {line['数量']:>7}{line['单位']} × {line['单价']:>5}元 = {line['小计']:>8}元")
    if q.get("未匹配项目"):
        print(f"  [!] 未匹配需人工核价：{q['未匹配项目']}")
    print(f"  ──────────────────────────────")
    print(f"  合计：{q['合计']} 元")
    print("\n【施工对接】")
    print(json.dumps(result["construction"], ensure_ascii=False, indent=2))
    print("\n【轨迹文件】", result["trace_file"])


if __name__ == "__main__":
    print("===== 家装多 Agent 系统 =====")
    print("链路：需求收集 → 信息补全 → 检索 → 方案生成 → 报价 → 施工对接\n")
    user_input = input("请描述你的装修需求（例：90平三居室，预算20万，现代简约，毛坯房，全屋装修）：").strip()
    result = run_pipeline(user_input)
    print_result(result)
