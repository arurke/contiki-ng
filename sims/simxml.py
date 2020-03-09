# Makes .csc files based on a baseline csc and a config file

import xml.etree.ElementTree as ET
import sys

def parse_xml(filename):
    return ET.parse(filename)

def update_xml(xml, key, content):
    # Note! Finds the first element
    root = xml.getroot()
    changed = False
    for element in root.iter(key):
        element.text = content
        changed = True
        
    if not changed:
        sys.exit("Unable to update XML")
    
def save_copy_of_xml(xml, sim_name, scenario):
    new_xml_dir = scenario['path']
    new_xml_filename = sim_name + '_scenario_' + scenario['name'] + '.csc'
    new_xml_path = new_xml_dir + new_xml_filename
    print("Writing xml", new_xml_path)
    xml.write(new_xml_path)

def simxml_make_xml_for_all_scenarios(sim_name, baseline_csc, scenarios, scenarios_config):
    sim_baseline_xml = parse_xml(baseline_csc)
    for scenario in scenarios:
        for key in scenarios_config[scenario['name']]:
            update_xml(sim_baseline_xml, key, scenarios_config[scenario['name']][key])
            update_xml(sim_baseline_xml, "source", "[CONTIKI_DIR]/sims/" + scenario['path'] + "code/node.c")
            save_copy_of_xml(sim_baseline_xml, sim_name, scenario)
    
