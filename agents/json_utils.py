# -*- coding: utf-8 -*-
"""
JSON 容错层 —— 整个系统的"灵魂"。

LLM 吐出来的东西经常不是合法 JSON：代码块围栏、尾逗号、夹带说明、半截截断。
这里统一兜底，保证链路不会因为一句坏 JSON 而崩掉。

核心函数 parse_json_response：解析失败时（若提供了重试回调）把报错回喂给模型重试，
仍失败就返回一个带 error 字段的 dict，绝不抛异常。
"""
import json
import re


def _strip_fences(text):
    """去掉 ```json ... ``` 之类的 markdown 代码块围栏。"""
    m = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if m:
        return m.group(1)
    return text


def _extract_brace_block(text):
    """截取第一个 { 到最后一个 } 之间的内容。"""
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return text
    return text[start:end + 1]


def _fix_trailing_commas(text):
    """去掉 } 或 ] 前面的尾逗号（LLM 最爱犯的错）。"""
    return re.sub(r",\s*([}\]])", r"\1", text)


def _try_parse(text):
    """多种姿势尝试把文本解析成 dict/list，返回 (结果, 是否成功)。"""
    cleaned = _strip_fences(text)
    candidates = [cleaned, _extract_brace_block(cleaned)]
    for c in candidates:
        for attempt in (c, _fix_trailing_commas(c)):
            try:
                obj = json.loads(attempt)
                if isinstance(obj, (dict, list)):
                    return obj, True
            except Exception:
                continue
    return None, False


def parse_json_response(text, llm_retry=None, max_retries=2):
    """把 LLM 原始输出解析成 dict/list。

    llm_retry: 可调用对象，接收错误信息，返回重新生成的文本（用于把报错回喂给模型）。
    返回 (obj, raw_text)；解析始终不抛异常，失败时 obj 是 {"error": ...}。
    """
    obj, ok = _try_parse(text)
    if ok:
        return obj, text

    last_err = "解析失败：输出不是合法 JSON"
    for _ in range(max_retries):
        if llm_retry is None:
            break
        try:
            text = llm_retry(last_err)
            obj, ok = _try_parse(text)
            if ok:
                return obj, text
        except Exception as e:
            last_err = f"重试调用失败：{e}"

    # 兜底：返回错误标记，链路不崩
    return {"error": last_err, "raw": text[:500]}, text
