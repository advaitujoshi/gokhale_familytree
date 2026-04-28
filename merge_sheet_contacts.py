import json
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

WORKBOOK_PATH = Path("sheets/family details - Updated as of 23022026.xlsx")
DATA_PATH = Path("data/family-tree.from-html.js")
NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"


def read_shared_strings(archive):
    sst = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    return ["".join(node.text or "" for node in item.iter(NS + "t")) for item in sst]


def read_sheet_rows(archive, sheet_path, strings):
    root = ET.fromstring(archive.read(sheet_path))
    rows = []

    for row in root.find(NS + "sheetData"):
        values = {}
        for cell in row:
            ref = cell.attrib["r"]
            col = ""
            for char in ref:
                if char.isalpha():
                    col += char
                else:
                    break
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
                value = value_node.text or ""
                if cell_type == "s":
                    value = strings[int(value)]

            values[col] = value.strip()

        if values:
            rows.append(values)

    return rows

def load_data():
    text = DATA_PATH.read_text(encoding="utf-8")
    payload = json.loads(text.split("=", 1)[1].rsplit(";", 1)[0].strip())
    return text, payload


def write_data(payload):
    DATA_PATH.write_text(
        "window.familyTreeData = " + json.dumps(payload, indent=2, ensure_ascii=True) + ";\n",
        encoding="utf-8",
    )


def main():
    _, payload = load_data()

    updated = 0
    for person in payload.get("people", []):
        changed = False
        for field in ("mobile", "email"):
            if field in person:
                del person[field]
                changed = True
        if changed:
            updated += 1

    write_data(payload)
    print(f"Removed contact details from {updated} people")


if __name__ == "__main__":
    main()
