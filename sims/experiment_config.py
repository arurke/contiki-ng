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
TESTBED_SPATIAL_COMPARISON = "spatial_comparison"
TESTBED_CONVERGENCE_COMPARISON = "rpl_convergence_comparison"

SCENARIO_CFLAGSEXTRA = "cflagsextra"
SCENARIO_MAKEFLAGS = "makeflags"
SCENARIO_DESCRIPTION = "description"
SCENARIO_HAS_SPATIAL = "has_spatial"

def experiment_config_parse(filename):
    config = configparser.ConfigParser()
    config.read(filename)

    experiment_config = {}
    scenarios = []

    # Parse other sections
    sections = config.sections()
    for section_name in sections:

        if section_name == GLOBAL_SECTION:
            experiment_config[GLOBAL_NUM_RUNS] = \
                int(config[GLOBAL_SECTION][GLOBAL_NUM_RUNS])
            experiment_config[TESTBED_SPATIAL_COMPARISON] = \
                config[GLOBAL_SECTION].getboolean(TESTBED_SPATIAL_COMPARISON)
            experiment_config[TESTBED_CONVERGENCE_COMPARISON] = \
                config[GLOBAL_SECTION].getboolean(TESTBED_CONVERGENCE_COMPARISON)
            continue

        if section_name == SIMULATION_SECTION:
            experiment_config["csc_baseline"] = \
                config[SIMULATION_SECTION][SIMULATION_CSC_BASELINE]
            continue

        if section_name == TESTBED_SECTION:
            experiment_config["duration"] = \
                int(config[TESTBED_SECTION][TESTBED_DURATION])
            experiment_config[TESTBED_NODES] = \
                config[TESTBED_SECTION][TESTBED_NODES]
            experiment_config["app_warmup"] = \
                config[TESTBED_SECTION][TESTBED_APP_WARMUP]
            continue

        # If not any of the above, it is a scenario
        scenario_config = config[section_name]
        scenario = {"name": section_name,
                    SCENARIO_CFLAGSEXTRA: "",
                    SCENARIO_MAKEFLAGS: "",
                    SCENARIO_HAS_SPATIAL: False}

        if SCENARIO_CFLAGSEXTRA in scenario_config:
            scenario[SCENARIO_CFLAGSEXTRA] = scenario_config[SCENARIO_CFLAGSEXTRA]

        if SCENARIO_MAKEFLAGS in scenario_config:
            scenario[SCENARIO_MAKEFLAGS] = scenario_config[SCENARIO_MAKEFLAGS]

        if SCENARIO_DESCRIPTION in scenario_config:
            scenario[SCENARIO_DESCRIPTION] = scenario_config[SCENARIO_DESCRIPTION]

        if SCENARIO_HAS_SPATIAL in scenario_config:
            scenario[SCENARIO_HAS_SPATIAL] = \
                scenario_config.getboolean(SCENARIO_HAS_SPATIAL)

        scenarios.append(scenario)
        continue

    # Add some testbed config to all scenarios for easier usage later
    # TODO not the nicest solution
    for scenario in scenarios:
        if TESTBED_APP_WARMUP not in scenario:
            scenario[TESTBED_APP_WARMUP] = experiment_config[TESTBED_APP_WARMUP]
        if TESTBED_SPATIAL_COMPARISON not in scenario:
            scenario[TESTBED_SPATIAL_COMPARISON] = \
                experiment_config[TESTBED_SPATIAL_COMPARISON]
        if TESTBED_CONVERGENCE_COMPARISON not in scenario:
            scenario[TESTBED_CONVERGENCE_COMPARISON] = \
                experiment_config[TESTBED_CONVERGENCE_COMPARISON]
        if TESTBED_NODES not in scenario:
            scenario[TESTBED_NODES] = experiment_config[TESTBED_NODES]

    return config, experiment_config, scenarios
