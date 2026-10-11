# 版本迭代说明 / CHANGELOG

**项目**：码头哥 2026 MS 战场版 (Matou 2026 MS Battleground Edition)
**当前版本**：2026.10

本文件记录本项目相对上游 AzerothCore 的全部改动。
上游基线见 [`NOTICE.md`](NOTICE.md)。

---

## [2026.10] — 2026-10-10

本版本聚焦**战场机器人 AI 强化**、**数据完整性修复**、**猎人宠物闭环**、
**炉石脚本重制**与**启动性能优化**五个方向。

---

### 一、数据库完整性修复

上游 AzerothCore 的建库流程在本环境下未完整执行，导致多张关键表严重残缺。
这是本版本修复量最大的部分，也是此前大量「玄学 Bug」的真实根因。

| 缺陷 | 修复前 | 修复后 | 影响 |
|---|---|---|---|
| `spell_dbc` | 4,518 行 | **49,854 行** | ID 880–990 区间原本为 **0 行**，导致召唤宠物(883)、复活宠物(982)、召唤水元素(1515)、召唤亡灵(2641) 等法术**无法施放**。表现为「`.learn` 成功但一用就失败」 |
| `lfgdungeons_dbc` | 2 行 | **195 行** | 随机副本列表为空，无法组副本 |
| `character_pet.slot` | 308 行为 `100` | 归位为 `0` / `1` | `slot=100` 等同「不在槽位」，属无效值。**29 个猎人**的宠物因此登录不载入、也无法召唤 |

**保留策略**：导入时仅覆盖原版 ID 区间（`ID < 100000`），
`ID >= 100000` 的 6 个自定义法术（`100001`、`100099`、`100100`、`100101`、`100102`、`200100`）完整保留。

**字段位宽问题**：`spell_dbc` 表中混有 `int`（152 列）、`int unsigned`（115 列）、
`bigint unsigned`（2 列）。DBC 按 uint32 存储，直接写入会在 MySQL 严格模式下触发
`Out of range value`。导入工具按列类型逐列重算有符号/无符号表示。

**工具**：[`scripts/dbc_import.py`](scripts/dbc_import.py)

> 该工具直接从核心的 `DBCfmt.h` 读取字段布局，而非硬编码格式串。
> `SpellEntryfmt` 有 234 个字符，手抄极易错位且难以察觉。

---

### 二、猎人宠物闭环

#### 2.1 策略层接线缺失

排查发现：mod-playerbots 中猎人的 `revive pet` / `call pet` / `feed pet`
等动作**已在 `HunterAiObjectContext` 注册，却没有任何策略引用它们**。

全类扫描结果：

```
注册数: 84 | 被引用: 60 | 零引用: 35
```

其中绝大多数是策略名（`bm`/`mm`/`surv` 等）属正常，但以下为**真实缺失**：

| 缺失项 | 后果 |
|---|---|
| `hunters pet dead → revive pet` | 宠物死亡后不再复活 |
| `pet not happy → feed pet` | 宠物心情持续下降 |
| `call pet` | 无主动召唤路径 |
| `low ammo` / `no ammo` | **弹药耗尽后 bot 站桩不动** |
| `trap weave` / `immolation trap` / `freezing trap` | 生存猎缺失稳定射击源 |
| `wyvern sting` / `scorpid sting` | 毒药 Buff 消失后无补 |
| **`aspect of the wild`** | **驯兽专精核心天赋常年不生效**（+15% 攻击力、宠物 5% 减伤） |
| `trueshot aura` | 驯兽专精光环不触发 |

新增接线见：
- `Ai/Class/Hunter/Strategy/GenericHunterStrategy.cpp`
- `Ai/Class/Hunter/Strategy/BeastMasteryHunterStrategy.cpp`

#### 2.2 数据层宠物归属

29 个猎人的 `character_pet.slot = 100`（无效值），导致宠物成为孤儿：
数据库里有记录，但登录不载入、召唤也找不到。已统一归位至 `slot = 0`。

---

### 三、战场机器人 AI

| 改动 | 文件 | 说明 |
|---|---|---|
| 动态回防 | `BattleGroundTactics.cpp` | `shouldReinforce()` 重写，援军判定结合友军密度与目标距离，而非固定脚本 |
| 岗位分配 | `BattleGroundJoinAction.cpp` | 引入稳定哈希（GUID 派生），避免同一战场内角色反复横跳导致队伍涣散 |
| 战场内主动接战 | `EnemyPlayerValue.cpp` | 提高对敌对玩家的仇恨上限与高差容忍，战场上不再无视敌人只打 NPC |
| AoE 判定 | `GenericTriggers.cpp` | 改为基于**周围敌对目标**判定，战场内半径放宽至 ×2.5 |
| 各职业 AoE 补齐 | 萨满/术士/德鲁伊/暗影牧师/法师（奥术·火） | 此前多个专精完全没有 AoE 逻辑 |

> 战场内链接优先级由 `AssignBgRole()` 分配，整体偏向防守，
> 避免 bot 集体前压导致据点失守。

**实测**：奥山战场可稳定拉满 40 人，攻防行为较此前明显改善。

---

### 四、装备与角色数据

#### 4.1 零护甲 bot

发现 **107 个 bot 角色完全没有护甲类物品**（`item_template.class = 4` 一件都没有），
其中 24 个为 80 级。背包里只有消耗品、武器、任务物品，
所以 `EquipUp` 无物可穿，表现为战场上「光膀子 bot」。

> 排查过程中一度误判为「物品数据损坏」，实为**连接键用错**：
> 本核心的 `character_inventory.item` 引用的是 `item_instance.guid` 而非
> `item_template.entry`，且列序被重排为 `(guid, bag, slot, item)`。

修复：按职业护甲类型生成分配装备，共 106 人 × 16–17 件。

**职业护甲规则**（`item_template.AllowableClass` 在本库中被错误地设为 `1535`（全职业）
的板甲较多，因此额外叠加了 subclass 硬规则）：

| 职业 | 可用护甲 |
|---|---|
| 战士 | 布 / 锁 / 甲 |
| 圣骑士、死骑 | 布 / 甲 |
| 猎人、萨满 | 布 / 锁 |
| 盗贼、德鲁伊、 Monk | 布 / 皮 |
| 牧师、法师、术士 | 布 |

**工具**：[`scripts/gear_up_naked_bots.py`](scripts/gear_up_naked_bots.py)
**回滚**：`acore_characters.nakedbots_backup`

#### 4.2 训练师菜单

修正若干训练师选项的发出顺序与列表刷新时机，并移除了动画播放对流程的阻塞。

---

### 五、炉石脚本重制

**更名**：`天蓝超级炉石自用 微调2.0版.lua` → **`码头哥炉石.lua`**
（Eluna 服务端脚本，2,724 行 / 835 个图标 / 68 个菜单页）

#### 5.1 配色收敛

原脚本 488 处颜色码使用 **26 种色相**，其中大量同义重复：

| 语义 | 原有色数 |
|---|---|
| 红系 | 5（`e60000` `b22222` `cc0033` `c41e3b` `800000`）|
| 绿系 | 6（`32cd32` `006400` `548b54` `2e8b57` `00ff96` `32cd99`）|
| 蓝系 | 3（`0070d0` `2359ff` `68ccef`）|
| 紫/粉 | 4 |

此外「联盟训练师」用蓝、「部落训练师」用红、中立用深绿，
而菜单文字里本来就写着阵营 —— 属于重复编码同一信息。

**最终方案**（经实测三轮后确定）：

| 颜色 | 用途 | 处数 |
|---|---|---|
| *不带色码* | 普通条目，走客户端默认色 | 365（色码已移除）|
| `cffff4040` | 危险红：不可逆操作 | 82 |
| `cffffd200` | 提示金：确认框关键词 | 41 |

> 菜单底色为羊皮纸/金色，浅色字会糊在底色上，因此普通条目的正确做法是
> **移除色码**而非替换为白色。分类信息由 372 个不同图标与文字本身承载。

#### 5.2 两个踩过的坑（已修复并记录）

1. **色码必须是 8 位 `AARRGGBB`**。写成 6 位 RGB 会导致客户端解析失败，
   把色码原样打印成 `|cffffff文本`，整个菜单呈现为乱码。
   → 已在工具中强制补 `ff` alpha 字节。

2. **行尾必须保持 CRLF**。Python `io.open()` 默认做通用换行转换，
   写回时会将 Windows 行尾变为 Unix 行尾，导致 Eluna 加载异常。
   → 工具已改为二进制读写。

**工具**：[`scripts/restyle_hstone.py`](scripts/restyle_hstone.py)
**原始文件**：`lua_scripts/天蓝超级炉石自用 微调2.0版.lua.ORIGINAL.bak`

---

### 九、发布与合规

为便于向社区公开，本版本补齐了开源发布的全套文档：

| 文件 | 内容 |
|---|---|
| `README.md` | 项目介绍、安装编译、配置、目录结构 |
| `CHANGELOG.md` | 本文件 |
| `DISCLAIMER.md` | 免责声明 + **非商用条款** + 暴雪数据归属说明 |
| `NOTICE.md` | 13 个第三方模块授权、传染性分析、自研部分清单 |
| `AUTHORS.md` | 上游、模块、脚本原作者致谢 |
| `CONTRIBUTING.md` | 贡献指南与提交前自查清单 |
| `LICENSE` | GPLv2 全文 |
| `.gitignore` | 十类拦截规则（暴雪数据 / 凭据 / 编译产物 / 备份） |
| `docs/ARCHITECTURE.md` | 战场 AI 设计、崩溃修复、性能根因、上游合并策略 |
| `docs/TROUBLESHOOTING.md` | 快速诊断 SQL + 五类问题排查 |
| `docs/PORTING.md` | 移植到 2.4.3 / TrinityCore / 4.x 的方法与检查清单 |

**发布包不含**任何暴雪娱乐的受版权保护内容：
`.dbc`、`maps/`、`mmaps/`、`vmaps`、客户端可执行文件与资源、实盘数据库转储。

> **关于「禁止商用」的效力**：GPLv2 §7 明确禁止对 GPL 程序施加附加限制，
> 因此该条款在许可证层面**不具备技术强制力**，
> 其效力为作者的使用意愿声明、伦理倡议与侵权主张依据。
> 详见 [`NOTICE.md`](NOTICE.md) 第三节。

---

### 六、启动性能优化

实测 `World Initialized` 约 **41–54 秒**，其中 mod-playerbots 初始化占 **22.4 秒**（52%）。

**根因**：`ParseTempTalentsOrder()` 在**参数为空字符串时**仍然全量扫描
`talent_dbc`（约 1,700 行）并重建标签映射，之后才在 `for` 循环里发现
`tab_links` 为空而退出。

该函数在启动时被调用 `MAX_CLASSES × MAX_SPECNO × MAX_LEVEL` = **3,200 次**，
而配置中实际存在 `AiPlayerbot.PremadeSpecLink.*` 的仅 **131** 个 ——
即 **3,069 次**在扫描一个必然为空的结果。

**修复**：在函数入口对空输入提前返回。
`ParseTempPetTalentsOrder()` 同步处理。

同时为各初始化阶段加入分项计时日志（`>> [phase] <name>: N ms`），
便于后续定位。

---

### 七、配置修复

- 补齐 86 个缺失配置项
- `MaxPlayerLevel` 由 180 修正为 80
- 清除 BOM、重复键、CP936 乱码
- `botActiveAloneSmartScale` 置 0
- `UpdateUptimeInterval` 修正为 1
- 删除灵魂熔炉 / 倒影大厅 8 条 attunement 限制
- `RandomBotJoinLfg = 0`（bot 不再自主排本）

---

### 八、运行时健壮性

| 修复 | 说明 |
|---|---|
| `ThreatManager::ProcessAIUpdates()` | 真人玩家持有的 ThreatManager 会走到此处并触发 `ASSERT_NOTNULL(_owner->ToCreature())` 崩溃 |
| authserver 启动顺序 | MySQL → worldserver → 等待 8085 → authserver |
| 编译并行度 | 固定 `-j 2`（`-j 16` 会将可用内存压至 7 MB 并冻结）|

### 十、发布形态

本版本采用**双发布物**形式，兼顾合规与可用性：

| 发布物 | 大小 | 内容 | 可公开 |
|---|---|---|---|
| `Az335_Source_2026.10.tar.gz` | 271 MB | **完整源码树**（13,775 文件），解压即可编译 | ✅ |
| 本文档仓库 | 0.6 MB | 文档 + 补丁 + 脚本 + 配置模板 | ✅ |
| `Az335_FULL_20261010.tar.gz` | 2.04 GB | 完整运行快照（含 MySQL 与地图数据）| ❌ 含暴雪数据 |

源码包包含 `src`、`modules`（含 mod-playerbots）、`data/sql`、`deps` 等
构建所需的全部内容，不含 `.git`、`build/`、`install/` 与任何暴雪数据。

**相对上游的改动已提交入 git 历史**，可直接追溯：

| 仓库 | 基线 | 本项目提交 |
|---|---|---|
| azerothcore-wotlk | `2a2211cd` | `6b18686` |
| modules/mod-playerbots | `037c0141` | `939f9cb` |

同时以 patch 形式单独提供，便于从上游 clone 后叠加，
或合并更新版上游时定位冲突。

---

---

## 已知问题 / Known Issues

1. **随机副本客户端列表仍为空**
   服务端数据完整（195 条，136 条符合条件），但客户端 UI 不显示。
   疑似客户端数据缓存或版本差异，待进一步排查。

2. **`item_template.spellid_*` 指向不存在的法术**
   `Errors.log` 中有此类告警，源于 `spell_dbc` 导入前数据缺失期间的残留。

3. **天赋预设解析**
   `AiPlayerbot.PremadeSpecLink.*` 仅配置了 131 / 3,200 条，
   缺失的等级段按「无预设天赋树」处理。

4. **商业训练师不判定职业**
   沿用上游实现，未按职业过滤。

---

## 版本命名约定

版本号格式：`YYYY.MM`，对应打包日期。
战场版专属功能与调优集中在 `2026 MS` 标记中。

---

[返回顶部](#版本迭代说明--changelog)
