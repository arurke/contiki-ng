# Makes stats DFs using triscale
import pandas as pd
import numpy as np
import sys
sys.path.append('triscale')
import triscale as triscale

NUM_ROWS_SKIP_SS_START = 1
NUM_ROWS_SKIP_SS_END = 1
TIME_TO_SKIP_STEADY_STATE = "1 Sec"

def calculate_metric(input_df, metric, measure, check_convergence=False):
    
    if measure == "absolute_etx":
        app_tx_etx = input_df["transmissions"].sum() / \
            len(input_df[input_df["result"] == "ok"])
        print("ETX: " + str(app_tx_etx))
        return app_tx_etx
    
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

def analyze_run(packets_df, energest_df, queue_df, mac_tx_df):
    # Make DF with app-mac-packets only
    app_mac_tx_df = mac_tx_df[mac_tx_df["app"] == 1].copy()
    
    # Create DFs with steady state (i.e. drop at start and end)
    ss_packets_df = packets_df.copy()
    ss_energest_df = energest_df.copy()
    ss_queue_df = queue_df.copy()
    ss_app_mac_tx_df = app_mac_tx_df.copy()
    
    packet_start = packets_df.index.values[0]
    packet_start_ss = packet_start + pd.Timedelta(TIME_TO_SKIP_STEADY_STATE)
    packet_end = packets_df.index.values[-1]
    packet_end_ss = packet_end - pd.Timedelta(TIME_TO_SKIP_STEADY_STATE)

    # By time
    #steady_state_df = steady_state_df[packet_start_ss:packet_end_ss]
    ss_energest_df = ss_energest_df[packet_start_ss:packet_end_ss]

    # By packets
    ss_packets_df = \
        ss_packets_df[NUM_ROWS_SKIP_SS_START:-NUM_ROWS_SKIP_SS_END]
    ss_queue_df = \
        ss_queue_df[NUM_ROWS_SKIP_SS_START:-NUM_ROWS_SKIP_SS_END]
    ss_app_mac_tx_df = \
        ss_app_mac_tx_df[NUM_ROWS_SKIP_SS_START:-NUM_ROWS_SKIP_SS_END]

    # Make queue DF per node
    ss_queue_df_2 = ss_queue_df.copy()
    ss_queue_df_2 = ss_queue_df_2[ss_queue_df_2.node == 2]
    ss_queue_df_3 = ss_queue_df.copy()
    ss_queue_df_3 = ss_queue_df_3[ss_queue_df_3.node == 3]

    # Make the following metrics for the given measures for the given DFs
    # The-per-node is a bit hackish - gave them special prefix
    default_measures = ["mean", 50, 95, 99, 99.9, "maximum"]
    metric_packets = [{"metric": "latency", "measures":default_measures},
                      {"metric": "pdr", "measures":["mean"]}]
    metric_mac_app_tx = [{"metric": "mac_app_tx_etx", "measures":["absolute_etx"]}]
    metric_energest = [{"metric": "duty_cycle", "measures":default_measures},
                       {"metric": "duty_cycle_tx", "measures":default_measures},
                       {"metric": "duty_cycle_rx", "measures":default_measures}]
    metric_queue = [{"metric": "queue_fill", "measures":default_measures}]
    dfs = [{"df":packets_df, "metric":metric_packets, "prefix":""},
           {"df":energest_df, "metric":metric_energest, "prefix":""},
           {"df":queue_df, "metric":metric_queue, "prefix":""},
           {"df":app_mac_tx_df, "metric":metric_mac_app_tx, "prefix":""},
           {"df":ss_app_mac_tx_df, "metric":metric_mac_app_tx, "prefix":"ss_"},
           {"df":ss_packets_df, "metric":metric_packets, "prefix":"ss_"},
           {"df":ss_energest_df, "metric":metric_energest, "prefix":"ss_"},
           {"df":ss_queue_df, "metric":metric_queue, "prefix":"ss_"},
           {"df":ss_queue_df_2, "metric":metric_queue, "prefix":"ss2_"},
           {"df":ss_queue_df_3, "metric":metric_queue, "prefix":"ss3_"}]
    
    # Actually make metrics and fill into DF entry
    run_entry = {}
    for df in dfs:
        for metric in df["metric"]:
            for measure in metric["measures"]:
                run_metric_name = df["prefix"] + metric["metric"] + "_" + str(measure)
                run_entry[run_metric_name] = \
                    calculate_metric(df["df"], metric["metric"], measure)
    
    # Make DF out of the entry
    return pd.DataFrame([run_entry])

def analyze_runs(raw_dfs):
    #TODO get only app_started
    raw_packets_dfs = raw_dfs["raw_packets_dfs"]
    raw_energest_dfs = raw_dfs["raw_energest_dfs"]
    raw_queue_dfs = raw_dfs["raw_queue_dfs"]
    raw_mac_tx_dfs = raw_dfs["raw_mac_tx_dfs"]

    runs_df_dict = []
    for key in raw_packets_dfs.keys():
        runs_df_dict.append(
            analyze_run(raw_packets_dfs[key][raw_packets_dfs[key]["app_started"] == 1],
                        raw_energest_dfs[key][raw_energest_dfs[key]["app_started"] == 1],
                        raw_queue_dfs[key][raw_queue_dfs[key]["app_started"] == 1],
                        raw_mac_tx_dfs[key][raw_mac_tx_dfs[key]["app_started"] == 1]))

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
    adhoc_percentile = 50
    adhoc_confidence = 95
    
    kpis = [{"metric":"latency",
                # "name":"_p" + str(adhoc_percentile) + "_%" + str(adhoc_confidence) + "_U",
                "name":"",
                "settings":{"percentile": adhoc_percentile,
                       "confidence": adhoc_confidence,
                       "bounds":[0.001,120],
                       "bound":"upper"}},
             {"metric":"latency",
                # "name":"_p" + str(adhoc_percentile) + "_%" + str(adhoc_confidence) + "_U",
                "name":"_U",
                "settings":{"percentile": adhoc_percentile,
                       "confidence": adhoc_confidence,
                       "bounds":[0.001,120],
                       "bound":"upper"}},
             {"metric":"latency",
                # "name":"_p" + str(adhoc_percentile) + "_%" + str(adhoc_confidence) + "_U",
                "name":"_L",
                "settings":{"percentile": adhoc_percentile,
                       "confidence": adhoc_confidence,
                       "bounds":[0.001,120],
                       "bound":"lower"}},
                {"metric":"pdr",
                #"name":"_p" + str(adhoc_percentile) + "_%" + str(adhoc_confidence) + "_L",
                "name":"",
                "settings":{"percentile": default_percentile,
                       "confidence": default_confidence,
                       "bounds":[0,100],
                       "bound":"lower"}},
               {"metric":"pdr",
                #"name":"_p" + str(adhoc_percentile) + "_%" + str(adhoc_confidence) + "_L",
                "name":"_L",
                "settings":{"percentile": adhoc_percentile,
                       "confidence": adhoc_confidence,
                       "bounds":[0,100],
                       "bound":"lower"}},
               {"metric":"pdr",
                #"name":"_p" + str(adhoc_percentile) + "_%" + str(adhoc_confidence) + "_L",
                "name":"_U",
                "settings":{"percentile": adhoc_percentile,
                       "confidence": adhoc_confidence,
                       "bounds":[0,100],
                       "bound":"upper"}},
               {"metric":"duty_cycle",
                #"name":"_p" + str(default_percentile) + "_%" + str(default_confidence) + "_U",
                "name":"",
                "settings":{"percentile": default_percentile,
                       "confidence": default_confidence,
                       "bounds":[0,100],
                       "bound":"upper"}},
               {"metric":"duty_cycle_tx",
                #"name":"_p" + str(default_percentile) + "_%" + str(default_confidence) + "_U",
                "name":"",
                "settings":{"percentile": default_percentile,
                       "confidence": default_confidence,
                       "bounds":[0,100],
                       "bound":"upper"}},
               {"metric":"duty_cycle_rx",
                #"name":"_p" + str(default_percentile) + "_%" + str(default_confidence) + "_U",
                "name":"",
                "settings":{"percentile": default_percentile,
                       "confidence": default_confidence,
                       "bounds":[0,100],
                       "bound":"upper"}},
               {"metric":"queue_fill",
                #"name":"_p" + str(default_percentile) + "_%" + str(default_confidence) + "_U",
                "name":"",
                "settings":{"percentile": default_percentile,
                       "confidence": default_confidence,
                       "bounds":[0,100],
                       "bound":"upper"}},
               {"metric":"mac_app_tx_etx",
                #"name":"_p" + str(adhoc_percentile) + "_%" + str(adhoc_confidence) + "_U",
                "name":"_U",
                "settings":{"percentile": adhoc_percentile,
                       "confidence": adhoc_confidence,
                       "bounds":[0,100],
                       "bound":"upper"}},
               {"metric":"mac_app_tx_etx",
                #"name":"_p" + str(adhoc_percentile) + "_%" + str(adhoc_confidence) + "_L",
                "name":"_L",
                "settings":{"percentile": adhoc_percentile,
                       "confidence": adhoc_confidence,
                       "bounds":[0,100],
                       "bound":"lower"}}]
    
    # TODO this needs some fixing as the naming of the columns in the resulting
    # DF will say _mean, _median, etc. while it is actually the default_percentile
    # default_confidence % CI of these values.
    for metric in runs_df.columns:
        for kpi in kpis:
            if kpi["metric"] in metric:
                scenario_entry[metric + kpi['name']] = calculate_kpi(runs_df[metric].values,
                                                       kpi["settings"],
                                                       metric)

    return pd.DataFrame([scenario_entry])

def stats_for_scenario(scenario, write_runs_csv = False):

    # Get stats per run (which are typically not very interesting)
    runs_df = analyze_runs(scenario['raw_dfs'])

    if write_runs_csv:
        runs_df_csv = scenario["path"] + "runs_df.csv"
        print("Saving csv of all runs at", runs_df_csv)
        runs_df.to_csv(runs_df_csv)

    # Add the runs_df to the scenario structure
    scenario["runs_df"] = runs_df
    #print("Analyzed runs: " + str(scenario['raw_dfs']['raw_packets_dfs'].keys()))
    #print("Analyzed runs: " + str(runs_df.columns))

    # Analyze the run-stats to get scenario-stats
    scenario_df = analyze_scenario(runs_df, scenario['name'])

    return scenario_df

def stats_for_scenarios(scenarios, write_runs_csv = False):
    scenarios_df_list = []

    for scenario in scenarios:
        scenarios_df_list.append(stats_for_scenario(scenario, write_runs_csv))

    # Make one DF from the list of scenario DFs
    scenarios_df = pd.concat(scenarios_df_list)
    scenarios_df.set_index("scenario", inplace=True)

    #print("Analyzed scenarios: " + str(scenarios))
    #print(scenarios_df)

    return scenarios_df
