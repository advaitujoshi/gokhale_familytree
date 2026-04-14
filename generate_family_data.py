import json
import re
import zipfile
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

XLSX_PATH = Path("/Users/unmeshjoshi/Downloads/family details - Updated as of 23022026.xlsx")
OUTPUT_PATH = Path("/Users/unmeshjoshi/work/familytree/family-data.js")
NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"

IGNORE_NAMES = {"Legends:"}
IGNORE_PATTERNS = [
    re.compile(r"^\d+(?:st|nd|rd|th)-generation$", re.I),
    re.compile(r"^\d+(?:st|nd|rd|th)\s+generation$", re.I),
]

CODE_WITH_NAME_RE = re.compile(
    r"^((?:[A-E](?:\.\d+)+\.?|[A-E]\.))(?:\s+-?\s*|\s*-\s*)(.+)$"
)
CODE_ONLY_RE = re.compile(r"^(?:[A-E](?:\.\d+)+\.?|[A-E]\.?$)$")
MOBILE_RE = re.compile(r"mob(?:ile|lie)?\s*[:\-]?\s*([+()\d\s]{7,})", re.I)
EMAIL_RE = re.compile(r"([A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,})", re.I)


def col_to_num(col):
    value = 0
    for char in col:
        value = value * 26 + ord(char) - 64
    return value


def num_to_col(num):
    value = ""
    while num:
        num, rem = divmod(num - 1, 26)
        value = chr(65 + rem) + value
    return value


def parse_ref(ref):
    match = re.match(r"([A-Z]+)(\d+)", ref)
    return match.group(1), int(match.group(2))


def normalize(text):
    text = (text or "").lower()
    text = text.replace("late", " ")
    text = re.sub(r"\([^)]*\)", " ", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def slugify(text):
    return normalize(text).replace(" ", "-") or "member"


def code_depth(code):
    return code.count(".") + 1 if code else 0


def last_code_index(code):
    try:
        return int(code.rsplit(".", 1)[1])
    except (IndexError, ValueError):
        return 0


def should_ignore(name):
    if not name or name in IGNORE_NAMES:
        return True
    return any(pattern.match(name.strip()) for pattern in IGNORE_PATTERNS)


def parse_value(value):
    if not value:
        return None, ""
    match = CODE_WITH_NAME_RE.match(value)
    if match:
        return match.group(1).rstrip("."), match.group(2).strip()
    if CODE_ONLY_RE.match(value):
        return value.rstrip("."), ""
    return None, value


def load_workbook_cells():
    with zipfile.ZipFile(XLSX_PATH) as archive:
        strings = []
        sst = ET.fromstring(archive.read("xl/sharedStrings.xml"))
        for shared_item in sst:
            strings.append("".join(node.text or "" for node in shared_item.iter(NS + "t")))

        def read_sheet_rows(sheet_path):
            root = ET.fromstring(archive.read(sheet_path))
            rows = []
            for row in root.find(NS + "sheetData"):
                values = []
                for cell in row:
                    ref = cell.attrib["r"]
                    cell_type = cell.attrib.get("t")
                    value_node = cell.find(NS + "v")
                    if value_node is None:
                        inline = cell.find(NS + "is")
                        value = (
                            "".join(node.text or "" for node in inline.iter(NS + "t"))
                            if inline is not None
                            else ""
                        )
                    else:
                        value = value_node.text
                        if cell_type == "s":
                            value = strings[int(value)]
                    values.append((ref, value.strip() if isinstance(value, str) else value))
                rows.append(values)
            return rows

        cells = {}
        for row in read_sheet_rows("xl/worksheets/sheet1.xml"):
            for ref, value in row:
                if value:
                    cells[ref] = value

        comments = {}
        comments_root = ET.fromstring(archive.read("xl/comments1.xml"))
        for comment in comments_root.find(NS + "commentList"):
            comments[comment.attrib["ref"]] = "".join(
                node.text or "" for node in comment.iter(NS + "t")
            ).strip()

        contacts = defaultdict(dict)
        for sheet_path in ["xl/worksheets/sheet2.xml", "xl/worksheets/sheet3.xml"]:
            for row in read_sheet_rows(sheet_path):
                values = {parse_ref(ref)[0]: value for ref, value in row}
                name = (values.get("B") or "").strip()
                if not name or name == "Name":
                    continue
                if values.get("C"):
                    contacts[normalize(name)]["mobile"] = values["C"]
                if values.get("D"):
                    contacts[normalize(name)]["email"] = values["D"]
                if values.get("E"):
                    contacts[normalize(name)]["birthday"] = values["E"]

    return cells, comments, contacts


def parse_entries_by_column(cells, comments):
    entries_by_col = defaultdict(list)
    used = set()
    min_col = col_to_num("I")
    max_col = col_to_num("BY")

    for row in range(1, 120):
        col = min_col
        while col <= max_col:
            ref = f"{num_to_col(col)}{row}"
            if ref in used or ref not in cells:
                col += 1
                continue

            value = cells[ref]
            code, name = parse_value(value)
            pair_col = col if (col - min_col) % 2 == 0 else col - 1

            if code and name:
                entries_by_col[pair_col].append(
                    {
                        "row": row,
                        "col": pair_col,
                        "sourceCode": code,
                        "name": name,
                        "ref": ref,
                        "comment": comments.get(ref, ""),
                    }
                )
                used.add(ref)
            elif code and not name:
                next_col = col + 1
                next_ref = f"{num_to_col(next_col)}{row}"
                next_value = cells.get(next_ref, "")
                next_code, _ = parse_value(next_value)
                if next_value and not next_code:
                    entries_by_col[pair_col].append(
                        {
                            "row": row,
                            "col": pair_col,
                            "sourceCode": code,
                            "name": next_value,
                            "ref": next_ref,
                            "comment": comments.get(next_ref) or comments.get(ref, ""),
                        }
                    )
                    used.add(ref)
                    used.add(next_ref)
                else:
                    entries_by_col[pair_col].append(
                        {
                            "row": row,
                            "col": pair_col,
                            "sourceCode": code,
                            "name": "",
                            "ref": ref,
                            "comment": comments.get(ref, ""),
                        }
                    )
                    used.add(ref)
            else:
                entries_by_col[pair_col].append(
                    {
                        "row": row,
                        "col": pair_col,
                        "sourceCode": None,
                        "name": value,
                        "ref": ref,
                        "comment": comments.get(ref, ""),
                    }
                )
                used.add(ref)

            col += 1

    ordered_columns = []
    for col in sorted(entries_by_col):
        filtered = [
            entry
            for entry in entries_by_col[col]
            if entry["sourceCode"] or not should_ignore(entry["name"])
        ]
        if filtered:
            ordered_columns.append((col, filtered))
    return ordered_columns


def build_member(entry, member_id_counts, contacts):
    base_slug = slugify(entry["name"])
    member_id_counts[base_slug] += 1
    member_id = base_slug if member_id_counts[base_slug] == 1 else f"{base_slug}-{member_id_counts[base_slug]}"

    key = normalize(entry["name"])
    record = dict(contacts.get(key, {}))
    comment = entry.get("comment", "")
    if comment:
        mobile_match = MOBILE_RE.search(comment)
        email_match = EMAIL_RE.search(comment)
        if mobile_match and not record.get("mobile"):
            record["mobile"] = " ".join(mobile_match.group(1).split())
        if email_match and not record.get("email"):
            record["email"] = email_match.group(1)

    member = {
        "id": member_id,
        "name": entry["name"],
        "photo": f"images/{slugify(entry['name'])}.jpg",
    }
    if entry.get("effectiveCode"):
        member["code"] = entry["effectiveCode"]
    if entry.get("sourceCode") and entry["sourceCode"] != entry.get("effectiveCode"):
        member["sourceCode"] = entry["sourceCode"]
    for field in ("mobile", "email", "birthday"):
        if record.get(field):
            member[field] = record[field]
    return member


def regenerate_data():
    cells, comments, contacts = load_workbook_cells()
    column_entries = parse_entries_by_column(cells, comments)

    units = []
    units_by_code = {}
    units_by_id = {}
    children_by_parent = defaultdict(list)
    sibling_counts = defaultdict(int)
    uncoded_counts = defaultdict(int)
    member_id_counts = defaultdict(int)
    coded_occurrences = []

    def create_unit(code=None, parent_id=None, title=""):
        if code:
            unit_id = f"code-{code.replace('.', '-')}"
        else:
            base = slugify(title or "family")
            uncoded_counts[base] += 1
            unit_id = f"uncoded-{base}" if uncoded_counts[base] == 1 else f"uncoded-{base}-{uncoded_counts[base]}"
        unit = {
            "id": unit_id,
            "parentId": parent_id,
            "code": code,
            "members": [],
        }
        units.append(unit)
        units_by_id[unit_id] = unit
        if code:
            units_by_code[code] = unit
        if parent_id:
            children_by_parent[parent_id].append(unit_id)
        return unit

    def nearest_prior_coded(entry):
        candidates = [
            occ
            for occ in coded_occurrences
            if occ["row"] <= entry["row"] and occ["col"] <= entry["col"]
        ]
        if not candidates:
            return None
        return min(
            candidates,
            key=lambda occ: ((entry["row"] - occ["row"]) * 10 + (entry["col"] - occ["col"])),
        )

    def nearest_prior_parent(entry, source_parent_code):
        candidates = [
            occ
            for occ in coded_occurrences
            if occ["sourceCode"] == source_parent_code
            and occ["row"] <= entry["row"]
            and occ["col"] <= entry["col"]
        ]
        if not candidates:
            return None
        return min(
            candidates,
            key=lambda occ: ((entry["row"] - occ["row"]) * 10 + (entry["col"] - occ["col"])),
        )

    root_entry = column_entries[0][1][0]
    root = create_unit(parent_id=None, title="Vireshwar Gokhale Family")
    root["id"] = "root-vireshwar-gokhale"
    units_by_id[root["id"]] = root
    root["members"].append(build_member(root_entry, member_id_counts, contacts))

    for column_index, (_, entries) in enumerate(column_entries):
        stack = {}
        current_unit = None
        last_coded_row = None
        first_coded_seen = False
        chain_parent = None
        pending_header_unit = None
        pending_header_row = None

        for entry_index, entry in enumerate(entries):
            if column_index == 0 and entry_index == 0 and entry["name"] == root_entry["name"]:
                continue

            source_code = entry["sourceCode"]

            if source_code:
                depth = code_depth(source_code)
                if depth == 1:
                    effective_code = source_code.split(".")[0]
                    parent_id = chain_parent["id"] if chain_parent else root["id"]
                    sibling_counts[root["id"]] = max(
                        sibling_counts[root["id"]], last_code_index(effective_code)
                    )
                else:
                    source_parent = source_code.rsplit(".", 1)[0]
                    parent_effective = stack.get(depth - 1)
                    parent_match = nearest_prior_parent(entry, source_parent)

                    if parent_match and (not parent_effective or parent_effective != source_parent):
                        parent_effective = parent_match["effectiveCode"]

                    if not parent_effective and current_unit and code_depth(current_unit["code"] or "") == depth - 1:
                        parent_effective = current_unit["code"]

                    if not parent_effective:
                        parent_effective = root["id"]

                    if parent_effective == root["id"]:
                        parent_id = root["id"]
                        parent_key = root["id"]
                    else:
                        parent_id = units_by_code[parent_effective]["id"]
                        parent_key = parent_effective

                    if parent_effective == source_parent and source_code not in units_by_code:
                        effective_code = source_code
                        sibling_counts[parent_key] = max(
                            sibling_counts[parent_key], last_code_index(effective_code)
                        )
                    else:
                        sibling_counts[parent_key] += 1
                        effective_code = (
                            f"{parent_effective}.{sibling_counts[parent_key]}"
                            if parent_effective != root["id"]
                            else source_code
                        )

                if effective_code in units_by_code:
                    unit = units_by_code[effective_code]
                else:
                    unit = create_unit(code=effective_code, parent_id=parent_id, title=entry["name"])

                if (
                    pending_header_unit
                    and pending_header_row is not None
                    and entry["row"] > pending_header_row
                    and effective_code != pending_header_unit["code"]
                    and not effective_code.startswith(f"{pending_header_unit['code']}.")
                ):
                    pending_header_unit = None
                    pending_header_row = None

                entry["effectiveCode"] = effective_code
                stack[depth] = effective_code
                for deeper in list(stack.keys()):
                    if deeper > depth:
                        del stack[deeper]

                current_unit = unit
                last_coded_row = entry["row"]
                first_coded_seen = True
                if entry["name"]:
                    unit["members"].append(build_member(entry, member_id_counts, contacts))
                    if unit is pending_header_unit and unit["members"]:
                        pending_header_unit = None
                        pending_header_row = None
                else:
                    pending_header_unit = unit
                    pending_header_row = entry["row"]
                coded_occurrences.append(
                    {
                        "code": effective_code,
                        "effectiveCode": effective_code,
                        "sourceCode": source_code,
                        "row": entry["row"],
                        "col": entry["col"],
                    }
                )
            else:
                if not first_coded_seen:
                    parent_id = chain_parent["id"] if chain_parent else root["id"]
                    node = create_unit(parent_id=parent_id, title=entry["name"])
                    node["members"].append(build_member(entry, member_id_counts, contacts))
                    chain_parent = node
                else:
                    target_unit = current_unit
                    if pending_header_unit:
                        current_code = (current_unit or {}).get("code") or ""
                        pending_code = pending_header_unit["code"] or ""
                        current_under_pending = current_code == pending_code or current_code.startswith(
                            f"{pending_code}."
                        )
                        if not current_under_pending:
                            target_unit = pending_header_unit
                    if not target_unit:
                        candidate = nearest_prior_coded(entry)
                        if candidate:
                            target_unit = units_by_code.get(candidate["code"], target_unit)
                    if target_unit:
                        target_unit["members"].append(build_member(entry, member_id_counts, contacts))

    payload = {
        "source": XLSX_PATH.name,
        "unitCount": len(units),
        "memberCount": sum(len(unit["members"]) for unit in units),
        "units": units,
    }
    OUTPUT_PATH.write_text(
        "window.familyTreeData = " + json.dumps(payload, ensure_ascii=True, separators=(",", ":")) + ";\n"
    )
    return payload


if __name__ == "__main__":
    result = regenerate_data()
    print(f"Wrote {OUTPUT_PATH} with {result['unitCount']} units and {result['memberCount']} members")
