from __future__ import annotations

from datetime import date, timedelta
from html import escape
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from modules.calculations import (
    ad_headroom, breakeven_price, breakeven_tacos, daily_record_metrics,
    estimate_status, fixed_cost, max_tacos_for_margin, pct_change,
    product_from_row, profit_breakdown, quick_profit_estimate,
    simulation_status, status, target_margin_price,
)
from modules.exporter import build_profit_workbook, export_filename
from modules.repository import repository

STAGES = ["新品", "成长期", "成熟期", "旺季", "淡季", "清库存"]
POSITIONS = ["核心款", "增长款", "利润款", "防守款", "清库存"]
PERIODS = ["近7天", "近14天", "近30天", "自定义"]

st.set_page_config(page_title="Amazon 多产品利润与经营决策助手", layout="wide")


def load_styles() -> None:
    stylesheet = Path(__file__).resolve().parent / "assets" / "style.css"
    try:
        css = stylesheet.read_text(encoding="utf-8") if stylesheet.exists() else ""
    except OSError:
        css = ""
    if not css:
        css = """
        :root { --ink:#1f2a44; --page:#f6f8fb; --line:#e5e9f0; --blue:#2f80ed; }
        html, body, [data-testid=stAppViewContainer] { background:var(--page); }
        .block-container { max-width:1420px; padding:28px 34px 64px; }
        h1, h2, h3, h4 { color:var(--ink); letter-spacing:0; }
        div[data-testid=stMetric] { background:#fff; border:1px solid var(--line); border-radius:12px; padding:14px 16px; min-height:92px; }
        div[data-testid=stMetricValue] { color:var(--ink); font-size:27px; }
        [data-testid=stTabs] [role=tab] { flex:1; min-height:82px; border:1px solid var(--line); border-radius:13px; background:#fff; color:var(--ink); font-weight:700; }
        [data-testid=stTabs] [role=tab][aria-selected=true] { background:var(--blue); border-color:var(--blue); color:#fff; }
        [data-testid=stDataFrame], [data-testid=stPlotlyChart] { border:1px solid var(--line); border-radius:12px; background:#fff; }
        """
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


load_styles()


def money(value: float | None) -> str:
    return "无法计算" if value is None else f"${value:,.2f}"


def pct(value: float | None) -> str:
    return "无法计算" if value is None else f"{value * 100:.1f}%"


def pp(value: float | None) -> str:
    return "无法计算" if value is None else f"{'+' if value >= 0 else ''}{value * 100:.1f}个百分点"


def signed_money(value: float | None) -> str:
    return "无法计算" if value is None else f"{'+' if value >= 0 else '-'}${abs(value):,.2f}"


def count_text(value: float | None) -> str:
    return "无法计算" if value is None else f"{value:,.0f}"


def parent_asin_of(product) -> str:
    return str(getattr(product, "parent_asin", "") or "")


def stored_fixed_cost(product) -> float:
    return float(getattr(product, "fixed_cost_usd", 0) or fixed_cost(product))


def section(title: str, caption: str | None = None) -> None:
    st.markdown(f'<div class="module-title">{title}</div>', unsafe_allow_html=True)
    if caption:
        st.caption(caption)


def input_warnings(product, *, sessions=None, units=None, tacos=None, ad_spend=None) -> list[str]:
    warnings = []
    if stored_fixed_cost(product) <= 0:
        warnings.append("固定成本为空或小于等于0")
    if product.price <= 0:
        warnings.append("售价小于等于0")
    for label, value in [("平台佣金率", product.commission_rate), ("当前TACOS", product.tacos), ("目标TACOS", product.target_tacos), ("退货率", product.return_rate), ("仓储率", product.storage_rate)]:
        if value < 0 or value > 1:
            warnings.append(f"{label}必须在0%到100%之间")
    if product.daily_sales < 0 or (units is not None and units < 0):
        warnings.append("销量不能为负数")
    if sessions is not None and units is not None and sessions < units:
        warnings.append("Session不能小于销量")
    if ad_spend is not None and ad_spend < 0:
        warnings.append("广告花费不能为负数")
    if tacos is not None and tacos > 1:
        warnings.append("TACOS超过100%")
    return warnings


def show_warnings(warnings: list[str]) -> bool:
    if warnings:
        st.error("请检查输入数据：" + "；".join(warnings))
        return True
    return False


def estimate_with_ad_input(product, average_price: float, units: float, tacos: float | None, ad_spend: float | None) -> dict:
    if tacos is None:
        revenue = average_price * units
        tacos = ad_spend / revenue if ad_spend is not None and revenue > 0 else 0.0
    try:
        return quick_profit_estimate(product, average_price, units, tacos=tacos, ad_spend=ad_spend)
    except TypeError:
        return quick_profit_estimate(product, average_price, units, tacos)


def profile_form(defaults: dict, button_label: str, form_key: str) -> dict | None:
    product = product_from_row(defaults)
    with st.form(form_key):
        st.markdown("**基础参数**")
        c1, c2, c3, c4 = st.columns(4)
        parent_asin = c1.text_input("Parent ASIN", parent_asin_of(product)); asin = c2.text_input("ASIN", product.asin); fnsku = c3.text_input("FNSKU", product.fnsku); name = c4.text_input("产品名称", product.name)
        c1, c2, c3, c4 = st.columns(4)
        fixed_cost_usd = c1.number_input("固定成本($/件)", min_value=0.0, value=stored_fixed_cost(product), step=0.01)
        commission_rate = c2.number_input("平台佣金率(%)", min_value=0.0, max_value=100.0, value=float(product.commission_rate * 100), step=0.1) / 100
        storage_rate = c3.number_input("仓储率(%)", min_value=0.0, max_value=100.0, value=float(product.storage_rate * 100), step=0.1) / 100
        return_rate = c4.number_input("退货率(%)", min_value=0.0, max_value=100.0, value=float(product.return_rate * 100), step=0.1) / 100
        st.markdown("**经营参数**")
        c1, c2, c3, c4 = st.columns(4)
        price = c1.number_input("当前售价($)", min_value=0.0, value=float(product.price), step=0.01); average_sale_price = c2.number_input("销售均价($)", min_value=0.0, value=float(product.average_sale_price or product.price), step=0.01); daily_sales = c3.number_input("预估销量(件/日)", min_value=0.0, value=float(product.daily_sales), step=1.0); tacos = c4.number_input("当前TACOS(%)", min_value=0.0, max_value=100.0, value=float(product.tacos * 100), step=0.1) / 100
        c1, c2, c3, c4 = st.columns(4)
        target_tacos = c1.number_input("目标TACOS(%)", min_value=0.0, max_value=100.0, value=float(product.target_tacos * 100), step=0.1) / 100; target_margin = c2.number_input("目标毛利率(%)", min_value=0.0, max_value=100.0, value=float(product.target_margin * 100), step=0.5) / 100; stage = c3.selectbox("产品阶段", STAGES, index=STAGES.index(product.stage) if product.stage in STAGES else 1); positioning = c4.selectbox("产品定位", POSITIONS, index=POSITIONS.index(product.positioning) if product.positioning in POSITIONS else 1)
        if not st.form_submit_button(button_label, type="primary"):
            return None
        payload = {"parent_asin": parent_asin.strip(), "asin": asin.strip() or "UNSET-ASIN", "fnsku": fnsku.strip(), "name": name.strip() or "未命名产品", "fixed_cost_usd": fixed_cost_usd, "commission_rate": commission_rate, "storage_rate": storage_rate, "return_rate": return_rate, "price": price, "average_sale_price": average_sale_price, "daily_sales": daily_sales, "tacos": tacos, "target_tacos": target_tacos, "target_margin": target_margin, "stage": stage, "positioning": positioning}
        if show_warnings(input_warnings(product_from_row(payload))):
            return None
        return payload


def status_order(label: str) -> int:
    return 0 if label.startswith("🔴") else 1 if label.startswith("🟡") else 2


def simulation_status_class(label: str) -> str:
    if label.startswith("🟢"):
        return "good"
    if label.startswith("🟡"):
        return "watch"
    return "risk"


def simulation_status_text(label: str) -> str:
    return label.replace("🟢 ", "").replace("🟡 ", "").replace("🔴 ", "")


def simulation_table(sim: list[dict]) -> str:
    headers = ["售价", "单件毛利润", "毛利率", "保本TACOS", "目标毛利率TACOS上限", "状态"]
    head_html = "".join(f"<th>{escape(header)}</th>" for header in headers)
    rows_html = []
    for item in sim:
        current_class = " current-price" if item["当前售价"] else ""
        state_class = simulation_status_class(item["状态"])
        state_text = simulation_status_text(item["状态"])
        rows_html.append(
            f'<tr class="{current_class}">'
            f'<td class="money-cell">{escape(money(item["售价"]))}{"<span class=\'current-mark\'>当前</span>" if item["当前售价"] else ""}</td>'
            f'<td class="money-cell {"negative" if item["单件毛利润"] < 0 else "positive"}">{escape(money(item["单件毛利润"]))}</td>'
            f'<td class="number-cell">{escape(pct(item["毛利率"]))}</td>'
            f'<td class="number-cell">{escape(pct(item["保本TACOS"]))}</td>'
            f'<td class="number-cell">{escape(pct(item["目标毛利率TACOS上限"]))}</td>'
            f'<td><span class="sim-status-pill {state_class}">{escape(state_text)}</span></td>'
            "</tr>"
        )
    return f'<div class="simulation-table-wrap"><table class="simulation-table"><thead><tr>{head_html}</tr></thead><tbody>{"".join(rows_html)}</tbody></table></div>'


def overview(products: list[dict]) -> None:
    st.title("Amazon 多产品利润与经营决策助手")
    st.caption("看全局：快速判断哪个产品贡献利润，哪个产品需要优先处理。")
    st.warning("当前使用 SQLite 演示存储；Streamlit Cloud 长期多人使用请配置 Supabase。" if not repository.is_cloud_persistent else "当前使用 Supabase 持久化存储。")
    if products:
        st.download_button("导出全部产品", build_profit_workbook(products), export_filename(products), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", type="primary", key="export_all_overview")
    rows = []; total_revenue = total_profit = total_ad = 0.0; healthy = watch = risky = 0
    for row in products:
        product = product_from_row(row); bd = profit_breakdown(product); label = status(product)
        total_revenue += bd["monthly_revenue"]; total_profit += bd["monthly_profit"]; total_ad += bd["price"] * product.tacos * product.daily_sales * 30; healthy += label.startswith("🟢"); watch += label.startswith("🟡"); risky += label.startswith("🔴")
        rows.append({"产品名称": product.name, "Parent ASIN": parent_asin_of(product) or "未分组", "ASIN": product.asin, "当前售价": money(product.price), "预估销量": f"{product.daily_sales:.0f}", "当前TACOS": pct(product.tacos), "目标TACOS": pct(product.target_tacos), "单件毛利润": money(bd["net_profit"]), "毛利率": pct(bd["net_margin"]), "月预估毛利润": money(bd["monthly_profit"]), "状态": label, "_profit": bd["monthly_profit"], "_margin": bd["net_margin"], "_tacos": product.tacos, "_status": status_order(label)})
    sort_label = st.selectbox("产品排序", ["月预估毛利润", "毛利率", "TACOS", "状态"], key="overview_sort"); sort_key = {"月预估毛利润": "_profit", "毛利率": "_margin", "TACOS": "_tacos", "状态": "_status"}[sort_label]; rows.sort(key=lambda item: item[sort_key], reverse=sort_label in {"月预估毛利润", "状态"})
    c1, c2, c3, c4 = st.columns(4); c1.metric("预估月销售额", money(total_revenue)); c2.metric("预估月毛利润", money(total_profit)); c3.metric("整体毛利率", pct(total_profit / total_revenue if total_revenue else 0)); c4.metric("整体TACOS", pct(total_ad / total_revenue if total_revenue else 0))
    c1, c2, c3 = st.columns(3); c1.metric("健康产品数", healthy); c2.metric("关注产品数", watch); c3.metric("风险产品数", risky)
    section("产品列表", "按当前经营状态推算，不是实际财务利润。")
    if not rows:
        st.info("还没有产品，请在侧边栏新增。"); return
    st.dataframe(pd.DataFrame(rows).drop(columns=["_profit", "_margin", "_tacos", "_status"]), width="stretch", hide_index=True)
    groups = {}
    for row in products:
        groups.setdefault(parent_asin_of(product_from_row(row)) or "未分组", []).append(row)
    summary = []
    for parent, children in groups.items():
        metrics = [profit_breakdown(product_from_row(row)) for row in children]; revenue = sum(item["monthly_revenue"] for item in metrics); profit = sum(item["monthly_profit"] for item in metrics)
        summary.append({"Parent ASIN": parent, "子体数量": len(children), "月总销售额": money(revenue), "月总毛利润": money(profit), "毛利率": pct(profit / revenue if revenue else 0)})
    section("Parent ASIN 汇总", "按子体汇总，比例按总额计算，不做简单平均。"); st.dataframe(pd.DataFrame(summary), width="stretch", hide_index=True)


def quick_estimate(product, key_prefix: str) -> None:
    section("经营快速测算", "只输入销售均价、销量和 TACOS / 广告花费，快速核算阶段毛利润。")
    input_col, result_col = st.columns([0.95, 1.45], gap="large")
    with input_col:
        period = st.selectbox("时间范围备注", ["昨日", "近7天", "近14天", "近30天", "自定义"], key=f"{key_prefix}_period")
        average_price = st.number_input("销售均价($)", min_value=0.0, value=float(product.average_sale_price or product.price), step=0.01, key=f"{key_prefix}_price")
        units = st.number_input("销量(件)", min_value=0.0, value=float(max(product.daily_sales, 1)), step=1.0, key=f"{key_prefix}_units")
        mode = st.selectbox("广告输入方式", ["输入TACOS", "输入广告花费"], key=f"{key_prefix}_mode")
        if mode == "输入TACOS":
            tacos = st.number_input("TACOS(%)", min_value=0.0, max_value=100.0, value=float(product.tacos * 100), step=0.1, key=f"{key_prefix}_tacos") / 100
            ad_spend = None
        else:
            ad_spend = st.number_input("广告花费($)", min_value=0.0, value=0.0, step=1.0, key=f"{key_prefix}_ad")
            tacos = None
    estimate = estimate_with_ad_input(product, average_price, units, tacos, ad_spend)
    if show_warnings(input_warnings(product, units=units, tacos=estimate["tacos"], ad_spend=ad_spend)): return
    with result_col:
        st.markdown('<div class="tool-result-heading">本次测算结果</div>', unsafe_allow_html=True)
        c1, c2 = st.columns(2); c1.metric("销售额", money(estimate["revenue"])); c2.metric("广告花费", money(estimate["ad_spend"]))
        c1, c2 = st.columns(2); c1.metric("单件毛利润", money(estimate["unit_net_profit"])); c2.metric("总毛利润", money(estimate["total_net_profit"]))
        c1, c2 = st.columns(2); c1.metric("毛利率", pct(estimate["net_margin"])); c2.metric("目标差值", pp(estimate["net_margin"] - product.target_margin))
        st.markdown(f'<div class="tool-status-line">{escape(period)}测算状态：<strong>{escape(estimate_status(estimate["total_net_profit"], estimate["net_margin"], product.target_margin))}</strong></div>', unsafe_allow_html=True)


def price_simulation(product, key_prefix: str) -> None:
    section("价格模拟", "调整价格、经营参数，看看结果会怎样。")
    control_col, result_col = st.columns([0.32, 0.68], gap="large")
    with control_col:
        with st.container(border=True):
            st.markdown('<div class="sim-card-heading">参数控制</div><div class="sim-card-caption">设置范围后生成价格决策结果</div>', unsafe_allow_html=True)
            st.metric("当前售价", money(product.price))
            low = st.number_input("最低模拟售价($)", min_value=0.01, value=max(0.01, round(product.price - 3, 2)), step=0.5, key=f"{key_prefix}_low")
            high = st.number_input("最高模拟售价($)", min_value=0.01, value=round(product.price + 3, 2), step=0.5, key=f"{key_prefix}_high")
            step = st.number_input("价格间隔($)", min_value=0.01, value=1.0, step=0.25, key=f"{key_prefix}_step")
            st.number_input("当前TACOS(%)", min_value=0.0, max_value=100.0, value=float(product.tacos * 100), step=0.1, disabled=True, key=f"{key_prefix}_current_tacos")
            st.number_input("目标毛利率(%)", min_value=0.0, max_value=100.0, value=float(product.target_margin * 100), step=0.5, disabled=True, key=f"{key_prefix}_target_margin")
            st.button("生成模拟结果", type="primary", width="stretch", key=f"{key_prefix}_generate")
    prices = []; current = high
    while current >= low - 1e-9 and len(prices) < 300: prices.append(round(current, 2)); current -= step
    prices = sorted(set(prices + [round(product.price, 2)]), reverse=True); sim = []
    for price in prices:
        bd = profit_breakdown(product, price=price); max_tacos = max_tacos_for_margin(product, product.target_margin, price=price); sim.append({"售价": price, "单件毛利润": bd["net_profit"], "毛利率": bd["net_margin"], "保本TACOS": breakeven_tacos(product, price), "目标毛利率TACOS上限": max_tacos, "状态": simulation_status(bd["net_profit"], bd["net_margin"], product.target_margin), "当前售价": abs(price - product.price) < 0.001})
    with result_col:
        with st.container(border=True):
            st.markdown('<div class="sim-card-heading">模拟结果</div><div class="sim-card-caption">当前售价用蓝色标记，状态标签只强调运营结论</div>', unsafe_allow_html=True)
            st.markdown(simulation_table(sim), unsafe_allow_html=True)
            st.markdown('<div class="chart-card-heading">价格趋势</div><div class="chart-card-caption">观察价格变化对毛利润、毛利率和广告承受力的影响</div>', unsafe_allow_html=True)
            chart_metric = st.radio("价格图表指标", ["毛利润", "毛利率", "目标毛利率TACOS上限"], horizontal=True, key=f"{key_prefix}_chart_metric")
            y_key = {"毛利润": "单件毛利润", "毛利率": "毛利率", "目标毛利率TACOS上限": "目标毛利率TACOS上限"}[chart_metric]
            st.markdown(f'<div class="chart-selection">当前指标：<strong>{escape(chart_metric)}</strong></div>', unsafe_allow_html=True)
    fig = go.Figure(go.Scatter(
        x=[item["售价"] for item in sim],
        y=[item[y_key] for item in sim],
        mode="lines+markers",
        line={"color": "#2f80ed", "width": 2},
        marker={
            "size": [13 if item["当前售价"] else 7 for item in sim],
            "color": ["#f59e0b" if item["当前售价"] else "#2f80ed" for item in sim],
            "line": {"color": "#ffffff", "width": 1.5},
        },
        customdata=[[pct(item["毛利率"]), money(item["单件毛利润"]), item["状态"]] for item in sim],
        hovertemplate="售价：$%{x:.2f}<br>值：%{y:.2%}<br>毛利率：%{customdata[0]}<br>毛利润：%{customdata[1]}<br>状态：%{customdata[2]}<extra></extra>" if y_key != "单件毛利润" else "售价：$%{x:.2f}<br>毛利润：$%{y:.2f}<br>毛利率：%{customdata[0]}<br>状态：%{customdata[2]}<extra></extra>",
    ))
    fig.update_layout(
        height=340,
        margin={"l": 20, "r": 20, "t": 20, "b": 20},
        paper_bgcolor="#ffffff",
        plot_bgcolor="#ffffff",
        font={"color": "#1f2a44"},
        xaxis={"title": "售价", "gridcolor": "#edf1f5", "zerolinecolor": "#edf1f5"},
        yaxis={"title": chart_metric, "gridcolor": "#edf1f5", "zerolinecolor": "#edf1f5"},
        showlegend=False,
    )
    with result_col:
        with st.container(border=True):
            st.plotly_chart(fig, width="stretch", config={"displayModeBar": False, "displaylogo": False})
    target_price = target_margin_price(product)
    if target_price is not None: st.info(f"在当前 TACOS 下，最低约为 {money(target_price)} 时可保持 {pct(product.target_margin)} 目标毛利率。")


def ad_budget_reference(product, key_prefix: str) -> None:
    section("广告预算参考", "这是经营目标对应的广告花费参考，不等于广告 Campaign 必须设置的 Budget。")
    input_col, result_col = st.columns([1.15, 0.85], gap="large")
    with input_col:
        c1, c2, c3 = st.columns(3)
        revenue = c1.number_input("目标日销售额($)", min_value=0.0, value=round(product.price * product.daily_sales, 2), step=10.0, key=f"{key_prefix}_revenue")
        target_tacos = c2.number_input("目标TACOS(%)", min_value=0.0, max_value=100.0, value=float(product.target_tacos * 100), step=0.5, key=f"{key_prefix}_tacos") / 100
        current = c3.number_input("当前广告花费($)", min_value=0.0, value=0.0, step=1.0, key=f"{key_prefix}_current")
    reference = revenue * target_tacos
    with result_col:
        c1, c2 = st.columns(2); c1.metric("可承受广告花费", f"{money(reference)}/天"); c2.metric("当前与目标差额", signed_money(reference - current))


def product_header(product, row: dict, selected_id, all_products: list[dict]) -> None:
    label = status(product)
    tone = "status-good" if label.startswith("🟢") else "status-watch" if label.startswith("🟡") else "status-risk"
    with st.container(border=True):
        left, middle, right = st.columns([2.2, 1.2, 1.15])
        left.markdown(
            f'<div class="product-header-name">{product.name}</div>'
            f'<div class="product-header-meta">Parent ASIN：{parent_asin_of(product) or "-"} · ASIN：{product.asin or "-"} · FNSKU：{product.fnsku or "-"}</div>'
            f'<span class="status-pill {tone}">{label}</span>',
            unsafe_allow_html=True,
        )
        if middle.button("编辑基础参数", key=f"open_editor_{selected_id}"):
            st.session_state[f"profile_editor_open_{selected_id}"] = True
            st.rerun()
        middle.download_button(
            "导出当前产品",
            build_profit_workbook([row]),
            export_filename([row]),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key=f"export_current_{selected_id}",
        )
        right.download_button(
            "导出全部产品",
            build_profit_workbook(all_products),
            export_filename(all_products),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key=f"export_all_{selected_id}",
        )
        right.caption(f"最后更新时间：{row.get('updated_at') or '未知'}")


def profile_editor(row: dict, selected_id) -> None:
    expanded = st.session_state.pop(f"profile_editor_open_{selected_id}", False)
    with st.expander("编辑基础参数", expanded=expanded):
        data = profile_form(row, "保存基础参数", f"edit_profile_{selected_id}")
        if data:
            repository.update_product(selected_id, data)
            st.rerun()


def overview_tab(product, row: dict, selected_id) -> None:
    bd = profit_breakdown(product); be_tacos = breakeven_tacos(product); limit = max_tacos_for_margin(product, product.target_margin); room = ad_headroom(product); be_price = breakeven_price(product); target_price = target_margin_price(product)
    if bd["net_profit"] <= 0 or (be_price is not None and product.price < be_price):
        banner_class = "risk"
    elif room >= 0.03:
        banner_class = "good"
    else:
        banner_class = "watch"
    if be_price is not None and product.price < be_price:
        conclusion = "当前售价低于绝对保本价，且当前利润为负，建议优先止损。"
    elif room < 0:
        conclusion = "当前毛利润仍需保护，TACOS 已超过目标毛利率允许水平，应优先优化广告效率。"
    elif room < 0.03:
        conclusion = f"当前毛利润正常，但 TACOS 距离目标毛利率上限仅剩 {pp(room)}，广告空间有限。"
    else:
        conclusion = f"当前毛利润正常，TACOS 距离目标毛利率上限还有 {pp(room)}，可以谨慎测试放量。"
    st.markdown(f'<div class="decision-banner {banner_class}">{conclusion}</div>', unsafe_allow_html=True)
    section("利润与成本", "毛利润为本工具的运营测算口径，不等同于财务报表利润。")
    c1, c2, c3, c4 = st.columns(4); c1.metric("售价", money(product.price)); c2.metric("固定成本", f"-{money(bd['fixed_cost'])}"); c3.metric("平台佣金", f"-{money(bd['commission'])}"); c4.metric("广告成本", f"-{money(bd['ad_cost'])}")
    c1, c2, c3, c4 = st.columns(4); c1.metric("仓储预留", f"-{money(bd['storage_reserve'])}"); c2.metric("退货预留", f"-{money(bd['return_reserve'])}"); c3.metric("单件毛利润", money(bd["net_profit"])); c4.metric("毛利率", pct(bd["net_margin"]))
    with st.expander("查看计算公式"):
        st.write("平台佣金 = 售价 × 平台佣金率"); st.write("广告成本 = 售价 × 当前 TACOS"); st.write("仓储预留 = 售价 × 仓储率"); st.write("退货预留 = 退货率 ×（固定成本 + 平台佣金 × 20%）"); st.write("本工具中的毛利润 = 售价 - 固定成本 - 平台佣金 - 广告成本 - 仓储预留 - 退货预留"); st.write("毛利率 = 单件毛利润 ÷ 售价")
    section("经营概览")
    target_margin = st.number_input("目标毛利率(%)", min_value=0.0, max_value=100.0, value=float(product.target_margin * 100), step=0.5, key=f"target_margin_{selected_id}") / 100
    if abs(target_margin - product.target_margin) > 1e-9:
        st.info("目标毛利率已临时调整，点击保存后写入产品。")
        if st.button("保存目标毛利率", key=f"save_margin_{selected_id}"):
            updated = dict(row); updated["target_margin"] = target_margin; repository.update_product(selected_id, updated); st.rerun()
        product.target_margin = target_margin; bd = profit_breakdown(product); be_tacos = breakeven_tacos(product); limit = max_tacos_for_margin(product, target_margin); room = ad_headroom(product); be_price = breakeven_price(product); target_price = target_margin_price(product)
    c1, c2, c3, c4 = st.columns(4); c1.metric("当前售价", money(product.price)); c2.metric("预估销量", f"{product.daily_sales:.0f} 件/日"); c3.metric("月预估销售额", money(bd["monthly_revenue"])); c4.metric("月预估毛利润", money(bd["monthly_profit"]))
    c1, c2, c3, c4 = st.columns(4); c1.metric("当前TACOS", pct(product.tacos)); c2.metric("目标TACOS", pct(product.target_tacos)); c3.metric("保本TACOS", pct(be_tacos)); c4.metric("目标毛利率TACOS上限", pct(limit))
    c1, c2, c3, c4 = st.columns(4); c1.metric("绝对保本售价", money(be_price)); c2.metric("目标毛利率最低售价", money(target_price)); c3.metric("距离保本价", signed_money(product.price - be_price if be_price is not None else None)); c4.metric("距离目标毛利率价格", signed_money(product.price - target_price if target_price is not None else None))
    st.caption(f"基础参数最后更新：{row.get('updated_at') or '未知'}")


def simulation_tab(product, selected_id) -> None:
    st.markdown('<div class="simulation-intro">调整价格、经营参数，看看结果会怎样。</div>', unsafe_allow_html=True)
    price_simulation(product, f"sim_{selected_id}")
    lower_left, lower_right = st.columns([1.55, 1], gap="large")
    with lower_left:
        with st.container(border=True):
            quick_estimate(product, f"estimate_{selected_id}")
    with lower_right:
        with st.container(border=True):
            ad_budget_reference(product, f"budget_{selected_id}")


def format_change(before: float, after: float, is_rate: bool = False, is_money: bool = False) -> str:
    diff = after - before
    if is_rate: return pp(diff)
    absolute = signed_money(diff) if is_money else f"{'+' if diff >= 0 else ''}{diff:,.0f}"; change = pct_change(before, after)
    return f"{absolute}，{pp(change)}" if change is not None else f"{absolute}，无可比百分比"


def aggregate_metrics(items: list[dict]) -> dict:
    revenue = sum(item["revenue"] for item in items); units = sum(item["units"] for item in items); sessions = sum(item["sessions"] for item in items); ad_spend = sum(item["ad_spend"] for item in items); profit = sum(item["total_net_profit"] for item in items)
    return {"average_price": revenue / units if units else 0, "sessions": sessions, "cvr": units / sessions if sessions else 0, "units": units, "ad_spend": ad_spend, "tacos": ad_spend / revenue if revenue else 0, "revenue": revenue, "unit_net_profit": profit / units if units else 0, "total_net_profit": profit, "net_margin": profit / revenue if revenue else 0}


def period_ranges(records: list[dict], mode: str, custom_start=None, custom_end=None) -> tuple[list[dict], list[dict]]:
    ordered = sorted(records, key=lambda item: item["record_date"])
    if not ordered: return [], []
    latest = pd.to_datetime(ordered[-1]["record_date"]).date()
    if mode == "自定义" and custom_start and custom_end:
        span = (custom_end - custom_start).days + 1; current = [item for item in ordered if custom_start.isoformat() <= item["record_date"] <= custom_end.isoformat()]; previous_start = custom_start - timedelta(days=span); previous_end = custom_start - timedelta(days=1); previous = [item for item in ordered if previous_start.isoformat() <= item["record_date"] <= previous_end.isoformat()]; return previous, current
    days = int(mode.replace("近", "").replace("天", "")); current_start = latest - timedelta(days=days - 1); previous_start = current_start - timedelta(days=days); previous_end = current_start - timedelta(days=1)
    return [item for item in ordered if previous_start.isoformat() <= item["record_date"] <= previous_end.isoformat()], [item for item in ordered if current_start.isoformat() <= item["record_date"] <= latest.isoformat()]


def comparison_table(product, records: list[dict], key_prefix: str) -> tuple[pd.DataFrame, dict | None, dict | None]:
    mode = st.radio("对比周期", PERIODS, horizontal=True, key=f"{key_prefix}_period"); start = end = None
    if mode == "自定义":
        c1, c2 = st.columns(2); start = c1.date_input("当前阶段开始", value=date.today() - timedelta(days=6), key=f"{key_prefix}_start"); end = c2.date_input("当前阶段结束", value=date.today(), key=f"{key_prefix}_end")
    previous_records, current_records = period_ranges(records, mode, start, end)
    if not previous_records or not current_records: return pd.DataFrame(), None, None
    previous = aggregate_metrics([daily_record_metrics(product, item) for item in previous_records]); current = aggregate_metrics([daily_record_metrics(product, item) for item in current_records]); rows = []
    for label, key, rate, money_value in [("销售均价", "average_price", False, True), ("Session", "sessions", False, False), ("CVR", "cvr", True, False), ("销量", "units", False, False), ("销售额", "revenue", False, True), ("广告花费", "ad_spend", False, True), ("TACOS", "tacos", True, False), ("单件毛利润", "unit_net_profit", False, True), ("总毛利润", "total_net_profit", False, True), ("毛利率", "net_margin", True, False)]:
        formatter = pct if rate else money if money_value else count_text; rows.append([label, formatter(previous[key]), formatter(current[key]), format_change(previous[key], current[key], is_rate=rate, is_money=money_value)])
    return pd.DataFrame(rows, columns=["指标", "上一阶段", "当前阶段", "变化"]), previous, current


def effect_conclusion(previous: dict | None, current: dict | None) -> str:
    if not previous or not current: return "至少需要两个完整阶段的数据，才能判断价格或经营调整是否有效。"
    price_change = current["average_price"] - previous["average_price"]; profit_change = current["total_net_profit"] - previous["total_net_profit"]; units_change = current["units"] - previous["units"]; cvr_change = current["cvr"] - previous["cvr"]; tacos_change = current["tacos"] - previous["tacos"]
    if profit_change > 0 and abs(price_change) > 0: return "🟢 本次价格调整有效：总毛利润增加，当前历史数据支持继续观察这个价格方向。"
    if profit_change < 0 and units_change <= 0: return "🔴 本次价格调整无效：价格变化没有带来足够销量提升，总毛利润下降。"
    if units_change > 0 and tacos_change > 0 and profit_change <= 0: return "🟡 增长有效但利润承压：销量提升伴随 TACOS 恶化，建议优先优化广告效率。"
    if cvr_change > 0 and units_change > 0: return "🟡 转化和销量有所改善，但总毛利润变化有限，建议继续积累样本。"
    return "当前阶段变化不明显，不能仅凭销量判断价格调整成功，建议继续记录。"


def history_charts(product, records: list[dict], key_prefix: str) -> None:
    metrics = [daily_record_metrics(product, item) for item in records]
    if not metrics: st.info("还没有足够记录生成图表。"); return
    df = pd.DataFrame(metrics).sort_values("record_date"); custom = [[m["record_date"], m["sessions"], m["cvr"], m["units"], m["tacos"], m["unit_net_profit"], m["total_net_profit"], m["note"]] for m in metrics]
    fig1 = go.Figure(go.Scatter(
        x=df["average_price"], y=df["total_net_profit"], mode="markers+lines",
        line={"color": "#2f80ed", "width": 2},
        marker={"size": (df["units"].clip(lower=1) ** 0.5) * 6, "color": "#2f80ed", "line": {"color": "#ffffff", "width": 1}},
        customdata=custom,
        hovertemplate="日期：%{customdata[0]}<br>销售均价：$%{x:.2f}<br>总毛利润：$%{y:.2f}<br>Session：%{customdata[1]:,.0f}<br>CVR：%{customdata[2]:.1%}<br>销量：%{customdata[3]:,.0f}<br>TACOS：%{customdata[4]:.1%}<br>单件毛利润：$%{customdata[5]:.2f}<br>备注：%{customdata[7]}<extra></extra>",
    ))
    fig2 = go.Figure(go.Scatter(
        x=df["average_price"], y=df["cvr"], mode="markers+lines",
        line={"color": "#16805b", "width": 2}, marker={"size": 10, "color": "#16805b", "line": {"color": "#ffffff", "width": 1}},
        customdata=custom,
        hovertemplate="日期：%{customdata[0]}<br>销售均价：$%{x:.2f}<br>CVR：%{y:.1%}<br>Session：%{customdata[1]:,.0f}<br>销量：%{customdata[3]:,.0f}<br>TACOS：%{customdata[4]:.1%}<br>总毛利润：$%{customdata[6]:.2f}<extra></extra>",
    ))
    chart_layout = {"height": 340, "margin": {"l": 20, "r": 20, "t": 45, "b": 20}, "paper_bgcolor": "#ffffff", "plot_bgcolor": "#ffffff", "font": {"color": "#1f2a44"}, "showlegend": False}
    fig1.update_layout(title="销售均价 vs 总毛利润", xaxis_title="销售均价", yaxis_title="总毛利润", xaxis={"gridcolor": "#edf1f5"}, yaxis={"gridcolor": "#edf1f5"}, **chart_layout)
    fig2.update_layout(title="销售均价 vs CVR", xaxis_title="销售均价", yaxis_title="CVR", xaxis={"gridcolor": "#edf1f5"}, yaxis={"gridcolor": "#edf1f5"}, **chart_layout)
    c1, c2 = st.columns(2); c1.plotly_chart(fig1, width="stretch", config={"displayModeBar": False, "displaylogo": False}, key=f"{key_prefix}_profit"); c2.plotly_chart(fig2, width="stretch", config={"displayModeBar": False, "displaylogo": False}, key=f"{key_prefix}_cvr")
    with st.expander("查看时间趋势", expanded=False): st.line_chart(df.rename(columns={"record_date":"日期", "average_price":"销售均价", "cvr":"CVR", "units":"销量", "tacos":"TACOS", "total_net_profit":"总毛利润"}).set_index("日期")[["销售均价", "CVR", "销量", "TACOS", "总毛利润"]])


def daily_records_block(product, product_id) -> list[dict]:
    records = repository.list_daily_records(product_id); section("每日经营数据", "记录真实阶段数据；广告花费和 TACOS 二选一，保存时写入参数快照。")
    with st.expander("新增每日经营数据", expanded=not records):
        with st.form(f"daily_add_{product_id}"):
            c1, c2, c3, c4 = st.columns(4); record_date = c1.date_input("日期", key=f"date_add_{product_id}"); average_price = c2.number_input("销售均价($)", min_value=0.0, value=float(product.average_sale_price or product.price), step=0.01, key=f"avg_add_{product_id}"); sessions = c3.number_input("Session", min_value=0.0, value=0.0, step=10.0, key=f"session_add_{product_id}"); units = c4.number_input("销量(件)", min_value=0.0, value=0.0, step=1.0, key=f"units_add_{product_id}")
            mode = st.selectbox("广告输入方式", ["输入TACOS", "输入广告花费"], key=f"ad_mode_add_{product_id}")
            if mode == "输入TACOS": tacos = st.number_input("TACOS(%)", min_value=0.0, max_value=100.0, value=float(product.tacos * 100), step=0.1, key=f"tacos_add_{product_id}") / 100; ad_spend = average_price * units * tacos
            else: ad_spend = st.number_input("广告花费($)", min_value=0.0, value=0.0, step=1.0, key=f"ad_add_{product_id}"); tacos = ad_spend / (average_price * units) if average_price * units else 0.0
            note = st.text_input("备注", placeholder="调价 / Coupon / Deal / 广告调整 / Listing调整")
            if st.form_submit_button("保存每日数据", type="primary") and not show_warnings(input_warnings(product, sessions=sessions, units=units, tacos=tacos, ad_spend=ad_spend)):
                repository.upsert_daily_record({"product_id":str(product_id), "record_date":record_date.isoformat(), "average_sale_price":average_price, "sessions":sessions, "units":units, "ad_spend":ad_spend, "tacos":tacos, "note":note.strip(), "snapshot_fixed_cost_usd":stored_fixed_cost(product), "snapshot_commission_rate":product.commission_rate, "snapshot_storage_rate":product.storage_rate, "snapshot_return_rate":product.return_rate}); st.rerun()
    if not records:
        st.info("还没有每日经营数据。先录入一条，开始跟踪价格变化。")
        section("阶段对比", "周期指标按阶段总额重新计算，不对每日百分比做简单平均。")
        st.radio("对比周期", PERIODS, horizontal=True, key=f"compare_{product_id}_empty_period")
        st.info("录入至少两个阶段的数据后，这里会显示上一阶段与当前阶段的对比结论。")
        return records
    with st.expander("编辑 / 删除历史记录", expanded=False):
        options = {record["id"]: f"{record['record_date']} · {record.get('note') or '无备注'}" for record in records}; record_id = st.selectbox("选择记录", list(options), format_func=lambda value: options[value], key=f"edit_pick_{product_id}"); selected = next(item for item in records if item["id"] == record_id)
        with st.form(f"daily_edit_{record_id}"):
            c1, c2, c3, c4 = st.columns(4); record_date = c1.date_input("日期", value=pd.to_datetime(selected["record_date"]).date()); average_price = c2.number_input("销售均价($)", min_value=0.0, value=float(selected["average_sale_price"]), step=0.01); sessions = c3.number_input("Session", min_value=0.0, value=float(selected["sessions"]), step=10.0); units = c4.number_input("销量(件)", min_value=0.0, value=float(selected["units"]), step=1.0)
            mode = st.selectbox("广告输入方式", ["输入TACOS", "输入广告花费"], key=f"ad_mode_edit_{record_id}")
            if mode == "输入TACOS": tacos = st.number_input("TACOS(%)", min_value=0.0, max_value=100.0, value=float(selected["tacos"]*100), step=0.1, key=f"tacos_edit_{record_id}")/100; ad_spend = average_price*units*tacos
            else: ad_spend = st.number_input("广告花费($)", min_value=0.0, value=float(selected["ad_spend"]), step=1.0, key=f"ad_edit_{record_id}"); tacos = ad_spend/(average_price*units) if average_price*units else 0.0
            note = st.text_input("备注", value=selected.get("note") or "", key=f"note_edit_{record_id}"); c1, c2 = st.columns(2); save_action = c1.form_submit_button("保存修改"); delete_action = c2.form_submit_button("删除记录")
            if save_action and not show_warnings(input_warnings(product, sessions=sessions, units=units, tacos=tacos, ad_spend=ad_spend)):
                repository.update_daily_record(record_id, {"product_id":str(product_id), "record_date":record_date.isoformat(), "average_sale_price":average_price, "sessions":sessions, "units":units, "ad_spend":ad_spend, "tacos":tacos, "note":note.strip(), "snapshot_fixed_cost_usd":selected.get("snapshot_fixed_cost_usd") or stored_fixed_cost(product), "snapshot_commission_rate":selected.get("snapshot_commission_rate") if selected.get("snapshot_commission_rate") is not None else product.commission_rate, "snapshot_storage_rate":selected.get("snapshot_storage_rate") if selected.get("snapshot_storage_rate") is not None else product.storage_rate, "snapshot_return_rate":selected.get("snapshot_return_rate") if selected.get("snapshot_return_rate") is not None else product.return_rate}); st.rerun()
            if delete_action: repository.delete_daily_record(record_id); st.rerun()
    section("周期对比", "周期指标按阶段总额重新计算，不对每日百分比做简单平均。")
    comparison, previous, current = comparison_table(product, records, f"compare_{product_id}")
    if comparison.empty: st.info("当前记录数量不足以组成两个阶段，请继续录入每日数据。")
    else: st.dataframe(comparison, width="stretch", hide_index=True); st.markdown(f"**价格变化效果判断**  {effect_conclusion(previous, current)}")
    history_charts(product, records, f"history_{product_id}")
    history = []
    for record in records:
        item = daily_record_metrics(product, record); history.append({"日期":item["record_date"], "销售均价":money(item["average_price"]), "Session":count_text(item["sessions"]), "CVR":pct(item["cvr"]), "销量":count_text(item["units"]), "广告花费":money(item["ad_spend"]), "TACOS":pct(item["tacos"]), "销售额":money(item["revenue"]), "单件毛利润":money(item["unit_net_profit"]), "总毛利润":money(item["total_net_profit"]), "毛利率":pct(item["net_margin"]), "备注":item["note"]})
    section("历史记录"); st.dataframe(pd.DataFrame(history), width="stretch", hide_index=True); return records


def parent_view(parent_asin: str, products: list[dict]) -> None:
    children = [row for row in products if parent_asin_of(product_from_row(row)) == parent_asin]
    if not children: st.info("该产品尚未绑定 Parent ASIN。"); return
    items = []
    for row in children:
        product = product_from_row(row); items.append((product, profit_breakdown(product), product.daily_sales*30))
    revenue = sum(bd["monthly_revenue"] for _, bd, _ in items); profit = sum(bd["monthly_profit"] for _, bd, _ in items); ad = sum(bd["ad_cost"]*units for _, bd, units in items); units = sum(units for _, _, units in items)
    st.subheader(f"父ASIN视角 · {parent_asin}"); c1, c2, c3, c4 = st.columns(4); c1.metric("子体数量", len(items)); c2.metric("总销量", count_text(units)); c3.metric("总销售额", money(revenue)); c4.metric("总毛利润", money(profit)); c1, c2, c3, c4 = st.columns(4); c1.metric("总广告花费", money(ad)); c2.metric("TACOS", pct(ad/revenue if revenue else 0)); c3.metric("毛利率", pct(profit/revenue if revenue else 0)); c4.metric("销售均价", money(revenue/units if units else 0))
    rows = []
    for product, bd, child_units in items: rows.append({"子ASIN":product.asin, "FNSKU":product.fnsku, "产品名称":product.name, "当前售价":money(product.price), "销量":count_text(child_units), "销售额":money(bd["monthly_revenue"]), "广告花费":money(bd["ad_cost"]*child_units), "TACOS":pct(product.tacos), "单件毛利润":money(bd["net_profit"]), "毛利率":pct(bd["net_margin"]), "毛利润贡献":money(bd["monthly_profit"]), "销量占比":pct(child_units/units if units else 0)})
    section("子体贡献表"); st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)


def detail(row: dict, selected_id, all_products: list[dict]) -> None:
    product = product_from_row(row); warnings = input_warnings(product)
    if warnings: st.error("请检查输入数据：" + "；".join(warnings))
    product_header(product, row, selected_id, all_products)
    profile_editor(row, selected_id)
    c1, c2 = st.columns([1.1, 1.9])
    if parent_asin_of(product):
        view = c1.radio("分析视角", ["子ASIN视角", "父ASIN视角"], horizontal=True, key=f"view_{selected_id}")
        if view == "父ASIN视角": parent_view(parent_asin_of(product), all_products); return
    else: c1.caption("未绑定 Parent ASIN")
    tabs = st.tabs(["① 概况", "② 模拟", "③ 记录"])
    with tabs[0]: st.caption("看现在：这个产品经营得怎么样？"); overview_tab(product, row, selected_id)
    with tabs[1]: st.caption("看未来：调整经营参数后会怎么样？"); price_simulation(product, f"sim_{selected_id}"); quick_estimate(product, f"estimate_{selected_id}"); ad_budget_reference(product, f"budget_{selected_id}")
    with tabs[2]: st.caption("看过去：之前的调整有没有效果？"); daily_records_block(product, selected_id)


def export_page(products: list[dict]) -> None:
    st.title("导出报表")
    st.caption("把当前保存的产品数据和最新测算结果导出为 Excel，用于留档和阶段复盘。")
    with st.container(border=True):
        st.markdown("### 利润测算表")
        st.write(f"当前共有 {len(products)} 个已保存产品。")
        if products:
            st.download_button(
                "导出全部产品",
                build_profit_workbook(products),
                export_filename(products),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary",
                key="export_page_all",
            )
        else:
            st.info("还没有可导出的产品。")


def settings_page() -> None:
    st.title("设置")
    st.caption("查看当前运行环境和数据存储状态。")
    with st.container(border=True):
        st.markdown("### 数据存储")
        if repository.is_cloud_persistent:
            st.success("当前使用 Supabase 持久化存储。")
        else:
            st.warning("当前使用 SQLite 演示存储，适合本地测试；线上长期使用请配置 Supabase。")
        st.caption("利润公式、每日记录快照和导出字段均由当前项目版本统一管理。")


def main() -> None:
    try: products = repository.list_products()
    except Exception: st.error("数据读取失败，请检查 Supabase 表结构、Secrets 配置或部署日志。"); return
    st.sidebar.markdown('<div class="side-brand">Amazon 运营决策助手<small>Operations workspace</small></div>', unsafe_allow_html=True)
    st.sidebar.markdown('<div class="side-section-label">工作台</div>', unsafe_allow_html=True)
    nav_options = ["▦  产品总览", "◉  单品分析", "⇩  导出报表", "⚙  设置"]
    page = st.sidebar.radio("导航", nav_options, label_visibility="collapsed", key="main_navigation")
    with st.sidebar.expander("新增产品"):
        data = profile_form({}, "保存新产品", "new_product_form")
        if data: new_id = repository.insert_product(data); st.session_state["selected_product_id"] = new_id; st.rerun()
    selected_id = None
    if products:
        ids = [item["id"] for item in products]; labels = {item["id"]:f"{item['asin']} · {item['name']}" for item in products}; current = st.session_state.get("selected_product_id", ids[0]); selected_id = st.sidebar.selectbox("根据 ASIN 切换产品", ids, format_func=lambda value:labels.get(value, str(value)), index=ids.index(current) if current in ids else 0); st.session_state["selected_product_id"] = selected_id
        c1, c2 = st.sidebar.columns(2)
        if c1.button("复制产品"): copied = repository.duplicate_product(selected_id); st.session_state["selected_product_id"] = copied if copied else selected_id; st.rerun()
        if c2.button("删除产品"): repository.delete_product(selected_id); st.session_state.pop("selected_product_id", None); st.rerun()
    if page == "▦  产品总览": overview(products)
    elif page == "◉  单品分析" and selected_id:
        row = repository.get_product(selected_id)
        if row: detail(row, selected_id, products)
    elif page == "⇩  导出报表": export_page(products)
    elif page == "⚙  设置": settings_page()
    else: st.info("请先在侧边栏新增一个产品。")


if __name__ == "__main__": main()
