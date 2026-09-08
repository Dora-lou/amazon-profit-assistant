from modules.calculations import (
    ProductInput,
    breakeven_price,
    breakeven_tacos,
    fixed_cost,
    max_tacos_for_margin,
    profit_breakdown,
    quick_profit_estimate,
    target_margin_price,
)


def close(a: float, b: float, tolerance: float = 0.01) -> None:
    assert abs(a - b) <= tolerance, f"{a} != {b}"


def main() -> None:
    product = ProductInput(
        asin="B0DEMO001",
        fnsku="X003KDO001",
        name="Kitchen Drawer Organizer",
        purchase_packaging_cny=47.88,
        first_leg_cny=8.28,
        fba_fee=3.05,
        commission_rate=0.15,
        exchange_rate=7.2,
        price=24.99,
        average_sale_price=24.99,
        daily_sales=18,
        tacos=0.18,
        target_tacos=0.20,
        target_margin=0.12,
        return_rate=0.06,
        storage_rate=0.02,
    )
    bd = profit_breakdown(product)
    close(fixed_cost(product), 10.85)
    close(bd["commission"], 3.7485)
    close(bd["ad_cost"], 4.4982)
    close(bd["storage_reserve"], 0.4998)
    close(bd["return_reserve"], 0.69597)
    close(bd["net_profit"], 4.69653)
    close(bd["net_margin"], 0.18794)

    be_tacos = breakeven_tacos(product)
    close(profit_breakdown(product, tacos=be_tacos)["net_profit"], 0, tolerance=0.001)

    target_tacos = max_tacos_for_margin(product, product.target_margin)
    target_bd = profit_breakdown(product, tacos=target_tacos)
    close(target_bd["net_margin"], product.target_margin, tolerance=0.001)

    be_price = breakeven_price(product)
    assert be_price is not None
    close(profit_breakdown(product, price=be_price)["net_profit"], 0, tolerance=0.001)

    target_price = target_margin_price(product)
    assert target_price is not None
    close(profit_breakdown(product, price=target_price)["net_margin"], product.target_margin, tolerance=0.001)

    estimate = quick_profit_estimate(product, average_price=24.99, units=10, tacos=0.18)
    close(estimate["total_net_profit"], bd["net_profit"] * 10)
    close(estimate["net_margin"], bd["net_margin"])

    print("Formula checks passed")
    print(f"Fixed cost: ${fixed_cost(product):.2f}")
    print(f"Sample unit net profit: ${bd['net_profit']:.2f}")
    print(f"Sample net margin: {bd['net_margin'] * 100:.1f}%")
    print(f"Breakeven TACOS: {be_tacos * 100:.1f}%")
    print(f"Target-profit TACOS limit: {target_tacos * 100:.1f}%")
    print(f"Breakeven price: ${be_price:.2f}")
    print(f"Target-margin minimum price: ${target_price:.2f}")


if __name__ == "__main__":
    main()
