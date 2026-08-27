# -*- coding: utf-8 -*-
"""方案生成 Agent：需求 JSON + 检索到的规范依据 → 装修方案 JSON。"""
import json

from agents import llm
from agents import json_utils


def _system_prompt():
    return "你是家装方案设计师，输出结构化 JSON 方案。"


def _build_user_prompt(req, citations):
    cited = "\n\n".join(f"[来源{i}] {text}" for i, text in citations)
    return (f"你是家装方案设计师。根据用户需求和下面的施工规范，输出一个装修方案。\n\n"
            f"用户需求（JSON）：\n{json.dumps(req, ensure_ascii=False)}\n\n"
            f"施工规范依据：\n{cited}\n\n"
            f"请输出 JSON 对象，格式：\n"
            f'{{"整体说明": "一句话概述方案", '
            f'"空间": [{{"名称": "客厅", "施工项目": ["墙面涂刷", "地面铺贴"], '
            f'"说明": "该空间做什么", "规范依据": ["[来源N] 摘录的规范要点"]}}]}}\n\n'
            f"方案要贴合需求，每个空间的施工项目尽量给出规范依据来源。只输出 JSON。")


def _retry_callback(error_message):
    return llm.call_llm([
        {"role": "system", "content": _system_prompt()},
        {"role": "user", "content": f"上次输出无法解析成 JSON（{error_message}）。请重新只输出合法 JSON 对象。"},
    ], json_mode=True)


def generate(req, citations, trace=None):
    """req: 需求 dict；citations: [(段号, 段落)]。返回方案 dict。"""
    messages = [
        {"role": "system", "content": _system_prompt()},
        {"role": "user", "content": _build_user_prompt(req, citations)},
    ]
    raw = llm.call_llm(messages, json_mode=True)
    plan, raw = json_utils.parse_json_response(raw, llm_retry=_retry_callback)
    if trace is not None:
        trace.log("方案生成", input=req, raw=raw, output=plan)
    return plan
