# 架构与关键改动说明 / ARCHITECTURE

本文说明本项目相对上游 AzerothCore + mod-playerbots 的**关键改动点**及其设计依据，
便于维护者理解、扩展或在合并上游时处理冲突。

---

## 一、代码分布

改动分为两个层次：

| 位置 | 改动量 | 内容 |
|---|---|---|
| `azerothcore-wotlk` 核心 | 10 文件 / +38 −13 | 崩溃修复、编译修复、少量战场接线 |
| `modules/mod-playerbots` | 22 文件 / +617 −76 | 战场 AI、职业策略、猎人触发器 |

> **核心改动极少**是刻意的。核心是 AzerothCore 与 mod-playerbots 之间的适配层，
> 改动越多，合并上游时冲突越严重。所有 bot 行为逻辑集中在模块内。

### 核心侧改动清单

| 文件 | 性质 | 说明 |
|---|---|---|
| `src/server/game/Combat/ThreatManager.cpp` | **崩溃修复** | 见 §3.1 |
| `src/server/game/Battlegrounds/Battleground.cpp` | 行为接线 | |
| `src/server/game/Battlegrounds/BattlegroundQueue.cpp` | 行为接线 | |
| `src/server/game/Entities/Creature/Trainer.cpp` | 行为修正 | |
| `src/server/game/Entities/Player/Player.cpp` / `.h` | 接口扩展 | |
| `src/common/Cryptography/OpenSSLCrypto.cpp` | 编译修复 | |
| `src/common/Utilities/Geometry.h` | 编译修复 | |
| `src/common/Utilities/Tokenize.h` | 编译修复 | |
| `modules/CMakeLists.txt` | 模块注册 | |

---

## 二、战场 AI 设计

### 2.1 问题

原版 mod-playerbots 的战场行为基于**时间驱动的固定脚本**：
「第 N 秒做某事」。这导致：

- bot 会集体前压或集体龟缩，缺乏位置感
- 不同战场共用一套时序，无法适配各自的地图结构
- bot 之间无协作判断

### 2.2 方案

改为**状态驱动 + 空间判断**。核心改动在
`Ai/Base/Actions/BattleGroundTactics.cpp`（+266 行）。

| 函数 | 改动 | 设计意图 |
|---|---|---|
| `shouldReinforce()` | 重写 | 由**友军密度 + 目标距离 + 据点归属**共同决定是否回防，而非固定时间 |
| `countFriendlyNear()` | 新增 | 统计指定范围内友军数量，避免「以为没人其实一堆」 |
| AV 角色分配 | 重写 | 按队伍构成动态轮换，避免固定分工被针对 |

### 2.3 岗位稳定性

`BattleGroundJoinAction.cpp` 引入**基于 GUID 的稳定哈希**来分配岗位。

**问题**：若岗位按加入顺序分配，bot 登录/掉线重连后顺序变化，
会导致整个队伍岗位重排，原本守 A 点的跑去守 B 点，防线瞬间瓦解。

**方案**：用角色 GUID 派生哈希 → 同一角色每次获得同一岗位。
只有实际死亡或地图切换才重新评估。

### 2.4 战场内感知

| 改动 | 文件 | 原因 |
|---|---|---|
| 敌对玩家仇恨上限提高 | `EnemyPlayerValue.cpp` | 原逻辑认为玩家不值得优先攻击，导致战场中 bot 只打 NPC |
| AoE 判定改为周围敌对目标 | `GenericTriggers.cpp` | 原逻辑依赖特定目标列表，战场中常判定为空 |
| 战场 AoE 半径 ×2.5 | 同上 | 战场地图开阔，原半径覆盖不足 |
| 高差容忍度放宽 | 同上 | 战场存在大量高低差地形 |

---

## 三、崩溃修复

### 3.1 ThreatManager 断言（核心）

**位置**：`src/server/game/Combat/ThreatManager.cpp`

```cpp
// 修改前
void ThreatManager::ProcessAIUpdates()
{
    CreatureAI* ai = ASSERT_NOTNULL(_owner->ToCreature())->AI();
    ...
```

**问题**：`ThreatManager` 的 owner 可以是 `Player`（真人玩家或玩家控制的单位）。
`ProcessAIUpdates()` 会经由 `GetCurrentVictim()` → `UpdateVictim()` 被调用，
而 `_needsAIUpdate` 此时为空 —— 断言在「什么都不会发生」的空路径上触发。

在 mod-playerbots 环境中，bot 与真人交互频繁，该路径被高频命中，导致 worldserver 崩溃。

**修改**：

```cpp
if (!CanHaveThreatList())
    return;

CreatureAI* ai = _owner->ToCreature()->AI();
```

**设计取舍**：未使用 `ASSERT` 改为静默返回。虽然理论上掩盖了「玩家不该有
CreatureAI」的假设，但 `CanHaveThreatList()` 本身已正确表达该语义，
且 `_owner->ToCreature()` 在此处必然非空。

---

## 四、猎人模块

### 4.1 问题的发现方式

统计 `HunterAiObjectContext` 中注册的 action 与各策略中 `NextAction()` 引用的差集：

```
注册数: 84 | 被引用: 60 | 零引用: 35
```

其中 35 个里大部分是策略名（`bm` / `mm` / `surv` / `cc` / `boost` 等）属正常，
真正缺失的是那些「动作已实现却无人调用」的部分。

> **这个排查方法可复用于任何类**：
> 用正则提取 `creators["..."]` 与 `NextAction("...")` 做差集，
> 能快速发现 AI 层的接线遗漏。

### 4.2 修复清单

| 触发器 | 动作 | 优先级 |
|---|---|---|
| `hunters pet dead` | `revive pet` | 99 |
| `pet not happy` | `feed pet` | 98 |
| `feed pet` | `feed pet` | 97 |
| `call pet` | `call pet` | 96 |
| `tranquilizing shot enrage` | `tranquilizing shot` | 61 |
| `tranquilizing shot magic` | `tranquilizing shot` | 61 |
| `deterrence` / `feign death` | 低血量生存 | 35 |
| `misdirection on main tank` | 坦克仇恨转移 | 27 |

### 4.3 驯兽专精

**`Aspect of the Wild`（野生之灵）**是驯兽专精的核心天赋，
提供 +15% 攻击力与宠物 5% 减伤。

原实现在 `HunterAiObjectContext` 中已注册，但 `BeastMasteryHunterStrategy`
**从未触发它**，导致该天赋常年失效。

修复后在 `getDefaultActions()` 中以 19.5 优先级加入，
使其成为常驻增益。

---

## 五、启动性能

### 5.1 问题定位

日志中 `>> Loaded playerbots config in 22368 ms` 占总启动时间的 52%。

**注意**：该日志行具有误导性 —— 它在 `PlayerbotAIConfig::Initialize()`
**全部结束后**才打印，因此 22.4 秒涵盖了整个 bot 初始化过程，而非仅配置读取。

各子步骤的日志显示缓存加载均为 4–31 ms，故怀疑耗时在无日志输出的环节。

### 5.2 根因

`PlayerbotAIConfig::ParseTempTalentsOrder()`：

```cpp
// 修改前
std::vector<std::vector<uint32>> PlayerbotAIConfig::ParseTempTalentsOrder(uint32 cls, std::string tab_link)
{
    uint32 classMask = 1 << (cls - 1);
    std::vector<std::string> tab_links = split(tab_link, "-");
    std::map<uint32, std::vector<TalentEntry const*>> spells;
    std::vector<std::vector<std::vector<uint32>>> orders(3);

    for (uint32 i = 0; i < sTalentStore.GetNumRows(); ++i)   // ← 无条件全扫
    {
        TalentEntry const* talentInfo = sTalentStore.LookupEntry(i);
        ...
        spells[talentTabInfo->tabpage].push_back(talentInfo);
    }

    for (int tab = 0; tab < 3; tab++)
    {
        if (tab_links.size() <= (size_t)tab)
            break;                                              // ← 才在这里退出
```

调用点在 `Initialize()` 中：

```cpp
for (uint32 cls = 1; cls < MAX_CLASSES; ++cls)        // 10
    for (uint32 spec = 0; spec < MAX_SPECNO; ++spec)  // ~4
        for (uint32 level = 0; level < MAX_LEVEL; ++level)  // 80
            premadeSpecLink[cls][spec][level] = sConfigMgr->GetOption<std::string>(...);
            parsedSpecLinkOrder[cls][spec][level] = ParseTempTalentsOrder(cls, premadeSpecLink[cls][spec][level]);
```

**3,200 次调用**。而配置中实际存在的 `AiPlayerbot.PremadeSpecLink.*`
仅 **131** 个 —— 即 **3,069 次**在扫描一个必然为空的结果。

### 5.3 修复

```cpp
// 修改后
if (tab_link.empty())
    return {};

uint32 classMask = 1 << (cls - 1);
...
```

`ParseTempPetTalentsOrder()` 同步处理。

### 5.4 分项计时

同时加入阶段计时宏，便于后续定位：

```cpp
#define PB_PHASE(name) \
    do { \
        uint32 now = getMSTime(); \
        LOG_INFO("server.loading", ">> [phase] {}: {} ms", name, uint32(now - phaseT)); \
        phaseT = now; \
    } while (0)
```

覆盖：`TalentSpec parse`、`AssignAccountTypes`、`RandomPlayerbotMgr.Init`、
`GuildMgr+InitArenaTeams`、`RandomItemMgr`、`BisListMgr`、`PlayerbotTextMgr`、
`PlayerbotFactory::Init`、`BuildAllSharedContexts`、`DungeonSuggestions`、`TravelMgr`。

---

## 六、数据层

### 6.1 DBC 加载机制

理解本项目的 DBC 问题前，需要理解 AzerothCore 的加载顺序：

```cpp
// DBCStores.cpp: LoadDBC()
if (storage.Load(dbcFilename.c_str()))       // 1. 先加载文件
    ...
if (dbTable)
    storage.LoadFromDB(dbTable, storage.GetFormat());  // 2. 再用数据库表覆盖
```

**数据库表优先级高于文件**。这意味着残缺的 `spell_dbc` 表会**覆盖**正确的
`Spell.dbc` 文件，导致本该可用的法术消失。

### 6.2 字段映射

`DBCDatabaseLoader.cpp` 的关键行为：

```cpp
for (; (*dbcFormat); ++dbcFormat)
{
    switch (*dbcFormat)
    {
        case FT_NA:      // 'x' 填充位
            break;
        ...
    }
    ++sqlColumnNumber;     // ← 在 switch 之外！
}
```

`++sqlColumnNumber` 在 `switch` **外部**，因此表格中**每一个格式字符
（包括 `x` 填充位与 `d` 排序位）都必须对应一列**。

`SpellEntryfmt` 有 234 个字符 → 表必须有 **234 列**。
若按「有效字段」来推断列数（187），会导致后续所有列错位。

### 6.3 列类型陷阱

`spell_dbc` 中混有三类整数列：

| 类型 | 列数 | 写入时的约束 |
|---|---|---|
| `int`（有符号）| 152 | 必须写入有符号值 |
| `int unsigned` | 115 | 必须写入无符号值 |
| `bigint unsigned` | 2 | 必须写入无符号值 |

DBC 按 uint32 存储，Python `struct.unpack` 按有符号解析。
必须按列类型逐列重算，否则在 MySQL 严格模式下触发
`ERROR 1264: Out of range value`。

> 另一个坑：`information_schema.COLUMNS.DATA_TYPE` 会**丢弃 unsigned 标记**，
> 必须使用 `COLUMN_TYPE`。

### 6.4 格式串来源

`SpellEntryfmt` 有 234 个字符，**手抄必然出错**（本次实际抄成 226 个）。
工具改为从 `DBCfmt.h` 直接读取：

```python
def load_fmt(entry_name, path=DBCFMT):
    """Read one `char constexpr <x>fmt[] = "...";` straight out of DBCfmt.h."""
```

这样解析器与服务器端**不可能不一致**。

---

## 七、合并上游时的注意事项

### 7.1 高冲突区域

| 文件 | 冲突概率 | 原因 |
|---|---|---|
| `BattleGroundTactics.cpp` | **高** | 本项目 +266 行，上游活跃修改 |
| `PlayerbotAIConfig.cpp` | 中 | 本项目改动集中在函数开头与末尾 |
| `GenericTriggers.cpp` | 中 | 通用触发器，上游常有调整 |
| 各职业 `Strategy.cpp` | 中 | 每次上游版本都可能调整 |

### 7.2 低冲突区域

`ThreatManager.cpp` 的改动是纯粹的缺陷修复，建议单独提交 PR 回上游。

### 7.3 建议的合并策略

1. **先合并 mod-playerbots 模块**，再解决核心冲突（反之会丢失模块改动）
2. 冲突时**优先保留上游**，再重新套用本项目的改动
3. `ParseTempTalentsOrder` 的提前返回如上游已修复，可直接丢弃本项目改动
4. 合并后**务必执行 README 中的数据完整性校验**

---

[返回顶部](#架构与关键改动说明--architecture)
