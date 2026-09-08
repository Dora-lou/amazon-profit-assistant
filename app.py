from __future__ import annotations

import pandas as pd
import streamlit as st

from modules.calculations import (
    ad_headroom,
    breakeven_price,
    breakeven_tacos,
    headroom_message,
    max_tacos_for_margin,
    product_from_row,
    profit_breakdown,
    status,
    target_margin_price,
)
from modules.repository import repository


STAGES = ["新品", "成长期", "成熟期", "旺季", "淡季", "清库存"]
POSITIONS = ["核心款", "增长款", "利润款", "防守款", "清库存"]


st.set_page_config(page_title="Amazon 多产品利润与经营决策助手", layout="wide")


def money(value: float | None) -> str:
    if value is None:
        return "无法计算"
    return f"${value:,.2f}"


def pct(value: float | None) -> str:
    if value is None:
        return "无法计算"
    return f"{value * 100:.1f}%"


def pp(value: float) -> str:
    sign = "+" if value >= 0 else ""
    return f"{sign}{value * 100:.1f} 个百分点"


def product_form(defaults: dict, button_label: str) -> dict | None:
    with st.form(button_label):
        left, right = st.columns(2)
        with left:
            name = st.text_input("产品名称", defaults.get("name", ""))
            asin = st.text_input("ASIN", defaults.get("asin", ""))
            sku = st.text_input("SKU", defaults.get("sku", ""))
            marketplace = st.text_input("站点", defaults.get("marketplace", "US"))
            purchase_cost = st.number_input("采购成本 $", min_value=0.0, value=float(defaults.get("purchase_cost", 0)), step=0.01)
            packaging_cost = st.number_input("包装成本 $", min_value=0.0, value=float(defaults.get("packaging_cost", 0)), step=0.01)
            first_leg_cost = st.number_input("头程 $", min_value=0.0, value=float(defaults.get("first_leg_cost", 0)), step=0.01)
            fba_fee = st.number_input("FBA 配送费 $", min_value=0.0, value=float(defaults.get("fba_fee", 0)), step=0.01)
            other_fixed_cost = st.number_input("其他固定成本 $", min_value=0.0, value=float(defaults.get("other_fixed_cost", 0)), step=0.01)
        with right:
            price = st.number_input("当前售价 $", min_value=0.0, value=float(defaults.get("price", 0)), step=0.01)
            tacos = st.number_input("当前 TACOS %", min_value=0.0, value=float(defaults.get("tacos", 0.2)) * 100, step=0.1) / 100
            daily_sales = st.number_input("日均销量", min_value=0.0, value=float(defaults.get("daily_sales", 0)), step=1.0)
            target_margin = st.number_input("目标净利率 %", min_value=0.0, value=float(defaults.get("target_margin", 0.12)) * 100, step=0.5) / 100
            commission_rate = st.number_input("平台佣金率 %", min_value=0.0, value=float(defaults.get("commission_rate", 0.15)) * 100, step=0.1) / 100
            storage_rate = st.number_input("仓储率 %", min_value=0.0, value=float(defaults.get("storage_rate", 0.02)) * 100, step=0.1) / 100
            return_rate = st.number_input("退货率 %", min_value=0.0, value=float(defaults.get("return_rate", 0.08)) * 100, step=0.1) / 100
            stage = st.selectbox("产品阶段", STAGES, index=STAGES.index(defaults.get("stage", "成长期")) if defaults.get("stage", "成长期") in STAGES else 1)
            positioning = st.selectbox("产品定位", POSITIONS, index=POSITIONS.index(defaults.get("positioning", "增长款")) if defaults.get("positioning", "增长款") in POSITIONS else 1)

        submitted = st.form_submit_button(button_label, type="primary")
        if not submitted:
            return None
        return {
            "name": name.strip() or "未命名产品",
            "asin": asin.strip(),
            "sku": sku.strip(),
            "marketplace": marketplace.strip() or "US",
            "purchase_cost": purchase_cost,
            "packaging_cost": packaging_cost,
            "first_leg_cost": first_leg_cost,
            "fba_fee": fba_fee,
            "other_fixed_cost": other_fixed_cost,
            "commission_rate": commission_rate,
            "storage_rate": storage_rate,
            "return_rate": return_rate,
            "price": price,
            "tacos": tacos,
            "daily_sales": daily_sales,
            "target_margin": target_margin,
            "stage": stage,
            "positioning": positioning,
        }


def overview(products: list[dict]) -> None:
    st.title("Amazon 多产品利润与经营决策助手")
    st.caption("公开演示版本使用临时 SQLite 数据库；用于快速判断利润、价格、TACOS 承受力和优先关注产品。")

    rows = []
    total_revenue = total_profit = total_ad_spend = 0.0
    healthy = watch = risky = 0
    for row in products:
        product = product_from_row(row)
        breakdown = profit_breakdown(product)
        item_status = status(product)
        total_revenue += breakdown["monthly_revenue"]
        total_profit += breakdown["monthly_profit"]
        total_ad_spend += breakdown["price"] * product.tacos * product.daily_sales * 30
        healthy += item_status.startswith("🟢")
        watch += item_status.startswith("🟡")
        risky += item_status.startswith("🔴")
        target_max = max_tacos_for_margin(product, product.target_margin)
        rows.append(
            {
                "ID": row["id"],
                "产品名称": row["name"],
                "ASIN": row["asin"],
                "当前售价": money(product.price),
                "日均销量": f"{product.daily_sales:.0f}",
                "当前 TACOS": pct(product.tacos),
                "单件净利润": money(breakdown["net_profit"]),
                "净利率": pct(breakdown["net_margin"]),
                "月预估利润": money(breakdown["monthly_profit"]),
                "目标净利率": pct(product.target_margin),
                "目标净利率下最大 TACOS": pct(target_max),
                "广告剩余空间": pp(target_max - product.tacos),
                "产品阶段": row["stage"],
                "产品定位": row["positioning"],
                "当前状态": item_status,
            }
        )

    cols = st.columns(7)
    cols[0].metric("预估月销售额", money(total_revenue))
    cols[1].metric("预估月利润", money(total_profit))
    cols[2].metric("整体净利率", pct(total_profit / total_revenue if total_revenue else 0))
    cols[3].metric("整体 TACOS", pct(total_ad_spend / total_revenue if total_revenue else 0))
    cols[4].metric("健康产品数量", healthy)
    cols[5].metric("关注产品数量", watch)
    cols[6].metric("风险产品数量", risky)

    st.subheader("产品列表")
    if rows:
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.info("还没有产品，请在侧边栏新增。")


def recommendations(product, breakdown: dict, target_price: float | None) -> list[str]:
    target_max = max_tacos_for_margin(product, product.target_margin)
    room = target_max - product.tacos
    suggestions = [
        f"当前净利率 {pct(breakdown['net_margin'])}，目标净利率 {pct(product.target_margin)}",
        f"当前 TACOS {pct(product.tacos)}，广告剩余空间 {pp(room)}",
    ]
    if breakdown["net_profit"] <= 0:
        headline = "当前状态：优先止损"
        suggestions.append("当前单件净利润为负，先检查售价、TACOS 或固定成本")
    elif room > 0.03:
        headline = "当前状态：可适度放量"
        suggestions.append("仍有一定广告放量空间，但不要同时大幅降价和提高广告投入")
    elif room >= 0:
        headline = "当前状态：谨慎观察"
        suggestions.append("利润空间较窄，促销前先看目标利润最低售价")
    else:
        headline = "当前状态：控制广告压力"
        suggestions.append("当前 TACOS 已超过目标利润允许水平")

    if target_price is not None:
        distance = product.price - target_price
        suggestions.append(f"当前价格距离目标利润最低售价 {money(target_price)} 为 {money(distance)}")
    suggestions.append(f"阶段：{product.stage if hasattr(product, 'stage') else ''}；定位：{product.positioning if hasattr(product, 'positioning') else ''}".strip("；"))
    return [headline] + suggestions[:4]


def detail(row: dict) -> None:
    product = product_from_row(row)
    product.stage = row["stage"]
    product.positioning = row["positioning"]
    breakdown = profit_breakdown(product)
    target_max = max_tacos_for_margin(product, product.target_margin)
    room = ad_headroom(product)
    be_tacos = breakeven_tacos(product)
    be_price = breakeven_price(product)
    target_price = target_margin_price(product)

    st.title(row["name"])
    st.caption(f"ASIN: {row['asin'] or '-'} · SKU: {row['sku'] or '-'} · 站点: {row['marketplace'] or '-'}")

    cols = st.columns(8)
    metrics = [
        ("当前售价", money(product.price)),
        ("单件净利润", money(breakdown["net_profit"])),
        ("当前净利率", pct(breakdown["net_margin"])),
        ("当前 TACOS", pct(product.tacos)),
        ("保本 TACOS", pct(be_tacos)),
        ("目标最大 TACOS", pct(target_max)),
        ("广告剩余空间", pp(room)),
        ("月预估利润", money(breakdown["monthly_profit"])),
    ]
    for col, (label, value) in zip(cols, metrics):
        col.metric(label, value)
    st.info(headroom_message(room))

    st.subheader("利润构成")
    st.table(
        pd.DataFrame(
            [
                ["售价", money(product.price), "当前售价"],
                ["固定成本", f"-{money(breakdown['fixed_cost'])}", "采购 + 包装 + 头程 + FBA配送费 + 其他固定成本"],
                ["平台佣金", f"-{money(breakdown['commission'])}", f"{money(product.price)} × {pct(product.commission_rate)}"],
                ["广告成本", f"-{money(breakdown['ad_cost'])}", f"{money(product.price)} × {pct(product.tacos)}"],
                ["仓储预留", f"-{money(breakdown['storage_reserve'])}", f"{money(product.price)} × {pct(product.storage_rate)}"],
                ["退货预留", f"-{money(breakdown['return_reserve'])}", f"{pct(product.return_rate)} × ({money(breakdown['fixed_cost'])} + {money(breakdown['commission'])} × 20%)"],
                ["单件净利润", money(breakdown["net_profit"]), "售价 - 所有成本与预留"],
            ],
            columns=["项目", "金额", "计算来源"],
        )
    )

    with st.expander("查看公式"):
        st.write("固定成本 = 采购成本 + 包装成本 + 头程 + FBA配送费 + 其他固定成本")
        st.write("退货预留 = 退货率 × [固定成本 + (售价 × 平台佣金率 × 20%)]")
        st.write("单件净利润 = 售价 - 固定成本 - 平台佣金 - 广告成本 - 仓储预留 - 退货预留")
        st.write("净利率 = 单件净利润 ÷ 售价")

    st.subheader("价格底线")
    c1, c2 = st.columns(2)
    c1.metric("绝对保本售价", money(be_price))
    c2.metric(f"目标净利率 {pct(product.target_margin)} 最低售价", money(target_price))

    st.subheader("价格模拟")
    low_default = max(0.01, product.price - 3)
    high_default = product.price + 3
    c1, c2, c3 = st.columns(3)
    low = c1.number_input("最低模拟售价 $", min_value=0.01, value=float(round(low_default, 2)), step=0.5)
    high = c2.number_input("最高模拟售价 $", min_value=0.01, value=float(round(high_default, 2)), step=0.5)
    step = c3.number_input("价格间隔 $", min_value=0.01, value=1.0, step=0.25)
    prices = []
    p = high
    while p >= low - 1e-9:
        prices.append(round(p, 2))
        p -= step
    if product.price not in prices:
        prices.append(round(product.price, 2))
        prices = sorted(set(prices), reverse=True)
    sim_rows = []
    for price in prices:
        bd = profit_breakdown(product, price=price)
        max_t = max_tacos_for_margin(product, product.target_margin, price=price)
        label = "当前售价" if abs(price - product.price) < 0.001 else ""
        achieved = bd["net_margin"] >= product.target_margin and bd["net_profit"] > 0
        sim_rows.append(
            {
                "售价": f"{money(price)} {label}",
                "单件净利": money(bd["net_profit"]),
                "净利率": pct(bd["net_margin"]),
                "保本 TACOS": pct(breakeven_tacos(product, price=price)),
                "目标利润最大 TACOS": pct(max_t),
                "状态": "达标" if achieved else ("亏损" if bd["net_profit"] <= 0 else "未达目标"),
            }
        )
    st.dataframe(pd.DataFrame(sim_rows), use_container_width=True, hide_index=True)

    st.subheader("广告花费参考")
    c1, c2, c3 = st.columns(3)
    target_daily_revenue = c1.number_input("目标日销售额 $", min_value=0.0, value=float(round(product.price * product.daily_sales, 2)), step=10.0)
    target_tacos = c2.number_input("目标 TACOS %", min_value=0.0, value=float(product.tacos * 100), step=0.5) / 100
    c3.metric("对应广告花费参考", f"{money(target_daily_revenue * target_tacos)} / 天")
    st.caption("此数值代表该销售目标和 TACOS 下可承受的广告花费，不等于广告活动必须设置的 Budget。")

    st.subheader("当前经营建议")
    recs = recommendations(product, breakdown, target_price)
    st.markdown(f"**{recs[0]}**")
    for item in recs[1:]:
        st.write(f"- {item}")


def main() -> None:
    try:
        repository.init_db()
        products = repository.list_products()
    except Exception:
        st.error("数据初始化失败，请稍后刷新页面或检查部署日志。")
        return

    st.sidebar.title("产品管理")
    page = st.sidebar.radio("页面", ["店铺总览", "单品详情"], horizontal=True)

    with st.sidebar.expander("新增产品"):
        data = product_form({}, "保存新产品")
        if data:
            repository.insert_product(data)
            st.rerun()

    selected_id = None
    if products:
        ids = [p["id"] for p in products]
        names = {p["id"]: f"{p['name']} ({p['asin'] or '无 ASIN'})" for p in products}
        selected_id = st.sidebar.selectbox(
            "切换产品",
            ids,
            format_func=lambda pid: names[pid],
            index=ids.index(st.session_state.get("selected_product_id", ids[0])) if st.session_state.get("selected_product_id", ids[0]) in ids else 0,
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

    if page == "店铺总览":
        overview(products)
    elif selected_id:
        row = repository.get_product(selected_id)
        if row:
            with st.sidebar.expander("编辑当前产品", expanded=False):
                data = product_form(row, "保存修改")
                if data:
                    repository.update_product(selected_id, data)
                    st.rerun()
            detail(row)
    else:
        st.info("请先新增一个产品。")


if __name__ == "__main__":
    main()
