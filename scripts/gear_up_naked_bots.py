#!/usr/bin/env python3
"""
gear_up_naked_bots.py - give armor to bot characters that have none.

Why this exists
---------------
107 bot characters owned no item of class 4 (armor) at all - not badly
equipped, literally none - so they render naked in battlegrounds and
mod-playerbots' EquipUp had nothing to equip. Weapons, consumables and quest
items were present, which is why it looked like an equip bug rather than a
loot bug.

Inputs are TSVs dumped from MySQL (no driver is installed, so this stays a pure
file transformer):
    chars.tsv  guid \\t class \\t level
    gear.tsv   entry \\t InventoryType \\t AllowableClass \\t RequiredLevel
               \\t ItemLevel \\t MaxDurability

Output is SQL that clones a template item into a fresh item_instance row and
references it from character_inventory. character_inventory's primary key is
`item` alone - it stores the item_instance GUID, not item_template.entry - so
every new instance needs its own globally unique GUID.

Slot mapping is AzerothCore's EQUIPMENT_SLOT_* order; AllowableClass is a class
bitmask where 0 / -1 mean "all", which is what keeps plate off rogues.
"""

import sys

# InventoryType -> EQUIPMENT_SLOT_*
# Slots 10/11 are the two finger slots and 12/13 the two trinket slots, so those
# map to two destinations each; the caller takes distinct picks per slot.
SLOTS = {
    1: [0],    # HEAD
    2: [1],    # NECK
    3: [2],    # SHOULDERS
    5: [4],    # CHEST
    6: [5],    # WAIST
    7: [6],    # LEGS
    8: [7],    # FEET
    9: [8],    # WRISTS
    10: [9],   # HANDS
    11: [10, 11],   # FINGER x2
    12: [12, 13],   # TRINKET x2
    14: [16],       # SHIELD / offhand
    16: [14],       # CLOAK / back
    13: [15],       # 1H weapon -> mainhand
    17: [15],       # 2H weapon -> mainhand
    15: [17],       # ranged (wand/gun)
    26: [17],       # bow
    27: [17],       # crossbow / gun
}

# Two-handed weapons cannot share the mainhand with a shield, and casters have
# no use for one - dropping the offhand for them keeps the set sane.
NO_OFFHAND_CLASSES = {5, 8, 9}          # priest, mage, warlock
TWO_HAND_ONLY = {17, 26, 27}

# item_template.subclass -> armor type. This world DB marks many plate pieces
# AllowableClass = 1535 (= every class), and the server honours that, so the
# bitmask alone hands a rogue a plate chest. The subclass rule is the real WoW
# restriction and has to be applied on top.
ALLOWED_SUBCLASS = {
    1:  {1, 3, 4},      # warrior: cloth, mail, plate
    2:  {1, 4},         # paladin: cloth, plate
    3:  {1, 3},         # hunter: cloth, mail
    4:  {1, 2},         # rogue: cloth, leather
    5:  {1},            # priest: cloth
    6:  {1, 4},         # death knight: cloth, plate
    7:  {1, 3},         # shaman: cloth, mail
    8:  {1},            # mage: cloth
    9:  {1},            # warlock: cloth
    10: {1, 2},         # druid: cloth, leather
    11: {1, 2},         # monk: cloth, leather
}


def class_bit(cls):
    # CLASS_* enum: 1 WARRIOR, 2 PALADIN, 3 HUNTER, 4 ROGUE, 5 PRIEST,
    # 6 DEATH_KNIGHT, 7 SHAMAN, 8 MAGE, 9 WARLOCK, 10 DRUID, 11 MONK
    return 1 << (cls - 1)


def usable(allow, bit):
    # AllowableClass 0 / -1 is unrestricted in AzerothCore; anything else is a
    # class bitmask. Without this a rogue ends up in plate and CanEquipItem
    # rejects it at load time - back to naked.
    if allow in (0, -1):
        return True
    return bool(allow & bit)


def main():
    chars_path, gear_path, out_path, base_guid, ench_path = sys.argv[1:6]
    base_guid = int(base_guid)

    with open(ench_path, encoding="ascii") as fh:
        plain_ench = fh.read().strip()

    chars = []
    with open(chars_path, encoding="utf-8") as fh:
        for line in fh:
            g, c, lv = line.split()
            chars.append((int(g), int(c), int(lv)))

    # (slot, invtype) -> candidates, later filtered per character
    best = {}
    with open(gear_path, encoding="utf-8") as fh:
        for line in fh:
            e, it, sub, allow, req, ilvl, dura = (int(x) for x in line.split())
            for slot in SLOTS.get(it, []):
                best.setdefault((slot, it), []).append((ilvl, e, req, dura, allow, sub))

    inst_rows, inv_rows = [], []
    next_guid = base_guid
    skipped = 0

    for guid, cls, level in chars:
        bit = class_bit(cls)
        ok_subs = ALLOWED_SUBCLASS.get(cls, {1})
        chosen = {}
        for (slot, invtype), cands in sorted(best.items()):
            if slot in chosen:
                continue
            ok = [c for c in cands
                  if c[2] <= level and usable(c[4], bit) and c[5] in ok_subs]
            if not ok:
                continue
            # highest item level wins; entry is the tiebreak so reruns are stable
            ilvl, entry, req, dura, allow, sub = max(ok, key=lambda c: (c[0], -c[1]))
            chosen[slot] = (ilvl, entry, dura, invtype)

        main_invtype = chosen.get(15, (0, 0, 0, 0))[3]
        if cls in NO_OFFHAND_CLASSES or main_invtype in TWO_HAND_ONLY:
            chosen.pop(16, None)

        if not chosen:
            skipped += 1
            continue

        for slot, (ilvl, entry, dura, invtype) in sorted(chosen.items()):
            next_guid += 1
            inst_rows.append((next_guid, entry, guid, dura))
            inv_rows.append((guid, 0, slot, next_guid))

    out = ["SET FOREIGN_KEY_CHECKS=0;"]
    out.append("-- %d characters equipped, %d item instances created"
               % (len(chars) - skipped, len(inst_rows)))
    for i in range(0, len(inst_rows), 400):
        vals = ["(%d,%d,%d,0,0,1,0,0,0,'%s',0,%d,0,'')"
                % (g, e, o, plain_ench, d)
                for g, e, o, d in inst_rows[i:i + 400]]
        out.append("INSERT INTO `acore_characters`.`item_instance` "
                   "(guid,itemEntry,owner_guid,creatorGuid,giftCreatorGuid,count,"
                   "duration,charges,flags,enchantments,randomPropertyId,"
                   "durability,playedTime,text) VALUES\n%s;" % ",\n".join(vals))
    for i in range(0, len(inv_rows), 400):
        vals = ["(%d,%d,%d,%d)" % r for r in inv_rows[i:i + 400]]
        out.append("INSERT INTO `acore_characters`.`character_inventory` "
                   "(guid,bag,slot,item) VALUES\n%s;" % ",\n".join(vals))
    out.append("SET FOREIGN_KEY_CHECKS=1;")

    with open(out_path, "w", encoding="ascii") as fh:
        fh.write("\n".join(out))

    print("characters: %d, skipped(未找到可用装备): %d" % (len(chars), skipped))
    print("item_instance rows: %d" % len(inst_rows))
    print("character_inventory rows: %d" % len(inv_rows))
    print("next free instance guid: %d" % next_guid)


if __name__ == "__main__":
    main()