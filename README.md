# Amazon 多产品利润与经营决策助手

面向 Amazon 运营的轻量经营决策工具，用来快速判断产品利润、价格底线、TACOS 承受力、广告放量空间和多产品处理优先级。

## 核心能力

- 多产品总览：加权月销售额、加权月利润、整体净利率、整体TACOS、健康/关注/风险产品数
- 单品详情：当前售价、单件净利润、净利率、月预估利润、当前TACOS、目标TACOS、保本TACOS、目标利润TACOS上限
- 产品基础档案：ASIN、FNSKU、产品名称、固定成本($/件)、平台佣金率、仓储率、退货率
- 经营参数：售价、销售均价、预估销量、当前TACOS、目标TACOS、目标净利率、退货率、仓储率、阶段、定位
- 利润快速估算：只输入销售均价、销量、TACOS，快速估算一段时间利润
- 每日经营数据：按ASIN保存销售均价、Session、销量、广告花费、TACOS和备注
- 广告费/TACOS二选一录入：系统自动换算另一项，并在保存前校验异常数据
- 历史参数快照：每日记录保存当时的固定成本、佣金率、仓储率和退货率，避免未来改参数后历史利润失真
- 价格变化效果分析：比较最新记录和上一记录，查看CVR、Session、销量、TACOS、利润变化
- 趋势图：价格与CVR、Session与销量、总利润与TACOS
- 价格底线和价格模拟：判断促销最低能做到什么价格
- 广告承受力和广告花费参考：判断TACOS是否过高、广告还有没有空间
- 导出 Excel：导出当前产品或全部产品利润测算表，便于留档、复盘和发给同事
- 当前经营建议：聚焦价格、广告、利润三件事

## 项目结构

```text
.
├── app.py
├── requirements.txt
├── README.md
├── verify_formulas.py
├── modules/
│   ├── __init__.py
│   ├── calculations.py
│   ├── exporter.py
│   └── repository.py
├── database/
│   └── .gitkeep
└── assets/
    └── .gitkeep
```

## 本地启动

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Streamlit Community Cloud 部署

1. 将本项目上传到 GitHub 仓库
2. 打开 Streamlit Community Cloud
3. 使用 GitHub 登录
4. 选择对应仓库
5. Branch 选择 `main`
6. Main file path 填 `app.py`
7. 点击 Deploy

## 持久化存储

当前代码支持两种数据存储：

- 配置 Supabase 时：使用 Supabase，适合 Streamlit Cloud 长期保存产品档案
- 未配置 Supabase 时：自动回退 SQLite，适合本地测试或公开演示，但不适合线上长期保存

Streamlit Cloud 上的 SQLite 运行时文件不能视为可靠持久化存储。实例重启、休眠、重新部署后，修改数据可能丢失；多用户同时修改也不适合作为正式协作数据库。

## Supabase 配置

在 Streamlit Cloud 的 App settings -> Secrets 中填写：

```toml
SUPABASE_URL = "https://你的项目.supabase.co"
SUPABASE_ANON_KEY = "你的 anon public key"
```

在 Supabase SQL Editor 中创建表：

```sql
create extension if not exists pgcrypto;

create table if not exists products (
  id uuid primary key default gen_random_uuid(),
  asin text not null,
  fnsku text,
  name text not null,
  fixed_cost_usd numeric not null default 0,
  purchase_packaging_cny numeric not null default 0,
  first_leg_cny numeric not null default 0,
  fba_fee numeric not null default 0,
  commission_rate numeric not null default 0.15,
  exchange_rate numeric not null default 7.2,
  price numeric not null default 0,
  average_sale_price numeric not null default 0,
  daily_sales numeric not null default 0,
  tacos numeric not null default 0.2,
  target_tacos numeric not null default 0.2,
  target_margin numeric not null default 0.12,
  return_rate numeric not null default 0.08,
  storage_rate numeric not null default 0.02,
  stage text not null default '成长期',
  positioning text not null default '增长款',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists daily_records (
  id uuid primary key default gen_random_uuid(),
  product_id text not null,
  record_date date not null,
  average_sale_price numeric not null default 0,
  sessions numeric not null default 0,
  units numeric not null default 0,
  ad_spend numeric not null default 0,
  tacos numeric not null default 0,
  note text,
  snapshot_fixed_cost_usd numeric,
  snapshot_commission_rate numeric,
  snapshot_storage_rate numeric,
  snapshot_return_rate numeric,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(product_id, record_date)
);
```

如果 Supabase 中已经有旧版表，请在 SQL Editor 额外执行：

```sql
alter table products add column if not exists fixed_cost_usd numeric not null default 0;
alter table daily_records add column if not exists snapshot_fixed_cost_usd numeric;
alter table daily_records add column if not exists snapshot_commission_rate numeric;
alter table daily_records add column if not exists snapshot_storage_rate numeric;
alter table daily_records add column if not exists snapshot_return_rate numeric;
```

## 公式校验

```bash
python verify_formulas.py
```

校验覆盖：

- 平台佣金
- 广告成本
- 仓储预留
- 退货预留
- 单件净利润
- 单件利润率
- 保本TACOS
- 目标利润TACOS上限
- 绝对保本售价
- 目标净利率最低售价
