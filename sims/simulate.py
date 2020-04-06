import sys
import os
import shutil
import subprocess
import argparse
import pandas as pd
from datetime import datetime
from simconfig import simconfig_parse
from parse_log import parse_logs_scenarios
from plot import plot_time_series
from plot import plot_scenarios
from plot import plot_duty_cycle
#from stats import stats_for_scenarios
from stats_triscale import stats_for_scenarios
from simxml import simxml_make_xml_for_all_scenarios

# Constants
CODE_FOLDER_NAME = "code"
BUILD_FOLDER_NAME = "build"
ORG_FOLDER_NAME = "org"
BUILD_Z1_NAME = "node.z1"
BUILD_COOJA_NAME = "node.cooja"
EXECUTIONS_FOLDER_NAME = "executions"
MAKEFILE = "Makefile"

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

def process_results(scenarios, execution_dir):
    # Get raw DFs for all runs of all scenarios.
    # The DFs are inserted into scenarios
    # Add True as second argument to squelch output
    parse_logs_scenarios(scenarios)

    # Make time-series from the raw DFs
    for scenario in scenarios:
        plot_time_series(scenario, 3, 'run1', 0)

    # Get stats from the DFs
    scenarios_df = stats_for_scenarios(scenarios)

    print("Scenarios stats:\n", scenarios_df)

    plot_scenarios(scenarios_df, execution_dir)
    plot_duty_cycle(scenarios_df, execution_dir)

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
    
# Make executions/[execution-id]/[scenario-name] directories
def prepare_filesystem(sim_name, sim_dir, scenarios):
    print("\nPreparing filesystem")

    # Make folder to hold all executions
    executions_dir = sim_dir + EXECUTIONS_FOLDER_NAME + "/"
    if not os.path.exists(executions_dir):
        print("Generating executions dir", executions_dir)
        os.mkdir(executions_dir)
    
    execution_id = create_execution_id(sim_name, executions_dir)
    execution_dir = executions_dir + execution_id + "/"

    print("Generating execution dir", execution_dir)
    os.mkdir(execution_dir)
    
    # Make scenario-folders and add the path to the scenarios list
    for scenario in scenarios:
        scenario['path'] = execution_dir + scenario['name'] + "/"
        if not os.path.exists(scenario['path']):
            print("Generating scenario dir", scenario['path'])
            os.mkdir(scenario['path'])

    copy_node_code(sim_dir, scenarios)
    copy_sim_config_file(sim_dir, sim_name, execution_dir)

    print("Filesystem prepared\n")

    return execution_id, execution_dir

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
    build_z1_file = code_src_dir + "/" + BUILD_Z1_NAME
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
            if os.path.isfile(build_z1_file):
                print("Found build artifacts, deleting", build_z1_file)
                os.remove(build_z1_file)
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
    argparser.add_argument('Path',
                           metavar = 'path',
                           type = str,
                           help = 'path to sim folder')
    argparser.add_argument('Config',
                           metavar = 'config',
                           type = str,
                           help = 'name of config file')
    argparser.add_argument('-b',
                           '--baseline',
                           type = str,
                           help = 'name of .csc baseline file')
    argparser.add_argument('-r',
                           '--runs',
                           type = int,
                           help = 'number of runs')
    argparser.add_argument('-s',
                           '--skipp',
                           action='store_true',
                           help = 'skip post-processing')
    args = argparser.parse_args()

    sim_dir = args.Path
    sim_cfg_filename = args.Config
    csc_baseline = args.baseline
    num_runs = args.runs
    skip_post = args.skipp
    
    return sim_dir, sim_cfg_filename, csc_baseline, num_runs, skip_post

def parse_config():
    # Get config from command line
    sim_dir, sim_cfg_filename, cmd_csc_baseline, cmd_num_runs, skip_post = \
        parse_arguments()
    sim_dir += "/"
    sim_cfg_path = sim_dir + sim_cfg_filename

    # Get config from config-file
    config, num_runs, csc_baseline, scenarios = simconfig_parse(sim_cfg_path)

    # Let config from command-line override
    if cmd_csc_baseline is not None:
        csc_baseline = cmd_csc_baseline
    if cmd_num_runs is not None:
        num_runs = cmd_num_runs

    # Sim name is same as config file
    sim_name = sim_cfg_filename[:-4] # Remove ".ini"
    csc_baseline_path = sim_dir + csc_baseline

    print("\nSimulation config:")
    print("Sim-name:    ", sim_name)
    print("Directory:   ", sim_dir)
    print("Config:      ", sim_cfg_path)
    print("CSC Baseline:", csc_baseline_path)
    print("# scenarios: ", len(scenarios))
    print("# runs:      ", num_runs)
    print("Skip post:   ", str(skip_post))
    
    return sim_name, sim_dir, scenarios, csc_baseline_path, \
            config, num_runs, skip_post

def main():
    start_time = datetime.now()
    print("Started:", start_time)

    sim_name, sim_dir, scenarios, csc_baseline_path, \
        config, num_runs, skip_post = parse_config()

    execution_id, execution_dir = prepare_filesystem(sim_name,
                                                     sim_dir,
                                                     scenarios)

    print("\nSimulation execution-id:", execution_id, "\n")
    
    print("\nMaking XML for all scenarios")
    simxml_make_xml_for_all_scenarios(sim_name,
                                      csc_baseline_path,
                                      scenarios,
                                      config)
    
    print("\nMaking simulation-run commands")
    run_cmds = create_run_sim_commands(sim_name, scenarios, num_runs)
    
    # Run simulations
    print("\nStarting simulations!")
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
        print("\nError in executions. Exiting.")
        exit()

    cleanup(scenarios)

    # Process results
    if not skip_post:
        process_results(scenarios, execution_dir)

    print("Finished simulation")
    print("\nSimulation config:")
    print("Sim-name:    ", sim_name)
    print("Directory:   ", sim_dir)
    print("CSC Baseline:", csc_baseline_path)
    print("# scenarios: ", len(scenarios))
    print("# runs:      ", num_runs)
    print("Skip post:   ", str(skip_post))
    print("Execution id:", execution_id, "in folder", execution_dir)

    end_time = datetime.now()
    print("End time:", end_time)
    print("Duration:", end_time - start_time)

main()

