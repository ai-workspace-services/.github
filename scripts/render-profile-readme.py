#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import urllib.request
from pathlib import Path
from typing import Any


ORG = "ai-workspace-services"
OUTPUT = Path(__file__).resolve().parents[1] / "profile" / "README.md"

PACKAGE_MAP = {
    "accounts": {"title": "accounts", "description": "账户与身份相关镜像。"},
    "billing-service": {"title": "billing-service", "description": "计费服务镜像。"},
    "docs": {"title": "docs", "description": "文档站镜像。"},
    "console": {"title": "console", "description": "控制台前端镜像。"},
    "postgresql": {"title": "postgresql", "description": "PostgreSQL 基础镜像。"},
}

ENV_PACKAGE_GROUPS = {
    "sit": ["console"],
    "uat": ["accounts", "billing-service", "docs", "postgresql"],
    "prod": [],
}

ENV_PRIORITY = {
    "sit": [re.compile(r"^sit-"), re.compile(r"^snapshot-")],
    "uat": [re.compile(r"^uat-"), re.compile(r"^uat/")],
    "prod": [re.compile(r"^prod-"), re.compile(r"^prod/"), re.compile(r"^v\d")],
}


def api(path: str) -> Any:
    req = urllib.request.Request(
        f"https://api.github.com{path}",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "ai-workspace-services-homepage-generator",
        },
    )
    with urllib.request.urlopen(req) as resp:
        return json.load(resp)


def list_packages() -> list[dict[str, Any]]:
    return api(f"/orgs/{ORG}/packages?package_type=container&per_page=100")


def list_versions(package_name: str) -> list[dict[str, Any]]:
    return api(f"/orgs/{ORG}/packages/container/{package_name}/versions?per_page=20")


def newest_version_for_env(versions: list[dict[str, Any]], env: str) -> dict[str, Any] | None:
    patterns = ENV_PRIORITY[env]
    scored = []
    for version in versions:
        tags = version.get("metadata", {}).get("container", {}).get("tags", []) or []
        score = 0
        for tag in tags:
            if any(p.match(tag) for p in patterns):
                score += 10
            elif tag == "latest" and env in {"sit", "uat"}:
                score += 1
        if score > 0:
            scored.append((score, version))
    if scored:
        scored.sort(key=lambda item: (item[0], item[1].get("created_at", "")), reverse=True)
        return scored[0][1]
    return versions[0] if versions else None


def classify_env(version: dict[str, Any]) -> str | None:
    tags = version.get("metadata", {}).get("container", {}).get("tags", []) or []
    for env, patterns in ENV_PRIORITY.items():
        for tag in tags:
            if any(pattern.match(tag) for pattern in patterns):
                return env
    if "latest" in tags:
        return "uat"
    if any(tag.startswith("sha-") for tag in tags):
        return "sit"
    return None


def env_version_for_package(package_name: str, env: str) -> dict[str, Any] | None:
    versions = list_versions(package_name)
    matched = []
    for version in versions:
        if classify_env(version) == env:
            matched.append(version)
    if matched:
        matched.sort(key=lambda version: version.get("created_at", ""), reverse=True)
        return matched[0]
    if env == "sit" and package_name in ENV_PACKAGE_GROUPS["sit"]:
        return newest_version_for_env(versions, "sit")
    if env == "uat" and package_name in ENV_PACKAGE_GROUPS["uat"]:
        return newest_version_for_env(versions, "uat")
    if env == "prod" and package_name in ENV_PACKAGE_GROUPS["prod"]:
        return newest_version_for_env(versions, "prod")
    return None


def format_tags(version: dict[str, Any] | None) -> str:
    if not version:
        return "暂无"
    tags = version.get("metadata", {}).get("container", {}).get("tags", []) or []
    return ", ".join(f"`{tag}`" for tag in tags) if tags else "未打 tag"


def badge(env: str) -> str:
    colors = {
        "sit": ("Integration Check", "16a34a"),
        "uat": ("Pre Release", "f59e0b"),
        "prod": ("Production Release", "dc2626"),
    }
    label, color = colors[env]
    return f"[![{env}](https://img.shields.io/badge/{env}-{label.replace(' ', '%20')}-{color}?style=for-the-badge)](https://github.com/orgs/{ORG}/packages)"


def latest_card(env: str, version: dict[str, Any] | None) -> str:
    title_map = {"sit": "验证集成", "uat": "预发验证", "prod": "生产发布"}
    tags = format_tags(version)
    updated = version.get("created_at", "").replace("T", " ").replace("Z", " UTC") if version else "暂无"
    return f"| `{env}` | {badge(env)} | {title_map[env]} | {tags} | {updated} |"


def env_card(env: str, package_names: list[str]) -> list[str]:
    rows = []
    for package_name in package_names:
        version = env_version_for_package(package_name, env)
        pkg = PACKAGE_MAP[package_name]
        rows.append(
            f"| `{pkg['title']}` | {format_tags(version)} | {pkg['description']} |"
        )
    return rows


def render() -> str:
    package_names = ["accounts", "billing-service", "docs", "console", "postgresql"]

    latest_cards = [
        latest_card("sit", env_version_for_package("console", "sit")),
        latest_card("uat", env_version_for_package("billing-service", "uat")),
        latest_card("prod", env_version_for_package("postgresql", "prod")),
    ]

    lines = []
    lines.append('<div align="center">')
    lines.append("")
    lines.append('<img src="../assets/services-hero.svg" alt="ai-workspace-services hero" width="100%" />')
    lines.append("")
    lines.append("# ai-workspace-services")
    lines.append("")
    lines.append("**开放的服务底座，统一承载身份、平台与可观测性。**")
    lines.append("")
    lines.append('<a href="https://console.svc.plus/" target="_blank">进入控制台 / Console</a> ·')
    lines.append('<a href="https://console.svc.plus/products/xworkmate" target="_blank">Xworkmate</a> ·')
    lines.append('<a href="https://console.svc.plus/products/xstream" target="_blank">Xstream Platform</a>')
    lines.append("")
    lines.append("<br /><br />")
    lines.append("")
    lines.append("[![Live Service](https://img.shields.io/badge/Live-Service-1f6feb?style=flat-square)](https://console.svc.plus/)")
    lines.append("[![GitHub OAuth](https://img.shields.io/badge/GitHub-OAuth-24292f?style=flat-square&logo=github)](https://console.svc.plus/)")
    lines.append("[![Google OAuth](https://img.shields.io/badge/Google-OAuth-4285F4?style=flat-square&logo=google)](https://console.svc.plus/)")
    lines.append("[![Production](https://img.shields.io/badge/Production-Running-0ea5e9?style=flat-square)](https://console.svc.plus/)")
    lines.append("")
    lines.append("</div>")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 最新发布")
    lines.append("")
    lines.append("| 环境 | 最新发布 | 说明 | 镜像 / 包 | 更新时间 |")
    lines.append("| --- | --- | --- | --- | --- |")
    lines.extend(latest_cards)
    lines.append("")
    lines.append("> 三张卡片会保持简洁，重点是让你一眼看到每条环境线的最新发布入口。")
    lines.append("")
    lines.append("## 镜像清单")
    lines.append("")
    lines.append("<table>")
    lines.append("<tr>")
    for env in ("sit", "uat", "prod"):
        lines.append("<td valign=\"top\" width=\"33%\">")
        lines.append("")
        lines.append(f"### {env}")
        lines.append("")
        lines.append("| 镜像 / 包 | 最新 tag | 说明 |")
        lines.append("| --- | --- | --- |")
        rows = env_card(env, ENV_PACKAGE_GROUPS[env])
        if rows:
            lines.extend(rows)
        else:
            lines.append("| `暂无` | `暂无` | 该环境当前没有可展示的镜像。 |")
        lines.append("")
        lines.append("</td>")
    lines.append("</tr>")
    lines.append("</table>")
    lines.append("")
    lines.append("## 中文")
    lines.append("")
    lines.append("`ai-workspace-services` 是面向真实业务运行的服务组织主页，聚合统一控制台、身份认证、AI 工作台与跨网络互联能力。")
    lines.append("")
    lines.append("- `Open-platform`：开放平台与基础设施能力中心")
    lines.append("- `Xworkmate`：AI 工作空间，面向持续推进的任务协作")
    lines.append("- `Xstream Platform`：海外 AI 服务加速与私有网络互联")
    lines.append("- `Auth`：支持 `GitHub OAuth` 与 `Google OAuth`")
    lines.append("")
    lines.append("所有展示内容都对应实际在线运行的服务，不是 demo。")
    lines.append("")
    lines.append("### 环境速览")
    lines.append("")
    lines.append("- `sit`: 验证集成")
    lines.append("- `uat`: 预发验证")
    lines.append("- `prod`: 生产发布")
    lines.append("")
    lines.append("## English")
    lines.append("")
    lines.append("`ai-workspace-services` is the organization home for real production services. It brings together the console, identity, AI workspace, and connectivity capabilities behind the platform.")
    lines.append("")
    lines.append("- `Open-platform`: the platform and infrastructure core")
    lines.append("- `Xworkmate`: an AI workspace for persistent task execution")
    lines.append("- `Xstream Platform`: overseas AI acceleration and private network interconnect")
    lines.append("- `Auth`: supports `GitHub OAuth` and `Google OAuth`")
    lines.append("")
    lines.append("Everything shown here points to live services, not a demo.")
    lines.append("")
    lines.append("### Environment Snapshot")
    lines.append("")
    lines.append("- `sit`: integration checks")
    lines.append("- `uat`: pre-release validation")
    lines.append("- `prod`: production release")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 入口 / Entry Points")
    lines.append("")
    lines.append("| 项目 | 说明 | 链接 |")
    lines.append("| --- | --- | --- |")
    lines.append("| `Console` | 统一入口与服务导航 | https://console.svc.plus/ |")
    lines.append("| `Xworkmate` | AI 工作空间 | https://console.svc.plus/products/xworkmate |")
    lines.append("| `Xstream Platform` | 海外 AI 服务加速与互联 | https://console.svc.plus/products/xstream |")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    if not os.environ.get("GITHUB_TOKEN"):
        raise SystemExit("GITHUB_TOKEN is required")
    OUTPUT.write_text(render() + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
