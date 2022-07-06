import sys
import os
import shutil
import subprocess
import argparse
from dataclasses import dataclass
from datetime import datetime
from experiment_config import experiment_config_parse
try:
    import pandas as pd
    from parse_log import parse_logs_scenarios
    from parse_csv import parse_csv_scenarios
    from plot import plot_time_series
    from plot import plot_pdr_latency
    from plot import plot_duty_cycle
    from plot import plot_queue_util_selected_nodes
    from plot import plot_spatial_comparison
    from plot import plot_comparison
    from plot import plot_comparison_single_kpi_grouped
    from plot import plot_etx_details
    #from stats import stats_for_scenarios
    from stats_triscale import stats_for_scenarios
    from simxml import simxml_make_xml_for_all_scenarios
except:
    #print("Allow imports to fail since some invocations do not need (remote)")
    pass

# Constants
CODE_FOLDER_NAME = "code"
BUILD_FOLDER_NAME = "build"
ORG_FOLDER_NAME = "org"
PLOT_FOLDER_NAME = "plots"
BUILD_COOJA_NAME = "node.cooja"
EXECUTIONS_FOLDER_NAME = "executions"
MAKEFILE = "Makefile"
IOTLAB_TARGET="iotlab"
IOTLAB_ARCH_PATH="../../../../../../iot-lab-contiki-ng/arch" # TODO improve?
IOTLAB_BINARY_NAME="node.iotlab"
IOTLAB_BUILD_ARGUMENTS="TESTBED=1 BOARD=m3 -j8"
REMOTE_EXPERIMENT_PATH = "~/experiments/"
REMOTE_CONNECT = "arurke@phd.netwurke.com"
REMOTE_LOG_FILE = "remote_execution.log"

@dataclass
class Config:
    type: str
    exp_name: str
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
    app_warmup: int
    nodes: str
    remote_execution: bool
    prepare_only: bool
    run_only: bool
    fetch_from_remote: bool
    remote_log_file: str
    from_csv: bool

def add_commands_run_sim(sim_name, scenarios, num_runs):
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

def add_commands_build_firmware(scenarios):
    for scenario in scenarios:
        src_path = scenario['path'] + CODE_FOLDER_NAME

        # Adding "chronic" which eats stdout unless there is an error
        make_baseline = "chronic make -C " + src_path + \
                        " TARGET=" + IOTLAB_TARGET + \
                        " ARCH_PATH=" + IOTLAB_ARCH_PATH

        # Clean command. One per scenario.
        clean_command = make_baseline + " clean"
        # We need to separate words in cmd into array for subprocess
        clean_command = clean_command.split(' ')
        scenario['clean_cmd'] = clean_command

        # Build command. One per scenario.
        build_command = make_baseline + " " + IOTLAB_BUILD_ARGUMENTS
        build_command = build_command.split(' ')
        # Add cflagsextra now because they may contain spaces
        build_command.append("CFLAGSEXTRA=" + scenario['cflagsextra'])
        if scenario["makeflags"] != "":
            build_command.append(scenario['makeflags'])
        scenario['build_cmd'] = build_command

        # Add firmware path
        scenario['firmware'] = src_path + "/" + IOTLAB_BINARY_NAME

# Must be called after adding build-firmare-commands since firmware-path is needed
def add_commands_run_testbed(exp_name, scenarios, num_runs, duration, nodes):
    for scenario in scenarios:
        # For testbed we add an array of run-cmds (to run testbed), one for each run
        # (with simulator, multiple runs are handled in the simulator-running-script)
        scenario_run_cmds = []
        for run in range(num_runs):
            run_name = exp_name + "_scenario_" + scenario['name']
            # Folder for runs have naming run00, run01, etc. for easy sorting
            run_str = "run" + str('%0.2d' % run)
            logs_path = scenario['path'] + run_str + "/"
            run_cmd = "./run-testbed.sh " + run_name + "-" + run_str + " " + \
                scenario['firmware'] + " " + logs_path + " " + \
                str(duration) + " grenoble,m3," + nodes

            # Add finished command to the scenario run-cmd array
            scenario_run_cmds.append(run_cmd.split(' '))

        scenario['run_cmds'] = scenario_run_cmds

def process_results(scenarios, execution_dir, from_csv):
    # Get raw DFs for all runs of all scenarios.
    # The DFs are inserted into scenarios
    # Add True as second argument to squelch output
    if from_csv:
        parse_csv_scenarios(scenarios)
    else:
        parse_logs_scenarios(scenarios)

    # Save scenario meta DFs to CSV
    for scenario in scenarios:
        df_csv = scenario["path"] + scenario["name"] + "_meta_df.csv"
        scenario["meta_df"].to_csv(df_csv)

    # Make time-series from the raw DFs
 #   for scenario in scenarios:
 #       plot_time_series(scenario, 350, 'run0', 0)
 #       plot_time_series(scenario, 353, 'run0', 0)

    # Prepare plot folders
    plots_dir = execution_dir + PLOT_FOLDER_NAME + "/"
    if os.path.exists(plots_dir):
        shutil.rmtree(plots_dir)

    print("Generating plots dir", plots_dir)
    os.mkdir(plots_dir)

    # TODO ad-hoc way to find if this experiment was a spatial-test
    spatial_comparison = False
    for scenario in scenarios:
        if scenario["spatial_comparison"]:
            spatial_comparison = True

    # Get stats from the DFs
    scenarios_df = stats_for_scenarios(scenarios,
                                       spatial_comparison,
                                       plots_dir,
                                       write_runs_csv = True)

    # Save DF to CSV
    df_csv = execution_dir + "scenarios_df.csv"
    print("Saving csv of all scenarios at", df_csv)
    scenarios_df.to_csv(df_csv)

    # Print all columns
    pd.set_option('display.max_columns', None)
    print("Scenarios stats:\n", scenarios_df)

    # Plot
    plot_comparison_single_kpi_grouped(scenarios, scenarios_df, plots_dir)
    plot_comparison(scenarios, scenarios_df, plots_dir)
    if spatial_comparison:
        plot_spatial_comparison(scenarios_df, plots_dir)
        plot_etx_details(scenarios_df, plots_dir)
    #plot_pdr_latency(scenarios_df, plots_dir)
    #plot_duty_cycle(scenarios_df, plots_dir)
    #plot_queue_util_selected_nodes(scenarios_df, plots_dir)

# Create execution-id
def create_execution_id(exp_name, executions_dir):
    # ID should be: [config_name]-[date]-[id] (id is incremental)
    new_execution_id = exp_name + \
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
def prepare_filesystem(exp_name, sim_dir, scenarios,
                       executions_dir, execution_dir, remote=False):
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

    copy_node_code(sim_dir, scenarios, remote)
    copy_experiment_config_file(sim_dir, exp_name, execution_dir)

    print("Filesystem prepared")

def copy_experiment_config_file(sim_dir, exp_name, execution_dir):
    config_file_name = exp_name + ".ini"
    config_file_src = sim_dir + config_file_name
    config_file_dst = execution_dir + config_file_name
    print("Copying config from", config_file_src, "to", config_file_dst)
    shutil.copyfile(config_file_src, config_file_dst)

# Copy sims/[sim-name]/code into executions/[execution-id]/[scenario-name]/code
# Copy sims/[sim-name]/Makefile into executions/[execution-id]/[scenario-name]/Makefile
def copy_node_code(sim_dir, scenarios, folders_only=False):
    code_src_dir = sim_dir + CODE_FOLDER_NAME
    build_src_dir = code_src_dir + "/" + BUILD_FOLDER_NAME
    build_cooja_file = code_src_dir + "/" + BUILD_COOJA_NAME
    makefile_src = sim_dir + MAKEFILE

    for scenario in scenarios:
        # Source code
        code_dst_dir = scenario['path'] + CODE_FOLDER_NAME

        if folders_only:
            os.mkdir(code_dst_dir)
            continue

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
    argparser.add_argument('-s',
                           '--skipp',
                           action='store_true',
                           help = 'skip post-processing')
    argparser.add_argument('-n',
                           '--norun',
                           action = 'store_true',
                           help = 'Dont run experiment (require -i)')
    argparser.add_argument('-r',
                           '--remote',
                           action = 'store_true',
                           help = 'Execute experiment run via remote host')
    argparser.add_argument('-i',
                           '--id-execution',
                           type = str,
                           help = 'Execution ID (e.g. spatial_test_20220116_20)')
    argparser.add_argument('-f',
                           '--fetch-remote',
                           action = 'store_true',
                           help = 'Fetches data from remote and analyses. Used after -r. Requires -i')
    argparser.add_argument('-p',
                           '--prepare',
                           action = 'store_true',
                           help = 'Only do preparations. Used in remote (automatically sets -r.). Requires -i')
    argparser.add_argument('-e',
                           '--run-only',
                           action = 'store_true',
                           help = 'Only execute runs. Used in remote (automatically sets -r.) Requires -i')
    argparser.add_argument('-c',
                           '--from-csv',
                           action = 'store_true',
                           help = 'Read data from CSVs instead of logs (requires --norun).')
    args = argparser.parse_args()

    type = args.Type
    sim_dir = args.Path
    sim_cfg_filename = args.Config
    skip_post = args.skipp
    no_run = args.norun
    remote_execution = args.remote
    prepare_only = args.prepare
    run_only = args.run_only
    execution_id = args.id_execution
    fetch_from_remote = args.fetch_remote
    from_csv = args.from_csv

    if prepare_only and execution_id is None:
        print("Execution id (-i) must be set when only preparing")
        exit()
    if run_only and execution_id is None:
        print("Execution id (-i) must be set when only doing runs ")
        exit()
    if no_run and execution_id is None:
        print("Execution id (-i) must be set when not running experiment")
        exit()
    if fetch_from_remote and execution_id is None:
        print("Execution id (-i) must be set fetching data from remote")
        exit()
    if from_csv and not no_run:
        print("Cannot do run (must set --norun) when reading data from CSV")
        exit()

    # If fetching we force no running
    if fetch_from_remote:
        no_run = True

    # If preparation or exection only we force remote
    if prepare_only or run_only:
        remote_execution = True

    return type, sim_dir, sim_cfg_filename, skip_post, no_run, \
        remote_execution, prepare_only, run_only, execution_id, \
        fetch_from_remote, from_csv

def parse_config():
    # Get config from command line
    type, sim_dir, sim_cfg_filename, skip_post, no_run, \
        remote_execution, prepare_only, run_only, execution_id, \
        fetch_from_remote, from_csv = parse_arguments()

    # Add '/'
    os.path.join(sim_dir)

    # Folder to hold all executions
    executions_dir = sim_dir + EXECUTIONS_FOLDER_NAME + "/"

    if not no_run:
        do_run = True
        sim_cfg_path = sim_dir + sim_cfg_filename
    else:
        do_run = False
        sim_cfg_path = executions_dir + \
            execution_id + "/" +  sim_cfg_filename

    # Parse config-file
    parsedconfig, experiment_config, scenarios = \
        experiment_config_parse(sim_cfg_path)

    # Sim name is same as config file
    exp_name = sim_cfg_filename[:-4] # Remove ".ini"
    if "csc_baseline" in experiment_config:
        csc_baseline_path = sim_dir + experiment_config["csc_baseline"]
    else:
        csc_baseline_path = None

    if execution_id is None:
        execution_id = create_execution_id(exp_name, executions_dir)

    # Folder for this execution
    execution_dir = executions_dir + execution_id + "/"

    # Remote log-file
    remote_execution_dir = REMOTE_EXPERIMENT_PATH + execution_dir
    remote_log_file = remote_execution_dir + REMOTE_LOG_FILE

    config = Config(type, exp_name, sim_dir, executions_dir, execution_dir,
                    csc_baseline_path, sim_cfg_path,
                    experiment_config["num_runs"], skip_post,
                    do_run, execution_id, scenarios,
                    experiment_config["duration"],
                    experiment_config["app_warmup"],
                    experiment_config["nodes"],
                    remote_execution, prepare_only, run_only,
                    fetch_from_remote, remote_log_file, from_csv)

    print_config(config)

    return parsedconfig, config

def print_config(config):
    if config.do_run is False:
        print("\nNo execution! Analyzing: ", config.execution_id)
    print("\nExperiment config:")
    print("\tType:          ", config.type)
    print("\tName:          ", config.exp_name)
    print("\tDirectory:     ", config.sim_dir)
    print("\tConfig:        ", config.sim_cfg_path)
    print("\tRemote execut.:", config.remote_execution)
    print("\tPrepare only:  ", config.prepare_only)
    print("\tFetch remote:  ", config.fetch_from_remote)
    print("\tCSC Baseline:  ", config.csc_baseline_path)
    print("\tApp. warmup:   ", config.app_warmup)
    print("\t# scenarios:   ", len(config.scenarios))
    print("\t# runs pr sc.: ", config.num_runs)
    if config.duration is not None:
        print("\tDuration:      ", config.duration)
    if config.nodes is not None:
        print("\tNodes:         ", config.nodes)
    print("\tSkip post:     ", str(config.skip_post))
    print("\tDo execution:  ", str(config.do_run))
    print("\tData from CSV: ", str(config.from_csv))
    print("\tExecution id:  ", config.execution_id)
    print("\tExecution dir: ", config.execution_dir)
    if config.remote_execution:
        print("\tRemote log:    ", config.remote_log_file)

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
    # We want to alternate between scenarios to avoid any time-dependent
    # effects which could happen if e.g. one scenario was done at night
    # and one during the day
    for run in range(num_runs):
        for scenario in scenarios:
            print("\nExecuting run:")
            print("\tScenario:    " + scenario['name'])
            print("\tCflagsextra: " + scenario['cflagsextra'])
            print("\tMakeflags:   " + scenario['makeflags'])
            print("\tRun:         " + str(run) + " (" + str(run + 1) +
                  " out of " + str(num_runs) + ")")
            print("\tTime now:    " + str(datetime.now()))
            print("")
            process = subprocess.run(scenario['run_cmds'][run])

            if process.returncode != 0:
                return False

    return True

def transfer_from_remote(remote_file, local_file, is_directory=False):
    scp_dir = ""
    if is_directory:
        scp_dir = "-r "
    transfer = "scp " + scp_dir + REMOTE_CONNECT + ":" + REMOTE_EXPERIMENT_PATH + \
        remote_file + " " + local_file
    
    print("Executing: " + transfer)
    process = subprocess.run(transfer.split())
    if process.returncode != 0:
        print("Failed executing: " + transfer)
        return False
    
    return True

def transfer_to_remote(local_file, remote_path=None):
    transfer = "scp " + local_file + " " + \
        REMOTE_CONNECT + ":" + REMOTE_EXPERIMENT_PATH
    if remote_path is not None:
        transfer += remote_path + "/"
    
    #print("Executing: " + transfer)
    process = subprocess.run(transfer.split())
    if process.returncode != 0:
        print("Failed executing: " + transfer)
        return False
    
    return True

def run_testbed_remote(exp_name, sim_dir, execution_id, execution_dir, scenarios, log_file):
    # Create experiment folder
    remote_experiment_folder = REMOTE_EXPERIMENT_PATH + sim_dir
    setup_remote = "ssh " + REMOTE_CONNECT + \
        " mkdir -p " + remote_experiment_folder
    #print("Executing: " + setup_remote)
    #print("Executing: " + str(setup_remote.split()))
    process = subprocess.run(setup_remote.split())
    if process.returncode != 0:
        return False

    # Transfer scripts
    if not transfer_to_remote("experiment.py"):
        return False
    if not transfer_to_remote("run-testbed.sh"):
        return False
    if not transfer_to_remote("serial_script.sh"):
        return False
    if not transfer_to_remote("experiment_config.py"):
        return False

    # Transfer experiment config
    config_file_name = exp_name + ".ini"
    config_file_src = sim_dir + config_file_name
    if not transfer_to_remote(config_file_src, sim_dir):
        return False

    # Call experiment.py -p which makes folders etc.
    prepare_remote = "ssh " + REMOTE_CONNECT + \
        " cd " + REMOTE_EXPERIMENT_PATH + ";" + \
        " python3 " + REMOTE_EXPERIMENT_PATH + "experiment.py" + \
        " testbed " + \
        sim_dir + " " + \
        config_file_name + \
        " -p" + \
        " -i " + execution_id
    #print(prepare_remote)
    #print(prepare_remote.split())
    process = subprocess.run(prepare_remote.split())
    if process.returncode != 0:
        return False

    # Transfer firmware
    for scenario in scenarios:
        firmware = REMOTE_EXPERIMENT_PATH + scenario['firmware']
        if not transfer_to_remote(scenario['firmware'], scenario['path'] + CODE_FOLDER_NAME):
            return False

    # Call experiment.py --remote_start_execution with correct parameters (including execution-id!)
    # Had problems with the auth. It would not work even though SSH key was added properly.
    # Logged in directly and did "iotlab auth -u urke" and now I cannot log out. So most likely
    # that has solved it...until next time. Suspicion is that the iotlab-cli tools cannot find
    # the ssh-instance(?) - try install them with --user? pip install --user iotlabcli?
    # That might also remove the need for the PATH manipulation on the server.
    # Also: redirection into tee (or straight to file for that matter) messes up the
    # order of output (python output comes after bash) TODO
    run_remote = "ssh " + REMOTE_CONNECT + \
        " cd " + REMOTE_EXPERIMENT_PATH + ";" + \
        " eval $(ssh-agent -s); ssh-add ~/.ssh/fitiotlab_do;" + \
        " tmux new-session -d -s " + execution_id + " '" + \
        " python3 " + REMOTE_EXPERIMENT_PATH + "experiment.py" + \
        " testbed " + \
        sim_dir + " " + \
        config_file_name + \
        " -e" + \
        " -i " + execution_id + \
        " 2>&1 | tee " + log_file + "'"
    #print(run_remote)
    #print(run_remote.split())
    process = subprocess.run(run_remote.split())
    if process.returncode != 0:
        return False

    return True

def add_firmware(scenarios):
    for scenario in scenarios:
        print("Building scenario " + scenario['name'] + \
              ", cflagsextra: " + scenario['cflagsextra'] + \
              ", makeflags: " + scenario['makeflags'])

        # Clean
        process = subprocess.run(scenario['clean_cmd'])
        if process.returncode != 0:
            return False

        # Build
        process = subprocess.run(scenario['build_cmd'])
        if process.returncode != 0:
            return False

        print("Built firmware: " +  scenario['firmware'])

    return True

def is_remote_execution_done(execution_dir, execution_id, log_file):
    # Check if tmux session is still running
    check_remote = "ssh " + REMOTE_CONNECT + \
        " tmux has-session -t " + execution_id
    process = subprocess.run(check_remote.split())
    if process.returncode == 0:
        print("Remote still running. Tail of log:")
        print("--------")
        tail_log = "ssh " + REMOTE_CONNECT + \
            " tail " + log_file
        process = subprocess.run(tail_log.split())
        print("--------")
        return False

    return True

def fetch_data_from_remote(execution_dir, scenarios, num_runs):
    # Fetching log file
    log_file = execution_dir + REMOTE_LOG_FILE
    if not transfer_from_remote(log_file, execution_dir):
        return False

    tail_log = "tail " + log_file
    print("Tail of log-file: " + log_file)
    print("--------")
    process = subprocess.run(tail_log.split())
    print("--------")

    # Fetching run logs
    for scenario in scenarios:
        for run in range(num_runs):
            # Runs always have two digits (run00, run01, etc.)
            run_log_dir = scenario['path'] + "run" + str('%0.2d' % run)
            if not transfer_from_remote(run_log_dir, scenario['path'], True):
                return False
    return True

def print_finished_message(config, start_time):
    print("Finished experiment")
    print_config(config)

    end_time = datetime.now()
    print("End time:", end_time)
    print("Duration:", end_time - start_time)

# Typical usage:
# With local execution of testbed:
# `python3 experiment.py testbed test-orchestra/ spatial_test.ini`
#
# With remote execution of testbed is done in two steps.
# First step:
#
# `python3 experiment.py testbed test-orchestra/ spatial_test.ini -r`
#
# which:
# 1) Prepare local filesystem and builds firmwares
# 2) Upload scripts and configuration to remote
# 3) Make remote filesystem ready (experiment.py at remote with -p)
# 4) Transfer firmwares from local to remote
# 5) Start execution of testbed via remote (experiment.py at remote with -e)
#
# Second step:
#
# `python3 experiment.py testbed test-orchestra/ spatial_test.ini -f -i spatial_test_20220116_1`
#
# which:
# 1) Check if remote execution is done
# 2) Download logs and run analysis
def main():
    parsedconfig, config = parse_config()

    start_time = datetime.now()
    print("Started:", start_time)

    prepare_datastructures(config.scenarios, config.execution_dir)

    # Only do preparations. Used at remote to ready for receiving firmware++
    if config.prepare_only:
        prepare_filesystem(config.exp_name,
             config.sim_dir,
             config.scenarios,
             config.executions_dir,
             config.execution_dir,
             config.remote_execution)
        exit()

    # Run testbed only. Used at remote after firmware++ has been received.
    if config.run_only:
        add_commands_build_firmware(config.scenarios)
        add_commands_run_testbed(
            config.exp_name, config.scenarios,
            config.num_runs, config.duration,
            config.nodes)
        if not run_testbed(config.scenarios, config.num_runs):
            print("\nError in executions. Exiting.")
            exit()

        print_finished_message(config, start_time)
        exit()

    # Start execution on remote. Used at local as first step (fetch is 2nd).
    if config.remote_execution:
        if config.type != "testbed":
            print("Only remote testbed supported!")
            exit()

        prepare_filesystem(config.exp_name,
                     config.sim_dir,
                     config.scenarios,
                     config.executions_dir,
                     config.execution_dir)

        print("Making testbed-run commands")
        add_commands_build_firmware(config.scenarios)
        add_commands_run_testbed(
            config.exp_name, config.scenarios,
            config.num_runs, config.duration,
            config.nodes)

        print("Adding firmwares")
        if not add_firmware(config.scenarios):
            exit()

        print("\nStarting testbed remotely!")
        if not run_testbed_remote(config.exp_name,
                           config.sim_dir,
                           config.execution_id,
                           config.execution_dir,
                           config.scenarios,
                           config.remote_log_file):
            print("Remote execution failed!")

        cleanup(config.scenarios)
        exit()

    # Fetch data from remote and analyse
    if config.fetch_from_remote:
        if not is_remote_execution_done(
            config.execution_dir, config.execution_id, config.remote_log_file):
            exit()

        if not fetch_data_from_remote(config.execution_dir, config.scenarios, config.num_runs):
            print("Fetching data from remote failed")
            exit()

        # Process results
        if not config.skip_post:
            process_results(config.scenarios, config.execution_dir, False)
        exit()

    # No special cases. Continue running (if not disabled) and analyze.
    if config.do_run: 
        prepare_filesystem(config.exp_name,
                             config.sim_dir,
                             config.scenarios,
                             config.executions_dir,
                             config.execution_dir)

        if config.type == "simulation":
            print("Making XML for all scenarios")
            simxml_make_xml_for_all_scenarios(config.exp_name,
                                      config.csc_baseline_path,
                                      config.scenarios,
                                      parsedconfig)

            print("Making simulation-run commands")
            run_cmds = add_commands_run_sim(
                config.exp_name, config.scenarios, config.num_runs)

            print("\nStarting simulation!")
            if not run_simulation(run_cmds):
                print("\nError in executions. Exiting.")
                exit()

        if config.type == "testbed":
            print("Making testbed-run commands")
            add_commands_build_firmware(config.scenarios)
            add_commands_run_testbed(
                config.exp_name, config.scenarios,
                config.num_runs, config.duration,
                config.nodes)

            print("Adding firmwares")
            if not add_firmware(config.scenarios):
                exit()

            print("\nStarting testbed!")
            if not run_testbed(config.scenarios, config.num_runs):
                print("\nError in executions. Exiting.")
                exit()

        cleanup(config.scenarios)

    # Process results
    if not config.skip_post:
        process_results(config.scenarios, config.execution_dir, config.from_csv)

    print_finished_message(config, start_time)

main()

