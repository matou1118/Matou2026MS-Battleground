# 码头哥 2026 MS 战场版

> **Matou 2026 MS Battleground Edition**
> 面向《魔兽世界》3.3.5 (巫妖王之怒) 的 AI 机器人服务器端增强版本

[![License: GPL v2](https://img.shields.io/badge/License-GPL%20v2-blue.svg)](LICENSE)
[![禁止商用](https://img.shields.io/badge/%E7%A6%81%E6%AD%A2%E5%95%86%E7%94%A8-red.svg)](DISCLAIMER.md)
[![版本](https://img.shields.io/badge/version-2026.10-green.svg)](CHANGELOG.md)

> ⚠️ **本项目仅供学习、开发与技术交流，禁止任何商业用途。**
> 请先阅读 [`DISCLAIMER.md`](DISCLAIMER.md)。

---

## 这是什么

基于 **AzerothCore** 的《魔兽世界》3.3.5 服务器端，内置 **mod-playerbots**
AI 机器人框架，并针对**战场（Battleground）**场景做了深度强化。

与原版 mod-playerbots 的区别：

| 方面 | 原版 | 本项目 |
|---|---|---|
| 战场战术 | 通用脚本 | 动态回防、稳定岗位分配、主动接战 |
| 职业 AoE | 部分缺失 | 8 个职业补齐 |
| 猎人宠物 | 动作已注册但**无策略引用** | 完整接线，含驯兽核心天赋 |
| 数据完整性 | 依赖用户自行导入 | 提供校验与修复工具链 |
| 启动性能 | 22.4 秒空转 | 空输入提前返回 + 分项计时 |

---

## 特性

### 战场 AI

- **动态回防** —— 援军判定结合友军密度与目标距离，而非固定时间脚本
- **稳定岗位分配** —— 基于 GUID 的稳定哈希，避免角色在岗位间横跳
- **主动接战** —— 战场上不再无视敌方玩家，只打 NPC
- **感知扩展** —— 战场内 AoE 判定半径放宽至 ×2.5，高差容忍度提高

### 职业 AI

- 萨满、术士、德鲁伊、暗影牧师、法师（奥术 / 火）AoE 逻辑补齐
- 猎人：宠物复活 / 召唤 / 喂食、弹药管理、陷阱布置、毒药维持
- 驯兽专精：野生之灵（Aspect of the Wild）接入，核心天赋不再失效

### 传送炉石

`lua_scripts/码头哥炉石.lua` —— Eluna 服务端脚本，2,724 行

- 地图 / 副本 / 城市 / 风景点传送
- 职业技能训练师、商业技能训练师
- 幻化 / 雕文 / 双重附魔
- 定点传送与坐标记录
- **配色统一**：488 处色码由 26 种收敛为 2 种（详见 CHANGELOG）

---

## 快速开始

> ⚠️ **前置条件**：你必须**自行持有正版 WoW 3.3.5 客户端**。
> 本项目不包含也不分发任何暴雪娱乐的数据文件。

### 1. 环境要求

| 项目 | 最低 | 推荐 |
|---|---|---|
| 操作系统 | Windows 10 x64 | Windows 11 x64 |
| 内存 | 8 GB | 16 GB |
| 硬盘 | 30 GB | 60 GB |
| 数据库 | MySQL 8.0 | MySQL 8.0 |
| 编译器 | Visual Studio 2019 v16.5 | VS 2022 v17.x |
| CMake | 3.20+ | 3.25+ |
| 编译器并行度 | — | **固定 `-j 2`** |

> ⚠️ **并行度说明**：使用 `-j 16` 或更高会将可用内存压至 7 MB 并冻结机器。
> Windows 下务必使用 `-j 2`。

### 2. 获取源码

```bash
git clone <本仓库地址> azerothcore-wotlk
cd azerothcore-wotlk
git submodule update --init --recursive
```

### 3. 应用本项目补丁

```bash
# 核心侧修改（战场 AI、训练师、ThreatManager 修复）
git apply patches/core_azerothcore.patch

# mod-playerbots 侧修改（职业策略、猎人、战场）
cd modules/mod-playerbots
git apply ../../patches/mod-playerbots.patch
cd ../..
```

### 4. 编译

```bash
# Windows
cmake -B build -S . -DCMAKE_BUILD_TYPE=Release -DTOOLS=ON -DSCRIPTS=static -DPREPARE_DB=ON
cmake --build build --config Release -j 2
```

### 5. 提取客户端数据

将正版客户端路径填入 `build/bin/worldserver.conf` 的 `DataDir`，
然后运行：

```
build/bin/map_extractor.exe        # -> data/maps
build/bin/vmap4_extractor.exe      # -> data/vmaps
build/bin/mmaps_generator.exe      # -> data/mmaps
```

### 6. 初始化数据库

```bash
mysql -u root -p < data/sql/base/db_world/*.sql
mysql -u root -p < data/sql/base/db_auth/*.sql
mysql -u root -p < data/sql/base/db_characters/*.sql
```

### 7. 数据完整性校验（重要）

**本项目修复了大量此类问题，请务必执行校验。**

```bash
# 检查 spell_dbc 是否完整（正常应约 5 万行）
mysql -u root -p -e "SELECT COUNT(*) FROM acore_world.spell_dbc;"

# 检查副本列表（正常应为 195 行）
mysql -u root -p -e "SELECT COUNT(*) FROM acore_world.lfgdungeons_dbc;"
```

若数量异常，使用 [`scripts/dbc_import.py`](scripts/dbc_import.py) 修复：

```bash
python scripts/dbc_import.py spell <路径>/Spell.dbc spell_import.sql <列元数据.txt>
```

### 8. 部署炉石脚本

将 `lua_scripts/码头哥炉石.lua` 放入服务端 `lua_scripts/` 目录，
重启或执行 `.reload eluna`。

### 9. 启动

**启动顺序很重要**：

```
MySQL  →  worldserver  →  等待 8085 端口  →  authserver
```

理由：`Main.cpp` 在 authserver 启动前会将 realm 标记为 offline，
顺序错误会导致客户端无法连接。

---

## 配置

配置文件位于 `config-templates/`，部署时复制到服务端的 `configs/` 目录。

| 文件 | 说明 |
|---|---|
| `worldserver.conf` | 主配置，数据库连接、端口、性能参数 |
| `modules/playerbots.conf` | 机器人核心配置（约 2,700 行） |
| `modules/mod_*.conf` | 各模块配置 |

### 关键配置项

```ini
AiPlayerbot.MaxAddedBots = 40          # 单次最多招募 bot 数
AiPlayerbot.AddClassCommand = 1        # 允许 .playerbots bot addclass
AiPlayerbot.RandomBotJoinLfg = 0       # bot 不自主排随机副本
AiPlayerbot.botActiveAloneSmartScale = 0
```

### 常用命令

| 命令 | 说明 |
|---|---|
| `.playerbots bot addclass <职业>` | 招募该职业 bot（一次一个职业）|
| `.playerbots bot randomize` | 随机化 bot |
| `.playerbots bot remove` | 移除 bot |
| `.dc on` | 副本难度切换（**需队伍内有 bot 坦克且在副本内**）|

---

## 项目结构

```
.
├── README.md                  本文件
├── CHANGELOG.md               版本迭代说明
├── LICENSE                    GPLv2 全文
├── DISCLAIMER.md              免责声明 + 非商用声明
├── NOTICE.md                  第三方组件与授权声明
├── AUTHORS.md                 致谢
├── CONTRIBUTING.md            贡献指南
├── docs/
│   ├── ARCHITECTURE.md        架构与关键改动说明
│   ├── TROUBLESHOOTING.md     常见问题排查
│   └── PORTING.md             移植到其他版本
├── patches/
│   ├── core_azerothcore.patch 核心侧修改
│   └── mod-playerbots.patch   机器人模块修改
├── lua_scripts/
│   └── 码头哥炉石.lua          传送炉石脚本
├── config-templates/           配置模板（已脱敏）
└── scripts/
    ├── dbc_import.py           DBC 解析导入
    ├── gear_up_naked_bots.py   批量装备分配
    └── restyle_hstone.py       脚本配色规范化
```

---

## 开发工具说明

本项目的工具脚本均针对「数据完整性」问题，可独立使用。

### `dbc_import.py`

 AzerothCore 自带的 `dbimport.exe` 在本环境下只运行 SQL 更新器，
不加载 DBC。本工具直接解析 WDBC 文件并生成 SQL。

**特性**：

- 字段布局**自动从核心的 `DBCfmt.h` 读取**，不硬编码格式串
  （`SpellEntryfmt` 有 234 个字符，手抄极易错位且难以察觉）
- 自动探测文件头布局
- 按列类型逐列计算有符号/无符号表示，避免 `Out of range value`
- 中文名称以 `CONVERT(0x.. USING utf8mb4)` 输出，规避 CP936 客户端编码问题

### `gear_up_naked_bots.py`

为缺少护甲的 bot 分配职业适配装备。

> 注意：本项目的 `item_template` 中，部分板甲的 `AllowableClass` 被标记为
> `1535`（全职业）。因此工具在位掩码过滤之上，**额外叠加 subclass 硬规则**。

### `restyle_hstone.py`

炉石脚本配色规范化。**两个已踩过的坑已在脚本中处理**：

1. **色码必须是 8 位 `AARRGGBB`** —— 写成 6 位 RGB 会被客户端原样打印成乱码
2. **必须以二进制方式读写** —— 否则 CRLF 行尾会被转换成 LF，导致 Eluna 加载异常

---

## 已知问题

1. **随机副本客户端列表为空** —— 服务端数据完整，客户端 UI 不显示，待排查
2. **`item_template.spellid_*` 存在无效法术引用** —— 遗留告警
3. **商业训练师不按职业过滤** —— 沿用上游实现
4. **mod-playerbots 无正式版本** —— 仅 `master` / `test-staging` 滚动分支

详见 [`CHANGELOG.md`](CHANGELOG.md) 的「已知问题」章节。

---

## 相关项目

| 项目 | 链接 |
|---|---|
| AzerothCore | https://github.com/azerothcore/azerothcore-wotlk |
| mod-playerbots | https://github.com/mod-playerbots/mod-playerbots |
| AzerothCore Discord | https://discord.gg/ymYfU8rrUy |

---

## 许可

代码以 **GPLv2** 发布，详见 [`LICENSE`](LICENSE)。
第三方组件授权见 [`NOTICE.md`](NOTICE.md)。

**本项目仅供学习、开发与技术交流，禁止任何商业用途。**
详见 [`DISCLAIMER.md`](DISCLAIMER.md)。

---

## 免责声明

本项目与暴雪娱乐无任何隶属、授权、合作或背书关系。
World of Warcraft® 是暴雪娱乐的注册商标。
本项目不承担因使用本项目导致的账号封禁或数据损失责任。
