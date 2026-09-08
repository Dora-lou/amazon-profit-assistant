from modules.calculations import (
    ProductInput,
    breakeven_price,
    breakeven_tacos,
    max_tacos_for_margin,
    profit_breakdown,
    target_margin_price,
)


def close(a: float, b: float, tolerance: float = 0.01) -> None:
    assert abs(a - b) <= tolerance, f"{a} != {b}"


def main() -> None:
    product = ProductInput(
        purchase_cost=6.2,
        packaging_cost=0.45,
        first_leg_cost=1.15,
        fba_fee=3.05,
        other_fixed_cost=0.35,
        commission_rate=0.15,
        storage_rate=0.02,
        return_rate=0.06,
        price=24.99,
        tacos=0.18,
        daily_sales=18,
        target_margin=0.12,
    )
    bd = profit_breakdown(product)
    close(bd["fixed_cost"], 11.20)
    close(bd["commission"], 3.7485)
    close(bd["ad_cost"], 4.4982)
    close(bd["storage_reserve"], 0.4998)
    close(bd["return_reserve"], 0.71697)
    close(bd["net_profit"], 4.32653)
    close(bd["net_margin"], 0.17313)

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

    print("Formula checks passed")
    print(f"Sample unit net profit: ${bd['net_profit']:.2f}")
    print(f"Sample net margin: {bd['net_margin'] * 100:.1f}%")
    print(f"Breakeven TACOS: {be_tacos * 100:.1f}%")
    print(f"Max TACOS for target margin: {target_tacos * 100:.1f}%")
    print(f"Breakeven price: ${be_price:.2f}")
    print(f"Target-margin minimum price: ${target_price:.2f}")


if __name__ == "__main__":
    main()
