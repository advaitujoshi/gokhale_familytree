import json
import re
from collections import defaultdict
from html.parser import HTMLParser
from pathlib import Path

SOURCE_HTML = Path("/Users/unmeshjoshi/Downloads/Family Tree.html")
OUTPUT_JSON = Path("/Users/unmeshjoshi/work/familytree/data/family-tree.from-html.json")
OUTPUT_JS = Path("/Users/unmeshjoshi/work/familytree/data/family-tree.from-html.js")


def slugify(value):
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = re.sub(r"-+", "-", value).strip("-")
    return value or "item"


def clean_label(label):
    return re.sub(r"\s*-\s*Click Here$", "", label, flags=re.I).strip()


def split_members(label):
    cleaned = clean_label(label)
    parts = re.split(r"\s*&\s*|\s*,\s*", cleaned)
    return [part.strip() for part in parts if part.strip()]


class FamilyTreeHtmlParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_tree = False
        self.capture = False
        self.text_parts = []
        self.roots = []
        self.stack = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        class_name = attrs.get("class", "")

        if tag == "ul" and attrs.get("id") == "myUL":
            self.in_tree = True
            self.stack = [{"children": self.roots, "last_node": None}]
            return

        if not self.in_tree:
            return

        if tag == "span" and class_name == "caret":
            self.capture = True
            self.text_parts = []
        elif tag == "ul" and class_name == "nested":
            parent = self.stack[-1]["last_node"]
            if parent is not None:
                self.stack.append({"children": parent["children"], "last_node": None})

    def handle_endtag(self, tag):
        if not self.in_tree:
            return

        if tag == "span" and self.capture:
            label = " ".join("".join(self.text_parts).split())
            self.capture = False
            self.text_parts = []
            if label:
                node = {"label": label, "children": []}
                self.stack[-1]["children"].append(node)
                self.stack[-1]["last_node"] = node
        elif tag == "ul" and len(self.stack) > 1:
            self.stack.pop()
        elif tag == "ul" and len(self.stack) == 1:
            self.in_tree = False
            self.stack.pop()

    def handle_data(self, data):
        if self.capture:
            self.text_parts.append(data)


def parse_tree():
    parser = FamilyTreeHtmlParser()
    parser.feed(SOURCE_HTML.read_text(encoding="utf-8"))
    return parser.roots


def iter_nodes(nodes, depth=0, parent=None):
    for node in nodes:
        yield node, depth, parent
        yield from iter_nodes(node["children"], depth + 1, node)


def build_json():
    roots = parse_tree()
    if not roots:
        raise ValueError(f"No family tree nodes found in {SOURCE_HTML}")

    person_id_counts = defaultdict(int)
    family_id_counts = defaultdict(int)
    people = []
    people_by_name = {}
    families = []
    family_id_by_node = {}

    def get_person_id(name):
        if name in people_by_name:
            return people_by_name[name]["id"]

        base = slugify(name)
        person_id_counts[base] += 1
        person_id = base if person_id_counts[base] == 1 else f"{base}-{person_id_counts[base]}"

        person = {
            "id": person_id,
            "name": name,
            "photo": f"images/{slugify(name)}.jpg",
            "notes": "",
        }
        people_by_name[name] = person
        people.append(person)
        return person_id

    for node, depth, _ in iter_nodes(roots):
        label = clean_label(node["label"])
        members = split_members(node["label"])
        base = slugify(label)
        family_id_counts[base] += 1
        family_id = f"fam-{base}" if family_id_counts[base] == 1 else f"fam-{base}-{family_id_counts[base]}"
        family_id_by_node[id(node)] = family_id

        member_ids = [get_person_id(name) for name in members]
        families.append(
            {
                "id": family_id,
                "label": label,
                "sourceLabel": node["label"],
                "generation": depth,
                "memberIds": member_ids,
                "childFamilyIds": [],
            }
        )

    families_by_id = {family["id"]: family for family in families}

    for node, _, _ in iter_nodes(roots):
        family = families_by_id[family_id_by_node[id(node)]]
        family["childFamilyIds"] = [family_id_by_node[id(child)] for child in node["children"]]

    payload = {
        "meta": {
            "title": "Gokhale Family Tree",
            "format": "family-tree-json-v1",
            "source": str(SOURCE_HTML),
            "rootFamilyIds": [family_id_by_node[id(node)] for node in roots],
            "familyCount": len(families),
            "personCount": len(people),
        },
        "people": people,
        "families": families,
    }

    json_text = json.dumps(payload, indent=2, ensure_ascii=True)
    OUTPUT_JSON.write_text(json_text + "\n", encoding="utf-8")
    OUTPUT_JS.write_text(f"window.familyTreeData = {json_text};\n", encoding="utf-8")
    return payload


if __name__ == "__main__":
    result = build_json()
    print(
        f"Wrote {OUTPUT_JSON} with {result['meta']['familyCount']} families and "
        f"{result['meta']['personCount']} people"
    )
