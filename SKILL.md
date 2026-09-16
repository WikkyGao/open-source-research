---
name: open-source-research
slug: open-source-research
version: 1.0.0
displayName: PRD 开源对标与技能派生
description: 拿到 PRD 后，在 GitHub、CNB(cnb.cool)、Gitee 三个开源平台检索同类项目，产出功能与业务流程对照材料（Markdown + HTML 可视化），按项目复杂度派生一份开发指引型 skill 或 skill 包；用户确认后也可按技能转化方式把确认的开源项目转成单文件参考 skill。触发场景：需求分析完成、拿到 PRD、想找开源参考、开源对标调研、竞品开源项目调研、"找个类似项目参考一下"、"造轮子前先看看有没有现成的"、"把这个开源项目转成 skill"。
agent_created: true
---

# PRD 开源对标与开发指引派生

## 目的

在需求分析产出 PRD 之后，用三平台开源检索回答三个问题：
**别人做过吗？做到什么程度？我们该参考什么、改什么、自己造什么？**
最终产出可交付的对照材料，并按需将其固化成一份可复用的开发指引 skill。

## 何时使用

- 需求分析完成、PRD 已产出（含 `pm-requirement-analysis__skillhub` 生成的 `PRD.md`）
- 用户问"有没有类似的开源项目"、"先看看别人怎么做的"、"造轮子前先调研一下"
- 用户明确要求在 GitHub / CNB / Gitee 上找参考项目并做对照
- 想把调研中确认的开源项目转成 skill，方便后续随时参考（技能转化）

## 输入

一份 PRD 文件路径，或一段用户需求描述。按以下顺序获取：

1. **用户已给出 PRD 路径**：直接使用。
2. **未指定路径**：在当前工作区查找 `PRD.md` / `docs/PRD.md` / `需求文档*.md`，找到即用。
3. **都没有**：**根据用户提问中的内容（需求描述、目标场景、期望功能）现场整理一份 PRD 草稿**
   （至少包含：背景与目标、核心功能清单、核心业务流程、关键实体、非功能性约束），
   **呈现给用户确认或补充**，确认后作为本流程的 PRD 依据再开始检索。
   除非用户明确说"不用确认直接跑"，否则不要跳过这一步——PRD 是后续对标分析的锚点，
   凭猜测检索会浪费整轮调研。

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

   > 下文命令中的 `<skill>` 一律指本 skill 的安装目录（即本 SKILL.md 所在目录）。

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
- **降级路径**：三平台 + 网页兜底全部跑完后，有效候选仍不足 3 条时——
  1. 先换检索面（放宽 `--min-stars`、去掉 `--lang`、改用核心流程名的中英文各检索一轮）；
  2. 仍不足则改判据：按 `references/comparison-method.md` 打分照常执行，深度分析对象
     放宽到得分最高且无硬否决项的 1~2 条（宁少勿编）；
  3. 一条都没有时，在报告里如实写明"未检索到同类开源项目，属自研空白"，直接进入
     阶段 4 产出差距分析（C 类自研难点为主），不要为了凑数把无关项目标成相关。

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

### 阶段 4.5｜用户确认候选项目（技能转化入口）

对照报告呈现后，问用户一句：**"有没有想把某个候选项目转成 skill 留作参考的？"**

- 用户点名了项目（一个或多个）→ 对每个项目执行**阶段 5 的 B 路线（技能转化）**。
- 用户没点名 → 跳过 B 路线，直接走阶段 5 的 A 路线（按复杂度派生开发指引）。
- 不要跳过确认：B 路线产物会引导 agent 使用别人的项目，不经用户确认就生成属于越界。

### 阶段 5｜派生 skill（A/B 两条路线）

#### A 路线｜开发指引 skill（默认，直接执行，不要请示）

按 `references/skill-derivation.md` **自行判断并执行**，不要为了定级、命名、存放位置去打断用户：

- **L1**：不建 skill，SOP 写进报告第 8 节即可。
- **L2 / L3**：直接派生 `<领域>-dev-guide` skill 包。
  - 命名：`<领域英文>-dev-guide`，全小写连字符。
  - 存放位置：**不硬编码目录，跟随调用本技能的 agent 自己的 skill 规则**——
    该 agent 的 skills 放在哪个目录、用哪种装载机制，派生 skill 就放到哪里
    （如项目级 `./<agent的skills目录>/<名称>/`，用户级则放到对应的用户级目录）。
    查不清楚或用户另有指定时，以用户指定的路径为准，并在汇报里写明实际位置。
- **执行完后汇报**：定级结论、skill 名称、存放路径、包含的 references 清单。
  用户不满意再改，不要事前反复确认。

#### B 路线｜技能转化（仅在阶段 4.5 用户确认后执行）

把用户确认的开源项目转成**单文件参考 skill**，完整流程（输入识别、镜像轮换、
数据抓取、分析、生成、存放询问、写入）严格按 `references/技能转化.md` 执行。
要点：

- **产物形态**：一个目录只放一个 `SKILL.md`，含全部章节（快速上手/概述/功能/安装/
  使用/API/配置/开发/排错/资源），不拆 references/。与 A 路线的拆分骨架是两种不同产物，
  用户点名"转成 skill"时指的就是这种。
- **frontmatter**：按技能转化规范带 `source`（来源仓库 URL）、`platform`、`tags`、
  `generated` 字段，保留溯源。
- **素材复用**：该项目在阶段 3 已抓过骨架（`raw/repo-<name>.json`），直接复用，
  缺什么（如 README 全文、docs/）再按技能转化的抓取步骤补齐，不要重复 clone。
- **存放位置**：按技能转化流程**询问用户**三选一（项目本地 / 用户全局 /
  当前 agent 的 skills 目录），与 A 路线"不问用户"的规则不同——B 路线本来就以用户确认为前提。
- **License 红线不变**：AGPL/GPL 项目只提炼思路与用法，SKILL.md 内不得搬运其源码片段。
- **汇报**：skill 名称、来源仓库、存放路径、章节清单。

## 硬性纪律

- **禁止无源断言**：每条结论必须能追溯到 `仓库 → 文件路径/章节`。写不出来源就标"待确认"。
- **异常分支优先**：开源项目真正的价值在异常分支，happy path 自家 PRD 通常已有。
- **star 不是相关性**：高 star 无关项目必须剔除（GitHub 搜索常见）。
- **License 必须判定**：AGPL/GPL 只提炼思路不搬代码，并在产物中写明。
- **不要为了流程问题打断用户**：定级、命名、存放位置、是否派生 skill（A 路线）一律
  自行决策、执行完统一汇报。只有三种情况才提问——PRD 缺关键信息、用户主动给出新约束、
  阶段 4.5 确认是否要把候选项目转成 skill（B 路线的前提）。

## 文件索引

| 文件                                      | 用途                                        |
| --------------------------------------- | ----------------------------------------- |
| `scripts/search_oss.py`                 | 三平台检索，分层降级，输出归一化 JSON                     |
| `scripts/fetch_repo.py`                 | 仓库骨架抓取（git/归档双通道）+ 技术栈推断 + 关键词定位          |
| `references/platform-search.md`         | 三平台端点、认证、字段、实测坑、兜底策略                      |
| `references/comparison-method.md`       | 打分模型、对照矩阵图例、流程对照四要素、差距三级分类                |
| `references/skill-derivation.md`        | 复杂度分级、派生 skill 骨架、抽取规则、验收 checklist       |
| `references/技能转化.md`                 | 技能转化执行手册；B 路线（用户确认后把开源项目转成单文件参考 skill） |
| `assets/benchmark-report-template.md`   | Markdown 报告模板                             |
| `assets/benchmark-report-template.html` | HTML 可视化模板（只改 `DATA` 对象）                  |
| `env.sample`                            | 平台凭证模板；复制为 `.env` 后填写，`.env` 已被 gitignore |

## 常见坑

- CNB 全部 API 要求 Bearer 认证，无 token 一律 401；Gitee 匿名搜索返回 **HTTP 200 + 空数组**，
  两者都极易被误判成"该平台没有相关项目"。
- 代理环境下 `git clone` 可能报 `Empty reply from server`，必须走归档包降级（脚本已内置）。
- Gitee 走代理响应约 10 秒，超时不要设太小。
- 一次建多个 skill 是错的：L3 项目也是**一个** skill 包，靠 `references/` 拆分。
