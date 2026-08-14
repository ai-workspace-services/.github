<div align="center">

<img src="../assets/services-hero.svg" alt="ai-workspace-services hero" width="100%" />

# AI Workspace Services 🌐

**开放的 AI 云原生服务底座 · 赋能下一代 AI 工作空间、全球低延迟连接与智能协作**  
*The Open AI Cloud-Native Foundation — Powering Next-Gen AI Workspaces, Global Low-Latency Interconnect & Autonomous Collaboration.*

<br />

<p align="center">
  <a href="https://console.svc.plus/"><strong>🚀 进入统一控制台 / Launch Console</strong></a>
  &nbsp;·&nbsp;
  <a href="https://console.svc.plus/products/xconnect"><strong>⚡ XConnect 加速连接器</strong></a>
  &nbsp;·&nbsp;
  <a href="https://console.svc.plus/products/xworkmate"><strong>🤖 XWorkmate AI 协作工作空间</strong></a>
</p>

<p align="center">
  <a href="https://console.svc.plus/"><img src="https://img.shields.io/badge/Production-Live%20Service-2563EB?style=flat-square" alt="Production Live Service" /></a>
  <img src="https://img.shields.io/badge/OAuth-GitHub%20%7C%20Google-111827?style=flat-square" alt="GitHub & Google OAuth" />
  <a href="https://github.com/ai-workspace-xstream"><img src="https://img.shields.io/badge/Open%20Source-100%25%20Available-10B981?style=flat-square" alt="100% Open Source" /></a>
  <img src="https://img.shields.io/badge/Uptime-99.9%25-8B5CF6?style=flat-square" alt="High Availability" />
</p>

<p align="center">
  <a href="#-中文主页">🇨🇳 中文介绍</a> ｜ <a href="#-english-guide">🇬🇧 English Overview</a>
</p>

</div>

---

## 最新发布

| 环境 | 最新发布 | 说明 | 镜像 / 包 | 更新时间 |
| --- | --- | --- | --- | --- |
| `sit` | [![sit](https://img.shields.io/badge/sit-Integration%20Check-16a34a?style=for-the-badge)](https://github.com/orgs/ai-workspace-services/packages) | 验证集成 | `sha-4a7176cb0b02ceadaee3e0d6335fa7c2bbda7c2b` | 2026-07-27 05:40:52 UTC |
| `uat` | [![uat](https://img.shields.io/badge/uat-Pre%20Release-f59e0b?style=for-the-badge)](https://github.com/orgs/ai-workspace-services/packages) | 预发验证 | `uat-platform-rebuild-2026.07.27-r4`, `sha-3a8a5ce0d99dbd62064d109b3c5c1fad7daf22f5`, `latest` | 2026-07-27 05:38:38 UTC |
| `prod` | [![prod](https://img.shields.io/badge/prod-Production%20Release-dc2626?style=for-the-badge)](https://github.com/orgs/ai-workspace-services/packages) | 生产发布 | 暂无 | 暂无 |

> 三张卡片会保持简洁，重点是让你一眼看到每条环境线的最新发布入口。

## 镜像清单

<table>
<tr>
<td valign="top" width="33%">

### sit

| 镜像 / 包 | 最新 tag | 说明 |
| --- | --- | --- |
| `console` | `sha-4a7176cb0b02ceadaee3e0d6335fa7c2bbda7c2b` | 控制台前端镜像。 |

</td>
<td valign="top" width="33%">

### uat

| 镜像 / 包 | 最新 tag | 说明 |
| --- | --- | --- |
| `accounts` | `sha-ca132850316149d428d547f57cf41f879d1c5fe0`, `latest` | 账户与身份相关镜像。 |
| `billing-service` | `uat-platform-rebuild-2026.07.27-r4`, `sha-3a8a5ce0d99dbd62064d109b3c5c1fad7daf22f5`, `latest` | 计费服务镜像。 |
| `docs` | `uat-platform-rebuild-2026.07.27-r4`, `sha-595931d1fb3b5b90220ed8568fa36fecb0a4f36e`, `latest` | 文档站镜像。 |
| `postgresql` | `uat-platform-rebuild-2026.07.27-r4` | PostgreSQL 基础镜像。 |

</td>
<td valign="top" width="33%">

### prod

| 镜像 / 包 | 最新 tag | 说明 |
| --- | --- | --- |
| `暂无` | `暂无` | 该环境当前没有可展示的镜像。 |

</td>
</tr>
</table>

## 中文

```mermaid
flowchart LR
    Start([选择你的使用模式]) --> ModeA["⚡ 个人加速：1 域名 + 1 VPS 一键自建<br/>3 分钟全自动部署节点并输出订阅链接"]
    Start --> ModeB["☁️ 免运维云服务：直接登录控制台<br/>GitHub/Google 一键免密登录，开箱即用"]
    Start --> ModeC["🏢 企业私有化：全栈开源私有部署<br/>Web UI + Agent + 多租户 DB 完整交付"]
```

- **🚀 3 分钟一键自建节点**（需 1 台 VPS + 1 个解析好的域名）：
  ```bash
  curl -fsSL https://raw.githubusercontent.com/cloud-neutral-toolkit/agent.svc.plus/main/scripts/setup-proxy.sh | \
    bash -s -- --node xhttp.example.com
  ```
- **📱 跨平台自研客户端**：下载 **[XConnect App 预览版)](https://github.com/ai-workspace-xstream/xconnect-app/releases/tag/main-149)**（支持 macOS / Windows / iOS / Linux）。
- **🌐 云端免运维即刻使用**：直接访问 **[console.svc.plus](https://console.svc.plus/)**。

---

## 🇬🇧 English Guide

### 💡 Why AI Workspace Services?

### 环境速览

- `sit`: 验证集成
- `uat`: 预发验证
- `prod`: 生产发布

## English

`ai-workspace-services` provides a battle-tested, **always-on production foundation** that unifies identity, AI workspace collaboration, and ultra-low-latency global network interconnect.

---

### 🌟 Core Product Suite

| Product | Key Capabilities | Best For | Link |
| :--- | :--- | :--- | :--- |
| ⚡ **XConnect / XStream** | **AI Workspace Acceleration & Connectivity**<br/>• Optimized for Cursor, Claude, ChatGPT streaming latency<br/>• 3-min 1-click self-host (1 Domain + 1 VPS) or fully managed SaaS<br/>• Kernel-level BBR+FQ pacing, auto Let's Encrypt TLS | Developers, AI power users, global teams | [Overview](https://console.svc.plus/products/xconnect) · [One-Click Script](https://github.com/ai-workspace-xstream/agent.svc.plus) |
| 🤖 **XWorkmate** | **Autonomous AI Workspace & Task Orchestration**<br/>• Persistent context execution for multi-step AI workflows<br/>• Multi-agent team collaboration and state tracking | Automated engineering, knowledge pipelines | [Launch XWorkmate](https://console.svc.plus/products/xworkmate) |
| 🛡️ **Open-Platform Core** | **Unified Identity & Multi-Tenant Core**<br/>• One-click sign-in with GitHub and Google OAuth<br/>• Tenant isolation, secret governance, and observability | Enterprise self-hosting, team management | [Console Home](https://console.svc.plus/) |

### Environment Snapshot

- `sit`: integration checks
- `uat`: pre-release validation
- `prod`: production release

---

### 🧭 Quick Start Options

1. **🚀 3-Minute Quick Self-Host**:
   ```bash
   curl -fsSL https://raw.githubusercontent.com/cloud-neutral-toolkit/agent.svc.plus/main/scripts/setup-proxy.sh | \
     bash -s -- --node xhttp.example.com
   ```
2. **📱 Native Client**: Download **[XConnect Client Preview](https://github.com/ai-workspace-xstream/xconnect-app/releases/tag/main-149)** (macOS / Windows / iOS / Linux).
3. **☁️ Zero-Ops Cloud**: Log in directly to **[console.svc.plus](https://console.svc.plus/)** with GitHub / Google OAuth.

---

<div align="center">

**[🚀 立即访问统一控制台 / Visit Console](https://console.svc.plus/)** · **[🏢 开源生态 / Open Source Ecosystem](https://github.com/ai-workspace-xstream)**

</div>
