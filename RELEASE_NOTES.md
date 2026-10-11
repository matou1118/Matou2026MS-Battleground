# 码头哥 2026 MS 战场版 — 版本说明

**版本号**：2026.10
**发布日期**：2026-10-10
**定位**：面向《魔兽世界》3.3.5 (巫妖王之怒) 的 AI 机器人服务器端增强版本

---

## 一、基线信息

本版本基于以下上游构建，**不是**上游的官方分支。

| 组件 | 基线版本 | 本项目提交 | 改动量 |
|---|---|---|---|
| **AzerothCore** (fork: mod-playerbots/azerothcore-wotlk) | `2a2211cd` (2026-10-09) | `6b18686` | 10 文件 / +38 −13 |
| **mod-playerbots** | `037c0141` (2026-10-02) | `939f9cb` | 23 文件 / +651 −76 |

> 本项目全部改动**已提交入 git 历史**，可逐行追溯。
> 改动集中于 mod-playerbots，核心仅作最小必要修改，
> 以降低日后合并上游的冲突成本。

---

## 二、这次更新做了什么（一句话版）

**修好了三个「看起来像玄学」的根因类问题**（数据缺失、宠物孤儿、角色无装备），
**重做了战场 AI 的决策逻辑**，**让猎人宠物与驯兽天赋真正生效**，
**砍掉 22 秒启动空转**，**重制了炉石菜单配色**。

---

## 三、重点更新

### 3.1 战场 AI 重做 ★主要

**改前**：战场行为基于固定时间脚本 ——「第 N 秒做某事」。

**改后**：状态驱动 + 空间判断。

| 改动 | 效果 |
|---|---|
| `shouldReinforce()` 重写 | 回防判定改由**友军密度 + 目标距离 + 据点归属**共同决定 |
| 新增 `countFriendlyNear()` | 统计范围内友军数量，避免「以为没人其实一堆」 |
| **岗位分配改用 GUID 稳定哈希** | **重连后队伍岗位不再重排** —— 此前守 A 点的会跑去守 B 点，防线瞬间瓦解 |
| 战场内提高敌对玩家仇恨上限 | bot 不再无视真人只打 NPC |
| AoE 判定改为周围敌对目标，战场半径 ×2.5 | 战场地图开阔，原半径覆盖不足 |
| 高差容忍度放宽 | 战场存在大量高低差地形 |
| AV 角色动态轮换 | 不再被固定分工针对 |

**实测**：奥山战场可稳定拉满 40 人，攻防行为较此前明显改善。

---

### 3.2 猎人宠物与驯兽天赋 ★主要

**改前**：宠物数据在库里，但**登录不载入、召唤也找不到**；
驯兽专精的核心天赋**常年不触发**。

| 问题 | 根因 | 修复 |
|---|---|---|
| 29 个猎人无法使用宠物 | `character_pet.slot = 100`（非法值，等同「不在槽位」）| 归位为 `slot = 0` |
| 宠物死亡后永不复活 | `revive pet` 动作已注册但**无策略引用** | 接入触发器 |
| 驯兽核心天赋失效 | `aspect of the wild` 已注册但**从未被触发** | 加入常驻增益 |
| 弹药耗尽后站桩不动 | `low ammo` / `no ammo` 无接线 | 补齐 |
| 宠物心情持续下降 | `feed pet` 无接线 | 补齐 |
| 生存猎缺稳定射击源 | 陷阱类动作无接线 | 补齐 |

**排查方法（可复用于任何职业）**：统计 AI 上下文中注册的 action
与各策略中 `NextAction()` 引用的差集。

> 猎人模块实测：84 个注册动作中 **35 个零引用**。
> 其中大部分是策略名（`bm`/`surv`/`cc` 等）属正常，
> 真正的遗漏是上面那批。

---

### 3.3 各职业 AoE 补齐

以下职业/专精此前**完全没有 AoE 逻辑**，现已补齐：

- 萨满
- 术士
- 德鲁伊
- 暗影牧师
- 法师（奥术 / 火法）

---

### 3.4 启动性能：22 秒 → 近 0

**改前**：`World Initialized` 约 41–54 秒，其中 mod-playerbots 初始化占 **22.4 秒（52%）**。

**根因**：`ParseTempTalentsOrder()` 在**参数为空字符串时**仍然全量扫描天赋库
（约 1,700 行）并重建标签映射，**之后才**在循环里发现输入为空而退出。

该函数在启动时被调用 **3,200 次**，而配置中实际存在的
`AiPlayerbot.PremadeSpecLink.*` 只有 **131** 个 ——
即 **3,069 次在扫描一个必然为空的结果**。

**修复**：函数入口对空输入提前返回。

同时新增分项计时日志，便于后续定位：

```
>> [phase] TalentSpec parse: N ms
>> [phase] RandomPlayerbotMgr.Init: N ms
>> [phase] BuildAllSharedContexts: N ms
...
```

---

### 3.5 崩溃修复

**`ThreatManager::ProcessAIUpdates()` 断言**

真人玩家持有的 `ThreatManager` 会经由 `GetCurrentVictim() → UpdateVictim()`
走到此处并触发 `ASSERT_NOTNULL(_owner->ToCreature())`，
而此时 `_needsAIUpdate` 为空 —— **在一个「什么都不会发生」的空路径上断言**。

mod-playerbots 环境中 bot 与真人交互频繁，该路径被高频命中，
导致 worldserver 崩溃。已改为由 `CanHaveThreatList()` 提前返回。

---

### 3.6 数据完整性工具链

**改前**：数据库多处残缺 —— `spell_dbc` 只有 4,518 行（应有约 5 万），
ID 880–990 区间**完全为空**，导致召唤宠物(883)、复活宠物(982) 等
**完全无法施放**（`.learn` 成功但一用就失败）。

| 工具 | 用途 |
|---|---|
| `dbc_import.py` | DBC 解析导入，字段布局**自动从核心 `DBCfmt.h` 读取** |
| `gear_up_naked_bots.py` | 为零装备角色生成分职业装备 |

> 工具可在任意版本复用 —— 换版本只需改 `DBCFMT` 常量指向新的 `DBCfmt.h`。

---

### 3.7 炉石脚本重制

**更名**：`天蓝超级炉石自用 微调2.0版.lua` → **`码头哥炉石.lua`**

**配色统一**：488 处颜色码由 **26 种收敛为 2 种**。

| 之前 | 之后 | 处数 |
|---|---|---|
| 红 5 种、绿 6 种、蓝 3 种、紫粉 4 种…… | *不带色码，走默认色* | 365（色码已移除）|
| — | `cffff4040` 危险红 | 82 |
| — | `cffffd200` 提示金 | 41 |

**关键判断**：菜单底色是羊皮纸/金色，浅色字会糊在底色上，
因此普通条目的正确做法是**移除色码**而非替换为白色。
分类信息由 372 个不同图标与文字本身承载。

> 详见 [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) 与
> [`CHANGELOG.md`](CHANGELOG.md) 第五节。

---

## 四、如何更新

### 4.1 从本版本源码包开始（推荐）

```bash
tar -xzf Az335_Source_2026.10.tar.gz
cd azerothcore-wotlk
# 直接编译即可，改动已包含在源码中
cmake -B build -S . -DCMAKE_BUILD_TYPE=Release -DTOOLS=ON -DSCRIPTS=static
cmake --build build --config Release -j 2
```

### 4.2 从已有的 AZ + BOT 升级

```bash
# 1. 拉取本项目提交
cd azerothcore-wotlk
git fetch <本项目仓库> <分支>
git cherry-pick 6b18686           # 核心改动

cd modules/mod-playerbots
git fetch <本项目仓库> <分支>
git cherry-pick 939f9cb           # 机器人改动
cd ../..
```

若不使用 git，可直接套用补丁：

```bash
git apply patches/core_azerothcore.patch
cd modules/mod-playerbots && git apply ../../patches/mod-playerbots.patch
```

### 4.3 数据迁移

**本版本修复的数据问题需一次性执行，之后无需重复：**

```sql
-- 1. 猎人宠物 slot 归位（29 行）
UPDATE acore_characters.character_pet p
JOIN acore_characters.characters c ON c.guid = p.owner
SET p.slot = 0
WHERE p.slot > 4 AND c.class = 3
  AND p.owner NOT IN (
    SELECT owner FROM (SELECT owner FROM acore_characters.character_pet WHERE slot = 0) x);

-- 2. spell_dbc 补全（从 4,518 → 49,854）
--    见 scripts/dbc_import.py，保留 ID >= 100000 的自定义法术

-- 3. lfgdungeons_dbc 补全（从 2 → 195）
```

> ⚠️ **务必先备份**。本版本已附带回滚脚本：
> `acore_characters.pet_slot100_backup`、`spell_dbc_backup_before_import`、
> `acore_characters.nakedbots_backup`。

### 4.4 配置变更

| 项 | 旧值 | 新值 | 原因 |
|---|---|---|---|
| `MaxPlayerLevel` | 180 | **80** | 与资料片一致 |
| `AiPlayerbot.RandomBotJoinLfg` | — | **0** | bot 不再自主排随机副本 |
| `botActiveAloneSmartScale` | — | **0** | 避免单体 bot 智能异常 |
| `UpdateUptimeInterval` | — | **1** | 修正计时 |
| 缺失配置项 | — | **补齐 86 项** | 见 `git diff` |

**移除**：灵魂熔炉 / 倒影大厅共 **8 条** attunement 限制。

---

## 五、破坏性变更

| 变更 | 影响 | 应对 |
|---|---|---|
| 炉石脚本更名 | Eluna 若引用旧文件名会失效 | 替换为 `码头哥炉石.lua` |
| 菜单配色移除 | 依赖颜色区分类别的用户需改用图标 | 图标未变，372 个不同图标 |
| `MaxPlayerLevel` 180→80 | 超出 80 级的角色会被降级处理 | 确认无需求后再升级 |
| `RandomBotJoinLfg=0` | bot 不再自动进随机副本队列 | **这是预期行为**，需人工发起 |
| 编译并行度 | 必须 `-j 2` | `-j 16` 会将可用内存压至 7 MB 并冻结 |

---

## 六、已知问题

| 问题 | 状态 |
|---|---|
| 随机副本客户端列表为空 | 服务端数据完整（195 条），客户端 UI 不显示，待排查 |
| `item_template.spellid_*` 存在无效法术引用 | 历史残留告警，不影响功能 |
| 商业训练师不按职业过滤 | 沿用上游实现 |
| mod-playerbots 无正式版本 | 仅 `master` / `test-staging` 滚动分支，无 release tag |
| 天赋预设仅配置 131 / 3,200 条 | 缺失等级段按「无预设天赋树」处理 |

---

## 七、系统要求

| 项目 | 最低 | 推荐 |
|---|---|---|
| 操作系统 | Windows 10 x64 | Windows 11 x64 |
| 内存 | 8 GB | 16 GB |
| 硬盘 | 30 GB | 60 GB |
| 数据库 | MySQL 8.0 | MySQL 8.0 |
| 编译器 | VS 2019 v16.5 | VS 2022 v17.x |
| 编译并行度 | — | **固定 `-j 2`** |

**启动顺序**（必须）：

```
MySQL  →  worldserver  →  等待 8085 端口  →  authserver
```

---

## 八、致谢

本项目站在巨人的肩膀上。

- **AzerothCore 团队** —— 让 WoW 3.3.5 服务器端重新开源成为可能
- **mod-playerbots 团队** —— 提供了功能最完整的 AI 机器人框架
- **AzerothCore Discord / mod-playerbots Discord** —— 技术支持
- **uiwow 论坛** —— 中文 WoW 服务器开发社区
- **炉石脚本原作者** —— 见 [`AUTHORS.md`](AUTHORS.md)

---

## 九、许可

代码以 **GPLv2** 发布，详见 [`LICENSE`](LICENSE)。
第三方组件授权见 [`NOTICE.md`](NOTICE.md)。

**本项目仅供学习、开发与技术交流，禁止商业用途。**

> **关于该条款的效力**：GPLv2 序言明确写道
> "The act of running the Program is not restricted" ——
> 运行行为不在 GPLv2 管辖范围内，因此无法通过附加条款约束。
> 该声明的效力为作者意愿、伦理倡议与侵权主张依据。
> 生态中真正约束商业化的是暴雪娱乐的著作权与 EULA。
> 详见 [`DISCLAIMER.md`](DISCLAIMER.md) 第 4.2 节。

---

**码头哥 2026 MS 战场版**
2026.10 · 仅供学习开发交流
