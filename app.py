from __future__ import annotations

import pandas as pd
import streamlit as st

from modules.calculations import (
    ad_headroom,
    breakeven_price,
    breakeven_tacos,
    estimate_status,
    first_leg_usd,
    fixed_cost,
    headroom_message,
    max_tacos_for_margin,
    product_from_row,
    profit_breakdown,
    purchase_packaging_usd,
    quick_profit_estimate,
    simulation_status,
    status,
    tacos_vs_target,
    target_margin_price,
)
from modules.exporter import build_profit_workbook, export_filename
from modules.repository import repository


STAGES = ["新品", "成长期", "成熟期", "旺季", "淡季", "清库存"]
POSITIONS = ["核心款", "增长款", "利润款", "防守款", "清库存"]
PERIODS = ["昨日", "近7天", "近14天", "近30天", "自定义"]


st.set_page_config(page_title="Amazon 多产品利润与经营决策助手", layout="wide")


st.markdown(
    """
    <style>
    .block-container {padding-top: 1.5rem; padding-bottom: 3rem; max-width: 1280px;}
    div[data-testid="stMetric"] {
        background: #ffffff;
        border: 1px solid #e5e7eb;
        border-radius: 8px;
        padding: 14px 16px;
        min-height: 104px;
    }
    div[data-testid="stMetricLabel"] p {font-size: 14px; color: #4b5563; white-space: normal;}
    div[data-testid="stMetricValue"] {font-size: 28px;}
    .section {
        border: 1px solid #e5e7eb;
        border-radius: 8px;
        padding: 18px 20px;
        margin: 26px 0;
        background: #ffffff;
    }
    .section h3 {margin-top: 0;}
    .decision {
        border-left: 5px solid #64748b;
        background: #f8fafc;
        padding: 14px 16px;
        border-radius: 8px;
        margin: 18px 0;
        font-size: 16px;
    }
    .positive {color: #047857; font-weight: 650;}
    .warning {color: #b45309; font-weight: 650;}
    .danger {color: #b91c1c; font-weight: 650;}
    .muted {color: #6b7280;}
    </style>
    """,
    unsafe_allow_html=True,
)


def money(value: float | None) -> str:
    if value is None:
        return "无法计算"
    return f"${value:,.2f}"


def yuan(value: float | None) -> str:
    if value is None:
        return "无法计算"
    return f"￥{value:,.2f}"


def pct(value: float | None) -> str:
    if value is None:
        return "无法计算"
    return f"{value * 100:.1f}%"


def pp(value: float) -> str:
    sign = "+" if value >= 0 else ""
    return f"{sign}{value * 100:.1f}个百分点"


def tone_class(value: float) -> str:
    if value < 0:
        return "danger"
    if value == 0:
        return "warning"
    return "positive"


def section(title: str):
    st.markdown(f'<div class="section"><h3>{title}</h3>', unsafe_allow_html=True)


def end_section() -> None:
    st.markdown("</div>", unsafe_allow_html=True)


def profile_form(defaults: dict, button_label: str) -> dict | None:
    product = product_from_row(defaults)
    with st.form(button_label):
        st.markdown("**产品基础档案**")
        c1, c2, c3 = st.columns(3)
        asin = c1.text_input("ASIN", product.asin)
        fnsku = c2.text_input("FNSKU", product.fnsku)
        name = c3.text_input("产品名称", product.name)

        c1, c2, c3, c4 = st.columns(4)
        purchase_packaging_cny = c1.number_input("采购+包装(￥)", min_value=0.0, value=float(product.purchase_packaging_cny), step=1.0)
        first_leg_cny = c2.number_input("头程(￥)", min_value=0.0, value=float(product.first_leg_cny), step=1.0)
        fba_fee = c3.number_input("FBA尾程($)", min_value=0.0, value=float(product.fba_fee), step=0.01)
        exchange_rate = c4.number_input("汇率", min_value=0.0001, value=float(product.exchange_rate), step=0.01)

        preview = product_from_row(
            {
                **defaults,
                "purchase_packaging_cny": purchase_packaging_cny,
                "first_leg_cny": first_leg_cny,
                "fba_fee": fba_fee,
                "exchange_rate": exchange_rate,
            }
        )
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("采购+包装($)", money(purchase_packaging_usd(preview)))
        c2.metric("头程($)", money(first_leg_usd(preview)))
        c3.metric("固定成本($)", money(fixed_cost(preview)))
        commission_rate = c4.number_input("平台佣金(%)", min_value=0.0, value=float(product.commission_rate * 100), step=0.1) / 100

        st.markdown("**经营参数**")
        c1, c2, c3, c4 = st.columns(4)
        price = c1.number_input("当前售价 / 划线价($)", min_value=0.0, value=float(product.price), step=0.01)
        average_sale_price = c2.number_input("销售均价($)", min_value=0.0, value=float(product.average_sale_price or product.price), step=0.01)
        daily_sales = c3.number_input("预估销量(件/日)", min_value=0.0, value=float(product.daily_sales), step=1.0)
        tacos = c4.number_input("当前TACOS(%)", min_value=0.0, value=float(product.tacos * 100), step=0.1) / 100

        c1, c2, c3, c4 = st.columns(4)
        target_tacos = c1.number_input("目标TACOS(%)", min_value=0.0, value=float(product.target_tacos * 100), step=0.1) / 100
        target_margin = c2.number_input("目标净利率(%)", min_value=0.0, value=float(product.target_margin * 100), step=0.5) / 100
        return_rate = c3.number_input("退货率(%)", min_value=0.0, value=float(product.return_rate * 100), step=0.1) / 100
        storage_rate = c4.number_input("仓储率(%)", min_value=0.0, value=float(product.storage_rate * 100), step=0.1) / 100

        c1, c2 = st.columns(2)
        stage = c1.selectbox("产品阶段", STAGES, index=STAGES.index(product.stage) if product.stage in STAGES else 1)
        positioning = c2.selectbox("产品定位", POSITIONS, index=POSITIONS.index(product.positioning) if product.positioning in POSITIONS else 1)

        submitted = st.form_submit_button(button_label, type="primary")
        if not submitted:
            return None
        return {
            "asin": asin.strip() or "UNSET-ASIN",
            "fnsku": fnsku.strip(),
            "name": name.strip() or "未命名产品",
            "purchase_packaging_cny": purchase_packaging_cny,
            "first_leg_cny": first_leg_cny,
            "fba_fee": fba_fee,
            "commission_rate": commission_rate,
            "exchange_rate": exchange_rate,
            "price": price,
            "average_sale_price": average_sale_price,
            "daily_sales": daily_sales,
            "tacos": tacos,
            "target_tacos": target_tacos,
            "target_margin": target_margin,
            "return_rate": return_rate,
            "storage_rate": storage_rate,
            "stage": stage,
            "positioning": positioning,
        }


def overview(products: list[dict]) -> None:
    st.title("Amazon 多产品利润与经营决策助手")
    st.caption("围绕利润、价格、TACOS承受力和经营优先级的轻量运营决策工具。")
    if repository.is_cloud_persistent:
        st.success("当前使用 Supabase 持久化存储，适合线上长期保存产品档案。")
    else:
        st.warning("当前使用 SQLite 演示存储。Streamlit Cloud 重启或重新部署后，运行时修改的数据可能丢失；正式多人使用请配置 Supabase。")

    if products:
        st.download_button(
            "导出全部产品",
            data=build_profit_workbook(products),
            file_name=export_filename(products),
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary",
        )

    sort_by = st.selectbox(
        "产品排序",
        ["月预估利润", "净利率", "TACOS", "状态"],
        index=0,
    )

    rows = []
    total_revenue = total_profit = total_ad_spend = 0.0
    healthy = watch = risky = 0
    for row in products:
        product = product_from_row(row)
        breakdown = profit_breakdown(product)
        item_status = status(product)
        target_limit = max_tacos_for_margin(product, product.target_margin)
        headroom = target_limit - product.tacos
        total_revenue += breakdown["monthly_revenue"]
        total_profit += breakdown["monthly_profit"]
        total_ad_spend += breakdown["price"] * product.tacos * product.daily_sales * 30
        healthy += item_status.startswith("🟢")
        watch += item_status.startswith("🟡")
        risky += item_status.startswith("🔴")
        rows.append(
            {
                "产品名称": row["name"],
                "ASIN": row["asin"],
                "当前售价": money(product.price),
                "预估销量": f"{product.daily_sales:.0f}",
                "当前TACOS": pct(product.tacos),
                "目标TACOS": pct(product.target_tacos),
                "单件净利": money(breakdown["net_profit"]),
                "净利率": pct(breakdown["net_margin"]),
                "月预估利润": money(breakdown["monthly_profit"]),
                "状态": item_status,
                "_profit": breakdown["monthly_profit"],
                "_margin": breakdown["net_margin"],
                "_tacos": product.tacos,
                "_headroom": headroom,
                "_status_order": 0 if item_status.startswith("🔴") else 1 if item_status.startswith("🟡") else 2,
            }
        )

    sort_map = {
        "月预估利润": ("_profit", True),
        "净利率": ("_margin", False),
        "TACOS": ("_tacos", False),
        "状态": ("_status_order", True),
    }
    sort_key, ascending = sort_map[sort_by]
    rows = sorted(rows, key=lambda item: item[sort_key], reverse=not ascending)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("预估月销售额", money(total_revenue))
    c2.metric("预估月利润", money(total_profit))
    c3.metric("整体净利率", pct(total_profit / total_revenue if total_revenue else 0))
    c4.metric("整体TACOS", pct(total_ad_spend / total_revenue if total_revenue else 0))
    c1, c2, c3 = st.columns(3)
    c1.metric("健康产品数", healthy)
    c2.metric("关注产品数", watch)
    c3.metric("风险产品数", risky)
    st.caption("月预估销售额和月预估利润按当前经营状态推算，不是实际财务利润。")

    st.subheader("产品列表")
    if rows:
        display = pd.DataFrame(rows).drop(columns=["_profit", "_margin", "_tacos", "_headroom", "_status_order"])
        st.dataframe(display, use_container_width=True, hide_index=True, row_height=40)
    else:
        st.info("还没有产品，请在侧边栏新增。")


def quick_estimate_block(product) -> None:
    section("利润快速估算")
    st.caption("只填写销售均价、销量、TACOS；基础成本、佣金率、仓储率、退货率自动读取当前产品档案。")
    c1, c2, c3, c4 = st.columns(4)
    period = c1.selectbox("时间范围备注", PERIODS)
    average_price = c2.number_input("销售均价($)", min_value=0.0, value=float(product.average_sale_price or product.price), step=0.01)
    units = c3.number_input("销量(件)", min_value=0.0, value=float(max(product.daily_sales, 1)), step=1.0)
    tacos = c4.number_input("TACOS(%)", min_value=0.0, value=float(product.tacos * 100), step=0.1, key="estimate_tacos") / 100
    estimate = quick_profit_estimate(product, average_price, units, tacos)
    gap = estimate["net_margin"] - product.target_margin
    est_status = estimate_status(estimate["total_net_profit"], estimate["net_margin"], product.target_margin)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("销售额", money(estimate["revenue"]))
    c2.metric("估算广告花费", money(estimate["ad_spend"]))
    c3.metric("单件估算净利润", money(estimate["unit_net_profit"]))
    c4.metric("总估算净利润", money(estimate["total_net_profit"]))
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("销售均价", money(estimate["average_price"]))
    c2.metric("销量", f"{estimate['units']:.0f} 件")
    c3.metric("估算净利率", pct(estimate["net_margin"]))
    c4.metric("目标差值", pp(gap))
    st.markdown(f"**{period}估算状态：{est_status}**")

    st.markdown("**与计划值对比**")
    compare = pd.DataFrame(
        [
            ["售价 / 销售均价", money(product.price), money(estimate["average_price"]), money(estimate["average_price"] - product.price)],
            ["TACOS", pct(product.target_tacos), pct(estimate["tacos"]), pp(estimate["tacos"] - product.target_tacos)],
            ["销量", f"{product.daily_sales:.0f} 件/日", f"{estimate['units']:.0f} 件", f"{estimate['units'] - product.daily_sales:+.0f} 件"],
            ["净利率", pct(product.target_margin), pct(estimate["net_margin"]), pp(gap)],
        ],
        columns=["项目", "计划值", "本次实际估算", "差值"],
    )
    st.dataframe(compare, use_container_width=True, hide_index=True, row_height=40)
    end_section()


def recommendation_block(product, breakdown: dict, be_price: float | None, target_price: float | None) -> None:
    section("当前经营建议")
    target_limit = max_tacos_for_margin(product, product.target_margin)
    be_tacos = breakeven_tacos(product)
    room = target_limit - product.tacos

    if breakdown["net_profit"] <= 0:
        headline = "当前状态：优先止损"
    elif product.tacos > target_limit:
        headline = "当前状态：优先压广告"
    elif product.price < (target_price or 0):
        headline = "当前状态：优先保利润"
    else:
        headline = "当前状态：可稳健经营"
    st.markdown(f"**【{headline}】**")

    if be_price and product.price < be_price:
        price_text = f"当前售价{money(product.price)}，低于绝对保本售价{money(be_price)}，不建议继续降价。"
    elif target_price and product.price < target_price:
        price_text = f"当前售价{money(product.price)}，低于目标利润最低售价{money(target_price)}，促销前先抬高利润安全边际。"
    else:
        price_text = f"当前售价{money(product.price)}，仍高于目标利润最低售价{money(target_price)}。" if target_price else "当前成本结构下无法计算目标利润最低售价。"

    if product.tacos > be_tacos:
        ad_text = f"当前TACOS{pct(product.tacos)}，高于保本TACOS{pct(be_tacos)}，应优先压缩低效广告花费。"
    elif product.tacos > target_limit:
        ad_text = f"当前TACOS{pct(product.tacos)}，高于目标利润TACOS上限{pct(target_limit)}，先控广告再放量。"
    else:
        ad_text = f"当前TACOS{pct(product.tacos)}，广告剩余空间{pp(room)}，{headroom_message(room)}。"

    if breakdown["net_profit"] <= 0:
        profit_text = "单件利润为负，先恢复正利润，再考虑放量。"
    elif product.positioning == "利润款":
        profit_text = "利润款更重视利润保护，避免用过高TACOS换短期销量。"
    elif product.positioning == "增长款":
        profit_text = "增长款可允许较低利润换增长，但净利率不能长期低于目标。"
    elif product.stage in {"新品", "成长期"}:
        profit_text = "新品或成长期允许适度低利润，但需确保广告投入正在换取订单、排名或自然流量增长。"
    elif product.positioning == "清库存" or product.stage == "清库存":
        profit_text = "清库存可接近保本，但需要清楚知道最低可接受售价。"
    else:
        profit_text = f"当前净利率{pct(breakdown['net_margin'])}，目标净利率{pct(product.target_margin)}。"

    st.write(f"价格：{price_text}")
    st.write(f"广告：{ad_text}")
    st.write(f"利润：{profit_text}")
    end_section()


def overview_line(product, breakdown: dict, be_price: float | None, target_price: float | None, room: float) -> str:
    price_parts = []
    if be_price is not None:
        be_gap = product.price - be_price
        price_parts.append(f"当前售价{'高于' if be_gap >= 0 else '低于'}保本售价{money(abs(be_gap))}")
    if target_price is not None:
        target_gap = product.price - target_price
        price_parts.append(f"当前售价{'高于' if target_gap >= 0 else '低于'}目标利润最低售价{money(abs(target_gap))}")
    ad_text = f"当前TACOS{'仍有' if room >= 0 else '超出'}{pp(abs(room))}空间"
    return "，".join(price_parts + [ad_text]) + "。"


def detail(row: dict, selected_id) -> None:
    product = product_from_row(row)
    breakdown = profit_breakdown(product)
    target_limit = max_tacos_for_margin(product, product.target_margin)
    room = ad_headroom(product)
    be_tacos = breakeven_tacos(product)
    be_price = breakeven_price(product)
    target_price = target_margin_price(product)
    target_gap = tacos_vs_target(product)

    st.title(product.name)
    st.caption(f"ASIN：{product.asin or '-'} · FNSKU：{product.fnsku or '-'} · 阶段：{product.stage} · 定位：{product.positioning}")
    c1, c2 = st.columns([1, 1])
    with c1:
        if st.download_button(
            "导出当前产品",
            data=build_profit_workbook([row]),
            file_name=export_filename([row]),
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ):
            pass
    with c2:
        all_products = repository.list_products()
        st.download_button(
            "导出全部产品",
            data=build_profit_workbook(all_products),
            file_name=export_filename(all_products),
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    with st.expander("编辑产品档案 / 经营参数", expanded=False):
        data = profile_form(row, "保存修改")
        if data:
            repository.update_product(selected_id, data)
            st.rerun()

    section("当前经营概览")
    target_margin = st.number_input(
        "目标净利率(%)",
        min_value=0.0,
        value=float(product.target_margin * 100),
        step=0.5,
        key=f"overview_target_margin_{selected_id}",
        help="修改后可立即查看测算结果，点击保存按钮后写入当前产品。",
    ) / 100
    if abs(target_margin - product.target_margin) > 1e-9:
        product.target_margin = target_margin
        breakdown = profit_breakdown(product)
        target_limit = max_tacos_for_margin(product, product.target_margin)
        room = ad_headroom(product)
        be_tacos = breakeven_tacos(product)
        be_price = breakeven_price(product)
        target_price = target_margin_price(product)
        if st.button("保存目标净利率到当前产品", key=f"save_target_margin_{selected_id}"):
            updated = dict(row)
            updated["target_margin"] = target_margin
            repository.update_product(selected_id, updated)
            st.rerun()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("当前售价", money(product.price))
    c2.metric("单件净利润", money(breakdown["net_profit"]))
    c3.metric("当前净利率", pct(breakdown["net_margin"]))
    c4.metric("月预估利润", money(breakdown["monthly_profit"]))
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("当前TACOS", pct(product.tacos))
    c2.metric("目标TACOS", pct(product.target_tacos))
    c3.metric("保本TACOS", pct(be_tacos))
    c4.metric("目标利润TACOS上限", pct(target_limit))
    st.markdown(
        f'<div class="decision">{overview_line(product, breakdown, be_price, target_price, room)}广告剩余空间：<span class="{tone_class(room)}">{pp(room)}</span>。{headroom_message(room)}。当前TACOS比目标TACOS{"高" if target_gap >= 0 else "低"}{pp(abs(target_gap))}。</div>',
        unsafe_allow_html=True,
    )
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("绝对保本售价", money(be_price))
    c2.metric("目标净利率最低售价", money(target_price))
    c3.metric("距离保本售价", money(product.price - be_price) if be_price is not None else "无法计算")
    c4.metric("距离目标利润最低售价", money(product.price - target_price) if target_price is not None else "无法计算")
    if be_price is not None and product.price < be_price:
        st.error("当前售价已经低于绝对保本售价。")
    st.caption("月预估销售额 = 当前售价 × 预估销量 × 30；月预估利润 = 单件净利润 × 预估销量 × 30。这是按当前经营状态推算的预估值，不是实际财务利润。")
    end_section()

    section("利润与成本")
    st.caption(
        f"基础成本来源：采购+包装 {yuan(product.purchase_packaging_cny)} → {money(purchase_packaging_usd(product))}；"
        f"头程 {yuan(product.first_leg_cny)} → {money(first_leg_usd(product))}；"
        f"FBA尾程 {money(product.fba_fee)}；固定成本 {money(fixed_cost(product))}。"
    )
    st.table(
        pd.DataFrame(
            [
                ["售价", money(product.price), "当前售价"],
                ["固定成本", f"-{money(breakdown['fixed_cost'])}", "采购+包装($) + 头程($) + FBA尾程($)"],
                ["平台佣金", f"-{money(breakdown['commission'])}", f"{money(product.price)} × {pct(product.commission_rate)}"],
                ["广告成本", f"-{money(breakdown['ad_cost'])}", f"{money(product.price)} × {pct(product.tacos)}"],
                ["仓储预留", f"-{money(breakdown['storage_reserve'])}", f"{money(product.price)} × {pct(product.storage_rate)}"],
                ["退货预留", f"-{money(breakdown['return_reserve'])}", f"{pct(product.return_rate)} × ({money(breakdown['fixed_cost'])} + {money(breakdown['commission'])} × 20%)"],
                ["单件净利润", money(breakdown["net_profit"]), "售价 - 固定成本 - 平台佣金 - 广告成本 - 仓储预留 - 退货预留"],
            ],
            columns=["项目", "金额", "计算来源"],
        )
    )
    with st.expander("查看公式"):
        st.write("平台佣金 = 售价 × 平台佣金率")
        st.write("广告成本 = 售价 × 当前TACOS")
        st.write("仓储预留 = 售价 × 仓储率")
        st.write("退货预留 = 退货率 × [固定成本 + (售价 × 平台佣金率 × 20%)]")
        st.write("单件净利润 = 售价 - 固定成本 - 平台佣金 - 广告成本 - 仓储预留 - 退货预留")
        st.write("单件利润率 = 单件净利润 ÷ 售价")
    end_section()

    section("广告决策")
    left, right = st.columns([2, 1])
    with left:
        c1, c2, c3 = st.columns(3)
        c1.metric("当前TACOS", pct(product.tacos))
        c2.metric("目标TACOS", pct(product.target_tacos))
        c3.metric("当前与目标差值", pp(target_gap))
        c1, c2, c3 = st.columns(3)
        c1.metric("保本TACOS", pct(be_tacos))
        c2.metric("目标利润TACOS上限", pct(target_limit))
        c3.metric("广告剩余空间", pp(room))
        st.info(headroom_message(room))
    with right:
        target_daily_revenue = st.number_input("目标日销售额($)", min_value=0.0, value=float(round(product.price * product.daily_sales, 2)), step=10.0)
        target_tacos = st.number_input("目标TACOS(%)", min_value=0.0, value=float(product.target_tacos * 100), step=0.5, key="ad_budget_tacos") / 100
        st.metric("广告花费参考", f"{money(target_daily_revenue * target_tacos)}/天")
        st.caption("这是当前销售目标和TACOS下可承受的广告花费，不等于广告活动必须设置的Budget。")
    end_section()

    quick_estimate_block(product)

    section("价格模拟")
    low_default = max(0.01, product.price - 3)
    high_default = product.price + 3
    c1, c2, c3 = st.columns(3)
    low = c1.number_input("最低价格($)", min_value=0.01, value=float(round(low_default, 2)), step=0.5)
    high = c2.number_input("最高价格($)", min_value=0.01, value=float(round(high_default, 2)), step=0.5)
    step = c3.number_input("价格间隔($)", min_value=0.01, value=1.0, step=0.25)
    prices = []
    p = high
    while p >= low - 1e-9:
        prices.append(round(p, 2))
        p -= step
    if round(product.price, 2) not in prices:
        prices.append(round(product.price, 2))
        prices = sorted(set(prices), reverse=True)

    sim_rows = []
    acceptable_prices = []
    for price in prices:
        bd = profit_breakdown(product, price=price)
        max_t = max_tacos_for_margin(product, product.target_margin, price=price)
        row_status = simulation_status(bd["net_profit"], bd["net_margin"], product.target_margin)
        label = "（当前售价）" if abs(price - product.price) < 0.001 else ""
        if bd["net_margin"] >= product.target_margin and bd["net_profit"] > 0:
            acceptable_prices.append(price)
        sim_rows.append(
            {
                "售价": f"{money(price)}{label}",
                "单件净利": money(bd["net_profit"]),
                "净利率": pct(bd["net_margin"]),
                "保本TACOS": pct(breakeven_tacos(product, price=price)),
                "目标利润TACOS上限": pct(max_t),
                "状态": row_status,
            }
        )
    st.dataframe(pd.DataFrame(sim_rows), use_container_width=True, hide_index=True, row_height=42)
    if target_price is not None:
        st.info(f"在当前TACOS下，最低降到{money(target_price)}左右仍可保持{pct(product.target_margin)}目标净利率。")
    end_section()

    recommendation_block(product, breakdown, be_price, target_price)


def main() -> None:
    try:
        products = repository.list_products()
    except Exception:
        st.error("数据读取失败。请检查 Supabase 表结构、Secrets 配置或部署日志。")
        return

    st.sidebar.title("产品管理")
    page = st.sidebar.radio("页面", ["多产品总览", "单品详情"], horizontal=True)

    with st.sidebar.expander("新增产品"):
        data = profile_form({}, "保存新产品")
        if data:
            new_id = repository.insert_product(data)
            st.session_state["selected_product_id"] = new_id
            st.rerun()

    selected_id = None
    if products:
        ids = [p["id"] for p in products]
        labels = {p["id"]: f"{p['asin']} · {p['name']}" for p in products}
        current = st.session_state.get("selected_product_id", ids[0])
        selected_id = st.sidebar.selectbox(
            "根据ASIN切换产品",
            ids,
            format_func=lambda pid: labels.get(pid, str(pid)),
            index=ids.index(current) if current in ids else 0,
        )
        st.session_state["selected_product_id"] = selected_id
        c1, c2 = st.sidebar.columns(2)
        if c1.button("复制产品"):
            copied_id = repository.duplicate_product(selected_id)
            if copied_id:
                st.session_state["selected_product_id"] = copied_id
                st.rerun()
        if c2.button("删除产品", type="secondary"):
            repository.delete_product(selected_id)
            st.session_state.pop("selected_product_id", None)
            st.rerun()

    if page == "多产品总览":
        overview(products)
    elif selected_id:
        row = repository.get_product(selected_id)
        if row:
            detail(row, selected_id)
    else:
        st.info("请先在侧边栏新增一个产品。")


if __name__ == "__main__":
    main()
