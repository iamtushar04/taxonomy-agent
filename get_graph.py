# """
# Extract a header taxonomy (1 to N levels) from an Excel sheet, auto-detecting
# where the header block is and how many rows deep it goes -- no need to know
# the row numbers in advance.

# Handles both styles:
#   - Multi-level merged headers (e.g. "Properties" -> "Mechanical" -> "Tensile
#     Strength" spread across 2-3 rows with merged cells).
#   - Flat single-row headers (a normal one-row column header).

# Usage:
#     # auto-detect everything
#     python extract_header_taxonomy.py "file.xlsx" "Sheet Name" --out tree.json

#     # auto-detect but override if it gets something wrong
#     python extract_header_taxonomy.py "file.xlsx" "Sheet Name" \
#         --rows 4 5 6 --start-col 2 --out tree.json

#     # scan every sheet in the workbook and report what was found
#     python extract_header_taxonomy.py "file.xlsx" --list-sheets

# Requires: openpyxl  (pip install openpyxl --break-system-packages)

# LIMITATIONS (read before trusting this on an unfamiliar file):
#   - Assumes the header sits above a block of row-based tabular data, with
#     the header rows more "label-like" (short strings) than the data rows.
#   - Works best when there IS an obvious first data row shortly below the
#     header (a numeric ID column, a long text field, etc). Sheets with no
#     such signal, oddly shaped reports, dashboards, or cover pages can
#     produce a wrong or empty guess -- use --rows / --start-col to override.
#   - Only detects ONE header block per sheet (the first one it finds in the
#     first `--scan-rows` rows, default 30). A sheet with several separate
#     mini-tables stacked on top of each other needs manual row ranges.
# """

# import argparse
# import json
# import openpyxl


# # ---------- detection heuristics ----------

# def _looks_like_banner(merged_range, max_col):
#     """A merge spanning almost the full sheet width is a title banner, not
#     a grouped column header -- exclude it."""
#     width = merged_range.max_col - merged_range.min_col
#     return merged_range.min_col <= 3 and merged_range.max_col >= max_col - 3 and width > 6


# def _header_like(ws, row, max_col):
#     """True if a row is mostly short text labels (typical of a header)."""
#     values = [ws.cell(row=row, column=c).value for c in range(1, max_col + 1)]
#     non_empty = [v for v in values if v is not None]
#     if len(non_empty) < 3:
#         return False
#     short_strings = [v for v in non_empty if isinstance(v, str) and len(v) < 60]
#     return len(short_strings) / len(non_empty) > 0.7


# def _row_has_seq_start(ws, row, max_col, scan_width=6):
#     """True if the row contains a literal 1 in one of the first few columns
#     -- a strong signal this is the first data row of an 'S.No'-style table."""
#     for c in range(1, min(max_col, scan_width) + 1):
#         if ws.cell(row=row, column=c).value == 1:
#             return True
#     return False


# def _row_is_data_like(ws, row, max_col):
#     values = [ws.cell(row=row, column=c).value for c in range(1, max_col + 1)]
#     non_empty = [v for v in values if v is not None]
#     if not non_empty:
#         return False
#     numeric = sum(1 for v in non_empty if isinstance(v, (int, float)))
#     long_text = sum(1 for v in non_empty if isinstance(v, str) and len(v) > 60)
#     return (numeric + long_text) > 0 or _row_has_seq_start(ws, row, max_col)


# def detect_header_block(ws, scan_rows=30):
#     """
#     Returns {'rows': [r1, r2, ...], 'start_col': c} or None if nothing
#     resembling a tabular header block was found.
#     """
#     max_col = ws.max_column
#     if max_col == 0:
#         return None

#     row_merge_count = {}
#     for merged_range in ws.merged_cells.ranges:
#         if merged_range.min_row > scan_rows:
#             continue
#         if _looks_like_banner(merged_range, max_col):
#             continue
#         if (merged_range.max_col - merged_range.min_col) < 1:
#             continue
#         for r in range(merged_range.min_row, merged_range.max_row + 1):
#             row_merge_count[r] = row_merge_count.get(r, 0) + 1

#     real_header_rows = sorted(r for r, count in row_merge_count.items() if count >= 2)

#     if real_header_rows:
#         top = min(real_header_rows)
#         bottom = max(real_header_rows)
#         while _header_like(ws, bottom + 1, max_col) and not _row_has_seq_start(ws, bottom + 1, max_col):
#             bottom += 1
#     else:
#         top = bottom = None
#         for r in range(1, scan_rows):
#             if not _header_like(ws, r, max_col):
#                 continue
#             for lookahead in range(r + 1, min(r + 6, scan_rows)):
#                 if _row_is_data_like(ws, lookahead, max_col):
#                     top = bottom = r
#                     break
#             if top is not None:
#                 break
#         if top is None:
#             return None

#     start_col = None
#     for c in range(1, max_col + 1):
#         if any(ws.cell(row=r, column=c).value is not None for r in range(top, bottom + 1)):
#             start_col = c
#             break

#     return {"rows": list(range(top, bottom + 1)), "start_col": start_col}


# # ---------- taxonomy extraction ----------

# def row_value_map(ws, row, max_col):
#     values = {}
#     for merged_range in ws.merged_cells.ranges:
#         if merged_range.min_row <= row <= merged_range.max_row:
#             top_left_value = ws.cell(row=merged_range.min_row, column=merged_range.min_col).value
#             if top_left_value is not None:
#                 for col in range(merged_range.min_col, merged_range.max_col + 1):
#                     values[col] = top_left_value
#     for col in range(1, max_col + 1):
#         cell_value = ws.cell(row=row, column=col).value
#         if cell_value is not None and col not in values:
#             values[col] = cell_value
#     return values


# def build_taxonomy(ws, header_rows, start_col=1):
#     max_col = ws.max_column
#     row_maps = [row_value_map(ws, r, max_col) for r in header_rows]
#     columns = []
#     for col in range(start_col, max_col + 1):
#         levels = [row_maps[i].get(col) for i in range(len(header_rows))]
#         if any(levels):
#             columns.append({"col": col, "levels": levels})
#     return columns


# def to_nested_tree(columns):
#     tree = {}
#     for item in columns:
#         levels = [lvl for lvl in item["levels"] if lvl is not None]
#         node = tree
#         for depth, label in enumerate(levels):
#             is_leaf = depth == len(levels) - 1
#             if is_leaf:
#                 node.setdefault("__leaves__", [])
#                 if label not in node["__leaves__"]:
#                     node["__leaves__"].append(label)
#             else:
#                 node = node.setdefault(label, {})
#     return tree


# def print_tree(tree, indent=0):
#     for key, value in tree.items():
#         if key == "__leaves__":
#             for leaf in value:
#                 print("  " * indent + "- " + str(leaf))
#         else:
#             print("  " * indent + str(key))
#             print_tree(value, indent + 1)


# # ---------- CLI ----------

# def main():
#     parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
#     parser.add_argument("file", help="Path to the .xlsx file")
#     parser.add_argument("sheet", nargs="?", help="Sheet name (omit with --list-sheets)")
#     parser.add_argument("--rows", nargs="+", type=int, help="Override: header row numbers, top-level first")
#     parser.add_argument("--start-col", type=int, help="Override: first data column (1-indexed)")
#     parser.add_argument("--scan-rows", type=int, default=30, help="How many rows to scan when auto-detecting")
#     parser.add_argument("--out", help="Optional path to write JSON output")
#     parser.add_argument("--list-sheets", action="store_true", help="Just show detected header blocks for every sheet")
#     args = parser.parse_args()

#     wb = openpyxl.load_workbook(args.file, data_only=True)

#     if args.list_sheets:
#         for sheet_name in wb.sheetnames:
#             ws = wb[sheet_name]
#             block = detect_header_block(ws, args.scan_rows)
#             print(f"{sheet_name:30s} -> {block}")
#         return

#     if not args.sheet:
#         parser.error("sheet name is required unless using --list-sheets")

#     ws = wb[args.sheet]

#     if args.rows and args.start_col:
#         header_rows, start_col = args.rows, args.start_col
#     else:
#         detected = detect_header_block(ws, args.scan_rows)
#         if detected is None:
#             print(f"Could not auto-detect a header block on '{args.sheet}'. "
#                   f"Pass --rows and --start-col manually.")
#             return
#         header_rows = args.rows or detected["rows"]
#         start_col = args.start_col or detected["start_col"]
#         print(f"[auto-detected] rows={header_rows} start_col={start_col}\n")

#     columns = build_taxonomy(ws, header_rows, start_col)
#     tree = to_nested_tree(columns)

#     print_tree(tree)

#     if args.out:
#         with open(args.out, "w", encoding="utf-8") as f:
#             json.dump(
#                 {"header_rows": header_rows, "start_col": start_col, "columns": columns, "tree": tree},
#                 f, indent=2, ensure_ascii=False,
#             )
#         print(f"\nSaved JSON to {args.out}")


# if __name__ == "__main__":
#     main()


"""
Extract a header taxonomy (1 to N levels) from an Excel sheet, auto-detecting
where the header block is and how many rows deep it goes -- no need to know
the row numbers in advance.

Handles both styles:
  - Multi-level merged headers (e.g. "Properties" -> "Mechanical" -> "Tensile
    Strength" spread across 2-3 rows with merged cells).
  - Flat single-row headers (a normal one-row column header).

Usage:
    # auto-detect everything
    python extract_header_taxonomy.py "file.xlsx" "Sheet Name" --out tree.json

    # auto-detect but override if it gets something wrong
    python extract_header_taxonomy.py "file.xlsx" "Sheet Name" \
        --rows 4 5 6 --start-col 2 --out tree.json

    # scan every sheet in the workbook and report what was found
    python extract_header_taxonomy.py "file.xlsx" --list-sheets

Requires: openpyxl  (pip install openpyxl --break-system-packages)

LIMITATIONS (read before trusting this on an unfamiliar file):
  - Assumes the header sits above a block of row-based tabular data, with
    the header rows more "label-like" (short strings) than the data rows.
  - Works best when there IS an obvious first data row shortly below the
    header (a numeric ID column, a long text field, etc). Sheets with no
    such signal, oddly shaped reports, dashboards, or cover pages can
    produce a wrong or empty guess -- use --rows / --start-col to override.
  - Only detects ONE header block per sheet (the first one it finds in the
    first `--scan-rows` rows, default 30). A sheet with several separate
    mini-tables stacked on top of each other needs manual row ranges.
"""

import argparse
import csv
import io
import json
import os
import openpyxl


# ---------- detection heuristics ----------

def _looks_like_banner(merged_range, max_col):
    """A merge spanning almost the full sheet width is a title banner, not
    a grouped column header -- exclude it."""
    width = merged_range.max_col - merged_range.min_col
    return merged_range.min_col <= 3 and merged_range.max_col >= max_col - 3 and width > 6


def _header_like(ws, row, max_col):
    """True if a row is mostly short text labels (typical of a header)."""
    values = [ws.cell(row=row, column=c).value for c in range(1, max_col + 1)]
    non_empty = [v for v in values if v is not None]
    if len(non_empty) < 3:
        return False
    short_strings = [v for v in non_empty if isinstance(v, str) and len(v) < 60]
    return len(short_strings) / len(non_empty) > 0.7


def _row_has_seq_start(ws, row, max_col, scan_width=6):
    """True if the row contains a literal 1 in one of the first few columns
    -- a strong signal this is the first data row of an 'S.No'-style table."""
    for c in range(1, min(max_col, scan_width) + 1):
        if ws.cell(row=row, column=c).value == 1:
            return True
    return False


def _row_is_data_like(ws, row, max_col):
    values = [ws.cell(row=row, column=c).value for c in range(1, max_col + 1)]
    non_empty = [v for v in values if v is not None]
    if not non_empty:
        return False
    numeric = sum(1 for v in non_empty if isinstance(v, (int, float)))
    long_text = sum(1 for v in non_empty if isinstance(v, str) and len(v) > 60)
    return (numeric + long_text) > 0 or _row_has_seq_start(ws, row, max_col)


def detect_header_block(ws, scan_rows=30):
    """
    Returns {'rows': [r1, r2, ...], 'start_col': c} or None if nothing
    resembling a tabular header block was found.
    """
    max_col = ws.max_column
    if max_col == 0:
        return None

    row_merge_count = {}
    for merged_range in ws.merged_cells.ranges:
        if merged_range.min_row > scan_rows:
            continue
        if _looks_like_banner(merged_range, max_col):
            continue
        if (merged_range.max_col - merged_range.min_col) < 1:
            continue
        for r in range(merged_range.min_row, merged_range.max_row + 1):
            row_merge_count[r] = row_merge_count.get(r, 0) + 1

    real_header_rows = sorted(r for r, count in row_merge_count.items() if count >= 2)

    if real_header_rows:
        top = min(real_header_rows)
        bottom = max(real_header_rows)
        while _header_like(ws, bottom + 1, max_col) and not _row_has_seq_start(ws, bottom + 1, max_col):
            bottom += 1
    else:
        top = bottom = None
        for r in range(1, scan_rows):
            if not _header_like(ws, r, max_col):
                continue
            for lookahead in range(r + 1, min(r + 6, scan_rows)):
                if _row_is_data_like(ws, lookahead, max_col):
                    top = bottom = r
                    break
            if top is not None:
                break
        if top is None:
            return None

    start_col = None
    for c in range(1, max_col + 1):
        if any(ws.cell(row=r, column=c).value is not None for r in range(top, bottom + 1)):
            start_col = c
            break

    return {"rows": list(range(top, bottom + 1)), "start_col": start_col}


# ---------- taxonomy extraction ----------

def row_value_map(ws, row, max_col):
    values = {}
    for merged_range in ws.merged_cells.ranges:
        if merged_range.min_row <= row <= merged_range.max_row:
            top_left_value = ws.cell(row=merged_range.min_row, column=merged_range.min_col).value
            if top_left_value is not None:
                for col in range(merged_range.min_col, merged_range.max_col + 1):
                    values[col] = top_left_value
    for col in range(1, max_col + 1):
        cell_value = ws.cell(row=row, column=col).value
        if cell_value is not None and col not in values:
            values[col] = cell_value
    return values


def build_taxonomy(ws, header_rows, start_col=1):
    max_col = ws.max_column
    row_maps = [row_value_map(ws, r, max_col) for r in header_rows]
    columns = []
    for col in range(start_col, max_col + 1):
        levels = [row_maps[i].get(col) for i in range(len(header_rows))]
        if any(levels):
            columns.append({"col": col, "levels": levels})
    return columns


def to_nested_tree(columns):
    tree = {}
    for item in columns:
        levels = [lvl for lvl in item["levels"] if lvl is not None]
        node = tree
        for depth, label in enumerate(levels):
            is_leaf = depth == len(levels) - 1
            if is_leaf:
                node.setdefault("__leaves__", [])
                if label not in node["__leaves__"]:
                    node["__leaves__"].append(label)
            else:
                node = node.setdefault(label, {})
    return tree


def print_tree(tree, indent=0):
    for key, value in tree.items():
        if key == "__leaves__":
            for leaf in value:
                print("  " * indent + "- " + str(leaf))
        else:
            print("  " * indent + str(key))
            print_tree(value, indent + 1)


# ---------- CLI ----------

def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("file", help="Path to the .xlsx file")
    parser.add_argument("sheet", nargs="?", help="Sheet name (omit with --list-sheets)")
    parser.add_argument("--rows", nargs="+", type=int, help="Override: header row numbers, top-level first")
    parser.add_argument("--start-col", type=int, help="Override: first data column (1-indexed)")
    parser.add_argument("--scan-rows", type=int, default=30, help="How many rows to scan when auto-detecting")
    parser.add_argument(
        "--format", choices=["json", "text", "csv", "all"], default="all",
        help="Output format to save. 'json' = nested tree + flat column list. "
             "'text' = indented tree as a .txt file. 'csv' = one row per column, "
             "one column per header level. 'all' (default) = save all three.",
    )
    parser.add_argument(
        "--out",
        help="Optional output path/prefix. Defaults to '<input file name>_<sheet name>' "
             "in the same folder as the input file. The chosen --format's extension "
             "(.json/.txt/.csv) is added automatically.",
    )
    parser.add_argument("--list-sheets", action="store_true", help="Just show detected header blocks for every sheet")
    args = parser.parse_args()

    wb = openpyxl.load_workbook(args.file, data_only=True)

    if args.list_sheets:
        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            block = detect_header_block(ws, args.scan_rows)
            print(f"{sheet_name:30s} -> {block}")
        return

    if not args.sheet:
        parser.error("sheet name is required unless using --list-sheets")

    if args.sheet not in wb.sheetnames:
        parser.error(
            f"Sheet '{args.sheet}' not found. Available sheets: {wb.sheetnames}. "
            f"(Tip: run --list-sheets, and check for hidden trailing spaces in the name.)"
        )

    ws = wb[args.sheet]

    if args.rows and args.start_col:
        header_rows, start_col = args.rows, args.start_col
    else:
        detected = detect_header_block(ws, args.scan_rows)
        if detected is None:
            print(f"Could not auto-detect a header block on '{args.sheet}'. "
                  f"Pass --rows and --start-col manually.")
            return
        header_rows = args.rows or detected["rows"]
        start_col = args.start_col or detected["start_col"]
        print(f"[auto-detected] rows={header_rows} start_col={start_col}\n")

    columns = build_taxonomy(ws, header_rows, start_col)
    tree = to_nested_tree(columns)

    print_tree(tree)

    # Work out the output prefix: user-given, or derived from input file + sheet name.
    if args.out:
        prefix = args.out
    else:
        input_dir = os.path.dirname(os.path.abspath(args.file))
        input_base = os.path.splitext(os.path.basename(args.file))[0]
        safe_sheet = "".join(c if c.isalnum() or c in " _-" else "_" for c in args.sheet).strip()
        prefix = os.path.join(input_dir, f"{input_base}_{safe_sheet}_tree")

    formats = ["json", "text", "csv"] if args.format == "all" else [args.format]
    saved = []

    if "json" in formats:
        path = prefix + ".json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(
                {"header_rows": header_rows, "start_col": start_col, "columns": columns, "tree": tree},
                f, indent=2, ensure_ascii=False,
            )
        saved.append(path)

    if "text" in formats:
        path = prefix + ".txt"
        buf = io.StringIO()
        _print_tree_to(buf, tree)
        with open(path, "w", encoding="utf-8") as f:
            f.write(buf.getvalue())
        saved.append(path)

    if "csv" in formats:
        path = prefix + ".csv"
        depth = len(header_rows)
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["column_index"] + [f"level_{i+1}" for i in range(depth)])
            for item in columns:
                writer.writerow([item["col"]] + [v if v is not None else "" for v in item["levels"]])
        saved.append(path)

    print("\nSaved:")
    for path in saved:
        print(f"  {path}")


def _print_tree_to(buf, tree, indent=0):
    for key, value in tree.items():
        if key == "__leaves__":
            for leaf in value:
                buf.write("  " * indent + "- " + str(leaf) + "\n")
        else:
            buf.write("  " * indent + str(key) + "\n")
            _print_tree_to(buf, value, indent + 1)


if __name__ == "__main__":
    main()