# component-autofiller
#
# a tool to auto fill BOM fields for common SMD passives and things like that

import os
import glob
import re
import sys
import shutil
import json
import urllib
import urllib.parse
import urllib.request
import colorama
from colorama import Fore, Back, Style

# COMMONLY USED PARTS TO AUTOFILL
# KEYED BY PART VALUE FIELD IN SCHEMATIC
PART_AUTOFILLS = {
    '2N7002P' : {
        'Manufacturer'  : 'Nexperia USA Inc.',
        'Part Number'   : '2N7002P,215',
        'Description'   : 'MOSFET N-CH 60V 0.36A SOT-23',
        'Package'       : 'SOT-23'
    },
    'AO3420' : {
        'Manufacturer'  : 'Alpha & Omega Semiconductor',
        'Part Number'   : 'AO3420',
        'Description'   : 'MOSFET N-CH 20V 6A SOT23',
        'Package'       : 'SOT-23'
    },
    'LT1013(C|CD)?' : {
        'Manufacturer'  : 'Texas Instruments',
        'Part Number'   : 'LT1013CDR',
        'Description'   : 'IC OPAMP GP 1MHZ 8SOIC',
        'Package'       : 'SO-8'
    },
    'BAT54S' : {
        'Manufacturer'  : 'ON Semiconductor',
        'Part Number'   : 'BAT54SLT1G',
        'Description'   : 'DIODE ARRAY SCHOTTKY 30V SOT23-3',
        'Package'       : 'SOT-23'
    },
    'MAX11100.*' : {
        'Manufacturer'  : 'Maxim Integrated',
        'Part Number'   : 'MAX11100EUB+',
        'Description'   : 'IC ADC 16BIT SRL 200KSPS 10UMAX',
        'Package'       : 'uMAX-10'
    },
    'LTC6994-1' : {
        'Manufacturer'  : 'Linear Technology',
        'Part Number'   : 'LTC6994CS6-1#TRMPBF',
        'Description'   : 'IC DELAY LINE 8TAP PROG TSOT23-6',
        'Package'       : 'SOT-23-6'
    },
    '(SN)?74HC04': {
        'Manufacturer'  : 'Texas Instruments',
        'Part Number'   : 'SN74HC04PW',
        'Description'   : 'IC HEX INVERTER 14-TSSOP',
        'Package'       : '14-TSSOP'
    },
    '(SN)?74HC08': {
        'Manufacturer'  : 'Texas Instruments',
        'Part Number'   : 'SN74HC08PW',
        'Description'   : 'IC GATE AND 4CH 2-INP 14-TSSOP',
        'Package'       : '14-TSSOP'
    },
    '(SN)?74HC21': {
        'Manufacturer'  : 'Texas Instruments',
        'Part Number'   : 'SN74HC21PW',
        'Description'   : 'IC GATE AND 2CH 4-INP 14-TSSOP',
        'Package'       : '14-TSSOP'
    },
    '(SN)?74HC74': {
        'Manufacturer'  : 'Texas Instruments',
        'Part Number'   : 'SN74HC74PW',
        'Description'   : 'IC D-TYPE POS TRG DUAL 14TSSOP',
        'Package'       : '14-TSSOP'
    },
    '(a+|1N4148(W-7-F)?)': {
        'Manufacturer'  : 'Diodes Incorporated',
        'Part Number'   : '1N4148W-7-F',
        'Description'   : 'DIODE GEN PURP 100V 300MA SOD123',
        'Package'       : 'SOD-123'
    },
    '(EC2_Relay|EC2-12NU)': {
        'Manufacturer'  : 'KEMET',
        'Part Number'   : 'EC2-12NU',
        'Description'   : 'RELAY GEN PURPOSE DPDT 2A 12V',
        'Package'       : '.'
    },
    'PTH08080W.*': {
        'Manufacturer'  : 'Texas Instruments',
        'Part Number'   : 'PTH08080WAS',
        'Description'   : 'MODULE PIP .9-5.5V 2.25A SMD',
        'Package'       : '.'
    },
    'LP2950ACDT-3.3':{
        'Manufacturer'  : 'ON Semiconductor',
        'Part Number'   : 'LP2950ACDT-3.3RG',
        'Description'   : 'IC REG LINEAR 3.3V 100MA DPAK-3',
        'Package'       : 'DPAK-3'
    }

}

def part_autofill_find(part_number):
    for regex,output in PART_AUTOFILLS.items():
        m = re.match(regex, part_number)
        if m is not None:
            return output
    return None

def octopart_find_part(part_number):
    url = 'http://octopart.com/api/v3/parts/search?apikey=95a05f7e'
    args = [
        ('q', part_number),
        ('start', 0),
        ('limit', 10)
    ]
    url += '&' + urllib.parse.urlencode(args)
    data = urllib.request.urlopen(url).read()
    resp = json.loads(data)

    print('{} Hits'.format(resp['hits']))
    for result in resp['results']:
        print(result['item'])

def digikey_find_part(part_number):
    pass

# returns a regex match object
def parse_field_line(field_line):
    FIELD_REGEX = 'F +(?P<number>[0-9]+) +"(?P<value>.+)" +[HV] +[0-9]+ +[0-9]+ +[0-9]+ +[0-9]+ +[A-Z]+ +[A-Z]+( +"(?P<name>[A-Za-z0-9 ]+)")?'
    m = re.match(FIELD_REGEX, field_line)
    return m

# Find the location and value of a given field in a $Comp...$EndComp block.
# Returns the line number
def find_field(block, field_name):
    field_numbers = {
        'reference':0,
        'value':    1,
        'footprint':2,
        'doc':      3
    }

    field_num = None

    if field_name.lower() in field_numbers.keys():
        field_num = field_numbers[field_name.lower()]

    for idx,line in enumerate(block):
        m = parse_field_line(line)
        # if this line is a field line
        if m is not None and (m.group('number') == str(field_num) or m.group('name') == field_name):
            return idx

    return None

# Read a field in a $Comp...$EndComp block.
# Returns None if not found.
def get_field(block, field_name):
    # Note: some built in fields have numbers but not listed names.
    idx = find_field(block, field_name)

    if idx is None: 
        return None

    line = block[idx]
    m = parse_field_line(line)
    return m.group('value')

def find_next_field_num(block):
    max_field_number = 4

    for line in block:
        m = parse_field_line(line)
        if m is not None:
            max_field_number = max(max_field_number, int(m.group('number')))

    return max_field_number + 1

# Change a field in a $Comp..$EndComp block, or add it if it doesn't already exist
# Returns the updated block.
def set_field(block, field_name, field_value):

    idx = find_field(block, field_name)

    if idx is None:
        # Field doesnt exist already, add it
        num = find_next_field_num(block)
        field_line = 'F {} "{}" V 4800 3050 60  0001 C CNN "{}"'.format(num, field_value, field_name)
        block.insert(len(block)-3, field_line)
    else:
        # Field exists already, we need to modify it
        # Replace the value by finding the first instance of a quoted string
        field_line = block[idx]
        field_line = re.sub('".*"', '"{}"'.format(field_value), field_line)
        block[idx] = field_line

    return block

# Name a component, this is where the magic happens.
# Generate the Manufacturer,  Part Number, Description, and Package fields
def figure_out_description(component_name, component_footprint, component_value):

    # Recommendations, default to no update
    output = {
        'Manufacturer' : None,
        'Part Number'  : None,
        'Description'  : None,
        'Package'      : None,
    }

    # Resistors!
    if component_name in ['R', 'R_Small']:
        # Accepted forms of component values:
        # 10
        # 10k
        # 4.99k
        # 4k99
        
        # Make sure it's a format we understand
        m = re.match('[0-9]+[\.]*[0-9]*k?', component_value)
        if m is None:
            return None
        else:
          #  print('Sorry, I don\'t understand "{}".'.format(component_value))
            pass

        res_size = '0603'

        possible_sizes = ['0402', '0603', '0805', '1206', '1210']
        for size in possible_sizes:
            if component_footprint.find(size) != -1:
                res_size = size

        desc_text = 'RES SMD {} OHM 1% {}'.format(component_value.upper(), res_size)

        output['Manufacturer'] = '.'
        output['Part Number'] = '.'
        output['Description'] = desc_text
        output['Package'] = res_size

    # Capacitors!
    elif component_name in ['C', 'C_Small']:

        cap_size = '0603'

        possible_sizes = ['0402', '0603', '0805', '1206', '1210']
        for size in possible_sizes:
            if component_footprint is not None and component_footprint.find(size) != -1:
                cap_size = size

        # ghetto shit
        if component_value.upper().find('PF') != -1:
            diel = 'C0G'
        else:
            diel = 'X7R'

        desc_text = 'CAP CER {} 25V {} {}'.format(component_value.upper().replace(' ',''), diel, cap_size)

        output['Manufacturer'] = '.'
        output['Part Number'] = '.'
        output['Description'] = desc_text
        output['Package'] = cap_size

    elif part_autofill_find(component_value) is not None:
        # Found it in our autofill list
        return part_autofill_find(component_value)
        
    # Not a typical part, search with the octopart API?
    else:
        print ('This isn\'t an easy passive, type in fields? [y/N]:', end='')
        choice = input()
        if choice == 'y':
            #octopart_find_part(component_value)
            #print('This functionality doesn\'t exist yet.')
            for field in ['Manufacturer', 'Part Number', 'Description', 'Package']:
                print('{} :'.format(field), end='')
                typed = input()
                if len(typed) > 0:
                    output[field] = typed
        else:
            pass

    return output

    return None

# Parse and interactively autofill a single component block.
# block_text: List of lines of the $Comp...$EndComp block.
# Returns modified block_text
def process_component_block(block_text):

    # Structure of a 'L' statement (Label?)
    # Group 1 : Schematic component name
    LABEL_REGEX = 'L (.+) (.+)'

    m = re.match(LABEL_REGEX, block_text[1])
    component_name = m.group(1)
    component_ref = m.group(2)

    print(('-->: '+Fore.LIGHTYELLOW_EX+'{}'+Style.RESET_ALL).format(component_ref))

    if block_text[1].find('#PWR')  != -1:
        print('\tSkipping power component')
        return block_text

    # Figure out this component's footprint name to see if it's something
    # that we can autofill
    component_footprint = get_field(block_text, 'footprint')
	
	if component_footprint is None:
		component_footprint = ''

    # Figure out this component's value
    component_value = get_field(block_text, 'value')
	
	if component_value is None:
		component_value = ''

    print('Type: ' + Fore.CYAN + '{}'.format(component_name) + Style.RESET_ALL)
    print('Value: ' + Fore.CYAN + '{}'.format(component_value) + Style.RESET_ALL)
    print('Footprint: ' + Fore.CYAN + '{}'.format(component_footprint) + Style.RESET_ALL)

    current = {}

    print('Current Properties:')
    for field in ['Manufacturer', 'Part Number', 'Description', 'Package']:
        current[field] = get_field(block_text, field)
        print('\t{}:\t{}'.format(field, current[field]))

    recommended = figure_out_description(component_name, component_footprint, component_value)
    if recommended is None:
        recommended = {
            'Manufacturer':None,
            'Part Number' : None,
            'Description' : None,
            'Package' : None
        }
    for field in ['Manufacturer', 'Part Number', 'Description', 'Package']:
        if recommended[field] is None:
            recommended[field] = current[field] if current[field] is not None else '.'

    if recommended != current:
        print('New Properties:')
        for field in ['Manufacturer', 'Part Number', 'Description', 'Package']:
            colo = ''
            if recommended[field] != current[field]:
                colo = Fore.LIGHTCYAN_EX
            
            print('\t{}:\t{}'.format(field, colo + recommended[field] + Style.RESET_ALL))

        print('Accept changes? [y/N]:', end='')
        choice = input().lower()

        if choice == 'y':
            print('\t\tCHANGING SHIT!!')
            for field in recommended.keys():
                block_text = set_field(block_text, field, recommended[field])
 #   else:
    #    print('\t\tAlready had my description: {}'.format(old_desc))
    
    return block_text


# Interactvely parse and autofill BOM fields for a sch file.
# 
# sch_file_text: Contents of sch file
# 
# Returns text with added autofill fields.
def autofill_sch_file(sch_file_text):
    lines = sch_file_text.splitlines()
    out = ''

    if lines[0] != 'EESchema Schematic File Version 2':
        print('Unknown .sch file header: {}'.format(lines[0]))
        os.exit(1)

    # iterate forward line by line until we find a $Comp...$EndComp block
    i = 0
    while i < len(lines):
        if lines[i] == '$Comp':
            # A block started, find its end
            block_end = i
            while lines[block_end] != '$EndComp':
                block_end += 1

            # Process the block we just found
            block = process_component_block(lines[i:block_end+1])
            for line in block:
                out += line + '\n'

            i = block_end+1
          #  i = block_end
        else:
            out += lines[i] + '\n'
            i += 1

    return out

# Main entry point
if __name__ == "__main__":

    colorama.init()

    working_dir = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()
    print('--------------------[ Component Autofiller ]--------------------')
    print('Working Dir: {}'.format(working_dir))

    files = glob.glob(os.path.join(working_dir, '*.sch'))
    print('')
    print('Found KiCAD Schematic Files:')

    for filename in files:
        print('\t{}'.format(os.path.basename(filename)))

    print('')
    print('Press any key to continue...')
    input()

    for filename in files: 
        out = None
        with open(filename, 'r') as f:
            text = f.read()
            out = autofill_sch_file(text)

        print('Finished components in {}. Write out? [Y/N] '.format(filename), end='')

        # Save a backup copy in case we fuck up the .sch file ( likely :) )
        shutil.copy(filename, filename+'.backup')

        if input().lower() == 'y':
            with open(filename, 'w') as f:
                f.write(out)
                print('Wrote {} characters'.format(len(out)))

