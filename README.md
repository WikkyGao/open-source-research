# open-source-research

> PRD 开源对标与开发指引派生 skill —— 造轮子之前，先看看别人怎么做的。

## 这是什么

拿到 PRD 之后，在 **GitHub、CNB（cnb.cool）、Gitee** 三个开源平台检索同类项目，回答三个问题：

**别人做过吗？做到什么程度？我们该参考什么、改什么、自己造什么？**

最终产出可交付的功能与业务流程对照材料（Markdown + HTML 可视化），并按需固化为可复用的开发指引 skill。

## 核心能力

- **三平台检索**：GitHub 复用已登录 `gh` CLI；CNB / Gitee 有 token 走 API，无 token 自动降级为网页兜底，绝不因缺凭证跳过平台
- **候选打分筛选**：相关度 / 活跃度 / 完整度三维打分（≥10 分且无硬否决项才进入深度分析），剔除高 star 无关项目
- **仓库骨架抓取**：`git clone` → 归档包双通道自动降级，代理/沙箱环境也可用；只抽目录树、README、依赖、关键词命中文件，不把整仓读进上下文
- **深度对照**：功能对照矩阵、业务流程四要素对照（触发条件 / 参与角色 / 状态流转 / 异常分支）、数据模型对照、差距三级分类
- **License 合规判定**：AGPL/GPL 只提炼思路不搬代码，每条结论可溯源到 `仓库 → 文件路径`
- **两条派生路线**：
  - **A 路线（默认）**：按复杂度 L1/L2/L3 自主定级，派生 `<领域>-dev-guide` 开发指引 skill 包
  - **B 路线（技能转化）**：用户确认后，把指定开源项目转成单文件参考 skill（含 source / platform / tags 溯源字段）

## 何时使用

- 需求分析完成、PRD 已产出，想找开源参考
- 开源对标调研、竞品开源项目调研
- "找个类似项目参考一下"、"造轮子前先看看有没有现成的"
- "把这个开源项目转成 skill"

## 安装

把本目录放入你的 agent 的 skills 目录（项目级或用户级均可）：

```bash
git clone https://github.com/WikkyGao/open-source-research.git <你的skills目录>/open-source-research
```

### 配置平台凭证（可选，推荐）

```bash
cd <你的skills目录>/open-source-research
cp env.sample .env
chmod 600 .env   # 然后编辑填入真实令牌
```

| 平台 | 变量 | 获取方式 |
|---|---|---|
| GitHub | `GITHUB_TOKEN` | 可选，`gh` CLI 已登录时不需要 |
| CNB | `CNB_TOKEN` | cnb.cool → 设置 → 访问令牌，勾选 `repo-basic-info:r` |
| Gitee | `GITEE_TOKEN` | gitee.com → 设置 → 私人令牌，勾选 `projects` |

`.env` 已被 `.gitignore` 忽略，不会提交。**未配置也能跑完整流程**——CNB/Gitee 自动走网页检索兜底。

## 使用

向你的 agent 说一句话即可，例如：

```
PRD 在 docs/PRD.md，帮我做个开源对标调研
```

流程会依次执行：

1. **前置确认**：读取 PRD，检查凭证，自主完成复杂度定级（不打断你）
2. **抽取检索输入**：中英关键词、核心实体、核心业务流程
3. **三平台检索**：多轮检索 + 网页兜底，原始结果存 `raw/` 便于复核
4. **候选筛选与深度分析**：打分筛 3~8 条，抓骨架分析业务流程与数据模型
5. **产出对照报告**：`benchmark.md` + `benchmark.html`，含六块必填内容
6. **确认与派生**：问你是否要把某候选项目转成参考 skill（B 路线）；否则按复杂度派生开发指引（A 路线）

输出目录约定：

```
oss-benchmark/<项目名>/
├── benchmark.md          # 对照报告
├── benchmark.html        # 可视化页面
└── raw/                  # 检索与分析原始 JSON
```

## 目录结构

```
open-source-research/
├── SKILL.md                                # 技能主文件：执行流程与硬性纪律
├── scripts/
│   ├── search_oss.py                       # 三平台检索，分层降级，输出归一化 JSON
│   └── fetch_repo.py                       # 仓库骨架抓取（git/归档双通道）
├── references/
│   ├── platform-search.md                  # 平台端点、认证、实测坑、兜底策略
│   ├── comparison-method.md                # 打分模型、对照矩阵、差距三级分类
│   ├── skill-derivation.md                 # 复杂度分级、派生 skill 骨架与验收
│   └── 技能转化.md                          # B 路线：开源项目转单文件参考 skill 的执行手册
├── assets/
│   ├── benchmark-report-template.md        # Markdown 报告模板
│   └── benchmark-report-template.html      # HTML 可视化模板（只改 DATA 对象）
└── env.sample                              # 平台凭证模板
```

## 硬性纪律

- **禁止无源断言**：每条结论必须追溯到 `仓库 → 文件路径/章节`，写不出来源就标"待确认"
- **异常分支优先**：开源项目的真正价值在异常分支，happy path 自家 PRD 通常已有
- **star 不是相关性**：高 star 无关项目必须剔除
- **License 必须判定**：AGPL/GPL 只提炼思路不搬代码，并在产物中写明

## 许可

跟随仓库根目录 License 声明。
