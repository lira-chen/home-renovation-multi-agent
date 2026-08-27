# -*- coding: utf-8 -*-
"""
报价 Agent —— 纯本地计算，不调用大模型。

核心约束：报价数字只来自本地价格库（price_table.json），不靠 LLM 编。
工程量按面积 × 系数估算（明确标注需现场量房确认），单价可复现、可审计。
"""
import json

import config


def load_price_table(path=config.PRICE_TABLE_PATH):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def match_price_key(item, table):
    """把方案里的施工项目名匹配到价格库的键：精确 → 别名 → 互相包含。找不到返回 None。"""
    if item in table:
        return item
    for key in table:
        if key.startswith("_"):          # 跳过 _说明 之类的元信息键
            continue
        if item in table[key].get("别名", []):
            return key
    for key in table:
        if key.startswith("_"):
            continue
        if key in item or item in key:
            return key
    return None


def estimate_quantity(rule, area):
    """按价格库里的"数量规则"估算工程量。类型：面积(系数=面积倍数) / 米(系数=米每平米) / 项(固定数量)。"""
    t = rule.get("类型", "项")
    if t in ("面积", "米"):
        return round(area * rule.get("系数", 1.0), 2)
    return rule.get("数量", 1)


def quote(req, plan, table, trace=None):
    """req: 需求 dict；plan: 方案 dict；table: 价格库。返回明细报价 dict。"""
    area = req.get("面积_平米", 0) or 0
    spaces = plan.get("空间", []) if isinstance(plan, dict) else []

    # 汇总去重：同名施工项目只计一次价，避免"每个房间都按全屋面积重复计价"
    projects = []
    for space in spaces:
        for item in space.get("施工项目", []):
            if item not in projects:
                projects.append(item)

    lines, unmatched, total = [], [], 0.0
    for item in projects:
        key = match_price_key(item, table)
        if key is None:
            unmatched.append(item)
            continue
        entry = table[key]
        qty = estimate_quantity(entry.get("数量规则", {}), area)
        subtotal = round(qty * entry["单价"], 2)
        total += subtotal
        lines.append({
            "项目": key, "单位": entry["单位"], "数量": qty,
            "单价": entry["单价"], "小计": subtotal, "备注": entry.get("备注", ""),
        })

    result = {
        "明细": lines,
        "未匹配项目": unmatched,
        "合计": round(total, 2),
        "说明": "单价来自本地价格库（price_table.json）；工程量按全屋面积估算（同名项目已去重），需现场量房确认。",
    }
    if trace is not None:
        trace.log("报价", input={"面积": area, "项目数": len(lines)}, raw=None, output=result)
    return result
