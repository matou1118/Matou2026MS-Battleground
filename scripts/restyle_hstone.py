#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
restyle_hstone.py - 统一码头哥炉石.lua 的字体配色

问题
----
原脚本 488 处颜色码用了 26 种不同色相，其中大量是视觉重复：
  红 5 种 (e60000 b22222 cc0033 c41e3b 800000)
  绿 4 种 (32cd32 006400 548b54 2e8b57)
  蓝 3 种 (0070d0 2359ff 68ccef)
单页最乱的技能训练页(SKLMENU)同时出现 19 种颜色。
更糟的是「联盟训练师」用蓝、「部落训练师」用红 —— 但菜单文字里本来就
写着联盟/部落/中立，颜色是在重复编码同一件事。

做法
----
1. 阵营色 (联盟蓝/部落红/中立深绿) -> 白。文字已含信息，颜色不再重复。
2. 职业色 -> 官方 WoW 职业色，一眼可辨且全服一致。
3. 功能色收敛：绿系归一、橙系归一、红系归一，金色留给提示高亮。
4. 修掉一个格式错误：|ce6000080 有 10 位十六进制，客户端无法解析。
5. 图标尺寸不动。全文只有 35 和 15 两种，且 15 仅出现在 ENCMENU
   (双重附魔 388 个条目) —— 那里不缩小就会溢出翻页，是刻意设计。

脚本只替换 |cff...... 颜色码本身，字符串字面量、引号、逗号一律不动。
"""

import io
import re
import sys

# ---------------------------------------------------------------- 配色表
# 菜单底色是羊皮纸/金色，|cffffffff 白字几乎糊在底色上，看着比原来还难受。
# 正确做法不是换成别的颜色，而是**把色码整个去掉**，让文字走客户端默认色
# （即用户要的"默认黑色"）。
# 所以正文的目标值是空字符串，不是白色。
#
# 只保留两个职责：
#   - 危险红：不可逆操作，需要跳出来
#   - 提示金：确认框里要玩家看清的那个词（确认框底色深，金字读得清）
WHITE = ""                       # 删除色码，走默认色
RED = "ffff4040"
GOLD = "ffffd200"

FACTION = {
    "ff0070d0": WHITE,   # 联盟训练师
    "ff006400": WHITE,   # 中立
}
CLASS = {
    "ff8b4513": WHITE,   # 战士
    "ffc71585": WHITE,   # 圣骑
    "ff548b54": WHITE,   # 猎人
    "ff2359ff": WHITE,   # 萨满
    "ff68ccef": WHITE,   # 法师
    "ff9382c9": WHITE,   # 术士
}
FUNC = {
    "ff00ccff": WHITE,   # 传送青
    "ff32cd32": WHITE, "ff32cd99": WHITE, "ff00ff96": WHITE,
    "ff2e8b57": WHITE, "ff548b54": WHITE, "e6000080": WHITE,
    "ffff6600": WHITE, "ffcc6633": WHITE, "ff9932cc": WHITE,
    "ff2359ff": WHITE, "ffffffff": WHITE, "ffff70b8": WHITE,
    # 危险与不可逆操作
    "ff800000": RED, "ffe60000": RED, "ffb22222": RED,
    "ffcc0033": RED, "ffc41e3b": RED,
    # 确认框里的关键词
    "fff0f000": GOLD, "ffffff00": GOLD,
}

MAP = {}
MAP.update(FACTION)
MAP.update(CLASS)
MAP.update(FUNC)


def main(path):
    # 必须按二进制读写。io.open() 默认会做通用换行转换（\r\n -> \n），
    # 写回时 Lua 文件就从 CRLF 变成了 LF，Eluna 加载器解析 LF-only 文件
    # 会出错。第一次改色就是这么把行尾弄坏的。
    raw = open(path, "rb").read()
    crlf = raw.count(b"\r\n") > 0
    text = raw.decode("utf-8")
    original = text

    counts = {}

    def repl(m):
        raw = m.group(0)
        key = raw[2:].lower()          # 去掉 "|c"，与映射表键一致
        if key in MAP:
            counts[key] = counts.get(key, 0) + 1
            val = MAP[key]
            if not val:
                # 目标色是"默认色"——直接把色码删掉。
                # 残留的 |r 是合法的复位符，无害，留着。
                return ""
            # Gossip 菜单文本按 8 位 AARRGGBB 解析。映射表里写的是 6 位 RGB，
            # 少写开头的 alpha 字节会变成 |cffffff 这种 6 位码，客户端不认，
            # 原样打印出来菜单就花了。这里统一补 ff 不透明。
            if len(val) == 6:
                val = "ff" + val
            return "|c" + val
        counts["__miss__" + key] = counts.get("__miss__" + key, 0) + 1
        return raw

    # 主菜单那一段原本保留了 8 种分类色，但用户反馈"还是五颜六色"。
    # 现在全局只有白/红/金三色，主菜单也一并统一——分类靠图标和文字。
    text = re.sub(r"\|c[0-9a-fA-F]{6,8}", repl, text)

    if text == original:
        print("没有任何改动")
        return

    with open(path, "wb") as fh:
        data = text.encode("utf-8")
        if crlf:
            data = data.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
        fh.write(data)
    print("行尾: %s" % ("CRLF (已保持)" if crlf else "LF"))

    hit = sum(v for k, v in counts.items() if not k.startswith("__miss__"))
    miss = sum(v for k, v in counts.items() if k.startswith("__miss__"))
    print("替换 %d 处，未命中 %d 处" % (hit, miss))
    for k in sorted(k for k in counts if not k.startswith("__miss__")):
        print("    %-12s x%-4d -> %s" % (k, counts[k], MAP[k]))
    if miss:
        print("未命中（保留原样）:")
        for k in sorted(k for k in counts if k.startswith("__miss__")):
            print("    %-12s x%d" % (k[8:], counts[k]))

    after = sorted(set(m.group(0).lower() for m in re.finditer(r"\|c[0-9a-fA-F]{6,8}", text)))
    print("剩余颜色种类: %d" % len(after))
    print("  " + " ".join(c.replace("|c", "") for c in after))


if __name__ == "__main__":
    main(sys.argv[1])