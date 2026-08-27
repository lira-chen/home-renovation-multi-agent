# -*- coding: utf-8 -*-
"""施工对接 Agent：把方案 + 规范依据整理成给施工方的要点（关键工序、验收标准、安全提示）。"""
import json

from agents import llm
from agents import json_utils


def _system_prompt():
    return "你是家装施工对接负责人，输出结构化 JSON 施工要点。"


def _build_user_prompt(req, plan, citations):
    cited = "\n\n".join(f"[来源{i}] {text}" for i, text in citations)
    return (f"你是家装施工对接负责人。根据装修方案和施工规范，整理给施工队的施工要点。\n\n"
            f"用户需求：{json.dumps(req, ensure_ascii=False)}\n"
            f"装修方案：{json.dumps(plan, ensure_ascii=False)}\n\n"
            f"施工规范依据：\n{cited}\n\n"
            f"请输出 JSON 对象：\n"
            f'{{"施工要点": [{{"项目": "防水", "关键工序": "...", "验收标准": "...", '
            f'"规范依据": ["[来源N] 摘录要点"]}}], '
            f'"安全提示": ["..."]}}\n\n只输出 JSON。')


def _retry_callback(error_message):
    return llm.call_llm([
        {"role": "system", "content": _system_prompt()},
        {"role": "user", "content": f"上次输出无法解析成 JSON（{error_message}）。请重新只输出合法 JSON 对象。"},
    ], json_mode=True)


def generate(req, plan, citations, trace=None):
    """返回施工要点 dict。"""
    messages = [
        {"role": "system", "content": _system_prompt()},
        {"role": "user", "content": _build_user_prompt(req, plan, citations)},
    ]
    raw = llm.call_llm(messages, json_mode=True)
    result, raw = json_utils.parse_json_response(raw, llm_retry=_retry_callback)
    if trace is not None:
        trace.log("施工对接", input=plan, raw=raw, output=result)
    return result
