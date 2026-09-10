from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from modules.calculations import (
    ad_headroom,
    breakeven_price,
    breakeven_tacos,
    daily_record_metrics,
    estimate_status,
    fixed_cost,
    headroom_message,
    max_tacos_for_margin,
    pct_change,
    product_from_row,
    profit_breakdown,
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


def signed_money(value: float | None) -> str:
    if value is None:
        return "无法计算"
    sign = "+" if value >= 0 else "-"
    return f"{sign}${abs(value):,.2f}"


def count_text(value: float | None) -> str:
    if value is None:
        return "无法计算"
    return f"{value:,.0f}"


def tone_class(value: float) -> str:
    if value < 0:
        return "danger"
    if value == 0:
        return "warning"
    return "positive"


def stored_fixed_cost(product) -> float:
    """Support one-release mixed deployments while Streamlit Cloud reloads modules."""
    return float(getattr(product, "fixed_cost_usd", 0) or fixed_cost(product))


def estimate_with_ad_input(product, average_price: float, units: float, tacos: float | None, ad_spend: float | None) -> dict:
    """Keep one release of compatibility for a cloud app with stale calculation modules."""
    if tacos is None:
        revenue = average_price * units
        tacos = ad_spend / revenue if ad_spend is not None and revenue > 0 else 0.0
    try:
        return quick_profit_estimate(product, average_price, units, tacos=tacos, ad_spend=ad_spend)
    except TypeError:
        return quick_profit_estimate(product, average_price, units, tacos)


def input_warnings(product, *, sessions: float | None = None, units: float | None = None, tacos: float | None = None, ad_spend: float | None = None) -> list[str]:
    warnings = []
    if stored_fixed_cost(product) <= 0:
        warnings.append("固定成本为空或小于等于0")
    if product.price <= 0:
        warnings.append("售价小于等于0")
    for label, value in [("平台佣金率", product.commission_rate), ("TACOS", product.tacos), ("目标TACOS", product.target_tacos), ("退货率", product.return_rate), ("仓储率", product.storage_rate)]:
        if value > 1:
            warnings.append(f"{label}超过100%")
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


def section(title: str):
    st.markdown(f'<div class="section"><h3>{title}</h3>', unsafe_allow_html=True)


def end_section() -> None:
    st.markdown("</div>", unsafe_allow_html=True)


def profile_form(defaults: dict, button_label: str) -> dict | None:
    product = product_from_row(defaults)
    with st.form(button_label):
        c1, c2, c3 = st.columns(3)
        asin = c1.text_input("ASIN", product.asin)
        fnsku = c2.text_input("FNSKU", product.fnsku)
        name = c3.text_input("产品名称", product.name)
        c1, c2, c3, c4 = st.columns(4)
        fixed_cost_usd = c1.number_input("固定成本($/件)", min_value=0.0, value=stored_fixed_cost(product), step=0.01)
        commission_rate = c2.number_input("平台佣金率(%)", min_value=0.0, value=float(product.commission_rate * 100), step=0.1) / 100
        storage_rate = c3.number_input("仓储率(%)", min_value=0.0, value=float(product.storage_rate * 100), step=0.1) / 100
        return_rate = c4.number_input("退货率(%)", min_value=0.0, value=float(product.return_rate * 100), step=0.1) / 100

        st.markdown("**经营参数**")
        c1, c2, c3, c4 = st.columns(4)
        price = c1.number_input("当前售价 / 划线价($)", min_value=0.0, value=float(product.price), step=0.01)
        average_sale_price = c2.number_input("销售均价($)", min_value=0.0, value=float(product.average_sale_price or product.price), step=0.01)
        daily_sales = c3.number_input("预估销量(件/日)", min_value=0.0, value=float(product.daily_sales), step=1.0)
        tacos = c4.number_input("当前TACOS(%)", min_value=0.0, value=float(product.tacos * 100), step=0.1) / 100

        c1, c2, c3, c4 = st.columns(4)
        target_tacos = c1.number_input("目标TACOS(%)", min_value=0.0, value=float(product.target_tacos * 100), step=0.1) / 100
        target_margin = c2.number_input("目标净利率(%)", min_value=0.0, value=float(product.target_margin * 100), step=0.5) / 100
        c1, c2 = st.columns(2)
        stage = c1.selectbox("产品阶段", STAGES, index=STAGES.index(product.stage) if product.stage in STAGES else 1)
        positioning = c2.selectbox("产品定位", POSITIONS, index=POSITIONS.index(product.positioning) if product.positioning in POSITIONS else 1)

        submitted = st.form_submit_button(button_label, type="primary")
        if not submitted:
            return None
        payload = {
            "asin": asin.strip() or "UNSET-ASIN",
            "fnsku": fnsku.strip(),
            "name": name.strip() or "未命名产品",
            "fixed_cost_usd": fixed_cost_usd,
            "commission_rate": commission_rate,
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
        if show_warnings(input_warnings(product_from_row(payload))):
            return None
        return payload


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
    mode = c4.selectbox("广告输入方式", ["输入TACOS", "输入广告花费"], key="estimate_ad_mode")
    c1, c2 = st.columns(2)
    if mode == "输入TACOS":
        tacos = c1.number_input("TACOS(%)", min_value=0.0, value=float(product.tacos * 100), step=0.1, key="estimate_tacos") / 100
        ad_spend = None
    else:
        ad_spend = c1.number_input("广告花费($)", min_value=0.0, value=0.0, step=1.0, key="estimate_ad_spend")
        tacos = None
    estimate = estimate_with_ad_input(product, average_price, units, tacos=tacos, ad_spend=ad_spend)
    if show_warnings(input_warnings(product, units=units, tacos=estimate["tacos"], ad_spend=ad_spend)):
        end_section()
        return
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


def format_change(before: float, after: float, is_rate: bool = False, is_money: bool = False) -> str:
    diff = after - before
    if is_rate:
        return pp(diff)
    change = pct_change(before, after)
    if is_money:
        absolute = signed_money(diff)
    else:
        sign = "+" if diff >= 0 else ""
        absolute = f"{sign}{diff:,.0f}"
    if change is None:
        return f"{absolute}，无可比百分比"
    return f"{absolute}，{pp(change)}"


def trend_conclusion(previous: dict | None, latest: dict | None) -> str:
    if not previous or not latest:
        return "至少录入两条每日数据后，系统会自动判断最近一次价格或经营调整是否有效。"
    cvr_up = latest["cvr"] > previous["cvr"]
    units_up = latest["units"] > previous["units"]
    profit_up = latest["total_net_profit"] > previous["total_net_profit"]
    tacos_up = latest["tacos"] > previous["tacos"]
    if cvr_up and units_up and profit_up:
        return "本次调整后CVR和销量提升，总利润增加，当前调整整体有效。"
    if units_up and not profit_up:
        return "销量虽然提升，但总利润下降，当前价格变化没有带来更好的经营收益。"
    if cvr_up and tacos_up and not profit_up:
        return "CVR提升明显，但TACOS同时恶化，建议继续观察，不宜立即继续调价。"
    if profit_up and not tacos_up:
        return "总利润改善且TACOS未恶化，当前经营方向可以继续观察。"
    return "最近一次变化效果不明显，建议结合备注中的调价、Coupon或广告动作继续观察。"


def history_dataframe(product, records: list[dict]) -> pd.DataFrame:
    rows = []
    for record in records:
        metrics = daily_record_metrics(product, record)
        rows.append(
            {
                "日期": metrics["record_date"],
                "销售均价": money(metrics["average_price"]),
                "Session": count_text(metrics["sessions"]),
                "CVR": pct(metrics["cvr"]),
                "销量": count_text(metrics["units"]),
                "广告花费": money(metrics["entered_ad_spend"]),
                "TACOS": pct(metrics["tacos"]),
                "销售额": money(metrics["revenue"]),
                "单件净利润": money(metrics["unit_net_profit"]),
                "总利润": money(metrics["total_net_profit"]),
                "净利率": pct(metrics["net_margin"]),
                "备注": metrics["note"],
            }
        )
    return pd.DataFrame(rows)


def comparison_dataframe(product, records: list[dict]) -> tuple[pd.DataFrame, dict | None, dict | None]:
    chronological = sorted(records, key=lambda item: item["record_date"])
    if len(chronological) < 2:
        return pd.DataFrame(), None, None
    previous = daily_record_metrics(product, chronological[-2])
    latest = daily_record_metrics(product, chronological[-1])
    rows = [
        ["销售均价", money(previous["average_price"]), money(latest["average_price"]), format_change(previous["average_price"], latest["average_price"], is_money=True)],
        ["Session", count_text(previous["sessions"]), count_text(latest["sessions"]), format_change(previous["sessions"], latest["sessions"])],
        ["CVR", pct(previous["cvr"]), pct(latest["cvr"]), format_change(previous["cvr"], latest["cvr"], is_rate=True)],
        ["销量", count_text(previous["units"]), count_text(latest["units"]), format_change(previous["units"], latest["units"])],
        ["广告花费", money(previous["entered_ad_spend"]), money(latest["entered_ad_spend"]), format_change(previous["entered_ad_spend"], latest["entered_ad_spend"], is_money=True)],
        ["TACOS", pct(previous["tacos"]), pct(latest["tacos"]), format_change(previous["tacos"], latest["tacos"], is_rate=True)],
        ["单件净利润", money(previous["unit_net_profit"]), money(latest["unit_net_profit"]), format_change(previous["unit_net_profit"], latest["unit_net_profit"], is_money=True)],
        ["总利润", money(previous["total_net_profit"]), money(latest["total_net_profit"]), format_change(previous["total_net_profit"], latest["total_net_profit"], is_money=True)],
        ["净利率", pct(previous["net_margin"]), pct(latest["net_margin"]), format_change(previous["net_margin"], latest["net_margin"], is_rate=True)],
    ]
    return pd.DataFrame(rows, columns=["指标", "调整前", "调整后", "变化"]), previous, latest


def trend_chart(df: pd.DataFrame, title: str, left_col: str, right_col: str, left_name: str, right_name: str, left_fmt: str, right_fmt: str) -> go.Figure:
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    hover = df[["日期", "备注"]].to_numpy()
    fig.add_trace(
        go.Scatter(
            x=df["日期"],
            y=df[left_col],
            mode="lines+markers",
            name=left_name,
            customdata=hover,
            hovertemplate=f"日期：%{{customdata[0]}}<br>{left_name}：%{{y:{left_fmt}}}<br>备注：%{{customdata[1]}}<extra></extra>",
        ),
        secondary_y=False,
    )
    fig.add_trace(
        go.Scatter(
            x=df["日期"],
            y=df[right_col],
            mode="lines+markers",
            name=right_name,
            customdata=hover,
            hovertemplate=f"日期：%{{customdata[0]}}<br>{right_name}：%{{y:{right_fmt}}}<br>备注：%{{customdata[1]}}<extra></extra>",
        ),
        secondary_y=True,
    )
    if not df.empty:
        latest = df.iloc[-1]
        fig.add_trace(
            go.Scatter(
                x=[latest["日期"]],
                y=[latest[left_col]],
                mode="markers",
                marker={"size": 12, "symbol": "circle-open"},
                name="最新记录",
                hoverinfo="skip",
            ),
            secondary_y=False,
        )
    fig.update_layout(
        title=title,
        height=300,
        margin={"l": 30, "r": 30, "t": 44, "b": 20},
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "right", "x": 1},
    )
    fig.update_xaxes(title_text="日期")
    fig.update_yaxes(title_text=left_name, secondary_y=False)
    fig.update_yaxes(title_text=right_name, secondary_y=True)
    return fig


def daily_data_block(product, product_id) -> list[dict]:
    section("每日经营数据 / 价格变化效果分析")
    records = repository.list_daily_records(product_id)
    st.caption("每日数据保存在当前ASIN下，用于判断调价、Coupon、Deal或广告调整后的真实效果。")

    with st.expander("新增每日经营数据", expanded=not records):
        with st.form(f"daily_record_form_{product_id}"):
            c1, c2, c3, c4 = st.columns(4)
            record_date = c1.date_input("日期")
            average_price = c2.number_input("销售均价($)", min_value=0.0, value=float(product.average_sale_price or product.price), step=0.01, key=f"daily_avg_{product_id}")
            sessions = c3.number_input("Session", min_value=0.0, value=0.0, step=10.0, key=f"daily_sessions_{product_id}")
            units = c4.number_input("销量(件)", min_value=0.0, value=0.0, step=1.0, key=f"daily_units_{product_id}")
            c1, c2 = st.columns(2)
            ad_mode = c1.selectbox("广告输入方式", ["输入TACOS", "输入广告花费"], key=f"daily_ad_mode_{product_id}")
            if ad_mode == "输入TACOS":
                tacos = c2.number_input("TACOS(%)", min_value=0.0, value=float(product.tacos * 100), step=0.1, key=f"daily_tacos_{product_id}") / 100
                ad_spend = average_price * units * tacos
            else:
                ad_spend = c2.number_input("广告花费($)", min_value=0.0, value=0.0, step=1.0, key=f"daily_ad_{product_id}")
                tacos = ad_spend / (average_price * units) if average_price * units > 0 else 0.0
            note = st.text_input("备注", placeholder="调价 / Coupon / Deal / 广告预算调整 / Listing调整 / 其它动作")
            if st.form_submit_button("保存每日数据", type="primary"):
                warnings = input_warnings(product, sessions=sessions, units=units, tacos=tacos, ad_spend=ad_spend)
                if show_warnings(warnings):
                    st.stop()
                repository.upsert_daily_record(
                    {
                        "product_id": str(product_id),
                        "record_date": record_date.isoformat(),
                        "average_sale_price": average_price,
                        "sessions": sessions,
                        "units": units,
                        "ad_spend": ad_spend,
                        "tacos": tacos,
                        "note": note.strip(),
                        "snapshot_fixed_cost_usd": stored_fixed_cost(product),
                        "snapshot_commission_rate": product.commission_rate,
                        "snapshot_storage_rate": product.storage_rate,
                        "snapshot_return_rate": product.return_rate,
                    }
                )
                st.rerun()

    if records:
        edit_options = {record["id"]: f"{record['record_date']} · {record.get('note') or '无备注'}" for record in records}
        with st.expander("编辑 / 删除历史记录", expanded=False):
            record_id = st.selectbox("选择记录", list(edit_options.keys()), format_func=lambda item: edit_options[item])
            selected = next(record for record in records if record["id"] == record_id)
            with st.form(f"edit_daily_record_{record_id}"):
                c1, c2, c3, c4 = st.columns(4)
                record_date = c1.date_input("日期", value=pd.to_datetime(selected["record_date"]).date(), key=f"edit_date_{record_id}")
                average_price = c2.number_input("销售均价($)", min_value=0.0, value=float(selected["average_sale_price"]), step=0.01, key=f"edit_avg_{record_id}")
                sessions = c3.number_input("Session", min_value=0.0, value=float(selected["sessions"]), step=10.0, key=f"edit_sessions_{record_id}")
                units = c4.number_input("销量(件)", min_value=0.0, value=float(selected["units"]), step=1.0, key=f"edit_units_{record_id}")
                c1, c2 = st.columns(2)
                ad_mode = c1.selectbox("广告输入方式", ["输入TACOS", "输入广告花费"], key=f"edit_ad_mode_{record_id}")
                if ad_mode == "输入TACOS":
                    tacos = c2.number_input("TACOS(%)", min_value=0.0, value=float(selected["tacos"] * 100), step=0.1, key=f"edit_tacos_{record_id}") / 100
                    ad_spend = average_price * units * tacos
                else:
                    ad_spend = c2.number_input("广告花费($)", min_value=0.0, value=float(selected["ad_spend"]), step=1.0, key=f"edit_ad_{record_id}")
                    tacos = ad_spend / (average_price * units) if average_price * units > 0 else 0.0
                note = st.text_input("备注", value=selected.get("note") or "", key=f"edit_note_{record_id}")
                c1, c2 = st.columns(2)
                save = c1.form_submit_button("保存修改")
                delete = c2.form_submit_button("删除记录")
                payload = {
                    "product_id": str(product_id),
                    "record_date": record_date.isoformat(),
                    "average_sale_price": average_price,
                    "sessions": sessions,
                    "units": units,
                    "ad_spend": ad_spend,
                    "tacos": tacos,
                    "note": note.strip(),
                }
                if save:
                    warnings = input_warnings(product, sessions=sessions, units=units, tacos=tacos, ad_spend=ad_spend)
                    if show_warnings(warnings):
                        st.stop()
                    payload.update({
                        "snapshot_fixed_cost_usd": selected.get("snapshot_fixed_cost_usd") or stored_fixed_cost(product),
                        "snapshot_commission_rate": selected.get("snapshot_commission_rate") if selected.get("snapshot_commission_rate") is not None else product.commission_rate,
                        "snapshot_storage_rate": selected.get("snapshot_storage_rate") if selected.get("snapshot_storage_rate") is not None else product.storage_rate,
                        "snapshot_return_rate": selected.get("snapshot_return_rate") if selected.get("snapshot_return_rate") is not None else product.return_rate,
                    })
                    repository.update_daily_record(record_id, payload)
                    st.rerun()
                if delete:
                    repository.delete_daily_record(record_id)
                    st.rerun()

        comparison, previous, latest = comparison_dataframe(product, records)
        if not comparison.empty:
            st.markdown("**最新阶段 vs 上一阶段**")
            st.dataframe(comparison, use_container_width=True, hide_index=True, row_height=40)
            st.info(trend_conclusion(previous, latest))
        else:
            st.info("已保存1条每日数据。再录入1条后，会自动生成最新阶段 vs 上一阶段对比。")

        history = history_dataframe(product, records)
        st.markdown("**历史记录**")
        st.dataframe(history, use_container_width=True, hide_index=True, row_height=40)

        chart_df = pd.DataFrame([daily_record_metrics(product, record) for record in records]).sort_values("record_date")
        chart_df = chart_df.rename(
            columns={
                "record_date": "日期",
                "average_price": "销售均价",
                "sessions": "Session",
                "units": "销量",
                "entered_ad_spend": "广告花费",
                "total_net_profit": "总利润",
                "tacos": "TACOS",
                "note": "备注",
                "cvr": "CVR",
            }
        )
        st.plotly_chart(trend_chart(chart_df, "价格与CVR趋势", "销售均价", "CVR", "销售均价", "CVR", "$,.2f", ".1%"), use_container_width=True)
        st.plotly_chart(trend_chart(chart_df, "Session与销量趋势", "Session", "销量", "Session", "销量", ",.0f", ",.0f"), use_container_width=True)
        st.plotly_chart(trend_chart(chart_df, "总利润与TACOS趋势", "总利润", "TACOS", "总利润", "TACOS", "$,.2f", ".1%"), use_container_width=True)
    else:
        st.info("还没有每日经营数据。先录入一条，用来开始跟踪价格变化和运营调整效果。")
    end_section()
    return records


def recommendation_block(product, breakdown: dict, be_price: float | None, target_price: float | None, records: list[dict] | None = None) -> None:
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

    if records and len(records) >= 2:
        chronological = sorted(records, key=lambda item: item["record_date"])
        previous = daily_record_metrics(product, chronological[-2])
        latest = daily_record_metrics(product, chronological[-1])
        if latest["total_net_profit"] < previous["total_net_profit"] and latest["units"] >= previous["units"]:
            profit_text = "最近销量没有变差，但总利润下降，先确认调价或广告动作是否压缩了利润。"
        elif latest["total_net_profit"] > previous["total_net_profit"] and latest["tacos"] <= previous["tacos"]:
            profit_text = "最近总利润改善且TACOS未恶化，当前调整可以继续观察。"

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
    show_warnings(input_warnings(product))
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

    with st.expander("编辑产品档案", expanded=False):
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
    st.caption(f"当前使用的固定成本：{money(fixed_cost(product))} / 件；基础参数最后更新：{row.get('updated_at') or '未知'}。")
    st.table(
        pd.DataFrame(
            [
                ["售价", money(product.price), "当前售价"],
                ["固定成本", f"-{money(breakdown['fixed_cost'])}", "产品基础参数中直接填写的固定成本"],
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
    records = daily_data_block(product, selected_id)

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

    recommendation_block(product, breakdown, be_price, target_price, records)


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
