# 常见问题排查 / TROUBLESHOOTING

本文件记录实际遇到并已定位的问题。**大部分「诡异现象」都源于数据不完整，
而非代码缺陷** —— 这是本项目最常见的踩坑模式。

---

## 快速诊断

启动后先检查这三项，可排除 80% 的问题：

```sql
-- 1. spell_dbc 是否完整（应为约 5 万行，若只有几千行则必然出问题）
SELECT COUNT(*) FROM acore_world.spell_dbc;

-- 2. 副本列表（应为 195 行）
SELECT COUNT(*) FROM acore_world.lfgdungeons_dbc;

-- 3. 是否有零护甲 bot（应为 0）
SELECT COUNT(*) FROM acore_characters.characters c
WHERE c.guid NOT IN (
  SELECT i.guid FROM acore_characters.character_inventory i
  JOIN acore_characters.item_instance ii ON ii.guid = i.item
  JOIN acore_world.item_template t ON t.entry = ii.itemEntry
  WHERE t.class = 4);
```

检查启动日志中的耗时分布：

```bash
grep -E "in [0-9]+ ms" logs/Server.log | sort -t' ' -k4 -rn | head -30
```

---

## 一、法术类问题

### 症状：`.learn <spell>` 成功，但施法时无反应或报「没有该法术」

**根因**：`spell_dbc` 表数据不完整。

**为什么数据库表会覆盖文件？**

```cpp
// DBCStores.cpp
if (storage.Load(dbcFilename.c_str()))              // 先加载 Spell.dbc 文件
    ...
if (dbTable)
    storage.LoadFromDB(dbTable, storage.GetFormat());  // 再用数据库表覆盖
```

**数据库表优先级更高**。残缺的表会覆盖正确的文件。

**诊断**：

```sql
SELECT ID FROM acore_world.spell_dbc WHERE ID IN (883, 982, 1515, 2641);
```

若返回空，说明该表缺少这些基础法术。

**修复**：使用 `scripts/dbc_import.py` 导入完整 `Spell.dbc`。

> **本项目实例**：修复前 4,518 行，ID 880–990 区间为 **0 行**，
> 导致召唤宠物(883)、复活宠物(982) 等完全无法使用。

---

## 二、角色数据类问题

### 症状：角色「光膀子」，但背包里有大量物品

**诊断**：

```sql
SELECT c.guid, c.class, c.level
FROM acore_characters.characters c
WHERE c.guid NOT IN (
  SELECT guid FROM acore_characters.character_inventory WHERE bag = 0 AND slot < 19);
```

**注意**：本核心的 `character_inventory` 列序为 `(guid, bag, slot, item)`，
与上游 AzerothCore 的 `(guid, item, bag, slot)` **不同**。查询时务必用列名。

> **本项目实例**：107 个 bot 完全没有护甲类物品，其中 24 个是 80 级。
> 他们不是「穿不上」，而是「没有」。mod-playerbots 的 `EquipUp` 无物可穿。

**修复**：`scripts/gear_up_naked_bots.py`

---

### 症状：猎人召唤宠物提示「没有可用的宠物」

**根因**：`character_pet.slot` 取值超出合法范围。

```cpp
// PetDefines.h
constexpr auto MAX_PET_STABLES = 4;
PET_SAVE_AS_CURRENT         =  0,
PET_SAVE_FIRST_STABLE_SLOT  =  1,
PET_SAVE_LAST_STABLE_SLOT   =  MAX_PET_STABLES,   // 1–4
```

**`slot >= 5` 的记录等同于「不在槽位」**，既不会被 `LoadPet()` 载入，
也无法被召唤。

**诊断**：

```sql
SELECT slot, COUNT(*) FROM acore_characters.character_pet GROUP BY slot;
```

若出现 100 之类的值，即为异常。

**修复**：将无活动宠物的猎人（`slot > 4` 且无 `slot = 0`）归位为 `slot = 0`：

```sql
UPDATE acore_characters.character_pet p
JOIN acore_characters.characters c ON c.guid = p.owner
SET p.slot = 0
WHERE p.slot > 4 AND c.class = 3
  AND p.owner NOT IN (
    SELECT owner FROM (SELECT owner FROM acore_characters.character_pet WHERE slot = 0) x);
```

> **注意**：子查询必须套一层派生表，否则 MySQL 报
> `ERROR 1093: You can't specify target table for update in FROM clause`。

---

## 三、AI 行为类问题

### 症状：某技能「从未触发过」

**排查方法**（本项目开发中最有效的手段）：

统计类上下文中注册的 action 与策略中引用的差集：

```bash
# 已注册的动作
grep -oP 'creators\["\K[^"]+' AiObjectContext.cpp | sort -u > /tmp/registered.txt

# 被策略引用的动作
grep -rhoP 'NextAction\("\K[^"]+' Strategy/ | sort -u > /tmp/referenced.txt

# 差集
comm -23 /tmp/registered.txt /tmp/referenced.txt
```

差集中大部分是策略名（`bm` / `surv` 等）属正常，
但「动作已实现却无人调用」的部分即为**接线遗漏**。

> **本项目实例**：猎人模块 84 个注册动作中有 35 个零引用，
> 包括 `aspect of the wild`（驯兽核心天赋）这类影响重大的遗漏。

---

### 症状：战斗中场/弹药耗尽后，bot 站着不动

检查是否缺少弹药相关触发器：

```
low ammo  /  no ammo  →  未接线时不会触发任何动作
```

本项目已在 `GenericHunterStrategy.cpp` 中补齐。

---

## 四、性能类问题

### 症状：启动超过 60 秒

**诊断**：

```bash
grep -oP 'in \K[0-9]+(?= ms)' logs/Server.log | sort -rn | head -10
```

**已知瓶颈**：`>> Loaded playerbots config` 曾达 22.4 秒（占总时间 52%）。

> **注意该日志行具有误导性** —— 它在 `PlayerbotAIConfig::Initialize()`
> 全部结束后才打印，覆盖整个 bot 初始化过程。
> 真实分布需看新增的 `>> [phase] <name>: N ms` 日志。

**相关修复**：见 [`../docs/ARCHITECTURE.md`](ARCHITECTURE.md) 第五节。

### 症状：编译时机器冻结

**固定使用 `-j 2`**。`-j 16` 会将可用内存压至 7 MB。

Windows 下不要使用 Windows 的 `Get-CimInstance Win32_OperatingSystem`
判断可用内存 —— 它的 `FreePhysicalMemory` 单位是 KB，直接比较会误判。

---

## 五、脚本类问题

### 症状：Eluna 脚本加载后菜单显示乱码 / 色码原样打印

**根因一：色码位数不足**

WoW 色码格式为 `|cAARRGGBB`（**8 位十六进制**）。

```
正确：  |cffffffff   （ff = alpha 全不透明）
错误：  |cffffff     （6 位，客户端解析失败 → 原样打印）
```

**根因二：行尾被转换为 LF**

Eluna 的脚本加载器对 LF-only 文件处理异常。

```python
# 错误写法 —— io.open() 会做通用换行转换（CRLF → LF）
with io.open(path, encoding="utf-8") as f:
    text = f.read()
with io.open(path, "w", encoding="utf-8", newline="") as f:
    f.write(text)

# 正确写法 —— 二进制读写
raw = open(path, "rb").read()
crlf = raw.count(b"\r\n") > 0
text = raw.decode("utf-8")
...
data = text.encode("utf-8")
if crlf:
    data = data.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
open(path, "wb").write(data)
```

**检查清单**：

```python
raw = open(path, "rb").read()
print(raw[:3] == b"\xef\xbb\xbf")           # BOM 应为 False
print(raw.count(b"\r\n"), raw.count(b"\n") - raw.count(b"\r\n"))  # 应为 (N, 0)
raw.decode("utf-8").count("\ufffd")         # 应为 0
```

---

## 六、通用排查原则

### 1. 先分清「代码问题」与「数据问题」

本项目 70% 的疑难问题源于数据。

典型判别方法：**若修改配置或数据后现象消失，优先怀疑数据。**

### 2. 注意核心版本差异

本 fork 的 `character_inventory` 列序与上游不同。
**任何 SQL 查询都用列名，不要用位置或 `SELECT *` 配合数字索引。**

### 3. 不要在 DB 中直接改玩家实例 ID

`character_inventory.item` 引用的是 `item_instance.guid`，不是
`item_template.entry`。插入数据时：

- `item` 值必须**全局唯一**（该列是主键）
- 新实例 GUID 起点须高于当前 `MAX(guid)` —— bot 在线时会持续创建新实例

### 4. 修改前先备份

```sql
CREATE TABLE xxx_backup AS SELECT * FROM xxx WHERE ...;
```

---

[返回顶部](#常见问题排查--troubleshooting)
