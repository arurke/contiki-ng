%matplotlib inline
import glob
import pandas as pd
from simconfig import simconfig_parse
from plot import plot_time_series
from plot import plot_pdr_latency
from plot import plot_duty_cycle
from plot import plot_queue_util_selected_nodes
from parse_log import parse_logs_scenarios
from parse_csv import parse_csv_scenarios
#from stats_triscale import stats_for_scenario
#from stats_triscale import stats_for_scenarios
from stats import stats_for_scenario
from stats import stats_for_scenarios



# Set these to select which results to inspect
#EXECUTION_DIR = "test-orchestra/executions/orchestra_test_20200518_2/"
#EXECUTION_DIR = "test-orchestra/executions/grid_55_20200509_0/"
EXECUTION_DIR = "test-orchestra/executions/orchestra_test_simple_20210623_2/"

def parse_existing_results(from_csvs):
    # Get config file used in the sim, it lies in the execution dir
    config_file = glob.glob(EXECUTION_DIR + "*.ini")
    config, num_runs, csc_baseline, scenarios = simconfig_parse(config_file)

    # Build list of scenarios (it contains paths to all the files)
    for scenario in scenarios:
        scenario['path'] = EXECUTION_DIR + scenario['name'] + "/"
    
    # Get DFs for all runs of all scenarios. DFs are inserted in scenarios.
    if from_csvs:
        parse_csv_scenarios(scenarios)
    else:
        parse_logs_scenarios(scenarios, quiet=True)

    return scenarios

def process_results_as_in_simulate(scenarios, execution_dir = EXECUTION_DIR):
    # Make time-series from the raw DFs
    #for scenario in scenarios:
        #plot_time_series(scenario, 2, 'run15', 0)
        #plot_time_series(scenario, 3, 'run15', 0)
       # if scenario['name'] == "60%":
       #     for i in range(1,20):
       #         plot_latency_packet_loss_time_series(scenario, 2, 'run' + str(i), 1)
       #         plot_latency_packet_loss_time_series(scenario, 3, 'run' + str(i), 1)

    # Get stats from the DFs
    scenarios_df = stats_for_scenarios(scenarios, write_runs_csv=False)

    # Save DF to CSV
    #df_csv = execution_dir + "scenarios_df.csv"
    #print("Saving csv of all scenarios at", df_csv)
    #scenarios_df.to_csv(df_csv)
    
    #print("Scenarios stats:\n", scenarios_df)

    plot_pdr_latency(scenarios_df, execution_dir)
    plot_duty_cycle(scenarios_df, execution_dir)
    plot_queue_util_selected_nodes(scenarios_df, execution_dir)
    
    return scenarios_df

# Parse results
scenarios = parse_existing_results(from_csvs=True)

# Get scenarios stats
#scenarios_df = stats_for_scenarios(scenarios)

scenarios_df = process_results_as_in_simulate(scenarios)

# Print all columns
pd.set_option('display.max_columns', None)
print("Scenarios stats:\n", scenarios_df)