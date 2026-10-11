#!/usr/bin/env python3
"""
dbc_import.py - parse WDBC files into SQL INSERT statements.

Written because the dbimport.exe shipped with this fork only runs the SQL
updater: Main.cpp calls StartDB() then immediately logs "Halting process...",
so it never touches a DBC. This does the tables directly.

Field layout comes from the core's own DBCfmt.h, e.g.

    LFGDungeonEntryfmt[] = "nssssssssssssssssxiiiiiiiiixxixixxxxxxxxxxxxxxxxx";
    SpellEntryfmt[]     = "niiiiiiiiiiiixixiiii...sss...xx...xfffxxxiiiiixxfffxx";

  n = uint32 (first field of the struct)
  s = std::string  -> byte offset into the file's trailing string block
  i = uint32
  f = float
  x = padding / unused, skipped
  d = uint32 stored as a string (bits), written as a quoted decimal

Header layout is probed rather than assumed (this fork's DBCs carry an extra
int32 between record_count and record_size) and every file is checked against
    20 + count * rec_size + str_size == len(file)
so a mismatched file fails loudly instead of writing garbage.

Strings are emitted as CONVERT(0x.. USING utf8mb4): the box's locale is zh-CN
with codepage 936, so the mysql client decodes a redirected SQL file as GBK
and mangles UTF-8 names unless the bytes are passed through opaquely.
"""

import struct
import sys

WDBC_MAGIC = b"WDBC"


def _parse_header(blob):
    canonical = struct.unpack_from("<3i", blob, 4)     # count, rec, str
    withfield = struct.unpack_from("<4i", blob, 4)     # count, fields, rec, str

    cands = [canonical, (withfield[0], withfield[2], withfield[3])]
    for count, rec, strs in cands:
        if rec <= 0 or count < 0 or strs < 0:
            continue
        if 20 + count * rec + strs == len(blob):
            return count, rec, strs
    raise SystemExit("header does not match the file length (%d bytes); tried %r"
                     % (len(blob), cands))


def read_dbc(path, fmt):
    """Return a list of dicts keyed by position in the fmt string."""
    with open(path, "rb") as fh:
        blob = fh.read()

    if blob[:4] != WDBC_MAGIC:
        raise SystemExit("not a WDBC file (magic %r)" % blob[:4])

    count, rec_size, str_size = _parse_header(blob)

    expect = len(fmt) * 4
    if rec_size != expect:
        raise SystemExit(
            "record size %d does not match format string (%d fields => %d bytes)"
            % (rec_size, len(fmt), expect))

    str_base = 20 + count * rec_size
    rows = []
    for i in range(count):
        off = 20 + i * rec_size
        row = {}
        for j, ch in enumerate(fmt):
            (raw,) = struct.unpack_from("<i", blob, off + j * 4)
            if ch == "s":
                if raw == 0 or raw >= str_size:
                    row[j] = ""
                else:
                    end = blob.index(b"\0", str_base + raw)
                    row[j] = blob[str_base + raw:end].decode("utf-8", "replace")
            elif ch == "f":
                row[j] = struct.unpack_from("<f", blob, off + j * 4)[0]
            elif ch == "d":
                row[j] = str(raw)
            elif ch == "x":
                pass
            else:
                row[j] = raw
        rows.append(row)
    return rows


def sql_str(v):
    if v is None:
        return "NULL"
    if v == "":
        return "''"
    data = str(v).encode("utf-8")
    if data.isascii():
        return "'" + str(v).replace("\\", "\\\\").replace("'", "\\'") + "'"
    return "CONVERT(0x" + data.hex().upper() + " USING utf8mb4)"


def num(v):
    if v is None:
        return "0"
    if isinstance(v, float):
        return repr(v)
    # The file stores these as uint32 but struct.unpack gives a signed int, and
    # several spell_dbc columns are BIGINT UNSIGNED - a negative literal is
    # rejected in strict mode. Emit the unsigned 32-bit value instead.
    return str(int(v) & 0xFFFFFFFF)


def coerce(v, dtype, ch):
    """Render one value so it fits its column.

    The DBC holds uint32 for every integer field, but spell_dbc mixes signed
    INT columns with 115 `int unsigned` ones plus two `bigint unsigned`, and
    MySQL strict mode rejects whichever end of the range does not fit. So the
    value is re-signed per column rather than globally - hence COLUMN_TYPE
    (which keeps the `unsigned` flag) rather than DATA_TYPE.
    """
    if ch in "xd":
        # FT_NA / FT_SORT: the loader consumes the column and then ignores it.
        return "0"
    if ch == "s":
        return sql_str(v)
    if ch == "f":
        return repr(float(v or 0))
    iv = int(v or 0) & 0xFFFFFFFF
    if "unsigned" not in dtype and iv >= 0x80000000:
        iv -= 0x100000000          # signed INT column
    return str(iv)


def build(table, cols, rows, delete_where=None, batch=500):
    """Emit the statements that replace the retail portion of `table`.

    delete_where is a WHERE clause on the ID column, or None to truncate.
    A plain TRUNCATE here would drop the server's own spells (ID >= 100000),
    which live only in this table, so spell_dbc passes 'ID < 100000'.
    """
    out = ["SET FOREIGN_KEY_CHECKS=0;"]
    if delete_where:
        out.append("DELETE FROM `%s` WHERE %s;" % (table, delete_where))
    else:
        out.append("TRUNCATE TABLE `%s`;" % table)
    out.append("SET FOREIGN_KEY_CHECKS=1;")

    collist = ",".join("`%s`" % c[0] for c in cols)
    for start in range(0, len(rows), batch):
        vals = []
        for r in rows[start:start + batch]:
            cells = [coerce(r.get(idx), c[2] if len(c) > 2 else "", c[1])
                     for idx, c in enumerate(cols)]
            vals.append("(" + ",".join(cells) + ")")
        out.append("INSERT INTO `%s` (%s) VALUES\n%s;"
                   % (table, collist, ",\n".join(vals)))
    return "\n".join(out)


def cols_from(prefix, fmt, names=None):
    """Build the (colname, char) list; the first fmt char is the ID column."""
    cols = []
    for i, ch in enumerate(fmt):
        if ch == "x":
            continue
        if names and i < len(names) and names[i]:
            cols.append((names[i], ch))
        else:
            cols.append(("%s_%d" % (prefix, i), ch))
    return cols


# ---------------------------------------------------------------- LFGDungeons

LFGDUNGEONS = "lfgdungeons_dbc"
LFGDUNGEONS_COLS = [
    ("ID", "n"),
    ("Name_Lang_enUS", "s"), ("Name_Lang_enGB", "s"), ("Name_Lang_koKR", "s"),
    ("Name_Lang_frFR", "s"), ("Name_Lang_deDE", "s"), ("Name_Lang_enCN", "s"),
    ("Name_Lang_zhCN", "s"), ("Name_Lang_enTW", "s"), ("Name_Lang_zhTW", "s"),
    ("Name_Lang_esES", "s"), ("Name_Lang_esMX", "s"), ("Name_Lang_ruRU", "s"),
    ("Name_Lang_ptPT", "s"), ("Name_Lang_ptBR", "s"), ("Name_Lang_itIT", "s"),
    ("Name_Lang_Unk", "s"),
    ("Name_Lang_Mask", "i"),
    ("MinLevel", "i"), ("MaxLevel", "i"),
    ("Target_Level", "i"), ("Target_Level_Min", "i"), ("Target_Level_Max", "i"),
    ("MapID", "i"), ("Difficulty", "i"), ("Flags", "i"), ("TypeID", "i"),
    ("Faction", "i"),
    ("TextureFilename", "s"),
    ("ExpansionLevel", "i"), ("Order_Index", "i"), ("Group_Id", "i"),
    ("Description_Lang_enUS", "s"), ("Description_Lang_enGB", "s"),
    ("Description_Lang_koKR", "s"), ("Description_Lang_frFR", "s"),
    ("Description_Lang_deDE", "s"), ("Description_Lang_enCN", "s"),
    ("Description_Lang_zhCN", "s"), ("Description_Lang_enTW", "s"),
    ("Description_Lang_zhTW", "s"), ("Description_Lang_esES", "s"),
    ("Description_Lang_esMX", "s"), ("Description_Lang_ruRU", "s"),
    ("Description_Lang_ptPT", "s"), ("Description_Lang_ptBR", "s"),
    ("Description_Lang_itIT", "s"), ("Description_Lang_Unk", "s"),
    ("Description_Lang_Mask", "i"),
]

# --------------------------------------------------------------------- Spell

SPELL = "spell_dbc"
DBCFMT = r"D:\My Games\az335_build\azerothcore-wotlk\src\server\shared\DataStores\DBCfmt.h"


def load_fmt(entry_name, path=DBCFMT):
    """Read one `char constexpr <x>fmt[] = "...";` straight out of DBCfmt.h.

    Hand-copying these format strings is a trap: SpellEntryfmt is 234
    characters and a single dropped one silently shifts every column after it.
    DBCDatabaseLoader asserts record size against the same header, so reading it
    from there means the parser and the server can never disagree.
    """
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if entry_name not in line or "char constexpr" not in line:
                continue
            start = line.index('"')
            end = line.index('"', start + 1)
            return line[start + 1:end]
    raise SystemExit("%s not found in %s" % (entry_name, path))


SPELL_FMT = load_fmt("SpellEntryfmt")
LFGDUNGEONS_FMT = load_fmt("LFGDungeonEntryfmt")


def spell_cols(names, dtypes):
    """Pair the format string with the real column names/types from the table.

    DBCDatabaseLoader.cpp does `++sqlColumnNumber` *outside* its switch, so the
    table carries one column per format character - including the 'x' padding
    and 'd' sort slots, which the loader reads and then ignores.  Walking 1:1
    keeps that contract; skipping 'x' would silently shift every later column.
    """
    if len(names) != len(SPELL_FMT):
        raise SystemExit("format string has %d chars, table has %d columns - "
                         "column order does not match DBCfmt.h"
                         % (len(SPELL_FMT), len(names)))
    return [(names[i], SPELL_FMT[i], dtypes[i]) for i in range(len(names))]


def main():
    if len(sys.argv) < 4:
        raise SystemExit(
            "usage: dbc_import.py lfgdungeons <file.dbc> <out.sql>\n"
            "       dbc_import.py spell <file.dbc> <out.sql> <column-list-file>")
    what, src, dst = sys.argv[1], sys.argv[2], sys.argv[3]

    if what == "lfgdungeons":
        rows = read_dbc(src, LFGDUNGEONS_FMT)
        print("parsed %d records" % len(rows))
        sql = build(LFGDUNGEONS, LFGDUNGEONS_COLS, rows)
    elif what == "spell":
        with open(sys.argv[4], encoding="utf-8") as fh:
            rowsmeta = [l.rstrip("\n").split("\t") for l in fh if l.strip()]
        cols = spell_cols([m[0] for m in rowsmeta], [m[1] for m in rowsmeta])
        rows = read_dbc(src, SPELL_FMT)
        print("parsed %d records, %d columns" % (len(rows), len(cols)))
        retail = [r for r in rows if r.get(0, 0) < 100000]
        over = len(rows) - len(retail)
        print("importing %d retail records; %d record(s) with ID >= 100000 in the "
              "DBC are skipped" % (len(retail), over))
        # Only wipe the retail range - the server's own spells stay.
        sql = build(SPELL, cols, retail, delete_where="`ID` < 100000")
    else:
        raise SystemExit("unknown table %r" % what)

    with open(dst, "w", encoding="utf-8") as fh:
        fh.write(sql)
    print("wrote %s (%d bytes)" % (dst, len(sql.encode("utf-8"))))


if __name__ == "__main__":
    main()