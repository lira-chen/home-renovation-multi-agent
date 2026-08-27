# -*- coding: utf-8 -*-
"""需求收集 Agent：把用户自然语言 → 结构化需求 JSON，并标注缺失字段。

输出 requirements.json（含"缺失字段"数组），缺失的关键字段交给编排器触发信息补全。
"""
from agents import llm
from agents import json_utils
import config

SCHEMA_DESC = """请输出一个 JSON 对象，字段如下：
{
  "户型": "几室几厅，如 三室两厅",
  "面积_平米": 数字（平方米）,
  "预算_元": 数字（元）,
  "风格": "装修风格，如 现代简约，没提就空字符串",
  "是否毛坯": "是/否，没提就空字符串",
  "装修范围": ["要装修的空间或项目，如 全屋 / 厨房 / 卫生间"],
  "特殊需求": "用户提到的其它要求，没提就空字符串",
  "缺失字段": ["上面必填项里没问出来的字段名，没有就空数组"]
}
必填字段是：户型、面积_平米、预算_元。问不出来的字段名放进"缺失字段"数组。"""


def _system_prompt():
    return "你是家装需求收集助手，把用户需求整理成结构化 JSON，只输出 JSON。"


def _build_user_prompt(user_input):
    return f"把用户的自然语言需求整理成结构化 JSON。\n\n{SCHEMA_DESC}\n\n用户说：{user_input}\n\n只输出 JSON，不要解释。"


def _retry_callback(error_message):
    """解析失败时，把报错回喂给模型让它重试。"""
    return llm.call_llm([
        {"role": "system", "content": _system_prompt()},
        {"role": "user", "content": f"你上次的输出无法解析成 JSON（错误：{error_message}）。请重新只输出一个合法 JSON 对象，不要解释、不要代码块。"},
    ], json_mode=True)


def collect(user_input, trace=None):
    """输入自然语言，返回需求 dict。trace 为可选轨迹记录器。"""
    messages = [
        {"role": "system", "content": _system_prompt()},
        {"role": "user", "content": _build_user_prompt(user_input)},
    ]
    raw = llm.call_llm(messages, json_mode=True)
    req, raw = json_utils.parse_json_response(raw, llm_retry=_retry_callback)
    if trace is not None:
        trace.log("需求收集", input=user_input, raw=raw, output=req)
    return req
