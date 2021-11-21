import configparser

# Constants
GLOBAL_SECTION = "global"
GLOBAL_NUM_RUNS = "num_runs"

SIMULATION_SECTION = "simulation"
SIMULATION_CSC_BASELINE = "csc_baseline"

TESTBED_SECTION = "testbed"
TESTBED_DURATION = "duration"
TESTBED_NODES = "nodes"
TESTBED_APP_WARMUP = "app_warmup"

SCENARIO_CFLAGSEXTRA = "cflagsextra"

def experiment_config_parse(filename):
    config = configparser.ConfigParser()
    config.read(filename)

    experiment_config = {}
    scenarios = []

    # Parse other sections
    sections = config.sections()
    for section_name in sections:

        if section_name == GLOBAL_SECTION:
            experiment_config["num_runs"] = \
                int(config[GLOBAL_SECTION][GLOBAL_NUM_RUNS])
            continue

        if section_name == SIMULATION_SECTION:
            experiment_config["csc_baseline"] = \
                config[SIMULATION_SECTION][SIMULATION_CSC_BASELINE]
            continue

        if section_name == TESTBED_SECTION:
            experiment_config["duration"] = \
                int(config[TESTBED_SECTION][TESTBED_DURATION])
            experiment_config["nodes"] = \
                config[TESTBED_SECTION][TESTBED_NODES]
            experiment_config["app_warmup"] = \
                config[TESTBED_SECTION][TESTBED_APP_WARMUP]
            continue

        # If not any of the above, it is a scenario
        scenario = {"name": section_name}
        cflagsextra = config[section_name][SCENARIO_CFLAGSEXTRA]
        scenario["cflagsextra"] = cflagsextra
        scenarios.append(scenario)
        continue

    # Add some testbed config to all scenario for easier usage later
    # TODO not the nicest solution
    for scenario in scenarios:
        if "app_warmup" not in scenario:
            scenario["app_warmup"] = experiment_config["app_warmup"]

    return config, experiment_config, scenarios
