from __future__ import annotations

from dataclasses import dataclass


RETURN_COMMISSION_FACTOR = 0.20


@dataclass
class ProductInput:
    purchase_cost: float
    packaging_cost: float
    first_leg_cost: float
    fba_fee: float
    other_fixed_cost: float
    commission_rate: float
    storage_rate: float
    return_rate: float
    price: float
    tacos: float
    daily_sales: float
    target_margin: float


def clamp_non_negative(value: float) -> float:
    return max(float(value or 0), 0.0)


def fixed_cost(product: ProductInput) -> float:
    return sum(
        clamp_non_negative(v)
        for v in (
            product.purchase_cost,
            product.packaging_cost,
            product.first_leg_cost,
            product.fba_fee,
            product.other_fixed_cost,
        )
    )


def profit_breakdown(product: ProductInput, price: float | None = None, tacos: float | None = None) -> dict:
    sale_price = clamp_non_negative(product.price if price is None else price)
    tacos_rate = clamp_non_negative(product.tacos if tacos is None else tacos)
    base_cost = fixed_cost(product)
    commission = sale_price * clamp_non_negative(product.commission_rate)
    ad_cost = sale_price * tacos_rate
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


def status(product: ProductInput, price: float | None = None) -> str:
    breakdown = profit_breakdown(product, price=price)
    if breakdown["net_profit"] <= 0:
        return "🔴 风险"
    if breakdown["net_margin"] >= clamp_non_negative(product.target_margin):
        return "🟢 健康"
    return "🟡 关注"


def headroom_message(headroom: float) -> str:
    if headroom > 0.03:
        return "仍有一定广告放量空间"
    if headroom >= 0:
        return "利润空间较窄，谨慎放量"
    return "当前 TACOS 已超过目标利润允许水平"


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


def product_from_row(row: dict) -> ProductInput:
    return ProductInput(
        purchase_cost=row["purchase_cost"],
        packaging_cost=row["packaging_cost"],
        first_leg_cost=row["first_leg_cost"],
        fba_fee=row["fba_fee"],
        other_fixed_cost=row["other_fixed_cost"],
        commission_rate=row["commission_rate"],
        storage_rate=row["storage_rate"],
        return_rate=row["return_rate"],
        price=row["price"],
        tacos=row["tacos"],
        daily_sales=row["daily_sales"],
        target_margin=row["target_margin"],
    )
