#!/usr/bin/env python3
"""
gh-hunter — GitHub 开源项目猎手 🔭
热搜排行榜 · 高星分类 · 新项目发现
"""

import os
import re
import sys
import json
import time
import argparse
import webbrowser
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from typing import Optional
from urllib.parse import quote_plus, urlencode

try:
    import requests
except ImportError:
    print("❌ 缺少 requests 库，请运行: pip install requests")
    sys.exit(1)

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.columns import Columns
    from rich.markdown import Markdown
    from rich import box
    from rich.prompt import Prompt, IntPrompt
    from rich.progress import Progress, SpinnerColumn, TextColumn
except ImportError:
    print("❌ 缺少 rich 库，请运行: pip install rich")
    sys.exit(1)

# ═══════════════════════════════════════════
#  配置
# ═══════════════════════════════════════════

GH_TOKEN = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
CACHE_DIR = os.path.join(os.path.dirname(__file__), ".cache")
os.makedirs(CACHE_DIR, exist_ok=True)
CACHE_TTL = 300  # 5分钟

console = Console()

# 语言分类（中文名 → GitHub 语言名）
LANG_CATEGORIES = {
    "python":       "Python",
    "javascript":   "JavaScript",
    "typescript":   "TypeScript",
    "rust":         "Rust",
    "go":           "Go",
    "java":         "Java",
    "c++":          "C++",
    "c":            "C",
    "c#":           "C#",
    "ruby":         "Ruby",
    "swift":        "Swift",
    "kotlin":       "Kotlin",
    "php":          "PHP",
    "lua":          "Lua",
    "zig":          "Zig",
    "r":            "R",
    "dart":         "Dart",
    "shell":        "Shell",
    "all":          None,
}

# 热门话题分类
TOPIC_CATEGORIES = {
    "ai-ml":          "AI/机器学习",
    "llm":            "LLM/大模型",
    "web":            "Web开发",
    "cli":            "命令行工具",
    "devops":         "DevOps",
    "database":       "数据库",
    "game":           "游戏开发",
    "mobile":         "移动开发",
    "security":       "安全",
    "blockchain":     "区块链/Web3",
    "data-science":   "数据科学",
    "frontend":       "前端",
    "backend":        "后端",
    "rust-wasm":      "Rust/WASM",
}

# ═══════════════════════════════════════════
#  数据模型
# ═══════════════════════════════════════════

@dataclass
class Repo:
    name: str              # owner/repo
    url: str
    description: str
    stars: int
    forks: int
    stars_today: int = 0
    language: str = ""
    topics: list = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""
    license_name: str = ""

    @property
    def owner(self) -> str:
        return self.name.split("/")[0] if "/" in self.name else ""

    @property
    def repo_name(self) -> str:
        return self.name.split("/")[1] if "/" in self.name else self.name

    @property
    def age_days(self) -> int:
        if not self.created_at:
            return 0
        try:
            created = datetime.fromisoformat(self.created_at.replace("Z", "+00:00"))
            return (datetime.now().astimezone() - created).days
        except:
            return 0

    @property
    def star_velocity(self) -> float:
        """日均获星数"""
        days = self.age_days
        return round(self.stars / days, 1) if days > 0 else self.stars


# ═══════════════════════════════════════════
#  GitHub API 封装
# ═══════════════════════════════════════════

class GitHubAPI:
    BASE = "https://api.github.com"
    TRENDING_URL = "https://github.com/trending"

    def __init__(self, token: Optional[str] = None):
        self.token = token
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "gh-hunter/1.0",
        })
        if token:
            self.session.headers["Authorization"] = f"token {token}"

    def _get(self, url: str, params: dict = None) -> dict:
        resp = self.session.get(url, params=params, timeout=15)
        if resp.status_code == 403:
            console.print("[yellow]⚠ API 限流了。设置 GH_TOKEN 环境变量可提升至 5000次/小时[/yellow]")
            if resp.headers.get("X-RateLimit-Remaining") == "0":
                reset = int(resp.headers.get("X-RateLimit-Reset", 0))
                wait = max(0, reset - time.time())
                console.print(f"[red]需等待 {int(wait)} 秒后重试[/red]")
                return {}
        if resp.status_code != 200:
            console.print(f"[red]API 错误 {resp.status_code}: {resp.text[:200]}[/red]")
            return {}
        return resp.json()

    def _search(self, query: str, sort: str = "stars", order: str = "desc", per_page: int = 25) -> list:
        """GitHub 搜索 API"""
        params = {"q": query, "sort": sort, "order": order, "per_page": min(per_page, 100)}
        data = self._get(f"{self.BASE}/search/repositories", params)
        items = data.get("items", [])
        results = []
        for item in items:
            results.append(Repo(
                name=item["full_name"],
                url=item["html_url"],
                description=item.get("description") or "",
                stars=item["stargazers_count"],
                forks=item["forks_count"],
                language=item.get("language") or "",
                topics=item.get("topics", []),
                created_at=item.get("created_at", ""),
                updated_at=item.get("updated_at", ""),
                license_name=item["license"]["spdx_id"] if item.get("license") else "",
            ))
        return results

    def trending(self, since: str = "daily", language: str = "") -> list:
        """爬取 GitHub Trending 页面（无 API）"""
        url = self.TRENDING_URL
        params = {"since": since}
        if language:
            params["spoken_language_code"] = ""  # 所有语言
            url = f"{self.TRENDING_URL}/{quote_plus(language)}"

        try:
            resp = self.session.get(url, params=params, timeout=15,
                                    headers={"Accept": "text/html"})
            if resp.status_code != 200:
                console.print(f"[red]Trending 页面请求失败: {resp.status_code}[/red]")
                return []

            html = resp.text
            repos = []

            # 解析 Trending 页面
            article_pattern = re.compile(
                r'<article[^>]*class="[^"]*Box-row[^"]*"[^>]*>.*?</article>',
                re.DOTALL
            )
            for article in article_pattern.findall(html):
                try:
                    # 仓库名
                    name_match = re.search(
                        r'<h2[^>]*>.*?<a[^>]*href="/([^"]+)"[^>]*>',
                        article, re.DOTALL
                    )
                    if not name_match:
                        continue
                    full_name = name_match.group(1).strip()

                    # 描述
                    desc_match = re.search(
                        r'<p[^>]*class="[^"]*col-9[^"]*"[^>]*>\s*(.*?)\s*</p>',
                        article, re.DOTALL
                    )
                    description = ""
                    if desc_match:
                        desc = desc_match.group(1)
                        description = re.sub(r'<[^>]+>', '', desc).strip()

                    # 星数
                    stars_match = re.search(
                        r'<a[^>]*href="/[^"]+/stargazers"[^>]*>\s*<svg[^>]*>.*?</svg>\s*([\d,]+)\s*',
                        article, re.DOTALL
                    )
                    stars = 0
                    if stars_match:
                        stars = int(stars_match.group(1).replace(",", ""))

                    # 今日新增星数
                    today_match = re.search(
                        r'<span[^>]*class="[^"]*d-inline-block[^"]*float-sm-right[^"]*"[^>]*>\s*[+]?([\d,]+)\s*',
                        article, re.DOTALL
                    )
                    stars_today = 0
                    if today_match:
                        stars_today = int(today_match.group(1).replace(",", ""))

                    # 语言
                    lang_match = re.search(
                        r'<span[^>]*itemprop="programmingLanguage"[^>]*>\s*(.*?)\s*</span>',
                        article, re.DOTALL
                    )
                    language_name = lang_match.group(1).strip() if lang_match else ""

                    # Fork
                    forks_match = re.search(
                        r'<a[^>]*href="/[^"]+/forks"[^>]*>\s*<svg[^>]*>.*?</svg>\s*([\d,]+)\s*',
                        article, re.DOTALL
                    )
                    forks = int(forks_match.group(1).replace(",", "")) if forks_match else 0

                    repos.append(Repo(
                        name=full_name,
                        url=f"https://github.com/{full_name}",
                        description=description,
                        stars=stars,
                        forks=forks,
                        stars_today=stars_today,
                        language=language_name,
                    ))
                except Exception:
                    continue

            return repos

        except requests.RequestException as e:
            console.print(f"[red]网络错误: {e}[/red]")
            return []

    def hot_by_language(self, language: str, per_page: int = 30) -> list:
        """按语言获取高星项目"""
        query = f"stars:>100"
        if language and language.lower() != "all":
            query += f" language:{language}"
        return self._search(query, sort="stars", per_page=per_page)

    def new_and_growing(self, min_stars: int = 50, per_page: int = 25) -> list:
        """新项目发现：近3个月创建、增速快的项目"""
        three_months_ago = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")
        query = f"created:>={three_months_ago} stars:>={min_stars}"
        return self._search(query, sort="stars", per_page=per_page)

    def by_topic(self, topic: str, per_page: int = 25) -> list:
        """按 topic 搜索"""
        query = f"topic:{topic} stars:>50"
        return self._search(query, sort="stars", per_page=per_page)

    def fast_rising(self, per_page: int = 25) -> list:
        """高速增长项目：近期 star 增速快"""
        last_month = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        query = f"pushed:>={last_month} stars:>500"
        return self._search(query, sort="stars", per_page=per_page)

    def repo_detail(self, full_name: str) -> Optional[Repo]:
        """获取单个仓库详情"""
        data = self._get(f"{self.BASE}/repos/{full_name}")
        if not data:
            return None
        return Repo(
            name=data["full_name"],
            url=data["html_url"],
            description=data.get("description") or "",
            stars=data["stargazers_count"],
            forks=data["forks_count"],
            language=data.get("language") or "",
            topics=data.get("topics", []),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            license_name=data["license"]["spdx_id"] if data.get("license") else "",
        )


# ═══════════════════════════════════════════
#  显示模块
# ═══════════════════════════════════════════

def format_number(n: int) -> str:
    """格式化数字：1.2k, 3.4w"""
    if n >= 10000:
        return f"{n/10000:.1f}w"
    elif n >= 1000:
        return f"{n/1000:.1f}k"
    return str(n)

def show_repos_table(repos: list, title: str, show_velocity: bool = False,
                     show_today: bool = False, lang_filter: str = None):
    """用 Rich 表格展示仓库列表"""
    if not repos:
        console.print("[yellow]没有找到结果[/yellow]")
        return

    # 过滤语言
    if lang_filter and lang_filter.lower() != "all":
        gh_lang = LANG_CATEGORIES.get(lang_filter.lower())
        if gh_lang:
            repos = [r for r in repos if r.language.lower() == gh_lang.lower()]
        if not repos:
            console.print(f"[yellow]语言 '{lang_filter}' 没有找到项目[/yellow]")
            return

    table = Table(
        title=f"🔥 {title}",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold cyan",
        title_style="bold yellow",
    )
    table.add_column("#", style="dim", width=4)
    table.add_column("项目", style="bold", no_wrap=True, max_width=40)
    table.add_column("⭐ Stars", justify="right", style="yellow")
    if show_today:
        table.add_column("📈 今日", justify="right", style="green")
    if show_velocity:
        table.add_column("⚡ 日均", justify="right", style="cyan")
    table.add_column("🔤 语言", style="magenta")
    table.add_column("📝 描述", max_width=50)

    for i, repo in enumerate(repos[:50], 1):
        desc = repo.description
        if len(desc) > 50:
            desc = desc[:47] + "..."

        row = [str(i), repo.name, format_number(repo.stars)]
        if show_today:
            row.append(f"+{format_number(repo.stars_today)}" if repo.stars_today else "-")
        if show_velocity:
            row.append(str(repo.star_velocity))
        row.append(repo.language or "N/A")
        row.append(desc)
        table.add_row(*row)

    console.print(table)
    console.print(f"[dim]共 {len(repos)} 个项目，显示前 {min(50, len(repos))} 个[/dim]")


def show_categories_menu(categories: dict, title: str = "分类") -> str:
    """显示分类菜单，返回用户选择"""
    console.print(f"\n[bold cyan]📂 {title}[/bold cyan]")
    items = list(categories.items())
    cols = Columns(expand=True)
    for i, (key, label) in enumerate(items, 1):
        cols.add(f"[bold]{i}.[/bold] {label}")
    console.print(cols)

    choice = IntPrompt.ask(
        f"\n请选择 (1-{len(items)})",
        default=1,
        choices=[str(i) for i in range(1, len(items) + 1)]
    )
    return list(categories.keys())[choice - 1]


def show_repo_detail(repo: Repo):
    """显示仓库详情"""
    if not repo:
        return

    info = Table(show_header=False, box=box.SIMPLE)
    info.add_column("属性", style="bold")
    info.add_column("值")

    info.add_row("📦 仓库", f"[link={repo.url}]{repo.name}[/link]")
    info.add_row("📝 描述", repo.description)
    info.add_row("⭐ Stars", format_number(repo.stars))
    info.add_row("⑂ Forks", format_number(repo.forks))
    info.add_row("🔤 语言", repo.language or "N/A")
    info.add_row("📜 许可证", repo.license_name or "N/A")
    info.add_row("📅 创建", repo.created_at[:10] if repo.created_at else "N/A")
    info.add_row("🔄 更新", repo.updated_at[:10] if repo.updated_at else "N/A")
    if repo.topics:
        info.add_row("🏷️ 标签", ", ".join(repo.topics[:10]))

    console.print(Panel(info, title=f"[bold cyan]{repo.name}[/bold cyan]"))


# ═══════════════════════════════════════════
#  功能模块
# ═══════════════════════════════════════════

def cmd_trending(api: GitHubAPI, args):
    """热搜排行榜"""
    since_map = {
        "1": "daily",
        "2": "weekly",
        "3": "monthly",
    }
    since_names = {"daily": "今日", "weekly": "本周", "monthly": "本月"}

    if args.since:
        since = args.since
    else:
        console.print("\n[bold cyan]📊 热搜排行榜 — 时间范围[/bold cyan]")
        console.print("1. [bold]今日[/bold] 🔥")
        console.print("2. [bold]本周[/bold]")
        console.print("3. [bold]本月[/bold]")
        choice = IntPrompt.ask("请选择", default=1, choices=["1", "2", "3"])
        since = since_map[str(choice)]

    language = args.language if args.language else ""
    if not language:
        # 可选语言过滤
        pass

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
    ) as progress:
        progress.add_task("正在获取 GitHub Trending...", total=None)
        repos = api.trending(since=since, language=language)

    if not repos:
        # Fallback: 用搜索 API
        console.print("[yellow]Trending 页面抓取失败，改用搜索 API...[/yellow]")
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            transient=True,
        ) as progress:
            progress.add_task("搜索中...", total=None)
            if since == "daily":
                date_filter = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
            elif since == "weekly":
                date_filter = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
            else:
                date_filter = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")
            query = f"pushed:>={date_filter} stars:>100"
            if language:
                query += f" language:{language}"
            repos = api._search(query, sort="stars", per_page=50)

    show_repos_table(repos, f"GitHub 热搜 — {since_names.get(since, since)}", show_today=True)

    if repos:
        console.print("\n[dim]输入编号查看详情，回车返回[/dim]")
        choice = Prompt.ask("查看详情", default="")
        if choice and choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(repos):
                show_repo_detail(repos[idx])
                open_choice = Prompt.ask("🌐 在浏览器中打开?", choices=["y", "n"], default="n")
                if open_choice == "y":
                    webbrowser.open(repos[idx].url)


def cmd_by_language(api: GitHubAPI, args):
    """按语言查看高星项目"""
    if args.language and args.language.lower() in LANG_CATEGORIES:
        lang_key = args.language.lower()
    else:
        lang_key = show_categories_menu(LANG_CATEGORIES, "编程语言")
    
    gh_lang = LANG_CATEGORIES[lang_key]
    label = gh_lang or "所有语言"
    lang_query_part = "" if gh_lang is None else gh_lang

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
    ) as progress:
        progress.add_task(f"正在搜索 {label} 高星项目...", total=None)
        repos = api.hot_by_language(lang_query_part)

    show_repos_table(repos, f"⭐ {label} 高星排行榜")

    if repos:
        console.print("\n[dim]输入编号查看详情，回车返回[/dim]")
        choice = Prompt.ask("查看详情", default="")
        if choice and choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(repos):
                show_repo_detail(repos[idx])


def cmd_by_topic(api: GitHubAPI, args):
    """按话题分类浏览"""
    if args.topic and args.topic.lower() in TOPIC_CATEGORIES:
        topic_key = args.topic.lower()
    else:
        topic_key = show_categories_menu(TOPIC_CATEGORIES, "技术话题")
    
    gh_topic = topic_key
    label = TOPIC_CATEGORIES[topic_key]

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
    ) as progress:
        progress.add_task(f"正在搜索 {label} 相关项目...", total=None)
        repos = api.by_topic(gh_topic)

    show_repos_table(repos, f"🏷️ {label} 精选项目")

    if repos:
        console.print("\n[dim]输入编号查看详情，回车返回[/dim]")
        choice = Prompt.ask("查看详情", default="")
        if choice and choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(repos):
                show_repo_detail(repos[idx])


def cmd_new_projects(api: GitHubAPI, args):
    """新项目发现"""
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
    ) as progress:
        progress.add_task("正在发现新项目...", total=None)
        repos = api.new_and_growing(min_stars=args.min_stars or 50)

    show_repos_table(repos, "🆕 近3个月新星项目", show_velocity=True)

    if repos:
        console.print("\n[dim]输入编号查看详情，回车返回[/dim]")
        choice = Prompt.ask("查看详情", default="")
        if choice and choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(repos):
                show_repo_detail(repos[idx])


def cmd_fast_rising(api: GitHubAPI, args):
    """高速增长"""
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
    ) as progress:
        progress.add_task("正在搜索高增速项目...", total=None)
        repos = api.fast_rising()

    show_repos_table(repos, "🚀 高速增长项目 (近30天有提交, >500星)")

    if repos:
        console.print("\n[dim]输入编号查看详情，回车返回[/dim]")
        choice = Prompt.ask("查看详情", default="")
        if choice and choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(repos):
                show_repo_detail(repos[idx])


def cmd_search(api: GitHubAPI, args):
    """搜索项目"""
    query = args.query
    if not query:
        query = Prompt.ask("🔍 输入搜索关键词")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
    ) as progress:
        progress.add_task(f"正在搜索 '{query}'...", total=None)
        repos = api._search(query, sort="stars")

    show_repos_table(repos, f"🔍 搜索结果: {query}")

    if repos:
        console.print("\n[dim]输入编号查看详情，回车返回[/dim]")
        choice = Prompt.ask("查看详情", default="")
        if choice and choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(repos):
                show_repo_detail(repos[idx])
                open_choice = Prompt.ask("🌐 在浏览器中打开?", choices=["y", "n"], default="n")
                if open_choice == "y":
                    webbrowser.open(repos[idx].url)


def cmd_detail(api: GitHubAPI, args):
    """查看仓库详情"""
    name = args.repo or Prompt.ask("📦 输入仓库名 (如: torvalds/linux)")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
    ) as progress:
        progress.add_task(f"正在获取 {name} 详情...", total=None)
        repo = api.repo_detail(name)

    if repo:
        show_repo_detail(repo)
        open_choice = Prompt.ask("🌐 在浏览器中打开?", choices=["y", "n"], default="n")
        if open_choice == "y":
            webbrowser.open(repo.url)
    else:
        console.print(f"[red]未找到仓库: {name}[/red]")


# ═══════════════════════════════════════════
#  交互模式
# ═══════════════════════════════════════════

def interactive_mode(api: GitHubAPI):
    """交互式菜单"""
    menu = """
[bold cyan]╔══════════════════════════════════════╗
║     🔭 GitHub 开源项目猎手            ║
╠══════════════════════════════════════╣
║  [/bold][bold yellow]1. 🔥 热搜排行榜[/bold cyan]               ║
║  [/bold][bold green]2. ⭐ 按语言查高星项目[/bold cyan]          ║
║  [/bold][bold blue]3. 🏷️ 按话题分类浏览[/bold cyan]            ║
║  [/bold][bold magenta]4. 🆕 新项目发现[/bold cyan]               ║
║  [/bold][bold cyan]5. 🚀 高速增长项目[/bold cyan]              ║
║  [/bold][bold yellow]6. 🔍 搜索项目[/bold cyan]                  ║
║  [/bold][bold white]7. 📦 查看仓库详情[/bold cyan]              ║
║  [/bold][bold red]0. 退出[/bold cyan]                        ║
╚══════════════════════════════════════╝
    """

    while True:
        console.print(menu)
        choice = Prompt.ask("请选择", choices=["0", "1", "2", "3", "4", "5", "6", "7"], default="1")

        if choice == "0":
            console.print("[bold green]👋 再见！[/bold green]")
            break
        elif choice == "1":
            cmd_trending(api, argparse.Namespace(since=None, language=""))
        elif choice == "2":
            cmd_by_language(api, argparse.Namespace(language=""))
        elif choice == "3":
            cmd_by_topic(api, argparse.Namespace(topic=""))
        elif choice == "4":
            cmd_new_projects(api, argparse.Namespace(min_stars=50))
        elif choice == "5":
            cmd_fast_rising(api, argparse.Namespace())
        elif choice == "6":
            cmd_search(api, argparse.Namespace(query=""))
        elif choice == "7":
            cmd_detail(api, argparse.Namespace(repo=""))


# ═══════════════════════════════════════════
#  主入口
# ═══════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        prog="gh-hunter",
        description="🔭 GitHub 开源项目猎手 — 热搜排行榜 · 高星分类 · 新项目发现",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("-i", "--interactive", action="store_true",
                        help="交互模式（默认有子命令时执行子命令，无子命令时进入交互模式）")

    sub = parser.add_subparsers(dest="command", help="子命令")

    # trending
    p = sub.add_parser("trending", aliases=["t", "hot"], help="🔥 热搜排行榜")
    p.add_argument("--since", choices=["daily", "weekly", "monthly"], help="时间范围")
    p.add_argument("--language", "-l", help="语言过滤")

    # by-language
    p = sub.add_parser("language", aliases=["lang", "l"], help="⭐ 按语言查高星项目")
    p.add_argument("language", nargs="?", help=f"语言 ({', '.join(LANG_CATEGORIES.keys())})")

    # by-topic
    p = sub.add_parser("topic", aliases=["cat"], help="🏷️ 按话题分类")
    p.add_argument("topic", nargs="?", help=f"话题 ({', '.join(TOPIC_CATEGORIES.keys())})")

    # new
    p = sub.add_parser("new", aliases=["fresh"], help="🆕 发现新项目")
    p.add_argument("--min-stars", type=int, default=50, help="最低星数 (默认50)")

    # rising
    p = sub.add_parser("rising", aliases=["fast", "r"], help="🚀 高速增长项目")

    # search
    p = sub.add_parser("search", aliases=["s", "find"], help="🔍 搜索项目")
    p.add_argument("query", nargs="*", help="搜索关键词")

    # detail
    p = sub.add_parser("detail", aliases=["info", "d"], help="📦 查看仓库详情")
    p.add_argument("repo", nargs="?", help="仓库名 (如: torvalds/linux)")

    args = parser.parse_args()
    api = GitHubAPI(token=GH_TOKEN)

    if args.command or args.interactive:
        # 有子命令
        if args.command == "trending" or args.command in ("t", "hot"):
            cmd_trending(api, args)
        elif args.command == "language" or args.command in ("lang", "l"):
            cmd_by_language(api, args)
        elif args.command == "topic" or args.command in ("cat",):
            cmd_by_topic(api, args)
        elif args.command == "new" or args.command in ("fresh",):
            cmd_new_projects(api, args)
        elif args.command == "rising" or args.command in ("fast", "r"):
            cmd_fast_rising(api, args)
        elif args.command == "search" or args.command in ("s", "find"):
            if args.query:
                args.query = " ".join(args.query)
            cmd_search(api, args)
        elif args.command == "detail" or args.command in ("info", "d"):
            cmd_detail(api, args)
        elif not args.command:
            interactive_mode(api)
    else:
        # 无子命令 → 交互模式
        interactive_mode(api)


if __name__ == "__main__":
    main()