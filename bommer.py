# KiCad BOM Export Script

import xml.etree.ElementTree as ET
import openpyxl
import os.path
import os 
import time
import sys




# ---- Customize this for your particular BOM template ----
SPREADSHEET_START_ROW = 3
SPREADSHEET_COLS = {
    'Ref'           : 'B',
    'Qty'           : 'C',
    'Value'         : 'D',
    'Manufacturer'  : 'E',
    'Part Number'   : 'F',
    'Description'   : 'G',
    'Package'       : 'H',
    'Notes'         : 'I'
}
TEMPLATE_FILENAME = 'PCB BOM Template.xlsx'
# ---------------------------------------------------------

def find_field(part, field_name):
    for field in part.iter('field'):
        if field.get('name') == field_name:
            if field.text == '.':
                return ''
            else:
                return field.text
    return '?'

print('--[ KiCAD BOM Export Script ]--')

netlist_filename = sys.argv[1]
output_dirname = sys.argv[2]

print('Searching for template file {}'.format(TEMPLATE_FILENAME))

# Find the Excel output template file by recursively searching upwards from the netlist directory.
search_dir = os.path.dirname(netlist_filename)

wb = None
while os.path.dirname(search_dir) != search_dir:
    print('\tSearching in dir {}'.format(search_dir))
    filename = os.path.join(search_dir, TEMPLATE_FILENAME)
    try:
        wb = openpyxl.load_workbook(filename)
        print('Success! Loaded "{}"'.format(TEMPLATE_FILENAME))
        break
    except FileNotFoundError as e:
        search_dir = os.path.dirname(search_dir)

if wb is None:
    print('Couldn\'t find template "{}" :('.format(TEMPLATE_FILENAME))
    sys.exit(1)

ws = wb.active

tree = ET.parse(netlist_filename)
root = tree.getroot()

component_iterator = root.iter('comp')

parts = []


for part in component_iterator:

    part_data = {}

    part_data['Ref'] = part.get('ref')
    part_data['Value'] = part.find('value').text

    part_data['Manufacturer'] = find_field(part, 'Manufacturer')
    part_data['Part Number'] = find_field(part, 'Part Number')
    part_data['Description'] = find_field(part, 'Description')
    part_data['Package'] = find_field(part, 'Package')
    part_data['Notes'] = find_field(part, 'Notes')

    parts.append(part_data)

# Sort parts by refdes
parts = sorted(parts, key=lambda x: x['Ref'])

bom_rows = []

# Add parts to rows, combining where necessary
for part in parts:
    smooshed = False
    for idx, row in enumerate(bom_rows):
        if row['Value'] == part['Value'] and row['Part Number'] == part['Part Number'] and row['Description'] == part['Description'] and row['Package'] == part['Package']:
            smooshed = True
            bom_rows[idx]['Qty'] = int(row['Qty']) + 1
            bom_rows[idx]['Ref'] += ',{}'.format(part['Ref'])
            break
    if not smooshed:
        new_row = part.copy()
        new_row['Qty'] = 1
        bom_rows.append(new_row)

# Write out bom rows
for row_idx, row in enumerate(bom_rows):
    for key, val in row.items():
        if key not in SPREADSHEET_COLS.keys():
            continue
        col = SPREADSHEET_COLS[key]
        ws['{}{}'.format(col, SPREADSHEET_START_ROW + row_idx)] = val

print('Success? Wrote {} rows from {} parts.'.format(len(bom_rows), len(parts)))

wb.save('{}-BOM.xlsx'.format(output_dirname))