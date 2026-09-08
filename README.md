# Amazon 多产品利润与经营决策助手

一个面向 Amazon 运营的轻量经营决策工具，用于快速查看多产品利润、价格底线、TACOS 承受力和当前经营状态。

第一版不接任何外部 API，不做复杂 ERP，也不做广告活动级诊断。核心目标是让运营快速回答：

- 产品现在是否赚钱
- 当前售价是否合理
- 广告还有多少放量空间
- 降价或促销后利润会变成多少
- 多个产品中哪些需要优先关注

## 功能

- 店铺总览：预估月销售额、预估月利润、整体净利率、整体 TACOS、健康/关注/风险产品数量
- 单品详情：当前售价、单件净利润、当前净利率、当前 TACOS、保本 TACOS、目标净利率下最大 TACOS
- 利润构成：固定成本、平台佣金、广告成本、仓储预留、退货预留、单件净利润
- 价格模拟：按当前售价附近区间模拟利润、净利率和 TACOS 上限
- 价格底线：绝对保本售价、目标利润最低售价
- 广告花费参考：根据目标日销售额和目标 TACOS 计算可承受广告花费
- 产品管理：新增、编辑、复制、删除、切换查看

## 项目结构

```text
.
├── app.py
├── requirements.txt
├── README.md
├── verify_formulas.py
├── database/
├── modules/
│   ├── calculations.py
│   └── repository.py
└── assets/
```

## 本地启动

```bash
pip install -r requirements.txt
streamlit run app.py
```

启动后浏览器会打开本地页面。

## Streamlit Community Cloud 部署

1. 将本项目 push 到 GitHub 仓库
2. 打开 Streamlit Community Cloud
3. 使用 GitHub 登录
4. 点击创建新应用
5. 选择对应 GitHub 仓库
6. 选择要部署的 branch
7. Main file path 填写 `app.py`
8. 点击 Deploy

部署成功后，Streamlit 会生成公开网页链接，其他人打开链接即可访问页面。

## SQLite 说明

当前版本使用 SQLite，数据库文件运行时生成在 `database/amazon_profit.db`。

这适合第一阶段演示和功能测试，但不适合长期多人正式使用：

- Streamlit Community Cloud 上的 SQLite 文件通常不应被视为可靠持久存储
- 多个用户同时新增、编辑、删除产品时，SQLite 不适合作为安全的多人协作数据库
- 云端实例重启、休眠、重新部署后，运行时写入的数据可能丢失或回到初始状态

后续如果要正式多人使用，建议把 `modules/repository.py` 中的 `ProductRepository` 抽象替换为 Supabase 或 PostgreSQL 实现。当前版本已经把数据访问层集中在该文件中，方便第二阶段替换。

## 公式校验

```bash
python verify_formulas.py
```

校验覆盖：

- 固定成本
- 平台佣金
- 广告成本
- 仓储预留
- 退货预留
- 单件净利润
- 净利率
- 保本 TACOS
- 目标净利率下最大 TACOS
- 绝对保本售价
- 目标利润最低售价
