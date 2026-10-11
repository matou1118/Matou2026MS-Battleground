# 移植指南 / PORTING

本文说明如何将本项目移植到其他版本的《魔兽世界》服务器端。

**目标版本**：
- AzerothCore 分支的 **2.4.3 (燃烧的远征)**
- TrinityCore / CMaNGOS 系
- **4.x (熊猫人之仙、军团再临)**（部分适用）

---

## 一、先评估：什么能搬，什么不能

| 组件 | 可移植性 | 说明 |
|---|---|---|
| **数据库修复方案** | ★★★★★ | 思路完全通用，与版本无关 |
| **`dbc_import.py`** | ★★★★★ | **自动读目标版本的 `DBCfmt.h`**，无需修改 |
| **`gear_up_naked_bots.py`** | ★★★★☆ | 职业护甲规则需按目标版本调整 |
| **`restyle_hstone.py`** | ★★★★★ | 纯字符串处理，通用 |
| **战场 AI 改动** | ★★★☆☆ | 逻辑通用，战场枚举与地图结构不同 |
| **猎人触发器** | ★★★☆☆ | 技能 ID 与专精结构随版本变化 |
| **炉石脚本** | ★★☆☆☆ | **几乎全部数据需重做**，见 §五 |

> **核心判断**：本项目的**价值主要在方法论与数据修复**，
> 而非代码本身。把 `spell_dbc` 从 4,518 行补到 49,854 行的思路，
> 换成任何版本都适用。

---

## 二、工具链移植（最省力）

### 2.1 `dbc_import.py` —— 零修改

这是本工具链最值得复用的部分。

```python
def load_fmt(entry_name, path=DBCFMT):
    """从核心的 DBCfmt.h 读取 char constexpr <x>fmt[] = "...";"""
```

**它不硬编码任何格式串**，而是运行时从目标源码树的 `DBCfmt.h` 解析。
移植到 2.4.3 或 Cataclysm 时，只需改 `DBCFMT` 常量指向新路径：

```python
DBCFMT = r"<新核心路径>\src\server\shared\DataStores\DBCfmt.h"
```

**工作流程**：

```bash
# 1. 从目标版本客户端提取对应 DBC
# 2. 从目标数据库导出列元数据（必须用 COLUMN_TYPE，不能用 DATA_TYPE）
mysql -u root -p --batch --raw --skip-column-names -e "
  SELECT CONCAT(COLUMN_NAME, CHAR(9), COLUMN_TYPE)
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA='<world库>' AND TABLE_NAME='spell_dbc'
  ORDER BY ORDINAL_POSITION;" > spellmeta.tsv

# 3. 生成 SQL
python scripts/dbc_import.py spell <Spell.dbc> spell.sql spellmeta.tsv

# 4. 导入
mysql -u root -p <target_world_db> < spell.sql
```

> ⚠️ **必须用 `COLUMN_TYPE` 而非 `DATA_TYPE`**。
> `DATA_TYPE` 会丢弃 `unsigned` 标记，导致 `int unsigned` 列被当作有符号处理，
> 在 MySQL 严格模式下抛 `ERROR 1264: Out of range value`。

### 2.2 需要保留的自定义数据

各版本的数据库自定义程度不同，导入前务必先确认：

```sql
SELECT COUNT(*) FROM spell_dbc WHERE ID >= 100000;   -- 自定义法术
SELECT COUNT(*) FROM creature_template WHERE entry > 35000;  -- 自定义生物
```

本项目的导入策略是 `DELETE ... WHERE ID < 100000`，
即**只覆盖原版区间，保留高 ID 的自定义内容**。
若你的自定义 ID 落在原版区间内，需调整阈值。

---

## 三、数据完整性检查清单（通用）

不同版本需要检查的表不同，但**问题模式一致**：

```sql
-- 通用检查：找出「明显偏少」的表
SELECT 'spell_dbc' t, COUNT(*) n FROM spell_dbc
UNION ALL SELECT 'lfgdungeons_dbc', COUNT(*) FROM lfgdungeons_dbc
UNION ALL SELECT 'item_template', COUNT(*) FROM item_template
UNION ALL SELECT 'creature_template', COUNT(*) FROM creature_template
UNION ALL SELECT 'quest_template', COUNT(*) FROM quest_template;
```

**判断标准**：与目标版本客户端 DBC 的记录数对比。
若 `spell_dbc` 明显少于 `Spell.dbc` 文件的记录数，即为残缺。

**残缺的危害**：AzerothCore 的加载顺序是
「先读文件，再用数据库表覆盖」（见 `ARCHITECTURE.md` §6.1），
所以**残缺的表会覆盖正确的文件**，让本该可用的数据消失。

---

## 四、mod-playerbots 改动移植

### 4.1 可以直接搬的部分

| 改动 | 移植性 | 说明 |
|---|---|---|
| `BattleGroundTactics.cpp` 的回防逻辑 | ★★★☆☆ | 逻辑通用，但需核对战场枚举名 |
| `BattleGroundJoinAction.cpp` 的 GUID 稳定哈希 | ★★★★★ | 与版本无关，可直接搬 |
| `GenericTriggers.cpp` 的 AoE 判定 | ★★★★☆ | 半径倍数需按版本调整 |
| `EnemyPlayerValue.cpp` 的玩家仇恨 | ★★★★☆ | 数值需重新调 |

### 4.2 必须重做的部分

| 改动 | 原因 |
|---|---|
| 猎人触发器接线 | 专精数量、技能 ID、职业色随版本变化 |
| `Aspect of the Wild` | 3.3.5 才有该天赋；TBC 驯兽天赋结构不同 |
| 各职业 AoE | 技能名与专精树不同 |

### 4.3 职业与专精结构差异

这是移植时最容易踩坑的地方：

| 版本 | 职业数 | 每职业专精 | 变化 |
|---|---|---|---|
| 1.12 经典 | 8 | 3 | 基线 |
| 2.4.3 TBC | 8 | 5 | 专精大幅扩充 |
| **3.3.5 WotLK** | **10** | 3 | **新增死亡骑士**，专精回归 3 树 |
| 4.x Cataclysm | 11 | 3 | 新增武僧，移除部分天赋 |

代码中的相关常量：

```cpp
// SharedDefines.h
MAX_CLASSES      // 职业总数
MAX_SPECNO       // 每职业专精数
```

**配置文件的对应变化**：

```ini
# 3.3.5 格式（每职业 3 专精，共 30 条）
AiPlayerbot.PremadeSpecName.<cls>.<spec>

# 2.4.3 格式（每职业 5 专精，共 40 条）
AiPlayerbot.PremadeSpecName.<cls>.<spec>
```

键名相同但**数量不同**。移植配置时需按目标版本补齐。

> 💡 **本项目的性能修复在移植后依然有效**：
> `ParseTempTalentsOrder` 的空输入提前返回与版本无关，
> 且在专精更多的 2.4.3 上收益更大
> （2.4.3 为 8 × 5 × 70 = 2,800 次调用，WotLK 为 3,200 次）。

### 4.4 移植后必做验证

```bash
# 1. 全类扫描动作接线遗漏（本项目最有效的排查手段）
grep -oP 'creators\["\K[^"]+' <Class>AiObjectContext.cpp | sort -u > /tmp/reg.txt
grep -rhoP 'NextAction\("\K[^"]+' Strategy/ | sort -u > /tmp/ref.txt
comm -23 /tmp/reg.txt /tmp/ref.txt    # 差集即遗漏

# 2. 检查启动日志中的 phase 计时（本项目新增）
grep "\[phase\]" logs/Server.log

# 3. 验证配置完整性
grep -c "Missing property" logs/Server.log    # 应为 0
```

---

## 五、炉石脚本移植（最麻烦）

`码头哥炉石.lua` 是本项目**版本耦合最严重**的组件。

### 5.1 版本耦合点实测

对本脚本的静态扫描结果：

| 类别 | 数量 | 可移植性 |
|---|---|---|
| 技能 / 法术 ID | **90 个**（1,000–99,999 区间）| ❌ 需逐个核对 |
| `LearnSpell` 调用 | 84 处 | ❌ 需逐个核对 |
| `AddItem` 调用 | 12 处 | ❌ 物品 ID 随版本变 |
| `SummonGameObject` | 5 处 | ❌ 物体 entry 随版本变 |
| 传送坐标 | 数百条 | ⚠️ 地图地形随资料片改版 |
| `GetClass` / `GetTeam` | 各 2 处 | ✅ 通用 |
| `GetRace` / `GetGender` | **0 处** | ✅ **无种族性别依赖** |

**结论**：**好消息**是脚本不依赖种族与性别，因此不存在「种族转种族」问题。
**坏消息**是几乎所有 ID 与坐标都需核对。

### 5.2 逐项核对方法

#### 技能 ID

```sql
-- 在目标版本的 spell 表中核对
SELECT ID FROM spell_template WHERE ID IN (883, 982, ...);
```

**ID 稳定性**：同一法术在不同资料片通常保持同 ID，但
**新资料片新增的法术使用新 ID**（WotLK 新增内容多在 45,000–80,000 区间）。
TBC → WotLK 时，WotLK 新增的天赋/技能在 TBC 中不存在。

#### 地图 ID

```sql
SELECT ID, MapID, MapName_Lang_zhCN FROM map_template ORDER BY ID;
```

老地图 ID 在资料片间基本稳定，但**部分地图被重新编号**。
移植后应**逐个实际跑一遍传送**，确认落点合理。

#### 坐标

坐标偏移是最容易出错的部分。资料片更新会改动地形：

| 资料片 | 典型影响 |
|---|---|
| Cataclysm | 大陆重做（暴风城、诺森德等），老坐标大量失效 |
| Legion | 部分区域地形调整 |

**验证方法**：为每个传送点加一段落地检测，例如：

```lua
if not player:IsInWorld() or player:GetZ() < -200 then
    player:SendMessage("传送点异常: "..text)
end
```

### 5.3 建议的移植策略

**不要整体重做，按功能分层重建**：

```
第 1 层  炉石核心功能     记录点 / 传回 / 定点传送   → 与版本无关，直接搬
第 2 层  城市传送         各主城坐标                → 需核对
第 3 层  副本 / 战场传送   副本入口、战场入口        → 需核对
第 4 层  训练师召唤       训练师 ID                 → 需核对
第 5 层  商业 / 附魔      物品与技能                → 需核对
```

第 1 层可以直接复用现有代码，其余按功能逐块重建与验证。

### 5.4 配色工具可直接复用

`restyle_hstone.py` 是纯字符串处理，**与版本完全无关**，可直接用于任何版本的脚本。

---

## 六、其他版本的分叉

### 6.1 AzerothCore 2.4.3 分支

官方仓库存在 `master`（3.3.5）分支，但**没有官方维护的 2.4.3 分支**。
社区版本（如 `AzerothCore/azerothcore-wotlk` 的某些 fork）存在，
但需自行确认质量与维护状态。

> **重要**：mod-playerbots 本身针对 3.3.5。
> 2.4.3 的 AI 框架通常用 TrinityCore 自带的 `AIPlayerbot`，
> **代码完全不同**，本项目的模块改动无法直接移植。

### 6.2 TrinityCore / CMaNGOS

| 项目 | 差异 |
|---|---|
| DBC 加载 | 类似，仍是「文件 + DB 覆盖」 |
| AI 框架 | TrinityCore 自带 `AIPlayerbot`，与 mod-playerbots 无继承关系 |
| 配置命名 | `AI.Playerbot.*` 而非 `AiPlayerbot.*` |
| Lua 支持 | Eluna，同样支持 `GossipMenuAddItem` |
| 编译并行度 | Linux 下可用更高并行度，Windows 仍建议 `-j 2` |

### 6.3 通用差异速查

| 维度 | 需核对的内容 |
|---|---|
| `DBCfmt.h` 字段布局 | 工具自动读取，一般无需干预 |
| 配置键名 | `AiPlayerbot.*` / `AI.Playerbot.*` |
| 类专精枚举 | `MAX_CLASSES` / `MAX_SPECNO` |
| 战场枚举 | 各 BG 的 `BattleGroundTypeId` |
| Eluna API | `GossipMenuAddItem` 签名可能不同 |
| DB 库名 | `acore_*` / `world` / `auth` / `characters` |

---

## 七、移植检查清单

### 7.1 数据层

- [ ] 用目标客户端 DBC 校验 `spell_dbc` 行数
- [ ] 用目标客户端 DBC 校验 `lfgdungeons_dbc`
- [ ] 确认自定义法术 / 生物 ID 未被覆盖
- [ ] 检查 `item_template.spellid_*` 是否有失效引用

### 7.2 编译层

- [ ] Windows 下使用 `-j 2`
- [ ] 无新增编译警告
- [ ] 模块 `CMakeLists.txt` 已注册

### 7.3 AI 层

- [ ] 执行全类动作接线差集扫描
- [ ] 确认 `RandomBotJoinLfg = 0`
- [ ] 确认 `PremadeSpecName.*` 按目标版本补齐
- [ ] 检查 `>> [phase]` 日志无异常耗时

### 7.4 脚本层

- [ ] 技能 ID 逐个核对
- [ ] 物品 / 物体 entry 核对
- [ ] 传送坐标逐个实跑
- [ ] 色码为 8 位 `AARRGGBB`
- [ ] 文件行尾为 CRLF

### 7.5 合规层

- [ ] 发布包不含任何暴雪数据
- [ ] 配置模板已脱敏
- [ ] `NOTICE.md` 中的模块授权与实际版本一致
- [ ] `.gitignore` 覆盖新的数据目录

---

## 八、贡献回本项目

若你完成了向其他版本的移植，**欢迎提交 Pull Request**：
不仅代码有价值，**「某版本的数据修复经验」同样宝贵**。

请在提交中说明：

- 目标版本与核心
- 数据缺失的具体表现
- 修复方式
- 验证方法

---

[返回顶部](#移植指南--porting)
