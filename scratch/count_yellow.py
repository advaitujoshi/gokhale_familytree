import xml.etree.ElementTree as ET
import os

def count_yellow_cells(base_dir):
    yellow_styles = set()
    
    # Generic function to get attribute with any namespace
    def get_attr(elem, attr_name):
        for key in elem.attrib:
            if key.split('}')[-1] == attr_name:
                return elem.attrib[key]
        return None

    for xml_file in ['content.xml', 'styles.xml']:
        file_path = os.path.join(base_dir, xml_file)
        if not os.path.exists(file_path): continue
        
        print(f"Scanning {xml_file}...")
        try:
            tree = ET.parse(file_path)
            for elem in tree.iter():
                tag = elem.tag.split('}')[-1]
                if tag == 'style':
                    style_name = get_attr(elem, 'name')
                    # Look for properties child
                    for child in elem:
                        if child.tag.split('}')[-1] == 'table-cell-properties':
                            bg = get_attr(child, 'background-color')
                            if bg and bg.lower() == '#ffff00':
                                if style_name:
                                    yellow_styles.add(style_name)
        except Exception as e: print(f"Error: {e}")

    if not yellow_styles:
        print("No yellow styles found.")
        return 0

    print(f"Yellow styles: {yellow_styles}")

    content_path = os.path.join(base_dir, 'content.xml')
    tree = ET.parse(content_path)
    
    yellow_count = 0
    yellow_names = []
    
    for table in tree.iter():
        if table.tag.split('}')[-1] == 'table':
            sheet_name = get_attr(table, 'name')
            if sheet_name and 'contact details' in sheet_name.lower():
                print(f"Searching sheet: {sheet_name}")
                for row in table.iter():
                    if row.tag.split('}')[-1] == 'table-row':
                        for cell in row:
                            if cell.tag.split('}')[-1] == 'table-cell':
                                style = get_attr(cell, 'style-name')
                                if style in yellow_styles:
                                    text = ""
                                    for p in cell.iter():
                                        if p.tag.split('}')[-1] == 'p' and p.text:
                                            text += p.text
                                    text = text.strip()
                                    if text:
                                        yellow_count += 1
                                        yellow_names.append(text)
                                        print(f"Yellow name: {text}")
                                    
                                    repeated = get_attr(cell, 'number-columns-repeated')
                                    if repeated and text:
                                        count = int(repeated)
                                        if 1 < count < 100:
                                            yellow_count += (count - 1)
                                            for _ in range(count - 1): yellow_names.append(text)

    print(f"\nTotal yellow names in 'Contact Details': {yellow_count}")
    return yellow_count

if __name__ == "__main__":
    count_yellow_cells('scratch/ods_content')
