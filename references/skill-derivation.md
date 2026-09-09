# 从对标结果到开发指引型 Skill 的 SOP

对标报告的终点不是报告本身，而是一份**能在后续开发时反复调用的 skill**。
本文件规定：什么情况下建、建成什么样、包含哪些内容。

## 一、复杂度分级（决定产物规模）

先给项目定级，再决定产出多少东西。**不要一律建大 skill**，小项目建大 skill 是纯浪费。

| 级别 | 判定标准 | 产物 |
|---|---|---|
| **L1 简单** | 单一技术栈；核心流程 ≤5 个；无复杂状态机；实体 ≤8 个 | 对照报告（MD + HTML）+ 报告内嵌 SOP 章节。**不单独建 skill** |
| **L2 中等** | 有前后端分离；核心流程 6~15 个；存在状态机；实体 9~25 个 | 报告 + 独立开发指引 skill（SKILL.md + `references/architecture.md` + `references/business-flows.md`） |
| **L3 复杂** | 多端（App/管理端/服务端）或多服务；流程 >15 个；多状态机联动；实体 >25 个；存在领域规则（财务/库存/权限） | 报告 + 完整 skill 包：SKILL.md + `references/`(架构、数据模型、业务流程、踩坑点、决策记录) + 可选 `assets/` 目录骨架 |

**自主定级后直接执行，不要为此打断用户。** 卡在 L1/L2 边界时，
按「宁可多输出一份轻量 skill」的原则取 L2——少一份指引的代价大于多维护一份文件的代价。

派生 skill 的存放位置：与调用 `open-source-research` 的层级保持一致
（用户级调用派生到 `~/.workbuddy/skills/`，项目级调用派生到 `./.workbuddy/skills/`），
用户另有指定时以用户为准。执行完毕后统一汇报，不要事前反复确认。

## 二、派生 skill 的标准骨架

```
<领域>-dev-guide/
├── SKILL.md                     # 必含：触发条件、开发总纲、文件索引
└── references/
    ├── architecture.md          # L2+：技术栈基线、模块划分、目录结构约定
    ├── data-model.md            # L3：核心实体、表结构、实体关系、关键字段语义
    ├── business-flows.md        # L2+：流程状态机、异常分支、触发条件
    ├── pitfalls.md              # L2+：已知坑、性能点、兼容性、踩过的雷
    └── decisions.md             # L3：技术选型决策及理由（ADR 风格）
└── assets/                      # 可选：目录骨架、配置模板、代码片段
```

命名：`<领域英文>-dev-guide`，全小写连字符，如 `tutoring-erp-dev-guide`。

## 三、SKILL.md 必含章节（缺一不可）

```markdown
---
name: <领域>-dev-guide
description: <这个 skill 在什么场景下用；用第三人称描述触发条件>
agent_created: true
---

# <领域> 开发指引

## 目的
两三句话说明这个 skill 解决什么问题。

## 何时使用
列出 3~5 条具体触发场景（用户会怎么描述需求）。

## 技术栈基线
框架 / 语言 / 版本 / 关键依赖，写死版本号，不要写"最新版"。

## 目录结构约定
项目骨架树 + 每个目录的职责一句话。

## 核心流程清单
流程名 → 一句话说明 + 指向 `references/business-flows.md` 的具体章节。

## 关键约束与红线
不可违反的规则（数据一致性、权限边界、离线约束、合规要求）。

## 常见坑
Top 5 坑，每条一句话 + 指向 `references/pitfalls.md`。

## 参考资料索引
列出本 skill 所有 references 文件及各自内容摘要。
```

## 四、内容抽取规则

从对标结果往 skill 里搬东西时，遵守：

1. **搬"决策与理由"，不搬"代码"。**
   `references/` 里写"为什么用 SQLite + 版本号冲突检测做离线同步"，
   而不是贴 200 行同步代码。代码由开发时按需生成。

2. **数据是骨架，优先抽数据模型。**
   实体 + 字段 + 关系 + 状态枚举，是最能直接指导开发的部分，L3 必须抽全。

3. **异常分支优先级高于 happy path。**
   自家 PRD 通常已经写了 happy path，skill 里重点写异常分支与边界条件。

4. **每个结论标注来源。**
   格式：`（参考 <repo> → <路径/章节>）`。便于后续回溯，也便于 License 审查。

5. **不确定就写"待确认 + 为什么不确定"**，禁止为了填满篇幅编造。

## 五、License 红线

- AGPL / GPL 项目：**只能提炼设计思路，不得搬运代码**；派生 skill 里不得包含其源码片段。
- MIT / Apache-2.0 / BSD：可搬运代码片段，但须在 skill 里注明来源与 License。
- 每条 references 文件末尾列出其内容的来源仓库与 License。

## 六、验收 Checklist

派生 skill 交付前逐条打勾：

- [ ] 复杂度已自主定级（未向用户请示），并存疑处已在 SKILL.md 注明
- [ ] `SKILL.md` frontmatter 含 `agent_created: true`
- [ ] SKILL.md 七个必含章节齐全
- [ ] 所有 references 都在 SKILL.md 里被索引到（不存在的孤儿文件）
- [ ] 每个流程都有异常分支，不是只有 happy path
- [ ] 每条关键结论都有来源标注
- [ ] License 合规判定已写进 skill
- [ ] 用 `quick_validate.py` 校验通过

## 七、不要做的事

- 不要把对标报告整篇塞进 skill。报告是一次性产物，skill 是可复用指引，两者信息密度不同。
- 不要建"通用开发指引"这种空 skill。没有具体领域、具体数据模型、具体流程的 skill 等于没有。
- 不要一次性建 3 个以上 skill。L3 项目也是**一个** skill 包，靠 references 拆分，不靠拆 skill。
