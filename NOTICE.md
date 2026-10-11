# 第三方组件与授权声明 / NOTICE

**码头哥 2026 MS 战场版 (Matou 2026 MS Battleground Edition)**
版本 2026.10 · 发布日期 2026-10-10

---

## 一、上游基线

本项目基于以下上游项目构建。本项目**不是**上游的官方分支，
所有署名权归各自上游作者所有。

| 组件 | 仓库 | 基线提交 |
|---|---|---|
| AzerothCore (fork) | `https://github.com/mod-playerbots/azerothcore-wotlk.git` | `2a2211cd8f3d157da432ec0175ddd4b8a191931f` |
| mod-playerbots | `https://github.com/mod-playerbots/mod-playerbots.git` | `037c01418b5d01506917a3db9b44fd56ac5f965c` |

基线提交日期：2026-10-09 / 2026-10-02

---

## 二、模块清单与授权

本项目包含以下模块，**各自保留其原始授权**。
分发本项目时必须一并保留这些授权文件。

| 模块 | 来源仓库 | 授权 |
|---|---|---|
| mod-playerbots | mod-playerbots/mod-playerbots | **GPLv2** |
| mod-ale | mod-playerbots/azerothcore-wotlk | **GPLv3** |
| mod-challenge-modes | mod-playerbots/azerothcore-wotlk | 随核心 GPLv2 |
| mod-improved-bank | mod-playerbots/azerothcore-wotlk | 随核心 GPLv2 |
| mod-item-upgrade | mod-playerbots/azerothcore-wotlk | 随核心 GPLv2 |
| mod-npc-beastmaster | mod-playerbots/azerothcore-wotlk | 随核心 GPLv2 |
| mod-player-bot-level-brackets | mod-playerbots/azerothcore-wotlk | 随核心 GPLv2 |
| mod-random-enchants | mod-playerbots/azerothcore-wotlk | 随核心 GPLv2 |
| mod-ah-bot | azerothcore/mod-ah-bot | 随核心 GPLv2 |
| mod-autobalance | azerothcore/mod-autobalance | 随核心 GPLv2 |
| mod-transmog | azerothcore/mod-transmog | **AGPLv3** |
| mod-dungeon-clear | jrad7/mod-dungeon-clear | 见其 LICENSE |
| mod-individual-progression | ZhengPeiRu21/mod-individual-progression | **MIT** |

### 授权兼容性提示

- **GPLv2 传染性**：AzerothCore 与 mod-playerbots 为 GPLv2，
  任何包含其代码的衍生作品**必须整体以 GPLv2 发布**，
  并提供完整源码与 GPLv2 许可证全文。
- **AGPLv3 传染性（更强）**：`mod-transmog` 为 AGPLv3。
  若您的衍生作品包含该模块，则须额外遵守 AGPLv3 第 13 条 ——
  即**通过网络提供服务时也必须向用户提供对应源码**。
- **MIT**：`mod-individual-progression` 为 MIT，兼容性良好。
- **GPLv3**：`mod-ale` 为 GPLv3。GPLv2 与 GPLv3 **不兼容**，
  二者同时存在于同一分发物中时，须由使用者自行判断如何处理
  （通常是保留上游各自授权并分别声明，而非声称整体为单一版本）。

> 发布前建议由熟悉 GPL 合规的人士复核本节。
> 本文件为工程实践指引，不构成法律意见。

---

## 三、本项目自身的授权

本项目源代码以 **GNU General Public License v2.0 (GPLv2)** 发布，
许可证全文见 [`LICENSE`](LICENSE)。

**附加限制（非 GPL 条款，属自愿承诺）：**

> 本项目仅供**学习、开发与技术交流**使用，
> **禁止任何形式的商业用途**。
> 详见 [`DISCLAIMER.md`](DISCLAIMER.md)。

> ⚠️ **关于「禁止商用」在 GPLv2 下的效力**
>
> 这不是本项目的特殊顾虑，而是整个 AzerothCore 生态的共性问题。
> 参考上游的实际做法：
>
> - **AzerothCore 本身**采用纯 GPLv2，未附加任何非商用条款。其 README 原话：
>   "AzerothCore does in any case sponsor nor support illegal public servers.
>   If you use this project to run an illegal public server and not for testing
>   and learning it is your own personal choice."
> - **AzerothCore 曾尝试改用 AGPL 并被迫回退**（2024-09 公告 #19868）。
>   原因：其代码源自 TrinityCore/MaNGOS 的 GPLv2+ 作品，
>   加 AGPL 在法律上不成立，官方自述为 "a mistake on our part"。
> - **mod-playerbots 各 fork 授权不一**（GPLv2 / AGPL），
>   但**没有任何一个添加非商用条款**。
>
> 法律层面，GPLv2 序言明确写道：
>
> > Activities other than copying, distribution and modification are not covered
> > by this License; they are outside its scope. **The act of running the Program
> > is not restricted.**
>
> 配合 §7「You may not impose any further restrictions on the recipients'
> exercise of the rights granted herein」，可得结论：
>
> **「能否运行服务器」根本不在 GPLv2 的管辖范围内，
> 因此不可能通过附加条款来约束。**
>
> 该声明的性质是：
> - 作者的**使用意愿声明**
> - 法律与伦理层面的**倡议**
> - 发生侵权时的**主张依据**
>
> 而非许可证层面的技术性封锁。
>
> **生态中真正约束商业化的是暴雪娱乐的著作权与 EULA**
> ——任何人在未获授权的情况下运营商业 WoW 服务器，
> 均违反暴雪的用户许可协议，可被 DMCA 下架。
> 本项目通过**不分发任何暴雪数据**来降低该风险，
> 但这并不能替代用户自身的合规判断。
>
> **当前决策：保持 GPLv2 以确保与上游兼容与可贡献性，
> 合规风险由使用者自行承担。**

---

## 四、暴雪娱乐知识产权

本项目**不包含**任何暴雪娱乐的受版权保护内容。

下列内容**刻意未包含在发布包中**，其著作权归暴雪娱乐所有：

- `*.dbc` 客户端数据文件（Spell.dbc / Map.dbc / Talent.dbc 等）
- `data/maps/` 地图网格
- `data/mmaps/` 寻路网格
- `data/vmaps/` 可视化模型
- 客户端可执行文件、MPQ / CASC 资源包、贴图、模型、音效
- 实盘数据库转储（含用户角色数据与账号信息）

使用者须自行持有正版客户端并提取上述数据。

本项目与暴雪娱乐无任何隶属、授权、合作或背书关系。
World of Warcraft® 是暴雪娱乐的注册商标。

---

## 五、本项目自研部分

以下部分为原创，版权归本项目作者所有，以 GPLv2 发布：

| 文件 | 说明 |
|---|---|
| `lua_scripts/码头哥炉石.lua` | Eluna 传送炉石脚本（含配色重制）|
| `scripts/dbc_import.py` | DBC 解析导入工具，字段布局自动读自 `DBCfmt.h` |
| `scripts/gear_up_naked_bots.py` | 批量装备分配工具 |
| `scripts/restyle_hstone.py` | 脚本配色规范化工具 |
| `patches/core_azerothcore.patch` | 核心侧修改（战场 AI、训练师、ThreatManager）|
| `patches/mod-playerbots.patch` | mod-playerbots 侧修改（职业策略、猎人、战场）|
| 本仓库全部 `*.md` 文档 | README / CHANGELOG / NOTICE / AUTHORS 等 |

上游文件仅作**最小必要修改**，修改内容全部以 patch 形式单独提供，
未修改的上游文件版权归原作者所有。

---

## 六、致谢

完整致谢见 [`AUTHORS.md`](AUTHORS.md)。

本项目站在巨人的肩膀上，特别感谢：

- **AzerothCore 团队** —— 让 WoW 3.3.5 服务器端重新开源成为可能
- **mod-playerbots 团队** —— 提供了功能最完整的 AI 机器人框架
- **所有上游模块维护者**

---

[返回顶部](#第三方组件与授权声明--notice)
