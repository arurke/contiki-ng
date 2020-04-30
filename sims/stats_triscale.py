# Makes stats DFs using triscale
import pandas as pd
import numpy as np
import sys
sys.path.append('triscale')
import triscale as triscale

NUM_ROWS_SKIP_SS_START = 100
NUM_ROWS_SKIP_SS_END = 20
TIME_TO_SKIP_STEADY_STATE = "2 Min"

def calculate_metric(input_df, metric, measure):
    # TriScale expects an index + two columns x and y
    
    # First make a copy so we can edit freely
    df = input_df.copy()
    
    # Select only the relevant column (timestamp is the index)
    df = df[metric]
    
    # Revert back to default index (i.e. incremental int).
    # Timestamp becomes just a regular column
    df = df.reset_index()
    
    # Rename to match Triscale requirements
    df = df.rename(columns={"timestamp":"x", metric:"y"})

    # Do not use the convergence test as this slightly impacts results (see TODO)
    # The result of this is same as if we would call mean(), median() etc. ourselves
    convergence_result, measure, figure = \
        triscale.analysis_metric(
            df, {"measure":measure}, {"expected":False, "tolerance": 7},
            plot=False, showplot=False, verbose=False)
    return measure

def analyze_run(packets_df, energest_df, queue_df):
    # Create DFs with steady state (i.e. drop at start and end)
    ss_packets_df = packets_df.copy()
    ss_energest_df = energest_df.copy()
    ss_queue_df = queue_df.copy()
    
    # By time
    packet_start = packets_df.index.values[0]
    packet_start_ss = packet_start + pd.Timedelta(TIME_TO_SKIP_STEADY_STATE)
    packet_end = packets_df.index.values[-1]
    packet_end_ss = packet_end - pd.Timedelta(TIME_TO_SKIP_STEADY_STATE)
    #steady_state_df = steady_state_df[packet_start_ss:packet_end_ss]
    ss_energest_df = ss_energest_df[packet_start_ss:packet_end_ss]

    # By packets
    ss_packets_df = \
        ss_packets_df[NUM_ROWS_SKIP_SS_START:-NUM_ROWS_SKIP_SS_END]
    ss_queue_df = \
        ss_queue_df[NUM_ROWS_SKIP_SS_START:-NUM_ROWS_SKIP_SS_END]

    # Make queue DF per node
    ss_queue_df_2 = ss_queue_df.copy()
    ss_queue_df_2 = ss_queue_df_2[ss_queue_df_2.node == 2]
    ss_queue_df_3 = ss_queue_df.copy()
    ss_queue_df_3 = ss_queue_df_3[ss_queue_df_3.node == 3]

    # Make the following metrics for the given measures for the given DFs
    # The-per-node is a bit hackish - gave them special prefix
    metric_packets = ["latency", "pdr"]
    metric_energest = ["duty_cycle", "channel_utilization"]
    metric_queue = ["queue_fill"]
    measures = ["mean", 50, 99, 99.9, "maximum"]
    dfs = [{"df":packets_df, "metric":metric_packets, "prefix":""},
           {"df":energest_df, "metric":metric_energest, "prefix":""},
           {"df":queue_df, "metric":metric_queue, "prefix":""},
           {"df":ss_packets_df, "metric":metric_packets, "prefix":"ss_"},
           {"df":ss_energest_df, "metric":metric_energest, "prefix":"ss_"},
           {"df":ss_queue_df, "metric":metric_queue, "prefix":"ss_"},
           {"df":ss_queue_df_2, "metric":metric_queue, "prefix":"ss2_"},
           {"df":ss_queue_df_3, "metric":metric_queue, "prefix":"ss3_"}]
    
    # Actually make metrics and fill into DF entry
    run_entry = {}
    for df in dfs:
        for metric in df["metric"]:
            for measure in measures:
                run_metric_name = df["prefix"] + metric + "_" + str(measure)
                run_entry[run_metric_name] = \
                    calculate_metric(df["df"], metric, measure)
    
    # Make DF out of the entry
    return pd.DataFrame([run_entry])

def analyze_runs(raw_packet_dfs, raw_energest_dfs, raw_queue_dfs):
    runs_df_dict = []
    for key in raw_packet_dfs.keys():
        runs_df_dict.append(
            analyze_run(raw_packet_dfs[key],
                        raw_energest_dfs[key],
                        raw_queue_dfs[key]))

    return pd.concat(runs_df_dict, ignore_index=True)

def calculate_kpi(values, settings, name):
    independent, kpi = triscale.analysis_kpi(
                        values,
                        settings,
                        verbose=False)
    # Independence is not critical in simulations?
    #if not independent:
        #print("Not independent for", name)
    if np.isnan(kpi):
        print("KPI Nan, probably too few values(" +
              str(len(values)) + ") for " + name)

    return kpi

def analyze_scenario(runs_df, scenario_name):
    scenario_entry = {"scenario": scenario_name}
    default_percentile = 95
    default_confidence = 95
    
    kpis = [{"metric":"latency",
                "settings":{"percentile": default_percentile,
                       "confidence": default_confidence,
                       "bounds":[0.001,12],
                       "bound":"upper"}},
               {"metric":"pdr",
                "settings":{"percentile": 5,
                       "confidence": default_confidence,
                       "bounds":[0,100],
                       "bound":"lower"}},
               {"metric":"duty_cycle",
                "settings":{"percentile": default_percentile,
                       "confidence": default_confidence,
                       "bounds":[0,100],
                       "bound":"upper"}},
               {"metric":"channel_utilization",
                "settings":{"percentile": default_percentile,
                       "confidence": default_confidence,
                       "bounds":[0,100],
                       "bound":"upper"}},
               {"metric":"queue_fill",
                "settings":{"percentile": default_percentile,
                       "confidence": default_confidence,
                       "bounds":[0,100],
                       "bound":"upper"}}]
    measures = ["mean", 50, 99, 99.9, "maximum"]
    prefixes = ["", "ss_", "ss2_", "ss3_"]
    
    # TODO this needs some fixing as the naming of the columns in the resulting
    # DF will say _mean, _median, etc. while it is actually the default_percentile
    # default_confidence % CI of these values.
    for kpi in kpis:
        for prefix in prefixes:
            for measure in measures:
                kpi_name = prefix + kpi["metric"] + "_" + str(measure)
                if kpi_name in runs_df.columns:
                    scenario_entry[kpi_name] = \
                        calculate_kpi(runs_df[kpi_name].values,
                                      kpi["settings"],
                                      kpi_name)

    return pd.DataFrame([scenario_entry])

def stats_for_scenario(scenario):
    # Get stats per run (which are typically not very interesting)
    # We only work on packet DF for now
    runs_df = analyze_runs(scenario['raw_packet_dfs'],
                           scenario['raw_energest_dfs'],
                           scenario['raw_queue_dfs'])
    #print("Analyzed runs: " + str(scenario['raw_packet_dfs'].keys()))

    # Analyze the run-stats to get scenario-stats
    scenario_df = analyze_scenario(runs_df, scenario['name'])

    return scenario_df

def stats_for_scenarios(scenarios):
    scenarios_df_list = []

    for scenario in scenarios:
        scenarios_df_list.append(stats_for_scenario(scenario))

    # Make one DF from the list of scenario DFs
    scenarios_df = pd.concat(scenarios_df_list)
    scenarios_df.set_index("scenario", inplace=True)

    #print("Analyzed scenarios: " + str(scenarios))
    #print(scenarios_df)

    return scenarios_df
