---
name: open-source-research
description: 拿到 PRD 后，在 GitHub、CNB(cnb.cool)、Gitee 三个开源平台检索同类项目，产出功能与业务流程对照材料（Markdown + HTML 可视化），并按项目复杂度派生一份开发指引型 skill 或 skill 包。触发场景：需求分析完成、拿到 PRD、想找开源参考、开源对标调研、竞品开源项目调研、"找个类似项目参考一下"、"造轮子前先看看有没有现成的"。
agent_created: true
---

# PRD 开源对标与开发指引派生

## 目的

在需求分析产出 PRD 之后，用三平台开源检索回答三个问题：
**别人做过吗？做到什么程度？我们该抄什么、改什么、自己造什么？**
最终产出可交付的对照材料，并按需将其固化成一份可复用的开发指引 skill。

## 何时使用

- 需求分析完成、PRD 已产出（含 `pm-requirement-analysis__skillhub` 生成的 `PRD.md`）
- 用户问"有没有类似的开源项目"、"先看看别人怎么做的"、"造轮子前先调研一下"
- 用户明确要求在 GitHub / CNB / Gitee 上找参考项目并做对照

## 输入

一份 PRD 文件路径。未指定时，在当前工作区查找 `PRD.md` / `docs/PRD.md` / `需求文档*.md`；
找不到就向用户索要路径，不要凭空开始。

## 输出目录约定

统一输出到 `./oss-benchmark/<项目名>/`：
```
oss-benchmark/<项目名>/
├── benchmark.md          # 对照报告（Markdown）
├── benchmark.html        # 可视化页面
└── raw/                  # 检索与分析原始 JSON，便于复核
    ├── search-*.json
    └── repo-*.json
```

## 执行流程

### 阶段 0｜前置确认（不要跳）

1. 读取 PRD，确认已理解业务领域、核心实体、核心流程。
   PRD 太粗（抽不出 ≥3 条核心流程）就先要求补充，不要硬检索。
2. 检查凭证（脚本自动读取技能目录下的 `.env`，无需 source；首次使用 `cp env.sample .env`）：
   ```bash
   gh auth status                                   # GitHub：已登录则无需处理
   python3 <skill>/scripts/search_oss.py -q "<一个试探词>" --limit 1 --platforms cnb,gitee
   ```
   输出 `needs_token` 表示缺凭证，走网页兜底；不要停下来向用户索要 token，先跑完整个流程。
3. **自主完成复杂度定级**（L1/L2/L3，判据见 `references/skill-derivation.md`），不要为此打断用户。
   用户未另行指定时，默认派生位置与调用技能的存放层级保持一致
   （本技能在用户级则派生到用户级，在项目级则派生到项目级）。

### 阶段 1｜抽取检索输入

从 PRD 抽出三组内容，写入 `raw/keywords.json`：
- **中英关键词各一组**（中文打 Gitee/CNB，英文打 GitHub）
- **核心实体清单**（名词）
- **核心业务流程清单**（动词 + 流程名）

### 阶段 2｜三平台检索

```bash
python3 <skill>/scripts/search_oss.py \
  -q "<英文关键词>" --keywords "<补充词1,补充词2>" \
  --limit 10 --lang <语言> --min-stars 100 \
  --out oss-benchmark/<项目名>/raw/search-1.json
```

- GitHub 优先复用已登录的 `gh` CLI；CNB/Gitee 有 token 走 API，无 token 自动判定 `needs_token`。
- **CNB 和 Gitee 绝不能因为缺 token 就跳过**——脚本输出的 `pending_web_fallback` 里的
  queries 必须用 WebSearch / WebFetch 补齐，并把结果合并进 JSON。
- 多轮检索：换关键词再跑 2~3 轮，覆盖不同侧面（按领域 / 按技术栈 / 按具体流程名）。
- 平台端点、认证、字段、实测坑与兜底策略见 `references/platform-search.md`。

### 阶段 3｜候选筛选与深度分析

1. 按 `references/comparison-method.md` 的三维打分（相关度 / 活跃度 / 完整度）筛出 3~8 条；
   总分 ≥10 且无硬否决项才进入深度分析。
2. 对入选项目抓骨架：
   ```bash
   python3 <skill>/scripts/fetch_repo.py <url> \
     --tree-depth 2 --grep "<业务关键词1,关键词2>" \
     --out oss-benchmark/<项目名>/raw/repo-<name>.json
   ```
   脚本内置 git clone → 归档包双通道降级，代理环境下也可用。
3. 深度分析读：README、目录树、依赖清单、`keyword_hits` 指向的业务模块文件。
   目标是搞清**业务流程与数据模型**，不是通读代码。

### 阶段 4｜产出对照材料

1. 复制 `assets/benchmark-report-template.md` → `benchmark.md`，
   按 `references/comparison-method.md` 填写。
2. 复制 `assets/benchmark-report-template.html` → `benchmark.html`，
   **只改页面底部 `DATA` 对象**即可渲染。
3. 必须包含的六块内容：功能对照矩阵、业务流程对照（含异常分支）、数据模型对照、
   差距分析三级分类、**建议补充到 PRD 的具体条款**、License 合规判定。
4. 完成后用 `present_files` 同时呈现 MD 与 HTML。

### 阶段 5｜派生开发指引 skill（直接执行，不要请示）

按 `references/skill-derivation.md` **自行判断并执行**，不要为了定级、命名、存放位置去打断用户：
- **L1**：不建 skill，SOP 写进报告第 8 节即可。
- **L2 / L3**：直接派生 `<领域>-dev-guide` skill 包。
  - 命名：`<领域英文>-dev-guide`，全小写连字符。
  - 存放位置：与调用本技能的层级保持一致（用户级调用 → `~/.workbuddy/skills/`；
    项目级调用 → `./.workbuddy/skills/`）。用户另有指定时以用户为准。
- **执行完后汇报**：定级结论、skill 名称、存放路径、包含的 references 清单。
  用户不满意再改，不要事前反复确认。

## 硬性纪律

- **禁止无源断言**：每条结论必须能追溯到 `仓库 → 文件路径/章节`。写不出来源就标"待确认"。
- **异常分支优先**：开源项目真正的价值在异常分支，happy path 自家 PRD 通常已有。
- **star 不是相关性**：高 star 无关项目必须剔除（GitHub 搜索常见）。
- **License 必须判定**：AGPL/GPL 只提炼思路不搬代码，并在产物中写明。
- **不要为了流程问题打断用户**：定级、命名、存放位置、是否派生 skill 一律自行决策、
  执行完统一汇报。只有两种情况才提问——PRD 缺关键信息、用户主动给出新约束。

## 文件索引

| 文件 | 用途 |
|---|---|
| `scripts/search_oss.py` | 三平台检索，分层降级，输出归一化 JSON |
| `scripts/fetch_repo.py` | 仓库骨架抓取（git/归档双通道）+ 技术栈推断 + 关键词定位 |
| `references/platform-search.md` | 三平台端点、认证、字段、实测坑、兜底策略 |
| `references/comparison-method.md` | 打分模型、对照矩阵图例、流程对照四要素、差距三级分类 |
| `references/skill-derivation.md` | 复杂度分级、派生 skill 骨架、抽取规则、验收 checklist |
| `assets/benchmark-report-template.md` | Markdown 报告模板 |
| `assets/benchmark-report-template.html` | HTML 可视化模板（只改 `DATA` 对象） |
| `env.sample` | 平台凭证模板；复制为 `.env` 后填写，`.env` 已被 gitignore |

## 常见坑

- CNB 全部 API 要求 Bearer 认证，无 token 一律 401；Gitee 匿名搜索返回 **HTTP 200 + 空数组**，
  两者都极易被误判成"该平台没有相关项目"。
- 代理环境下 `git clone` 可能报 `Empty reply from server`，必须走归档包降级（脚本已内置）。
- Gitee 走代理响应约 10 秒，超时不要设太小。
- 一次建多个 skill 是错的：L3 项目也是**一个** skill 包，靠 `references/` 拆分。
