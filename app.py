# -*- coding: utf-8 -*-
"""
网页界面：输入装修需求，看完整链路结果（商业简洁风格）。

运行：
    C:/Users/86189/miniconda3/envs/dl/python.exe -m streamlit run app.py
"""
import os

import streamlit as st

# 注入 Streamlit Cloud 的 secrets 到环境变量（本地无 secrets 时自动跳过），
# 让 config.py 里的 os.environ.get("DEEPSEEK_KEY") 能读到云端配置的 key。
try:
    for _k, _v in st.secrets.items():
        if isinstance(_v, str) and _k not in os.environ:
            os.environ[_k] = _v
except Exception:
    pass

from orchestrator import run_pipeline

st.set_page_config(page_title="家装方案智能生成系统", layout="wide")

# ---- 头部 ----
st.title("家装方案智能生成系统")
st.caption("多 Agent 协作链路：需求解析 · 规范检索 · 方案设计 · 报价核算 · 施工对接")
st.divider()

# ---- 输入区 ----
st.subheader("装修需求")
user_input = st.text_area(
    "请描述您的装修需求",
    placeholder="例：90平三居室，预算20万，现代简约，毛坯房，全屋装修",
    height=100,
)
extra = st.text_input("补充说明（可选，如具体面积 / 预算 / 风格）", "")

if st.button("生成方案", type="primary"):
    full = user_input.strip()
    if extra.strip():
        full = full + ("。" if full else "") + extra.strip()
    if not full:
        st.warning("请先输入需求。")
    else:
        with st.spinner("正在生成..."):
            result = run_pipeline(full, followup_fn=lambda missing, req: {})

        # ---- 结果分栏 ----
        tab1, tab2, tab3, tab4 = st.tabs(["需求", "方案", "报价", "施工"])

        with tab1:
            req = result["requirements"]
            if isinstance(req, dict) and "error" not in req:
                rows = [{"字段": k, "值": ("、".join(v) if isinstance(v, list) else v)}
                        for k, v in req.items() if k != "缺失字段"]
                st.dataframe(rows, use_container_width=True, hide_index=True)
                if req.get("缺失字段"):
                    st.warning("缺少信息：" + "、".join(req["缺失字段"]))

        with tab2:
            plan = result["plan"]
            if isinstance(plan, dict) and "error" not in plan:
                st.markdown(f"**整体说明**：{plan.get('整体说明', '')}")
                for space in plan.get("空间", []):
                    name = space.get("名称", "")
                    items = "、".join(space.get("施工项目", []))
                    with st.expander(f"{name} · {items}"):
                        st.markdown(f"**说明**：{space.get('说明', '')}")
                        for c in space.get("规范依据", []):
                            st.markdown(f"- {c}")

        with tab3:
            q = result["quote"]
            if q.get("明细"):
                st.dataframe(
                    [{"项目": l["项目"], "数量": l["数量"], "单位": l["单位"],
                      "单价(元)": l["单价"], "小计(元)": l["小计"]} for l in q["明细"]],
                    use_container_width=True, hide_index=True,
                )
            if q.get("未匹配项目"):
                st.warning("未匹配需人工核价：" + "、".join(q["未匹配项目"]))
            st.success(f"合计：{q['合计']} 元")

        with tab4:
            cons = result["construction"]
            if isinstance(cons, dict) and "error" not in cons:
                st.dataframe(
                    [{"项目": d.get("项目", ""), "关键工序": d.get("关键工序", ""),
                      "验收标准": d.get("验收标准", "")} for d in cons.get("施工要点", [])],
                    use_container_width=True, hide_index=True,
                )
                if cons.get("安全提示"):
                    st.markdown("**安全提示**：\n" + "\n".join(f"- {s}" for s in cons["安全提示"]))

        st.caption(f"轨迹文件：{result['trace_file']}")
