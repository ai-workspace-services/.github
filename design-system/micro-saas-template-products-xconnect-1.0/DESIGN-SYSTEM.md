# XConnect Micro SaaS 模版 — 设计系统规范 v1.0

产出范围：产品主页 / 用户中心 / 订阅计费 / 帮助中心 四个核心页面，统一 token 驱动。
排版语言借鉴 Supabase，品牌色沿用 portal 控制台既有的 `--color-primary: #0058bd`。

---

## 1. 现状审计

基于 `portal/src` 实际扫描（范围：`app/products`、`app/panel`、`app/prices`、`app/docs`、`components/marketing`、`components/billing`、`modules/extensions/builtin/user-center`）。

### 1.1 Token 覆盖率

| 指标 | 实测 |
|---|---|
| 硬编码 Tailwind 调色板实例（`text-slate-900`、`bg-gray-50` …） | **527** |
| token 实例（`text-primary`、`border-surface-border` …） | **186** |
| **Token 覆盖率** | **26%** |

高频硬编码 Top 6：`text-slate-900`(51)、`border-slate-200`(39)、`bg-slate-50`(39)、`text-slate-600`(33)、`text-slate-700`(32)、`border-slate-900`(28)。

营销页与控制台是**两套互不相干的色彩语言**：营销页走 `indigo-600 / purple-50 / slate-*`，控制台走 `--color-primary #0058bd`。同一个产品的注册前后视觉不连续。

### 1.2 圆角与阴影发散

| 类别 | 唯一取值数 | 明细 |
|---|---|---|
| 圆角 | **20 种** | `rounded-full`(73)、`lg`(50)、`xl`(43)、`2xl`(41)、`md`(21)、`[8px]`(15)、`[var(--radius-xl)]`(11)、`3xl`(7)、`[12px]`(6)、`[1rem]`(5)、`[16px]`、`[14px]`、`[0.9rem]`、`[0.95rem]`、`[6px]`、`[10px]`、`[2rem]`、`[999px]` … |
| 阴影 | **13 种** | `shadow-sm`(34)、`[var(--shadow-soft)]`(18)、`[var(--shadow-sm)]`(13)、`2xl`(6)、`inner`(4)、`[var(--shadow-md)]`(4)、以及 5 个一次性 `shadow-[0_18px_45px_...]` 字面量 |

`rounded-[0.9rem]` / `rounded-[0.95rem]` / `rounded-[1rem]` 三个几乎无法区分的值同时存在，是典型的「无规范可依」信号。

### 1.3 排版是最大的问题

`globals.css` 当前：

```css
--type-body-size: 0.8125rem;        /* 13px */
--type-body-line-height: 1.1538;    /* 行高 15px */
--type-heading-3-size: 0.8125rem;   /* h3 = 13px，与正文同号 */
--type-heading-1-size: 1.5rem;      /* h1 = 24px */
```

三个后果：

1. **13px / 1.15 的正文**在中文下几乎无呼吸感 —— 15px 的行盒装 13px 的字，行间只剩 2px。Supabase 正文是 16px / 1.5。
2. **h3 与正文同为 13px**，标题层级在 h3 处塌陷。
3. **h1 只有 24px**，营销页 hero 不得不绕过 token 直接写 `text-6xl`，token 层形同虚设。

字号使用分布也印证了这点：`text-sm`(251) + `text-xs`(151) = 402 / 534，**75% 的文字 ≤14px**。字重 `font-semibold` 用了 175 次、`font-bold` 35 次、`font-extrabold` 6 次 —— 靠加粗代偿层级不足。

### 1.4 页面级问题（来自实际截图）

| 页面 | 问题 |
|---|---|
| 用户中心 | 3 个引导步骤各带一个同等权重的按钮（"完成安全设置"/"查看 VLESS 二维码"/"查看运行节点"），用户不知道先点哪个。第 2 步用蓝色实心按钮，反而比真正待办的第 1 步更抢眼。 |
| 订阅计费 | 右上角"绑定 MFA 后可管理账单"是个**灰紫色禁用按钮**，同时下方黄色横幅说同一件事。禁用按钮读起来像坏了；同一诉求出现两次。 |
| 订阅计费 | 4 个数据卡全为 0/空态，页面读起来像出故障，没有引导下一步的出口。 |
| 产品主页 | Hero → showcase 图文，缺少"3 步开启"的转化主干；下载入口只有一个泛按钮，没有平台矩阵。 |

---

## 2. 排版规范（借鉴 Supabase）

Supabase 排版的三个可迁移特征：**轻字重**（几乎全 400/500）、**宽行高**（正文 1.5–1.6）、**大小对比强**（hero 与正文差 4 倍以上，而不是靠加粗拉开）。

### 2.1 字号阶梯

| Token | 值 | 行高 | 字重 | 用途 |
|---|---|---|---|---|
| `--fs-display-1` | 68px | 1.04 | 500 | 营销 hero |
| `--fs-display-2` | 48px | 1.08 | 500 | 区块 hero / 终版 CTA |
| `--fs-h1` | 36px | 1.18 | 500 | 营销区块标题 |
| `--fs-h2` | 28px | 1.18 | 500 | 控制台页标题 |
| `--fs-h3` | 21px | 1.18 | 500 | 文档 h2 |
| `--fs-h4` | 17px | 1.18 | **600** | 卡片 / 面板标题 |
| `--fs-body-lg` | 17px | 1.75 | 400 | 营销正文 |
| `--fs-body` | **15px** | **1.6** | 400 | 默认正文 |
| `--fs-body-sm` | 14px | 1.6 | 400 | 控制台正文 / 表格 |
| `--fs-caption` | 13px | 1.35 | 400 | 卡片补充说明 |
| `--fs-micro` | 12px | 1.35 | 500 | 标签 / 表头 |
| `--fs-eyebrow` | 11px | 1.35 | 600 | 全大写眉标（mono，`ls: 0.09em`） |

**关键变更**：正文 13px/1.15 → 15px/1.6；h3 13px → 21px；h1 24px → 36px。

### 2.2 字重与字距

只用三档：`400` 正文 / `500` 标题与按钮 / `600` 面板标题与眉标。**禁用 `font-bold` 与 `font-extrabold`** —— 层级由字号和颜色承担。

字距：display `-0.032em`、heading `-0.018em`、正文 `0`、eyebrow `+0.09em`。

### 2.3 等宽字的角色

Supabase 用 mono 承载"技术性"。本模版沿用：**所有标识符与数值走 mono** —— UUID、节点地址、端口、账单号、金额、百分比、延迟、配额。带来两个好处：数字用 `tabular-nums` 天然对齐；营销页的 `99.95%` / `<40ms` 有工程质感而不靠图形装饰。

---

## 3. 颜色

### 3.1 中性色阶（12 档，替代混用的 slate/gray/zinc）

`#ffffff` `#fcfcfd` `#f7f8fa` `#eff1f5` `#e3e7ee` `#d0d6e0` `#9aa4b5` `#616c80` `#525c6e` `#3d4553` `#262c37` `#141920`

### 3.2 语义别名

```
背景  canvas #f7f8fa · surface #fff · raised #fcfcfd · sunken #eff1f5 · inverse #141920
文字  primary #141920 · secondary #525c6e · tertiary #616c80 · disabled #9aa4b5
边框  subtle #eff1f5 · default #e3e7ee · strong #d0d6e0 · brand #b4cef4
```

### 3.3 品牌与语义色

| 角色 | 值 | 说明 |
|---|---|---|
| Primary | `#0058bd` | 沿用控制台既有主色，营销页 indigo/violet 全部收敛到此 |
| Primary hover / active | `#004a9e` / `#003c80` | |
| Success | `#0f7c46` on `#e6f5ed` | 已连通 / 已支付 / 已验证 |
| Warning | `#8a5300` on `#fdf3e0` | 高延迟 / 需 MFA / 退款处理中 |
| Danger | `#b42318` on `#fdeceb` | 已退款 / 取消订阅 |
| Info | `#004a9e` on `#eef4fd` | 当前套餐 / 中性提示 |

### 3.4 对比度校验（WCAG 2.1 AA）

全部实测通过：

| 配对 | 对比度 | 要求 |
|---|---|---|
| text-primary / surface | 17.65 | 4.5 ✅ |
| text-secondary / surface | 6.74 | 4.5 ✅ |
| text-tertiary / raised | 5.17 | 4.5 ✅ |
| text-tertiary / sunken | 4.68 | 4.5 ✅ |
| blue-500 / surface（链接） | 6.71 | 4.5 ✅ |
| white / blue-500（主按钮） | 6.71 | 4.5 ✅ |
| success / success-bg | 4.67 | 4.5 ✅ |
| warning / warning-bg | 5.75 | 4.5 ✅ |
| danger / danger-bg | 5.75 | 4.5 ✅ |
| info / info-bg | 7.68 | 4.5 ✅ |
| 侧栏图标 #8b95a5 / #141920 | 5.83 | 3.0 ✅ |

> 审计过程中 `--text-tertiary` 原定 `#6b7688`，在 `raised(#fcfcfd)` 与 `sunken(#eff1f5)` 背景上分别只有 4.48 / 4.06，已下调至 `#616c80`。眉标类文字（`.nav-label`、`.wizard-idx`、`.tile-tag`）原用 `text-disabled`（2.51），已改用 `text-tertiary`；`--text-disabled` 现在只服务真正的禁用控件。

---

## 4. 形状、层次与间距

### 4.1 圆角：20 种 → 4 种

| Token | 值 | 用途 |
|---|---|---|
| `--r-xs` | 4px | badge · tag · input · 色块 |
| `--r-sm` | 6px | button · 卡内子元素 · code |
| `--r-md` | 10px | card · panel · 表格容器 |
| `--r-lg` | 14px | 大容器 · 模态 |
| `--r-pill` | 999px | 仅用于 hero 徽标与筛选 chip |

### 4.2 阴影：13 种 → 3 种，且平面不投影

Supabase 的关键取舍：**深度由边框强度表达，不由阴影表达**。本模版照此执行。

```
--shadow-overlay  0 4px 12px rgba(20,25,32,.08), 0 1px 3px rgba(20,25,32,.06)   /* 下拉 / 气泡 */
--shadow-modal    0 16px 48px rgba(20,25,32,.14), 0 2px 8px rgba(20,25,32,.08)  /* 模态 */
--focus-ring      0 0 0 3px rgba(0,88,189,.22)
```

卡片、面板、表格、按钮**一律 `shadow: none`**，靠 `border-subtle → default → strong` 三档边框分层。这一条直接消灭现有的 `shadow-2xl`、`shadow-[0_28px_90px_...]` 之类的一次性字面量。

### 4.3 间距

4px 基准：`4 · 8 · 12 · 16 · 20 · 24 · 32 · 40 · 56 · 80 · 120`。

节奏对比：营销区块之间 **80–120px**（cinematic pacing），卡片内部 **16–24px**（tight clustering）。这是 Supabase 页面呼吸感的主要来源，而不是字体本身。

---

## 5. 组件规范

### 5.1 Button

| 变体 | 用途 | 视觉 |
|---|---|---|
| `btn-primary` | 每屏**唯一**主行动 | 实心 `blue-500`，白字 |
| `btn-secondary` | 并列次级行动 | 白底 + `border-strong` |
| `btn-ghost` | 表格行内 / 低权重 | 透明，hover 出 `sunken` 底 |
| `btn-danger` | 破坏性 | 白底 + `danger-border`，文字 danger |

尺寸：`sm` 28px · 默认 36px · `lg` 44px。
状态：default / hover（色阶 +1 档）/ active / focus-visible（`--focus-ring`）/ disabled（`opacity .5` + `pointer-events: none`）/ loading。

**规则**：一个视觉区块内只能有一个 `btn-primary`。这条直接修掉用户中心三个步骤三个同权按钮的问题 —— 只有"当前待办步骤"用 primary，其余用 secondary / ghost。

### 5.2 Badge / 状态

`badge` + `badge-{success|warning|danger|info}`，内含 `.dot` 色点。高 20px，`--r-xs`，11px 字重 500。
**状态必须同时用颜色和文字表达**，不允许只靠色点区分（色觉障碍可达性）。

### 5.3 Card / Panel

`card`（`border-default` + `--r-md`，无阴影）+ `card-head` / `card-body` / `card-foot`。
`card-head` 底部 `border-subtle`；`card-foot` 用 `bg-raised` 承载元信息与次级链接。
可交互卡片加 `card-hover`：只变 `border-color` 与背景，**不做位移**。

### 5.4 Stepper（向导）

两个形态共用同一语义：

- **营销页** `.wizard-card` —— 三格无缝拼接，每格带 `STEP 0N` 眉标、时长徽标、和一个"结果预览"缩略视觉（勾选列表 / 二维码 / 节点表）。让用户在注册前就看到每步会得到什么。
- **控制台** `.s3` —— 带完成度进度条（`1 / 3`）、`is-done` / `is-active` 状态、每步下挂具体校验项（`邮箱已验证` ✓ / `多因素认证未设置` ○）。

`step-num`：默认空心灰、`is-active` 实心蓝、`is-done` 实心绿带勾。

### 5.5 Meter（配额 / 用量）

6px 高 pill 轨道。`is-warning`（≥75%）/ `is-danger`（≥90%）自动换色。
必须与等宽数字文本配对：`0 B / 10 GB`、`剩余 10 GB`、`本期重置 09-01`。

### 5.6 Table

表头 `bg-raised` + 12px `text-tertiary`；行分隔 `border-subtle`；hover `bg-hover`。
数值列 `.num`：mono + `tabular-nums` + 右对齐。行内操作用 `btn-ghost btn-sm`。

### 5.7 Empty state

虚线 `border-strong` + `bg-raised`，含图标 / 标题 / 一句说明 / **一个出口按钮**。
空态永远要给下一步 —— "暂无订阅记录"配"查看套餐"，"还没有流量数据"配"查看运行节点"。这是修掉计费页"全 0 像坏了"的关键。

### 5.8 Alert / Gate

`alert-{info|warning|danger|success}`。
**安全门禁（MFA）只出现一处**：一条 warning alert，左侧图标、中间说明、右侧一个 primary 行动按钮。删除原先右上角那个灰紫禁用按钮。文案要先说"不受影响的部分"再说"受限的部分"：

> 浏览用量、配额和账单不受影响。发起 Stripe 购买、变更订阅或进入客户门户前需要完成一次身份验证。

### 5.9 其它

`tabs`（下划线 2px）· `seg`（分段控件）· `input` / `search-big` · `kv-strip`（账户元信息条）· `code-box`（深底代码）· `value-box`（浅底可复制值）· `stat`（数据卡）· `qr` · `tag` · `kbd`。

---

## 6. 四个页面的设计决策

### 6.1 产品主页（Marketing）

结构：Nav → Hero → 信任数据条 → **3 步向导** → 能力矩阵 6 格 → 下载矩阵 → 定价锚点 → FAQ → 深色终版 CTA → Footer。

- **3 步向导是转化主干**，不是装饰。每步给出时长预期（1 分钟 / 30 秒 / 即时）和结果预览，降低"要折腾多久"的不确定感。区块末尾只有一个 primary："创建账户，开始第 1 步"。
- **下载做成表格而非按钮云**：平台 / 架构 / 安装包名 / 大小 / 下载，一眼可比。"明确不支持鸿蒙 OS"放 `card-foot` 而不是 hero —— 否定信息不该占据首屏。
- **定价只做锚点**，三档并列，详细计费规则交给计费页与文档。

### 6.2 用户中心（Console）

结构：icon rail + sidebar + topbar → 页标题 → **账户设置进度** → 账户元信息条 → VLESS 连接 + 代理 UUID → 实时流量 + 月度配额 → 运行节点表。

- 引导区加**完成度进度条**（`1 / 3` + meter）和"还差 1 步即可解锁计费与订阅操作"—— 把抽象的步骤变成有终点的进度。
- 只有第 1 步用 primary 按钮，第 2 步 secondary，第 3 步 ghost。视线自然落在真正待办的地方。
- UUID / 订阅链接用 `value-box`（mono、可全选、`word-break: break-all`），复制按钮点击后 1.6s 内变"已复制"。
- 节点表带延迟条形图与状态徽标；`—` 明确表示"API 未返回"，不编造数值。
- 流量为空时不是留白，而是 empty state + "查看运行节点"出口。

### 6.3 订阅计费（Console）

结构：MFA 门禁（单处）→ Tabs → 4 张数据卡 → 套餐三档 → 用量趋势 + 付款方式 → 账单记录（空态 + 有数据形态）→ 退款与取消（危险区）。

- **门禁只出现一次**，并且是可行动的（右侧 primary "去绑定 MFA"）。套餐卡上的"升级到 Pro"保留可点外观 + 锁图标 + "需先绑定 MFA"注脚，而不是变灰。
- 账单表同时给出**空态与有数据形态**，便于评审时确认状态徽标、金额右对齐、行内发票下载的设计。
- 退款/取消收进**危险区**：`danger-border` 卡片 + 粉底 head，两项各自带完整说明（退款窗口、降级后果）。破坏性操作必须解释后果。

### 6.4 帮助中心（Docs）

结构：搜索 Hero + 热门问题 chip → **按任务开始** 4 格 → 文档阅读形态（三栏：左目录 / 正文 / 右 on-this-page）→ 全部文档集 → 还没解决？

- 入口按**任务**而非按产品模块组织：第一次连通 / 客户端配置 / 订阅与账单 / 排查与错误码。用户带着问题来，不带着目录来。
- 正文 `prose` 用 17px / 1.75，有序步骤用 counter 圆点，`code-box` 深底，警示用 alert。
- 右栏放"对应控制台位置"直达链接 —— 文档与控制台**双向可跳**，是这套模版的核心连接。
- "还没解决"三个出口：工单 / 状态页 / 社区，先建议查状态页（很多问题不是用户的问题）。

---

## 7. 落地到 portal 的迁移路径

建议分四批，每批可独立合入：

**批次 1 — token 层（改动最小，收益最大）**
替换 `src/app/globals.css` 的 `:root` 变量块与 `tailwind.config.js` 的 `theme.extend`。重点是排版四行：

```css
--type-body-size:        0.9375rem;  /* 13px → 15px */
--type-body-line-height: 1.6;        /* 1.1538 → 1.6 */
--type-heading-3-size:   1.3125rem;  /* 13px → 21px */
--type-heading-1-size:   2.25rem;    /* 24px → 36px */
```

这一步会让全站正文可读性立刻改观，风险集中在紧凑布局的溢出，需回归 `panel` 各页。

**批次 2 — 圆角与阴影收敛**
全局替换 20 种圆角为 4 档、13 种阴影为 3 档。可用 codemod：`rounded-[0.9rem]|rounded-[0.95rem]|rounded-[1rem]|rounded-xl|rounded-2xl → rounded-[var(--r-md)]`，`shadow-*` 在非浮层组件上一律删除。

**批次 3 — 颜色去硬编码**
527 处硬编码调色板按映射表批量替换：
`text-slate-900|text-gray-900 → text-[var(--text-primary)]`、`text-slate-600|text-gray-600 → text-[var(--text-secondary)]`、`border-slate-200|border-gray-200 → border-[var(--border-default)]`、`bg-slate-50 → bg-[var(--bg-canvas)]`、`indigo-*|purple-*|violet-* → blue-*`。目标是把 token 覆盖率从 26% 提到 90%+。

**批次 4 — 组件与页面重构**
按 `src/components/ui/` 沉淀 Button / Card / Badge / Meter / Stepper / EmptyState / Alert / Table，再把四个页面切过去。
`user-center` 的引导区（`UserOverview.tsx`）、计费门禁（`SubscriptionPanel.tsx` / `BillingOptionsPanel.tsx`）优先，因为交互问题最明确。

> 仓库既有约束（见 `AGENTS.md`）：不新增依赖、Zustand 为唯一全局状态、`packages/**` 内禁用 `@/` 别名。以上四批均只触及 `src/app/**` 与 `src/components/**`，不涉及这些边界。

---

## 8. 交付物

| 文件 | 说明 |
|---|---|
| `00-design-overview.html` | 4 页平铺设计稿 + token 摘要（双栏配平 masonry，1440px 设计视口按 61% 缩放） |
| `01-product-home.html` | 产品主页，可交互 |
| `02-user-center.html` | 用户中心，可交互 |
| `03-billing.html` | 订阅计费，可交互 |
| `04-help-center.html` | 帮助中心，可交互 |
| `tokens.css` | 全部 token + 组件样式，可直接并入 `globals.css` |

原型可交互部分：Tabs 切换、分段控件、侧栏/文档导航高亮、FAQ 展开、复制反馈、输入框聚焦环。响应式断点 1100px / 680px。
