# 🔭 gh-hunter — GitHub 开源项目猎手

> 热搜排行榜 · 高星分类 · 新项目发现 · 全中文终端体验

## 截图预览

```
🔥 GitHub 热搜 — 今日
┌──────┬──────────────────────────────┬───────────┬──────────┬──────────┬──────────────────────────────────────────────────────┐
│ #    │ 项目                         │ ⭐ Stars  │ 📈 今日  │ 🔤 语言  │ 📝 描述                                              │
├──────┼──────────────────────────────┼───────────┼──────────┼──────────┼──────────────────────────────────────────────────────┤
│  1   │ deepseek-ai/DeepSeek-V3      │ 98.2k     │ +1.2k    │ Python   │ DeepSeek-V3: A powerful open-source LLM...            │
│  2   │ shadcn-ui/ui                 │ 82.5k     │ +890     │ TypeScript│ Beautifully designed components...                     │
│  ...                                                                    │
└──────┴──────────────────────────────┴───────────┴──────────┴──────────┴──────────────────────────────────────────────────────┘
```

## 安装

```bash
# 1. 克隆或下载
git clone https://github.com/yourname/gh-hunter.git
cd gh-hunter

# 2. 安装依赖
pip install -r requirements.txt

# 3. （可选）设置 GitHub Token 提升 API 限额
# 访问 https://github.com/settings/tokens 生成
export GH_TOKEN="ghp_xxxxx"
```

## 使用

### 交互模式（推荐）

```bash
python gh_hunter.py
```

### 命令行模式

```bash
# 🔥 热搜排行榜
python gh_hunter.py trending                     # 交互式选择时间
python gh_hunter.py trending --since daily        # 今日热搜
python gh_hunter.py trending --since weekly       # 本周热搜
python gh_hunter.py trending --since monthly      # 本月热搜

# ⭐ 按语言查高星项目
python gh_hunter.py language python               # Python 高星
python gh_hunter.py language rust                 # Rust 高星
python gh_hunter.py language                      # 菜单选择

# 🏷️ 按话题分类
python gh_hunter.py topic ai-ml                   # AI/ML 项目
python gh_hunter.py topic web                     # Web 开发

# 🆕 新项目发现（近3个月创建）
python gh_hunter.py new
python gh_hunter.py new --min-stars 100

# 🚀 高速增长项目
python gh_hunter.py rising

# 🔍 搜索
python gh_hunter.py search "RAG framework"
python gh_hunter.py search "stable diffusion"

# 📦 查看仓库详情
python gh_hunter.py detail torvalds/linux
python gh_hunter.py detail deepseek-ai/DeepSeek-V3
```

### 别名

```
trending  → t, hot
language  → lang, l
topic     → cat
new       → fresh
rising    → fast, r
search    → s, find
detail    → info, d
```

## 功能

| 功能 | 说明 |
|------|------|
| 🔥 热搜排行榜 | 今日/本周/本月 GitHub Trending |
| ⭐ 按语言分类 | Python/JS/Rust/Go 等 18 种语言 |
| 🏷️ 按话题分类 | AI/LLM/Web/DevOps 等 14 个话题 |
| 🆕 新项目发现 | 近3个月创建的高星新项目 |
| 🚀 高速增长 | 近期活跃的高增速项目 |
| 🔍 搜索 | 全 GitHub 搜索 |
| 📦 仓库详情 | 查看仓库完整信息，一键浏览器打开 |
| 🌐 中文界面 | 全中文终端输出 |

## 环境变量

| 变量 | 说明 |
|------|------|
| `GH_TOKEN` / `GITHUB_TOKEN` | GitHub Personal Access Token（无 token 时 60次/小时，有 token 5000次/小时） |