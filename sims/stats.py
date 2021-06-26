# Makes stats for all
import pandas as pd

NUM_ROWS_SKIP_STEADY_STATE = 100
TIME_TO_SKIP_STEADY_STATE = "2 Min"

def analyze_run(packets_df, energest_df):
    run_entry = {}
    run_entry['latency_mean'] = packets_df.latency.mean()
    run_entry['latency_50'] = packets_df.latency.median()
    run_entry['latency_99'] = packets_df.latency.quantile(0.99)
    run_entry['latency_n2_mean'] = packets_df[packets_df.node == 2].latency.mean()
    run_entry['latency_n3_mean'] = packets_df[packets_df.node == 3].latency.mean()

    run_entry['pdr_mean'] = packets_df.pdr.mean()
    # Not sure if these make sense
    run_entry['pdr_50'] = packets_df.pdr.median()
    run_entry['pdr_99'] = packets_df.pdr.quantile(0.99)

    run_entry['duty_cycle_mean'] = energest_df.duty_cycle.mean()
    run_entry['duty_cycle_50'] = energest_df.duty_cycle.median()
    run_entry['duty_cycle_99'] = energest_df.duty_cycle.quantile(0.99)

    #run_entry['channel_utilization_mean'] = energest_df.channel_utilization.mean()
    #run_entry['channel_utilization_50'] = energest_df.channel_utilization.median()
    #run_entry['channel_utilization_99'] = energest_df.channel_utilization.quantile(0.99)

    # Drop at start and end to get only the steady-state
    ss_packets_df = packets_df.copy()
    ss_energest_df = energest_df.copy()
    # By time
    packet_start = packets_df.index.values[0]
    packet_start_ss = packet_start + pd.Timedelta(TIME_TO_SKIP_STEADY_STATE)
    packet_end = packets_df.index.values[-1]
    packet_end_ss = packet_end - pd.Timedelta(TIME_TO_SKIP_STEADY_STATE)
    #steady_state_df = steady_state_df[packet_start_ss:packet_end_ss]
    ss_energest_df = ss_energest_df[packet_start_ss:packet_end_ss]

    # By packets
    ss_packets_df[NUM_ROWS_SKIP_STEADY_STATE:]
    ss_packets_df = ss_packets_df[:-NUM_ROWS_SKIP_STEADY_STATE]

    run_entry['ss_latency_mean'] = ss_packets_df.latency.mean()
    run_entry['ss_latency_50'] = ss_packets_df.latency.median()
    run_entry['ss_latency_99'] = ss_packets_df.latency.quantile(0.99)

    run_entry['ss_pdr_mean'] = ss_packets_df.pdr.mean()
    # Not sure if these make sense
    run_entry['ss_pdr_50'] = ss_packets_df.pdr.median()
    run_entry['ss_pdr_99'] = ss_packets_df.pdr.quantile(0.99)

    run_entry['ss_duty_cycle_mean'] = ss_energest_df['duty_cycle'].mean()
    run_entry['ss_duty_cycle_50'] = ss_energest_df['duty_cycle'].median()
    run_entry['ss_duty_cycle_99'] = ss_energest_df['duty_cycle'].quantile(0.99)
    
    run_entry['ss_duty_cycle_tx_mean'] = ss_energest_df['duty_cycle_tx'].mean()
    run_entry['ss_duty_cycle_tx_50'] = ss_energest_df['duty_cycle_tx'].median()
    run_entry['ss_duty_cycle_tx_99'] = ss_energest_df['duty_cycle_tx'].quantile(0.99)

    run_entry['ss_duty_cycle_rx_mean'] = ss_energest_df['duty_cycle_rx'].mean()
    run_entry['ss_duty_cycle_rx_50'] = ss_energest_df['duty_cycle_rx'].median()
    run_entry['ss_duty_cycle_rx_99'] = ss_energest_df['duty_cycle_rx'].quantile(0.99)

    #run_entry['ss_channel_utilization_mean'] = ss_energest_df.channel_utilization.mean()
    #run_entry['ss_channel_utilization_50'] = ss_energest_df.channel_utilization.median()
    #run_entry['ss_channel_utilization_99'] = ss_energest_df.channel_utilization.quantile(0.99)
    
    return pd.DataFrame([run_entry])

def analyze_runs(raw_packets_dfs, raw_energest_dfs):
    runs_df_dict = []
    for key in raw_packets_dfs.keys():
        runs_df_dict.append(
            analyze_run(raw_packets_dfs[key], raw_energest_dfs[key]))

    return pd.concat(runs_df_dict, ignore_index=True)

def analyze_scenario(runs_df, scenario_name):
    scenario_entry = {"scenario": scenario_name}
    # TODO get CIs
    scenario_entry['latency_50'] = runs_df.latency_50.median()
    scenario_entry['latency_mean'] = runs_df.latency_mean.mean()
    scenario_entry['ss_latency_50'] = runs_df.ss_latency_50.median()
    scenario_entry['ss_latency_mean'] = runs_df.ss_latency_mean.mean()
    scenario_entry['ss_latency_99'] = runs_df.ss_latency_99.quantile(0.99)

    scenario_entry['n2_latency_mean'] = runs_df.latency_n2_mean.mean()
    scenario_entry['n3_latency_mean'] = runs_df.latency_n3_mean.mean()

    scenario_entry['pdr_mean'] = runs_df.pdr_mean.mean()
    scenario_entry['ss_pdr_mean'] = runs_df.ss_pdr_mean.mean()
    scenario_entry['ss_pdr_99'] = runs_df.ss_pdr_mean.quantile(0.99)

    scenario_entry['duty_cycle_mean'] = runs_df.duty_cycle_mean.mean()
    scenario_entry['duty_cycle_50'] = runs_df.duty_cycle_50.median()
    scenario_entry['duty_cycle_99'] = runs_df.duty_cycle_99.quantile(0.99)

    #scenario_entry['channel_utilization_mean'] = runs_df.channel_utilization_mean.mean()
    #scenario_entry['channel_utilization_50'] = runs_df.channel_utilization_50.median()
    #scenario_entry['channel_utilization_99'] = runs_df.channel_utilization_99.quantile(0.99)

    scenario_entry['ss_duty_cycle_mean'] = runs_df.ss_duty_cycle_mean.mean()
    scenario_entry['ss_duty_cycle_50'] = runs_df.ss_duty_cycle_50.median()
    scenario_entry['ss_duty_cycle_99'] = runs_df.ss_duty_cycle_99.quantile(0.99)

    scenario_entry['ss_duty_cycle_tx_mean'] = runs_df.ss_duty_cycle_tx_mean.mean()
    scenario_entry['ss_duty_cycle_tx_50'] = runs_df.ss_duty_cycle_tx_50.median()
    scenario_entry['ss_duty_cycle_tx_99'] = runs_df.ss_duty_cycle_tx_99.quantile(0.99)

    scenario_entry['ss_duty_cycle_rx_mean'] = runs_df.ss_duty_cycle_rx_mean.mean()
    scenario_entry['ss_duty_cycle_rx_50'] = runs_df.ss_duty_cycle_rx_50.median()
    scenario_entry['ss_duty_cycle_rx_99'] = runs_df.ss_duty_cycle_rx_99.quantile(0.99)

    #scenario_entry['ss_channel_utilization_mean'] = runs_df.ss_channel_utilization_mean.mean()
    #scenario_entry['ss_channel_utilization_50'] = runs_df.ss_channel_utilization_50.median()
    #scenario_entry['ss_channel_utilization_99'] = runs_df.ss_channel_utilization_99.quantile(0.99)

    return pd.DataFrame([scenario_entry])

def stats_for_scenario(scenario, write_runs_csv=False):
    # Get stats per run (which are typically not very interesting)
    # We only work on packet DF for now
    runs_df = analyze_runs(scenario['raw_packets_dfs'], scenario['raw_energest_dfs'])
    #print("Analyzed runs: " + str(scenario['raw_packets_dfs'].keys()))

    # Analyze the run-stats to get scenario-stats
    scenario_df = analyze_scenario(runs_df, scenario['name'])

    return scenario_df

def stats_for_scenarios(scenarios, write_runs_csv=False):
    scenarios_df_list = []

    for scenario in scenarios:
        scenarios_df_list.append(stats_for_scenario(scenario, write_runs_csv))

    # Make one DF from the list of scenario DFs
    scenarios_df = pd.concat(scenarios_df_list)
    scenarios_df.set_index("scenario", inplace=True)

    #print("Analyzed scenarios: " + str(scenarios))
    #print(scenarios_df)

    return scenarios_df
