from __future__ import annotations

from dataclasses import dataclass


RETURN_COMMISSION_FACTOR = 0.20


@dataclass
class ProductInput:
    asin: str = ""
    fnsku: str = ""
    name: str = ""
    purchase_packaging_cny: float = 0.0
    first_leg_cny: float = 0.0
    fba_fee: float = 0.0
    commission_rate: float = 0.15
    exchange_rate: float = 7.2
    price: float = 0.0
    average_sale_price: float = 0.0
    daily_sales: float = 0.0
    tacos: float = 0.2
    target_tacos: float = 0.2
    target_margin: float = 0.12
    return_rate: float = 0.08
    storage_rate: float = 0.02
    stage: str = "成长期"
    positioning: str = "增长款"


def clamp_non_negative(value: float | int | None) -> float:
    return max(float(value or 0), 0.0)


def safe_exchange_rate(product: ProductInput) -> float:
    return max(clamp_non_negative(product.exchange_rate), 0.0001)


def purchase_packaging_usd(product: ProductInput) -> float:
    return clamp_non_negative(product.purchase_packaging_cny) / safe_exchange_rate(product)


def first_leg_usd(product: ProductInput) -> float:
    return clamp_non_negative(product.first_leg_cny) / safe_exchange_rate(product)


def fixed_cost(product: ProductInput) -> float:
    return purchase_packaging_usd(product) + first_leg_usd(product) + clamp_non_negative(product.fba_fee)


def profit_breakdown(product: ProductInput, price: float | None = None, tacos: float | None = None) -> dict:
    sale_price = clamp_non_negative(product.price if price is None else price)
    current_tacos = clamp_non_negative(product.tacos if tacos is None else tacos)
    base_cost = fixed_cost(product)
    commission = sale_price * clamp_non_negative(product.commission_rate)
    ad_cost = sale_price * current_tacos
    storage_reserve = sale_price * clamp_non_negative(product.storage_rate)
    return_reserve = clamp_non_negative(product.return_rate) * (
        base_cost + commission * RETURN_COMMISSION_FACTOR
    )
    net_profit = sale_price - base_cost - commission - ad_cost - storage_reserve - return_reserve
    net_margin = net_profit / sale_price if sale_price > 0 else 0.0
    monthly_revenue = sale_price * clamp_non_negative(product.daily_sales) * 30
    monthly_profit = net_profit * clamp_non_negative(product.daily_sales) * 30

    return {
        "price": sale_price,
        "fixed_cost": base_cost,
        "commission": commission,
        "ad_cost": ad_cost,
        "storage_reserve": storage_reserve,
        "return_reserve": return_reserve,
        "net_profit": net_profit,
        "net_margin": net_margin,
        "monthly_revenue": monthly_revenue,
        "monthly_profit": monthly_profit,
    }


def max_tacos_for_margin(product: ProductInput, target_margin: float, price: float | None = None) -> float:
    sale_price = clamp_non_negative(product.price if price is None else price)
    if sale_price <= 0:
        return 0.0

    base_cost = fixed_cost(product)
    commission_rate = clamp_non_negative(product.commission_rate)
    storage_rate = clamp_non_negative(product.storage_rate)
    return_rate = clamp_non_negative(product.return_rate)
    non_ad_cost = (
        base_cost
        + sale_price * commission_rate
        + sale_price * storage_rate
        + return_rate * (base_cost + sale_price * commission_rate * RETURN_COMMISSION_FACTOR)
    )
    allowed_ad_cost = sale_price * (1 - clamp_non_negative(target_margin)) - non_ad_cost
    return allowed_ad_cost / sale_price


def breakeven_tacos(product: ProductInput, price: float | None = None) -> float:
    return max_tacos_for_margin(product, 0.0, price)


def ad_headroom(product: ProductInput, price: float | None = None) -> float:
    return max_tacos_for_margin(product, product.target_margin, price) - clamp_non_negative(product.tacos)


def tacos_vs_target(product: ProductInput) -> float:
    return clamp_non_negative(product.tacos) - clamp_non_negative(product.target_tacos)


def status(product: ProductInput, price: float | None = None) -> str:
    breakdown = profit_breakdown(product, price=price)
    if breakdown["net_profit"] <= 0:
        return "🔴 风险"
    if breakdown["net_margin"] >= clamp_non_negative(product.target_margin):
        return "🟢 健康"
    return "🟡 关注"


def estimate_status(net_profit: float, net_margin: float, target_margin: float) -> str:
    if net_profit <= 0:
        return "🔴 预计亏损"
    if net_margin >= clamp_non_negative(target_margin):
        return "🟢 达到目标"
    return "🟡 盈利但未达目标"


def simulation_status(net_profit: float, net_margin: float, target_margin: float) -> str:
    if net_profit <= 0:
        return "🔴 亏损"
    if net_margin >= clamp_non_negative(target_margin):
        return "🟢 达到目标"
    return "🟡 盈利但未达目标"


def headroom_message(headroom: float) -> str:
    if headroom > 0.03:
        return "仍有一定广告放量空间"
    if headroom >= 0:
        return "利润空间较窄，谨慎放量"
    return "当前TACOS已经超过目标利润允许水平"


def price_for_margin(product: ProductInput, target_margin: float) -> float | None:
    denominator = (
        1
        - clamp_non_negative(product.tacos)
        - clamp_non_negative(product.commission_rate)
        - clamp_non_negative(product.storage_rate)
        - clamp_non_negative(target_margin)
        - clamp_non_negative(product.return_rate)
        * clamp_non_negative(product.commission_rate)
        * RETURN_COMMISSION_FACTOR
    )
    cost_multiplier = 1 + clamp_non_negative(product.return_rate)
    if denominator <= 0:
        return None
    return fixed_cost(product) * cost_multiplier / denominator


def breakeven_price(product: ProductInput) -> float | None:
    return price_for_margin(product, 0.0)


def target_margin_price(product: ProductInput) -> float | None:
    return price_for_margin(product, product.target_margin)


def quick_profit_estimate(product: ProductInput, average_price: float, units: float, tacos: float) -> dict:
    avg_price = clamp_non_negative(average_price)
    unit_count = clamp_non_negative(units)
    tacos_rate = clamp_non_negative(tacos)
    revenue = avg_price * unit_count
    ad_spend = revenue * tacos_rate
    unit_commission = avg_price * clamp_non_negative(product.commission_rate)
    total_commission = unit_commission * unit_count
    unit_storage = avg_price * clamp_non_negative(product.storage_rate)
    total_storage = unit_storage * unit_count
    unit_return = clamp_non_negative(product.return_rate) * (
        fixed_cost(product) + unit_commission * RETURN_COMMISSION_FACTOR
    )
    total_return = unit_return * unit_count
    total_fixed_cost = fixed_cost(product) * unit_count
    unit_ad_cost = avg_price * tacos_rate
    unit_net_profit = avg_price - fixed_cost(product) - unit_commission - unit_ad_cost - unit_storage - unit_return
    total_net_profit = unit_net_profit * unit_count
    net_margin = total_net_profit / revenue if revenue > 0 else 0.0

    return {
        "average_price": avg_price,
        "units": unit_count,
        "tacos": tacos_rate,
        "revenue": revenue,
        "ad_spend": ad_spend,
        "unit_commission": unit_commission,
        "total_commission": total_commission,
        "unit_storage": unit_storage,
        "total_storage": total_storage,
        "unit_return": unit_return,
        "total_return": total_return,
        "total_fixed_cost": total_fixed_cost,
        "unit_net_profit": unit_net_profit,
        "total_net_profit": total_net_profit,
        "net_margin": net_margin,
    }


def daily_record_metrics(product: ProductInput, record: dict) -> dict:
    average_price = clamp_non_negative(record.get("average_sale_price"))
    units = clamp_non_negative(record.get("units"))
    sessions = clamp_non_negative(record.get("sessions"))
    tacos = clamp_non_negative(record.get("tacos"))
    estimate = quick_profit_estimate(product, average_price, units, tacos)
    estimate["record_date"] = record.get("record_date", "")
    estimate["sessions"] = sessions
    estimate["cvr"] = units / sessions if sessions > 0 else 0.0
    estimate["entered_ad_spend"] = clamp_non_negative(record.get("ad_spend"))
    estimate["note"] = record.get("note", "") or ""
    estimate["id"] = record.get("id")
    return estimate


def pct_change(previous: float, current: float) -> float | None:
    previous_value = float(previous or 0)
    if previous_value == 0:
        return None
    return (float(current or 0) - previous_value) / abs(previous_value)


def product_from_row(row: dict) -> ProductInput:
    exchange_rate = row.get("exchange_rate", 7.2)
    purchase_packaging_cny = row.get("purchase_packaging_cny")
    first_leg_cny = row.get("first_leg_cny")

    if purchase_packaging_cny is None:
        legacy_purchase = clamp_non_negative(row.get("purchase_cost")) + clamp_non_negative(row.get("packaging_cost"))
        purchase_packaging_cny = legacy_purchase * clamp_non_negative(exchange_rate)
    if first_leg_cny is None:
        first_leg_cny = clamp_non_negative(row.get("first_leg_cost")) * clamp_non_negative(exchange_rate)

    return ProductInput(
        asin=row.get("asin", "") or "",
        fnsku=row.get("fnsku") or row.get("sku", "") or "",
        name=row.get("name", "") or "",
        purchase_packaging_cny=purchase_packaging_cny,
        first_leg_cny=first_leg_cny,
        fba_fee=row.get("fba_fee", 0),
        commission_rate=row.get("commission_rate", 0.15),
        exchange_rate=exchange_rate,
        price=row.get("price", 0),
        average_sale_price=row.get("average_sale_price") or row.get("price", 0),
        daily_sales=row.get("daily_sales", 0),
        tacos=row.get("tacos", 0.2),
        target_tacos=row.get("target_tacos", 0.2),
        target_margin=row.get("target_margin", 0.12),
        return_rate=row.get("return_rate", 0.08),
        storage_rate=row.get("storage_rate", 0.02),
        stage=row.get("stage", "成长期") or "成长期",
        positioning=row.get("positioning", "增长款") or "增长款",
    )
