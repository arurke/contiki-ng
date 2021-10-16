import sys
import os
import shutil
import subprocess
import argparse
import pandas as pd
from dataclasses import dataclass
from datetime import datetime
from simconfig import simconfig_parse
from experiment_config import experiment_config_parse
from parse_log import parse_logs_scenarios
from plot import plot_time_series
from plot import plot_pdr_latency
from plot import plot_duty_cycle
from plot import plot_queue_util_selected_nodes
from plot import plot_etx_comparison
#from stats import stats_for_scenarios
from stats_triscale import stats_for_scenarios
from simxml import simxml_make_xml_for_all_scenarios

# Constants
CODE_FOLDER_NAME = "code"
BUILD_FOLDER_NAME = "build"
ORG_FOLDER_NAME = "org"
BUILD_COOJA_NAME = "node.cooja"
EXECUTIONS_FOLDER_NAME = "executions"
MAKEFILE = "Makefile"
#NODES = "358+343+328+313+298+290+203+188"
NODES = "358+356+354+351+348+346+344+342+340+338+336+334+332+330+328+326+324+322+320+318"
DURATION_MIN = "80"

@dataclass
class Config:
    type: str
    sim_name: str
    sim_dir: str
    executions_dir: str
    execution_dir: str
    csc_baseline_path: str
    sim_cfg_path: str
    num_runs: int
    skip_post: bool
    do_run: bool
    execution_id: str
    scenarios: dict
    duration: int
    nodes: str

def create_run_sim_commands(sim_name, scenarios, num_runs):
    scenario_run_cmds = []
    for scenario in scenarios:
        scenario_run_cmd = "contiker_notty bash -c \"" + \
                "make -C sims/" + scenario['path'] + " " + \
                sim_name + "_scenario_" + scenario['name'] + ".testlog " + \
                "RUNCOUNT=" + str(num_runs) + "\""
        #scenario_run_cmd =  \
        #        "make -C sims/" + scenario['path'] + " " + \
        #        sim_name + "_scenario_" + scenario['name'] + ".testlog " + \
        #        "RUNCOUNT=" + str(num_runs)
        scenario_run_cmds.append(scenario_run_cmd)

    return scenario_run_cmds

def create_run_testbed_commands(sim_name, scenarios, num_runs, duration, nodes):
    for scenario in scenarios:

        # For testbed we add an array of run-cmds, one for each run
        # (with simulator, multiple runs are handled in the simulator-running-script)
        scenario_run_cmds = []
        for run in range(num_runs):
            run_name = sim_name + "_scenario_" + scenario['name']
            # Ad-hoc run0 while we do not have run-concept with testbed
            logs_path = scenario['path'] + "run" + str(run) + "/"
            src_path = scenario['path'] + CODE_FOLDER_NAME
            scenario_run_cmd = "./run-testbed.sh " + run_name + " " + src_path + \
                " " + logs_path + " " + str(duration) + " grenoble,m3," + nodes

            # We need to separate words in cmd into array for subprocess
            run_cmd_array = scenario_run_cmd.split(' ')
            # Add cflagsextra now because they may contain spaces
            run_cmd_array.append(scenario['cflagsextra'])

            # Add finished command to the scenario run-cmd array
            scenario_run_cmds.append(run_cmd_array)

        scenario['run_cmd'] = scenario_run_cmds

def process_results(scenarios, execution_dir):
    # Get raw DFs for all runs of all scenarios.
    # The DFs are inserted into scenarios
    # Add True as second argument to squelch output
    parse_logs_scenarios(scenarios)

    # Make time-series from the raw DFs
    for scenario in scenarios:
        plot_time_series(scenario, 350, 'run0', 0)
        plot_time_series(scenario, 353, 'run0', 0)

    # Get stats from the DFs
    scenarios_df = stats_for_scenarios(scenarios, True)

    # Save DF to CSV
    df_csv = execution_dir + "scenarios_df.csv"
    print("Saving csv of all scenarios at", df_csv)
    scenarios_df.to_csv(df_csv)

    # Plot
    plot_pdr_latency(scenarios_df, execution_dir)
    plot_duty_cycle(scenarios_df, execution_dir)
    plot_queue_util_selected_nodes(scenarios_df, execution_dir)

    # Print all columns
    pd.set_option('display.max_columns', None)
    print("Scenarios stats:\n", scenarios_df)

# Create execution-id
def create_execution_id(sim_name, executions_dir):
    # ID should be: [config_name]-[date]-[id] (id is incremental)
    new_execution_id = sim_name + \
                        "_" + datetime.now().strftime("%Y%m%d")
    
    # Find next available id
    i = 0
    while os.path.exists(executions_dir + new_execution_id +  "_%s" % i):
        i += 1
    new_execution_id += "_%s" % i
    
    return new_execution_id

def prepare_datastructures(scenarios, execution_dir):
    for scenario in scenarios:
        scenario['path'] = execution_dir + scenario['name'] + "/"

# Make executions/[execution-id]/[scenario-name] directories
def prepare_filesystem(sim_name, sim_dir, scenarios, executions_dir, execution_dir):
    print("\nPreparing filesystem")

    if not os.path.exists(executions_dir):
        print("Generating executions dir", executions_dir)
        os.mkdir(executions_dir)
    
    print("Generating execution dir", execution_dir)
    os.mkdir(execution_dir)

    # Make scenario-folders
    for scenario in scenarios:
        if not os.path.exists(scenario['path']):
            print("Generating scenario dir", scenario['path'])
            os.mkdir(scenario['path'])

    copy_node_code(sim_dir, scenarios)
    copy_sim_config_file(sim_dir, sim_name, execution_dir)

    print("Filesystem prepared")

def copy_sim_config_file(sim_dir, sim_name, execution_dir):
    config_file_name = sim_name + ".ini"
    config_file_src = sim_dir + config_file_name
    config_file_dst = execution_dir + config_file_name
    print("Copying config from", config_file_src, "to", config_file_dst)
    shutil.copyfile(config_file_src, config_file_dst)

# Copy sims/[sim-name]/code into executions/[execution-id]/[scenario-name]/code
# Copy sims/[sim-name]/Makefile into executions/[execution-id]/[scenario-name]/Makefile
def copy_node_code(sim_dir, scenarios):
    code_src_dir = sim_dir + CODE_FOLDER_NAME
    build_src_dir = code_src_dir + "/" + BUILD_FOLDER_NAME
    build_cooja_file = code_src_dir + "/" + BUILD_COOJA_NAME
    makefile_src = sim_dir + MAKEFILE

    for scenario in scenarios:
        # Source code
        code_dst_dir = scenario['path'] + CODE_FOLDER_NAME
        if not os.path.exists(code_dst_dir):

            # Make sure there is no existing build artificats in the folder
            # This can happen if cooja gui has called the .csc
            # Copying existing artifacts can lead to great confusion as old code
            # would run in the sim.
            if os.path.exists(build_src_dir):
                print("Found build artifacts, deleting", build_src_dir)
                shutil.rmtree(build_src_dir)
            if os.path.isfile(build_cooja_file):
                print("Found build artifacts, deleting", build_cooja_file)
                os.remove(build_cooja_file)

            print("Copying code from", code_src_dir, "to", code_dst_dir)
            shutil.copytree(code_src_dir, code_dst_dir)

        # Makefile
        makefile_dst = scenario['path'] + MAKEFILE
        print("Copying Makefile from", makefile_src, "to", makefile_dst)
        shutil.copyfile(makefile_src, makefile_dst)

def cleanup(scenarios):
    print("Removing build artifacts")
    for scenario in scenarios:
        # Remove the org and code folder since we don't need them in the
        # results and they take up a lot of space (especially code)
        build_dir = scenario['path'] + CODE_FOLDER_NAME + "/" + BUILD_FOLDER_NAME
        org_dir = scenario['path'] + ORG_FOLDER_NAME
        if os.path.exists(build_dir):
            shutil.rmtree(build_dir)
        if os.path.exists(org_dir):
            shutil.rmtree(org_dir)

def parse_arguments():
    argparser = argparse.ArgumentParser()
    argparser.add_argument('Type',
                           metavar = 'type',
                           type = str,
                           choices=['simulation', 'testbed'],
                           help = 'Type of experiment')
    argparser.add_argument('Path',
                           metavar = 'path',
                           type = str,
                           help = 'path to sim folder')
    argparser.add_argument('Config',
                           metavar = 'config',
                           type = str,
                           help = 'name of config file')
    argparser.add_argument('-r',
                           '--runs',
                           type = int,
                           help = 'number of runs')
    argparser.add_argument('-s',
                           '--skipp',
                           action='store_true',
                           help = 'skip post-processing')
    argparser.add_argument('-n',
                           '--norun',
                           type = str,
                           help = 'Dont run experiment. Execution id to analyze')
    args = argparser.parse_args()

    type = args.Type
    sim_dir = args.Path
    sim_cfg_filename = args.Config
    num_runs = args.runs
    skip_post = args.skipp
    analyse_execution_id = args.norun
    
    return type, sim_dir, sim_cfg_filename,\
        num_runs, skip_post, analyse_execution_id

def parse_config():
    # Get config from command line
    type, sim_dir, sim_cfg_filename, \
        cmd_num_runs, skip_post, analyse_execution_id = parse_arguments()

    # Add '/'
    os.path.join(sim_dir)
    
    # Folder to hold all executions
    executions_dir = sim_dir + EXECUTIONS_FOLDER_NAME + "/"

    if analyse_execution_id is None:
        do_run = True
        sim_cfg_path = sim_dir + sim_cfg_filename
    else:
        do_run = False
        sim_cfg_path = executions_dir + \
            analyse_execution_id + "/" +  sim_cfg_filename

    # Parse config-file
    parsedconfig, experiment_config, scenarios = \
        experiment_config_parse(sim_cfg_path)

    # Sim name is same as config file
    sim_name = sim_cfg_filename[:-4] # Remove ".ini"
    csc_baseline_path = sim_dir + experiment_config["csc_baseline"]

    # Let num-runs from command-line override
    if cmd_num_runs is None:
        num_runs = experiment_config["num_runs"]
    else:
        num_runs = cmd_num_runs

    if analyse_execution_id is not None:
        execution_id = analyse_execution_id
    else:
        execution_id = create_execution_id(sim_name, executions_dir)

    # Folder for this execution
    execution_dir = executions_dir + execution_id + "/"
    
    config = Config(type, sim_name, sim_dir, executions_dir, execution_dir,
                    csc_baseline_path, sim_cfg_path, num_runs, skip_post,
                    do_run, execution_id, scenarios,
                    experiment_config["duration"], experiment_config["nodes"])

    print_config(config)

    return parsedconfig, config

def print_config(config):
    if config.do_run is False:
        print("\nNo execution! Analyzing: ", config.execution_id)
    print("\nExperiment config:")
    print("\tType:         ", config.type)
    print("\tSim-name:     ", config.sim_name)
    print("\tDirectory:    ", config.sim_dir)
    print("\tConfig:       ", config.sim_cfg_path)
    print("\tCSC Baseline: ", config.csc_baseline_path)
    print("\t# scenarios:  ", len(config.scenarios))
    print("\t# runs:       ", config.num_runs)
    if config.duration is not None:
        print("\tDuration:     ", config.duration)
    if config.nodes is not None:
        print("\tNodes:        ", config.nodes)
    print("\tSkip post:    ", str(config.skip_post))
    print("\tDo execution: ", str(config.do_run))
    print("\tExecution id: ", config.execution_id)
    print("\tExecution dir:", config.execution_dir)

def run_simulation(run_cmds):
    #CNG_PATH = "/home/andreas/vizaworkspace/contiki-ng"
    # Starting contiker cmd (had trouble using the alias with subprocess.Popen
    # Changed -it to -i based on
    # https://stackoverflow.com/questions/43099116/error-the-input-device-is-not-a-tty
    #contiker_cmd = \
    #    "docker run --privileged --sysctl net.ipv6.conf.all.disable_ipv6=0 " \
    #    "--mount type=bind,source=" + CNG_PATH + \
    #    ",destination=/home/user/contiki-ng -e DISPLAY=$DISPLAY " \
    #    "-v /tmp/.X11-unix:/tmp/.X11-unix -v /dev/bus/usb:/dev/bus/usb " \
    #    "-i contiker/contiki-ng"

    # Note that "contiker" alias does not work with Popen
    # Therefore made contiker_notty (without TTY, or else shell gets garbled
    # after execution) into a bash-script and placed in /usr/local/bin
    # see https://stackoverflow.com/questions/12060863/python-subprocess-call-a-bash-alias
    process_list = []
    for run_cmd in run_cmds:
        # Needed stdout and stdin to avoid terminal
        # stop working after execution
        # shell needed so that it would find contiker_notty
        print("Executing:", run_cmd)
        process = subprocess.Popen(run_cmd,
                                   shell=True,
                                   stdout=subprocess.PIPE,
                                   stdin=subprocess.PIPE)
        process_list.append(process)

    exit_codes = [process.wait() for process in process_list]
    print("\nExecutions exited with:", exit_codes)
    if not all(code == 0 for code in exit_codes):
        return False

    return True

def run_testbed(scenarios, num_runs):
    for scenario in scenarios:
        print("\nRunning scenario:")
        print("\tName:      " + scenario['name'])
        print("\tNum runs:  " + str(num_runs))
        print("\tCflagsextra: " + scenario['cflagsextra'])

        for run in range(num_runs):
            print("\nStarting run:")
            print("\tRun:       " + str(run))
            print("\tTime now:  " + str(datetime.now()))
            #print("\tFull cmd:  " + str(scenario['run_cmd'][run]))
            print("")
            process = subprocess.run(scenario['run_cmd'][run])

            if process.returncode != 0:
                return False

    return True

def main():
    start_time = datetime.now()
    print("Started:", start_time)

    parsedconfig, config = parse_config()

    prepare_datastructures(config.scenarios, config.execution_dir)

    if config.do_run: 
        prepare_filesystem(config.sim_name,
                             config.sim_dir,
                             config.scenarios,
                             config.executions_dir,
                             config.execution_dir)

        if config.type == "simulation":
            print("Making XML for all scenarios")
            simxml_make_xml_for_all_scenarios(config.sim_name,
                                      config.csc_baseline_path,
                                      config.scenarios,
                                      parsedconfig)

            print("Making simulation-run commands")
            run_cmds = create_run_sim_commands(
                config.sim_name, config.scenarios, config.num_runs)

            print("\nStarting simulation!")
            if not run_simulation(run_cmds):
                print("\nError in executions. Exiting.")
                exit()


        if config.type == "testbed":
            print("Making testbed-run commands")
            create_run_testbed_commands(
                config.sim_name, config.scenarios,
                config.num_runs, config.duration,
                config.nodes)

            print("\nStarting testbed!")
            if not run_testbed(config.scenarios, config.num_runs):
                print("\nError in executions. Exiting.")
                exit()

        cleanup(config.scenarios)

    # Process results
    if not config.skip_post:
        process_results(config.scenarios, config.execution_dir)

    print("Finished experiment")
    print_config(config)

    end_time = datetime.now()
    print("End time:", end_time)
    print("Duration:", end_time - start_time)

main()

