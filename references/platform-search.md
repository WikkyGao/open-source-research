# 三平台检索通道手册（GitHub / CNB / Gitee）

本文件记录三个平台的**真实可用性与调用细节**（2026-09 实测），并给出降级策略。
直接按本文件执行，不要凭印象猜接口。

## 一、通道总览

| 平台 | API Base | 认证要求 | 无凭证时表现 | 推荐通道 |
|---|---|---|---|---|
| GitHub | `api.github.com` | 可匿名；有 token 配额更高 | 匿名可用（10 次/分钟） | `gh api`（复用已登录 CLI）→ 匿名 API |
| CNB | `api.cnb.cool` | **必须** Bearer token | **401**，全部接口拒绝 | API（有 token）→ 网页搜索兜底 |
| Gitee | `gitee.com/api/v5` | 仓库搜索需 token | HTTP 200 但返回 `[]` | API（有 token）→ 网页搜索兜底 |

关键判断：**没有 token 不代表没有结果，必须走兜底，不能跳过 CNB 和 Gitee。**

## 二、GitHub

- 优先用 `gh api`（本机 `gh` 已登录账号 WikkyGao，配额 5000 次/小时）：
  ```bash
  gh api "search/repositories?q=<urlencoded>&sort=stars&order=desc&per_page=20"
  ```
- 无 `gh` 时退回匿名 API：
  ```bash
  curl -s "https://api.github.com/search/repositories?q=..." -H "Accept: application/vnd.github+json"
  ```
- 搜索语法加成（写进 q 里能显著提高信噪比）：
  - `language:dart` / `language:java` / `language:go`
  - `stars:>200`、`pushed:>2024-01-01`
  - `in:name,description,readme <关键词>`
- **坑**：GitHub 搜索按 star 排序时会混入高 star 但无关的项目（实测搜 "flutter erp" 会返回一个 2 万 star 的书籍收藏仓库）。
  **star 只作为排序参考，不能作为相关性依据**，必须逐个读 description 人工判相关性。

## 三、CNB（cnb.cool）

- API Base：`https://api.cnb.cool`，Swagger：`https://api.cnb.cool/swagger.json`（可公开拉取，无需认证）
- 认证 Header：
  ```
  Authorization: Bearer ${CNB_TOKEN}
  Accept: application/vnd.cnb.api+json
  ```
- 令牌创建：cnb.cool → 设置 → 访问令牌，需勾选 `repo-basic-info:r` 权限
- 公开仓库搜索端点：
  ```
  GET /search/public-repos?key=<关键词>&order_by=stars&desc=true&topN=20
  ```
  `order_by` 可选：`created_at` / `last_updated_at` / `stars` / `forks`；`topN` 最大 100
- 返回字段（用于归一化）：`path`（slug）、`web_url`、`description`、`star_count`、
  `fork_count`、`language`、`license`、`last_updated_at`、`topics`、`open_issue_count`
- 无 token 时的兜底：
  - WebSearch：`site:cnb.cool <关键词>`、`cnb.cool 开源 <关键词>`
  - WebFetch 直接抓 `https://cnb.cool/<slug>` 仓库页
- 归档下载（分析与克隆都可用）：`https://cnb.cool/<slug>/-/archive/<branch>/<name>.tar.gz`
- **坑**：CNB 上大量仓库是「知识库 / NPC / Skills」类型，搜到后用 `flags` 字段或仓库页面判断，别把文档仓库当业务系统对标。

## 四、Gitee

- API：`https://gitee.com/api/v5/search/repositories?q=<kw>&access_token=<token>&sort=stars_count&order=desc&per_page=20`
- 令牌：Gitee → 设置 → 私人令牌
- **坑 1**：匿名调用返回 **HTTP 200 + 空数组 `[]`**，看起来像"搜不到"，实际是未登录。
  脚本里已用这个特征判定为 `needs_token`，不要误判为"该平台没有相关项目"。
- **坑 2**：走代理时响应慢（实测约 10 秒），超时不要设低于 20 秒。
- 无 token 兜底：
  - WebSearch：`site:gitee.com <关键词>`、`码云 开源项目 <关键词>`、`gitee 开源 <关键词>`
  - WebFetch 抓 `https://gitee.com/<slug>` 项目页
- 归档下载：`https://gitee.com/<slug>/repository/archive/<branch>.zip`
- **坑 3**：Gitee 上大量项目是高校/培训机构的教学 demo，star 虚高但无生产价值，
  判活要看最近提交时间与 issue 处理情况。

## 五、本地 git 通道的坑（重要）

公司代理 / 沙箱环境可能拦截 git 协议，表现为：
```
fatal: unable to access 'https://github.com/xxx.git/': Empty reply from server
```
`scripts/fetch_repo.py` 已内置双通道：
1. 先试 `git clone --depth 1`
2. 失败自动改用归档包下载（GitHub 走 codeload、CNB 走 /-/archive、Gitee 走 repository/archive）

实测：同一环境下 `cnb.cool` 的 git clone 能通而 `github.com` 不通，所以**必须保留双通道**，
不要因为某一平台 git 失败就判定整体不可达。

## 六、Token 配置（推荐用文件，一劳永逸）

### 方式一：token 文件（推荐）

在**技能目录下**创建 `.env`（权限 600），直接复制随技能自带的模板：

```bash
cp env.sample .env
chmod 600 .env
# 然后编辑 .env 填入真实值
```

文件格式：

```bash
# GitHub：可选，gh CLI 已登录时不需要
GITHUB_TOKEN=<GitHub PAT>

# CNB：https://cnb.cool → 设置 → 访问令牌（权限勾选 repo-basic-info:r）
CNB_TOKEN=<CNB 访问令牌>

# Gitee：https://gitee.com → 设置 → 私人令牌（权限勾选 projects）
GITEE_TOKEN=<Gitee 私人令牌>
```

`scripts/search_oss.py` 启动时自动读取，规则：
- 搜索顺序：`--token-file` → **技能目录 `.env`** → `~/.workbuddy/oss-tokens.env` → `~/.config/open-source-research/tokens.env`
- `.env` 已被 `.gitignore` 忽略，**绝不会提交**；`env.sample` 是模板，始终提交
- **已存在的环境变量优先**，不会被文件覆盖（方便临时用别的账号）
- 支持 `export` 前缀、引号包裹、`#` 注释
- 含占位符标记（`{{`、`<你的`、`<your`）的值视为未配置，不会把模板占位符当 token 发出去
- 加载成功会在 stderr 打印 `[凭证] 已从 <路径> 加载 <KEY>`

### 方式二：临时环境变量

```bash
export CNB_TOKEN="<cnb 访问令牌>"
export GITEE_TOKEN="<gitee 私人令牌>"
export GITHUB_TOKEN="<github pat>"   # gh 已登录时可省略
```

### 未配置时怎么办

**照常跑完整流程**，CNB/Gitee 走网页兜底，不要因为缺 token 停下来向用户索要。
首次运行时提示一次「`cp env.sample .env` 填入平台令牌可提升检索质量」即可。

### 打包分发前

`.env` 不进 git，但 `package_skill.py` 会把目录内所有文件打进 zip。
**打包前确认 `.env` 不含真实 token**，否则令牌会随 zip 泄露。

## 七、检索质量自检

跑完检索后逐条确认：
- [ ] 三个平台都跑过，没有因为缺 token 就跳过 CNB / Gitee
- [ ] 每条候选都读过 description，剔除高 star 无关项目
- [ ] 候选数量：每平台 3~8 条，总计不超过 15 条（超过说明关键词太泛）
- [ ] 至少 3 条候选进入深度分析（README + 目录树）
