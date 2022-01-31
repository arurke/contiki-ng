# Makes stats DFs using triscale
import pandas as pd
import numpy as np
import sys
import matplotlib.pyplot as plt
sys.path.append('triscale')
import triscale as triscale

def calculate_absolute_metrics(input_df, metric, measure):
    if measure == "absolute_etx":
        app_tx_etx = input_df["transmissions"].sum() / \
            len(input_df[input_df["result"] == "ok"])
        print("ETX for all TXs: %0.4f" % app_tx_etx)
        return app_tx_etx

    if measure == "absolute_etx_spatial" or measure == "absolute_etx_no_spatial":
        # Find ETX for spatial reused cells. Only supported when running Layered! (due to app field)
        app_cells_df = input_df

        # Find spatial reuse via groupby and filter
        spatial_reuse_df = app_cells_df.groupby(["asn", "channel"]).filter(lambda x: len(x) >= 2)

        # Find non-spatial reuse via drop_duplicates
        # (could have done merge of spatial-reuse)
        no_spatial_reuse_df = app_cells_df.drop_duplicates(subset=["asn", "channel"], keep=False)

        spatial_reuse_total = len(spatial_reuse_df)
        no_spatial_reuse_total = len(no_spatial_reuse_df)

        if measure == "absolute_etx_spatial":
            if spatial_reuse_total != 0:
                spatial_reuse_success = len(spatial_reuse_df[spatial_reuse_df["result"] == 0])
                spatial_reuse_etx = spatial_reuse_total / spatial_reuse_success
                print("ETX for spatial reuse cells: %.4f" % spatial_reuse_etx)
                return spatial_reuse_etx
            else:
                #print("No spatial reuse")
                return 0
        elif measure == "absolute_etx_no_spatial":
            no_spatial_reuse_success = len(no_spatial_reuse_df[no_spatial_reuse_df["result"] == 0])
            no_spatial_reuse_etx = no_spatial_reuse_total / no_spatial_reuse_success
            print("ETX for no-spatial reuse cells: %.4f" %
                  (len(no_spatial_reuse_df) /
                  len(no_spatial_reuse_df[no_spatial_reuse_df["result"] == 0])))
            return no_spatial_reuse_etx

    return None

def calculate_metric(input_df, metric, measure, check_convergence=False):

    # Calculate metrics which does not require TriScale
    if type(measure) == str and "absolute" in measure:
        return calculate_absolute_metrics(input_df, metric, measure)

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

def analyze_run(run_name, packets_df, energest_df, queue_df, mac_tx_df, cell_df, switches_df):
    run_entry = {"name": run_name}
    if len(switches_df) == 0:
        run_entry["converged"] = True
    else:
        run_entry["converged"] = False

    # Make DF with app-mac-packets only
    app_mac_tx_df = mac_tx_df[mac_tx_df["app"] == 1].copy()
    app_cell_df = cell_df[cell_df["app"] == 1].copy()

    # Make queue DF per node
    #ss_queue_df_2 = ss_queue_df.copy()
    #ss_queue_df_2 = ss_queue_df_2[ss_queue_df_2.node == 2]
    #ss_queue_df_3 = ss_queue_df.copy()
    #ss_queue_df_3 = ss_queue_df_3[ss_queue_df_3.node == 3]

    # Make the following metrics for the given measures for the given DFs
    # The-per-node is a bit hackish - gave them special prefix
    default_measures = ["mean", 50, 95, 99, 99.9, "maximum"]
    metric_packets = [{"metric": "latency", "measures":default_measures},
                      {"metric": "pdr", "measures":["mean"]}]
    metric_mac_app_tx = [{"metric": "mac_app_tx_etx", "measures":["absolute_etx"]}]
    metric_app_cell = [{"metric": "app_cell_etx",
                        "measures":["absolute_etx_spatial", "absolute_etx_no_spatial"]}]
    metric_energest = [{"metric": "duty_cycle", "measures":default_measures},
                       {"metric": "duty_cycle_tx", "measures":default_measures},
                       {"metric": "duty_cycle_rx", "measures":default_measures}]
    metric_queue = [{"metric": "queue_fill", "measures":default_measures}]
    dfs = [{"df":packets_df, "metric":metric_packets, "prefix":""},
           {"df":energest_df, "metric":metric_energest, "prefix":""},
           {"df":queue_df, "metric":metric_queue, "prefix":""},
           {"df":app_mac_tx_df, "metric":metric_mac_app_tx, "prefix":""},
           {"df":app_cell_df, "metric":metric_app_cell, "prefix":""},
           #{"df":ss_queue_df_2, "metric":metric_queue, "prefix":"ss2_"},
           #{"df":ss_queue_df_3, "metric":metric_queue, "prefix":"ss3_"}
           ]

    # Actually make metrics and fill into DF entry
    for df in dfs:
        for metric in df["metric"]:
            for measure in metric["measures"]:
                run_metric_name = df["prefix"] + metric["metric"] + "_" + str(measure)
                run_entry[run_metric_name] = \
                    calculate_metric(df["df"], metric["metric"], measure)

    # Make DF out of the entry
    df = pd.DataFrame([run_entry])
    df = df.set_index("name")
    return df

def analyze_runs(raw_dfs):
    raw_packets_dfs = raw_dfs["raw_packets_dfs"]
    raw_energest_dfs = raw_dfs["raw_energest_dfs"]
    raw_queue_dfs = raw_dfs["raw_queue_dfs"]
    raw_mac_tx_dfs = raw_dfs["raw_mac_tx_dfs"]
    raw_cell_dfs = raw_dfs["raw_mac_cell_dfs"]
    raw_switches_dfs = raw_dfs["raw_switches_dfs"]

    runs_df_dict = []
    for run in raw_packets_dfs.keys():
        runs_df_dict.append(
            analyze_run(run,
                        raw_packets_dfs[run][raw_packets_dfs[run]["app_started"] == 1],
                        raw_energest_dfs[run][raw_energest_dfs[run]["app_started"] == 1],
                        raw_queue_dfs[run][raw_queue_dfs[run]["app_started"] == 1],
                        raw_mac_tx_dfs[run][raw_mac_tx_dfs[run]["app_started"] == 1],
                        raw_cell_dfs[run][raw_cell_dfs[run]["app_started"] == 1],
                        raw_switches_dfs[run][raw_switches_dfs[run]["app_started"] == 1]))

    #ad_hoc_etx_per_node(raw_mac_tx_dfs,raw_cell_dfs)

    return pd.concat(runs_df_dict)

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
                       "bound":"lower"}},
               {"metric":"app_cell_etx",
                #"name":"_p" + str(adhoc_percentile) + "_%" + str(adhoc_confidence) + "_L",
                "name":"_U",
                "settings":{"percentile": adhoc_percentile,
                       "confidence": adhoc_confidence,
                       "bounds":[0,100],
                       "bound":"upper"}},
               {"metric":"app_cell_etx",
                #"name":"_p" + str(adhoc_percentile) + "_%" + str(adhoc_confidence) + "_L",
                "name":"_L",
                "settings":{"percentile": adhoc_percentile,
                       "confidence": adhoc_confidence,
                       "bounds":[0,100],
                       "bound":"lower"}}
               ]

    # TODO this needs some fixing as the naming of the columns in the resulting
    # DF will say _mean, _median, etc. while it is actually the default_percentile
    # default_confidence % CI of these values.
    for metric in runs_df.columns:
        for kpi in kpis:
            if kpi["metric"] in metric:
                scenario_entry[metric + kpi['name']] = calculate_kpi(runs_df[metric].values,
                                                       kpi["settings"],
                                                       metric)

    # Now do only converged runs
    runs_convergence_df = runs_df.copy()
    runs_convergence_df = runs_convergence_df[runs_convergence_df["converged"] == True]
    for metric in runs_convergence_df.columns:
        for kpi in kpis:
            if kpi["metric"] in metric:
                scenario_entry["converged_" + metric + kpi['name']] = \
                    calculate_kpi(runs_convergence_df[metric].values,
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

def ad_hoc_etx_per_node_all(scenarios):
    node_max_etx = []
    for scenario in scenarios:
        mac_tx_all_runs_df = scenario['raw_dfs']["raw_mac_tx_dfs"]
        for run in mac_tx_all_runs_df.keys():
            mac_tx_run_df = mac_tx_all_runs_df[run]
            app_mac_tx_all_runs_df = \
                mac_tx_run_df[mac_tx_run_df["app_started"] == 1]

            groups = app_mac_tx_all_runs_df.groupby("node")["transmissions"]
            for name, group in groups:
                num_tx = group.sum()
                node_df = app_mac_tx_all_runs_df[app_mac_tx_all_runs_df["node"] == name]
                num_success = len(node_df[node_df["result"] == "ok"])
                node_etx = num_tx / num_success
                #print("Node %s: %d / %d : %.4f" % (name, num_tx, num_success, node_etx))
            break

def meta_parent_switches(scenarios, execution_dir):
    # 1. Distribution of last parent switch
    last_switches = []
    last_switches_per_scenario = []
    for scenario in scenarios:
        switch_all_runs_df = scenario['raw_dfs']["raw_switches_dfs"]
        #last_switches_in_scenario = np.empty(0)
        last_switches_in_scenario = []
        for run in switch_all_runs_df.keys():
            switch_df = switch_all_runs_df[run]
            if len(switch_df) == 0:
                continue
            last_switch = switch_df.iloc[-1:].index.tolist()
            #print("Last parent switch: " + str(last_switch))
            last_switches.append(last_switch)

            # We try to fetch the index of the last row in the df
            # Problem is that this is datatype TimeDelta which does not play
            # well when we try to plot histograms with multiple variables,
            # which expects an array of arrays of numbers.

            # Convert from timedelta
            # I don't understand this one, but we get a Float64Index
            # (which is basically a list, and then we get a Float64 by fetching first value.
            # From https://stackoverflow.com/questions/23543909/plotting-pandas-timedelta/54729327
            last_switch_timestamp = switch_df.iloc[-1:].index / pd.Timedelta(minutes=1)
            last_switches_in_scenario.append(last_switch_timestamp.values[0])

        last_switches_per_scenario_array = np.array(last_switches_in_scenario)
        last_switches_per_scenario.append(last_switches_per_scenario_array)

    # Last switch for all runs
    df = pd.DataFrame(last_switches, columns= ['last_switch'])
    df['last_switch'].astype('timedelta64[m]').plot.hist(bins=20)
    plt.xlabel("Duration of experiment (minutes)")
    plt.ylabel("Number of runs with last parent switches")
    plt.savefig(execution_dir + "meta_last_parent_switch.pdf")
    plt.close()

    # Last switch per scenario
    plt.hist(last_switches_per_scenario, bins=20, stacked=False)
    scenario_names = []
    for scenario in scenarios:
        scenario_names.append(scenario["name"])
    plt.legend(scenario_names)
    plt.xlabel("Duration of experiment (minutes)")
    plt.ylabel("Number of runs with last parent switches")
    plt.locator_params(axis='y', integer=True)
    plt.savefig(execution_dir + "meta_last_parent_switch_per_scenario.pdf")
    plt.close()


    # 2. Distribution of all parent switches
    switches_per_scenario = []
    for scenario in scenarios:
        switches = []
        switches_in_scenario = np.empty(0)
        switch_all_runs_df = scenario['raw_dfs']["raw_switches_dfs"]
        for run in switch_all_runs_df.keys():
            switch_df = switch_all_runs_df[run]
            if len(switch_df) == 0:
                continue
            # Same technique as above
            switch_timestamps = switch_df.index / pd.Timedelta(minutes=1)
            switches_in_scenario = \
                np.concatenate((switches_in_scenario, switch_timestamps.values))
            switches.append(switch_timestamps)

        switches_per_scenario.append(switches_in_scenario)

        # All runs individually per scenario
        plt.hist(switches, bins=60, stacked=True)
        plt.xlabel("Duration of experiment (minutes)")
        plt.ylabel("Number of parent switches")
        plt.locator_params(axis='y', integer=True)
        plt.savefig(execution_dir +
                    "meta_" +
                    scenario["name"] +
                    "_parent_switch.pdf")
        plt.close()

    # All runs in each scenario combined
    plt.hist(switches_per_scenario, bins=30, stacked=False)
    scenario_names = []
    for scenario in scenarios:
        scenario_names.append(scenario["name"])
    plt.xlabel("Duration of experiment (minutes)")
    plt.ylabel("Number of parent switches")
    plt.locator_params(axis='y', integer=True)
    plt.legend(scenario_names)
    plt.savefig(execution_dir + "meta_parent_switch.pdf")
    plt.close()

def meta_etx_timelines(scenarios, execution_dir):
    for scenario in scenarios:
        mac_tx_all_runs_df = scenario['raw_dfs']["raw_mac_tx_dfs"]
        for run in mac_tx_all_runs_df.keys():
            mac_tx_df = mac_tx_all_runs_df[run]
            app_tx_df = mac_tx_df[mac_tx_df["app"] == 1]

            # Look only at runs which had parent-switches
            switches_df = scenario['raw_dfs']["raw_switches_dfs"][run]
            switches_app_df = switches_df[switches_df["app_started"] == 1]
            if len(switches_app_df) == 0:
                continue

            # Resample so that we get one row per 10 second
            # TODO using transmissions only does not handle failed TXs
            # TODO we also do all cells and not just the spatial reused
            app_tx_df = app_tx_df["transmissions"].resample('10s').mean()

            # Convert the index to minutes instead of nanoseconds
            # (also changes the datatype from TimeDelta to Float64)
            app_tx_df.index = app_tx_df.index / pd.Timedelta(minutes=1)

            # Get timestamps for parent switches
            switches = switches_app_df.index / pd.Timedelta(minutes=1)

            #fig, ax = plt.subplots(figsize=(14, 6), dpi=80)
            fig, ax = plt.subplots()
            ax.plot(app_tx_df)
            for switch in switches:
                plt.axvline(x=switch, color="red", linestyle="--", label="Parent switch")
            plt.legend()
            plt.xlabel("Duration of experiment (minutes)")
            plt.ylabel("Mean ETX")
            plt.savefig(execution_dir + "meta_" + scenario['name'] + \
                         "_" + run + "_etx_timeline.pdf")
            plt.close()

def meta_stats(scenarios, execution_dir):

    meta_parent_switches(scenarios, execution_dir)

    meta_etx_timelines(scenarios, execution_dir)

    #ad_hoc_etx_per_node_all(scenarios)

    for scenario in scenarios:
        print("Meta for scenario " + scenario['name'] + ":")
        print(scenario["meta_df"])

def print_meta_info(scenarios):
    for scenario in scenarios:
        scenario_meta_df = scenario["meta_df"]
        total_runs = len(scenario_meta_df)
        parsed_runs = len(scenario_meta_df[scenario_meta_df["result"] == "ok"])
        skipped_runs_spatial = \
            len(scenario_meta_df[scenario_meta_df["result"] == "spatial"])
        skipped_runs_switch = \
            len(scenario_meta_df[scenario_meta_df["result"] == "switch"])
        skipped_runs_error = \
            len(scenario_meta_df[scenario_meta_df["result"] == "error"])

        print("Scenario " + scenario["name"] + ":")
        print("\tParsed " + str(parsed_runs) + " out of " + str(total_runs))
        print("\tSkips due to spatial: " + str(skipped_runs_spatial) +
              ", parent switch: " + str(skipped_runs_switch) +
              ", errors: " + str(skipped_runs_error))

def stats_for_scenarios(scenarios, execution_dir, write_runs_csv = False):
    meta_stats(scenarios, execution_dir)

    scenarios_df_list = []
    for scenario in scenarios:
        scenarios_df_list.append(stats_for_scenario(scenario, write_runs_csv))

    # Make one DF from the list of scenario DFs
    scenarios_df = pd.concat(scenarios_df_list)
    scenarios_df.set_index("scenario", inplace=True)

    print_meta_info(scenarios)

    #print("Analyzed scenarios: " + str(scenarios))
    #print(scenarios_df)

    return scenarios_df
