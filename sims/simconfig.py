import configparser

# Constants
GLOBAL_CFG_SECTION = "Global"
GLOBAL_CFG_NUM_RUNS = "num_runs"
GLOBAL_CFG_BASELINE_CSC = "baseline_csc"

def simconfig_parse(filename):
    config = configparser.ConfigParser()
    config.read(filename)

    # Parse global config
    num_runs = config[GLOBAL_CFG_SECTION][GLOBAL_CFG_NUM_RUNS] 
    csc_baseline = config[GLOBAL_CFG_SECTION][GLOBAL_CFG_BASELINE_CSC]
    
    # Parse scenario configs
    cfg_sections = config.sections()
    scenarios = []
    for name in cfg_sections:
        if name != GLOBAL_CFG_SECTION:
            scenario = {"name": name}
            scenarios.append(scenario)

    return num_runs, csc_baseline, scenarios