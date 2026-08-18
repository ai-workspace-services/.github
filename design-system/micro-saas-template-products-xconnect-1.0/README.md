# Micro SaaS 模版 v1.0 (XConnect)

面向 Micro SaaS 产品的四页模版：**产品主页 / 用户中心 / 订阅计费 / 帮助中心**。
首个落地案例为 [XConnect](https://console.onwalk.net/products/xconnect)。

## 设计取向

排版语言借鉴 Supabase，可迁移的是三点，而不是它的绿色：

- **轻字重** —— 只用 400 / 500 / 600，禁用 bold / extrabold，层级由字号和颜色承担
- **宽行高** —— 正文 1.6，标题 1.18
- **深度靠边框分层，不靠阴影** —— 平面组件一律无阴影，只有浮层投影

品牌色沿用控制台既有的 `#0058bd`，营销页与控制台首次共用同一套变量。

## 文件

| 文件 | 说明 |
|---|---|
| `DESIGN-SYSTEM.md` | 完整规范：现状审计实测数据、token 定义、组件规范、四页设计决策、分四批迁移路径 |
| `00-design-overview.html` | 四页平铺设计稿总览 + token 摘要（双栏配平 masonry） |
| `01-product-home.html` | 产品主页，可交互 |
| `02-user-center.html` | 用户中心，可交互 |
| `03-billing.html` | 订阅计费，可交互 |
| `04-help-center.html` | 帮助中心，可交互 |
| `tokens.css` | 全部 token + 组件样式，可直接并入项目全局样式 |

原型可交互部分：Tabs 切换、分段控件、侧栏与文档导航高亮、FAQ 展开、复制反馈、输入框聚焦环。
响应式断点 1100px / 680px。

## 关键数字

- 圆角 **20 种 → 4 种**（4 / 6 / 10 / 14px + pill）
- 阴影 **13 种 → 3 种**（overlay / modal / focus-ring）
- 正文 **13px / 行高 1.15 → 15px / 1.6**
- 对比度全部通过 WCAG 2.1 AA
