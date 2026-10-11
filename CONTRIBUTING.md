# 贡献指南 / CONTRIBUTING

感谢您考虑为本项目贡献代码。

---

## 一、开始之前

请先阅读：

- [`../DISCLAIMER.md`](../DISCLAIMER.md) —— 免责声明与**非商用**要求
- [`../NOTICE.md`](../NOTICE.md) —— 第三方组件授权
- [`../LICENSE`](../LICENSE) —— GPLv2

提交贡献即表示您：

1. 同意您的代码以 **GPLv2** 发布
2. 确认您的贡献**不含**暴雪娱乐的受版权保护内容
3. 确认您的贡献**不含**任何凭据、密钥或个人数据
4. 理解本项目**禁止商业用途**，您的贡献同样受此约束

---

## 二、提交前自查清单

- [ ] 已阅读 [`../DISCLAIMER.md`](../DISCLAIMER.md)
- [ ] 改动仅涉及**一个**逻辑主题（不要把 bug 修复和格式调整混在一起）
- [ ] 未引入任何新的编译警告
- [ ] 改动**不含**任何暴雪数据（`.dbc` / `maps/` / `mmaps/` / `vmaps/`）
- [ ] 改动**不含**任何凭据、IP、内网地址、真实服务器名
- [ ] 若涉及配置模板，使用 `.conf.dist` 而非 `.conf`
- [ ] 若涉及数据库，提供 `*.sql` 并说明**是否可重复执行**（幂等性）
- [ ] 已在 [`../CHANGELOG.md`](../CHANGELOG.md) 的「未发布」章节记录变更
- [ ] 代码风格与上游一致（4 空格缩进，成员变量 `m_` 前缀等）

---

## 三、分支策略

| 分支类型 | 命名 | 说明 |
|---|---|---|
| 功能 | `feat/<简述>` | 新功能 |
| 修复 | `fix/<简述>` | 缺陷修复 |
| 文档 | `docs/<简述>` | 仅文档变更 |
| 重构 | `refactor/<简述>` | 不改变行为的结构调整 |

> **强烈建议**：改动集中在 `modules/mod-playerbots`。
> 核心（AzerothCore）改动会增加合并上游的成本，
> 除非是明确的崩溃修复，否则应优先在模块层解决。

---

## 四、代码风格

遵循上游 AzerothCore 风格：

```cpp
// 4 空格缩进，大括号独占一行
if (condition)
{
    DoSomething();
}

// 成员变量 m_ 前缀，全局变量 g_ 前缀，静态变量 s_ 前缀
uint32 m_value;

// 优先早返回，避免深层嵌套
if (!condition)
    return;
```

### 注释原则

**注释解释「为什么」，而不是「是什么」。**

```cpp
// ✗ 不好：复述代码
// 递增 i
++i;

// ✓ 好：解释意图与背景
// Skip the full talent-store scan when there is no link to parse;
// this runs 3200 times at startup and 3069 of those are empty.
if (tab_link.empty())
    return {};
```

> 本项目的全部补丁都遵循这一原则，请保持一致。

---

## 五、数据库变更

### 必须幂等

```sql
-- ✗ 不好：重复执行会报错或产生重复数据
INSERT INTO spell_dbc VALUES (...);
TRUNCATE TABLE spell_dbc;

-- ✓ 好：可重复执行
DROP TABLE IF EXISTS xxx_backup;
CREATE TABLE xxx_backup AS SELECT * FROM xxx WHERE ...;

DELETE FROM xxx WHERE `ID` < 100000;
INSERT INTO xxx (...) VALUES ...;
```

### 不得破坏用户数据

- 覆盖前**必须**判断是否需要保留（如同 `ID >= 100000` 的自定义法术）
- 提供回滚脚本或备份表
- 在注释中说明影响范围

---

## 六、提交信息

采用 [Conventional Commits](https://www.conventionalcommits.org/) 格式：

```
<type>(<scope>): <subject>

<body>

<footer>
```

| type | 说明 |
|---|---|
| `feat` | 新功能 |
| `fix` | 缺陷修复 |
| `docs` | 文档 |
| `perf` | 性能优化 |
| `refactor` | 重构 |
| `test` | 测试 |
| `chore` | 构建 / 工具 / 杂项 |

示例：

```
fix(hunter): 接上 aspect of the wild 触发器

野生之灵是驯兽专精核心天赋（+15% 攻击力、宠物 5% 减伤），
在 HunterAiObjectContext 中已注册但从未被任何策略引用，
导致该天赋常年失效。

用注册/引用差集排查发现猎人模块共 35 个动作零引用，
本次一并补齐弹药管理、陷阱布置与毒药维持。
```

---

## 七、报告 Bug

请提供：

1. **环境** —— 核心 commit、模块 commit、操作系统
2. **复现步骤** —— 尽量精确到命令
3. **实际现象** 与 **预期现象**
4. **日志片段** —— `logs/Server.log` 与 `logs/Errors.log` 相关行
5. **数据库校验结果** —— 参考 [`../docs/TROUBLESHOOTING.md`](../docs/TROUBLESHOOTING.md) 的快速诊断

> **请勿提交含真实数据的日志**，其中可能包含账号信息。

---

## 八、提交被拒的常见原因

| 原因 | 说明 |
|---|---|
| 引入暴雪数据 | 立即拒绝，无例外 |
| 含凭据或个人数据 | 立即拒绝 |
| 核心改动但模块层可解 | 会要求重构到模块层 |
| 缺少 CHANGELOG 条目 | 要求补充 |
| SQL 不可幂等 | 要求修正 |
| 未说明如何验证 | 要求补充验证步骤 |

---

## 九、致谢

贡献被合并后，您可选择加入 [`../AUTHORS.md`](../AUTHORS.md)：

```markdown
## 我的贡献

<!-- 姓名 (@GitHub用户名) — 贡献内容 -->
```

---

## 十、许可确认

您提交的代码将以 **GPLv2** 发布，并受
[`../DISCLAIMER.md`](../DISCLAIMER.md) 的**非商用条款**约束。

如不同意，请勿提交。

---

[返回顶部](#贡献指南--contributing)
