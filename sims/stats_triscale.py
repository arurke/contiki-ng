# Makes stats DFs using triscale
import pandas as pd
import numpy as np
import sys
import copy
import matplotlib.pyplot as plt
sys.path.append('triscale')
import triscale as triscale

PLOT_TIMESERIES_FOLDER_NAME = "timeseries"
PLOT_META_FOLDER_NAME = "meta"
PLOT_TRISCALE_FOLDER_NAME = "triscale"

spatial_reuse_links = []

def generate_list_of_links_with_spatial_reuse(scenarios):
    spatial_reuse_links = []
    for scenario in scenarios:
        # We are only interested in spatial reuse
        # Note, not generic implementation
        if scenario["name"] == "no_spatial_reuse":
            continue

        mac_cell_tx_dfs = scenario['raw_dfs']["raw_mac_cell_dfs"]

        for run in mac_cell_tx_dfs.keys():
            mac_cell_tx_df = mac_cell_tx_dfs[run]
            # We are only interested in app-packets in measurement period
            mac_cell_tx_app_df = mac_cell_tx_df[mac_cell_tx_df["app_started"] == 1]
            mac_cell_tx_app_df = mac_cell_tx_app_df[mac_cell_tx_app_df["app"] == 1]

            # Now identify the links which have more than X % spatial reuse
            # or just any spatial reuse? Let's begin with the second one.

            # Extract only TXes which are spatial reuse
            spatial_reuse_tx_df = \
                mac_cell_tx_app_df.groupby(["asn", "channel"]).filter(lambda x: len(x) >= 2)

            # Fetch unique links
            spatial_reuse_links_df = \
                spatial_reuse_tx_df.drop_duplicates(subset=["node_src", "node_dest"], keep='first')

            # Iterate the unique links and add to list
            # Note! Internet says iteration is an anti-pattern
            for index, link in spatial_reuse_links_df.iterrows():
                link = {"src": link["node_src"], "dest": link["node_dest"]}
                if link not in spatial_reuse_links:
                    spatial_reuse_links.append(link)

    return spatial_reuse_links

def calculate_etx_for_selected_links(mac_cell_df):
    global spatial_reuse_links

    # We have a list of links which had spatial reuse in the spatial reuse scenario
    # Now when we analyze the non-spatial reuse scenario we pick only
    # transmissions on those links
    # mac_tx df does not give us the recepient, so therefore use mac_cell df
    links_dfs = []
    for link in spatial_reuse_links:
        link_df = mac_cell_df[(mac_cell_df["node_src"] == link["src"]) & \
                              (mac_cell_df["node_dest"] == link["dest"])]
        links_dfs.append(link_df)

    tx_selected_links_df = pd.concat(links_dfs, ignore_index=True)

    # Calculate the ETX for those links
    # Remove any stray non-spatial reuse TX (not necessary? confuses the semantic of the function)
    # no_spatial_reuse_df = app_cells_df.drop_duplicates(subset=["asn", "channel"], keep=False)
    tx_total = len(tx_selected_links_df)
    tx_success = len(tx_selected_links_df[tx_selected_links_df["result"] == 0])

    if tx_total == 0:
        print("No TX on selected links!")
        return NaN

    if tx_success == 0:
        print("No success TX on selected links!")
        return NaN

    etx = tx_total / tx_success
    return etx

def calculate_absolute_metrics(input_df, metric, measure):
    if metric == "mac_app_tx_etx" and measure == "absolute":
        app_tx_etx = input_df["transmissions"].sum() / \
            len(input_df[input_df["result"] == "ok"])
        #print("ETX for all TXs: %0.4f" % app_tx_etx)
        return app_tx_etx

    if metric == "app_cell_etx" and \
        (measure == "absolute_spatial" or measure == "absolute_no_spatial"):
        # Find ETX for spatial reused cells. Only supported when running Layered! (due to app field)
        app_cells_df = input_df

        # Find spatial reuse via groupby and filter
        spatial_reuse_df = app_cells_df.groupby(["asn", "channel"]).filter(lambda x: len(x) >= 2)

        # Find non-spatial reuse via drop_duplicates
        # (could have done merge of spatial-reuse)
        no_spatial_reuse_df = app_cells_df.drop_duplicates(subset=["asn", "channel"], keep=False)

        spatial_reuse_total = len(spatial_reuse_df)
        no_spatial_reuse_total = len(no_spatial_reuse_df)

        if measure == "absolute_spatial":
            if spatial_reuse_total != 0:
                spatial_reuse_success = len(spatial_reuse_df[spatial_reuse_df["result"] == 0])
                if spatial_reuse_success == 0:
                    return 8
                spatial_reuse_etx = spatial_reuse_total / spatial_reuse_success
                #print("ETX for spatial reuse cells: %.4f" % spatial_reuse_etx)
                return spatial_reuse_etx
            else:
                #print("No spatial reuse")
                return 0
        elif measure == "absolute_no_spatial":
            no_spatial_reuse_success = len(no_spatial_reuse_df[no_spatial_reuse_df["result"] == 0])
            no_spatial_reuse_etx = no_spatial_reuse_total / no_spatial_reuse_success
            #print("ETX for no-spatial reuse cells: %.4f" %
            #      (len(no_spatial_reuse_df) /
            #      len(no_spatial_reuse_df[no_spatial_reuse_df["result"] == 0])))
            return no_spatial_reuse_etx

    return None

def calculate_metric(input_df, metric, measure, name, plots_dir):
    # Calculate metrics which does not require TriScale
    if metric == "app_selected_cell_etx":
        return calculate_etx_for_selected_links(input_df)

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

    # Convergence test makes a set of windows/subsets of the data and
    # calculates our metric on each window. If test passes, it gives us
    # the median of all those calculations. If not it gives us NaN.
    # When not using the convergence tets, this is the same as if we
    # would call mean(), median() etc. ourselves
    # TODO test with configured bounds?

    # transmitters_hop data is so different from other data
    # we ad-hoc remove it from here for now. TODO
    #if "transmitters_hop" in name:
    #    return np.nan

    convergence_result, calculated_measure, figure = \
        triscale.analysis_metric(
            df, {"measure":measure},
            convergence={"expected": True},
            #showplot=False, verbose=False, plot_out_name=plots_dir + name + ".pdf")
            showplot=False, verbose=False)

    if not convergence_result:
        print("Not converged for " + name)
        # Make plot
        triscale.analysis_metric(
            df, {"measure":measure},
            convergence={"expected": True},
            showplot=False, verbose=False,
            plot_out_name=plots_dir + name + ".pdf")
    #else:
        #print("Converged for " + name)
    return calculated_measure

def analyze_run(run_name, plots_dir, packets_df, energest_df, queue_df,
                mac_tx_df, cell_df, switches_df, rpl_stats_df):
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

    # RPL stats for the transmitting nodes only
    #transmitting_nodes = [332, 330, 328, 326]
    #rpl_stats_transmitters_df = \
    #    rpl_stats_df[rpl_stats_df["node"].isin(transmitting_nodes)]

    # Make the following metrics for the given measures for the given DFs
    # The-per-node is a bit hackish - gave them special prefix
    #default_measures = ["mean", 50, 95, 99, "maximum"]
    # Experienced TriScale crashes with "maximum" and "minimum" in metric convergence test
    default_measures = ["mean", 50]
    metric_packets = [{"metric": "latency", "measures":default_measures},
                      {"metric": "pdr", "measures":["mean"]}]
    metric_mac_app_tx = [{"metric": "mac_app_tx_etx", "measures":["absolute"]}]
    metric_app_cell = [{"metric": "app_cell_etx",
                        "measures":["absolute_spatial", "absolute_no_spatial"]}]
    metric_app_selected_cell = [{"metric": "app_selected_cell_etx",
                        "measures":["absolute"]}]
    metric_energest = [{"metric": "duty_cycle", "measures":default_measures},
                       {"metric": "duty_cycle_tx", "measures":default_measures},
                       {"metric": "duty_cycle_rx", "measures":default_measures}]
    metric_queue = [{"metric": "queue_fill", "measures":default_measures}]
    # Experienced TriScale crashes with "maximum" and "minimum" in metric convergence test
    #metric_rpl = [{"metric": "hop_count", "measures":["mean", "minimum"]}]
    metric_rpl = [{"metric": "hop_count", "measures":["mean"]}]

    dfs = [{"df":packets_df, "metric":metric_packets, "prefix":""},
           #{"df":energest_df, "metric":metric_energest, "prefix":""},
           #{"df":queue_df, "metric":metric_queue, "prefix":""},
           {"df":app_mac_tx_df, "metric":metric_mac_app_tx, "prefix":""},
           {"df":app_cell_df, "metric":metric_app_cell, "prefix":""},
           {"df":app_cell_df, "metric":metric_app_selected_cell, "prefix":""},
           {"df":rpl_stats_df, "metric":metric_rpl, "prefix":""},
           #{"df":rpl_stats_transmitters_df, "metric":metric_rpl, "prefix":"transmitters_"},
           #{"df":ss_queue_df_2, "metric":metric_queue, "prefix":"ss2_"},
           #{"df":ss_queue_df_3, "metric":metric_queue, "prefix":"ss3_"}
           ]

    # Actually calculate metrics and fill into DF entry
    for df in dfs:
        for metric in df["metric"]:
            for measure in metric["measures"]:
                run_metric_name = df["prefix"] + metric["metric"] + "_" + str(measure)
                run_entry[run_metric_name] = \
                    calculate_metric(df["df"], metric["metric"], measure,
                                     run_name + "_" + run_metric_name, plots_dir)

    # Make DF out of the entry
    df = pd.DataFrame([run_entry])
    df = df.set_index("name")
    return df

def analyze_runs(raw_dfs, scenario_name, plots_dir):
    raw_packets_dfs = raw_dfs["raw_packets_dfs"]
    raw_energest_dfs = raw_dfs["raw_energest_dfs"]
    raw_queue_dfs = raw_dfs["raw_queue_dfs"]
    raw_mac_tx_dfs = raw_dfs["raw_mac_tx_dfs"]
    raw_cell_dfs = raw_dfs["raw_mac_cell_dfs"]
    raw_switches_dfs = raw_dfs["raw_switches_dfs"]
    raw_rpl_stats_dfs = raw_dfs["raw_rpl_stats_dfs"]

    runs_df_dict = []
    for run in raw_packets_dfs.keys():
        runs_df_dict.append(
            analyze_run(scenario_name + "_" + run, plots_dir,
                        raw_packets_dfs[run][raw_packets_dfs[run]["app_started"] == 1],
                        raw_energest_dfs[run][raw_energest_dfs[run]["app_started"] == 1],
                        raw_queue_dfs[run][raw_queue_dfs[run]["app_started"] == 1],
                        raw_mac_tx_dfs[run][raw_mac_tx_dfs[run]["app_started"] == 1],
                        raw_cell_dfs[run][raw_cell_dfs[run]["app_started"] == 1],
                        raw_switches_dfs[run][raw_switches_dfs[run]["app_started"] == 1],
                        raw_rpl_stats_dfs[run][raw_rpl_stats_dfs[run]["app_started"] == 1]))

    #ad_hoc_etx_per_node(raw_mac_tx_dfs,raw_cell_dfs)

    return pd.concat(runs_df_dict)

def calculate_kpi(values, settings, metric, name, plots_dir):
    bounds_was_set = False
    if "bounds" in settings:
        bounds_was_set = True

    independent, kpi = triscale.analysis_kpi(
                        values,
                        settings,
                        #to_plot=["autocorr", "horizontal", "vertical"], plot_out_name=name,
                        # Only "vertical" and "horizontal" prints to file.
                        # Note that they overwrite each other!
                        plots=["vertical"],
                        plot_out_name=(plots_dir + name + ".pdf"),
                        verbose=False)
    if np.isnan(kpi):
        print("KPI Nan, too few values(" +
              str(sum(~np.isnan(values))) + ") for " + name)
        return kpi

    # Independence is not critical in simulations?
    if not independent:
        print("Not independent for", name)
        # Run with verbose for debugging
        independent, kpi = triscale.analysis_kpi(
                    values,
                    settings,
                    #to_plot=["autocorr", "horizontal", "vertical"], plot_out_name=name,
                    # Only "vertical" and "horizontal" prints to file.
                    # Note that they overwrite each other!
                    #plots=["vertical"], plot_out_name=(plots_dir + "/" + name + ".pdf"),
                    verbose=True)

        if bounds_was_set:
            print("Bounds set: " + str(settings["bounds"]))
        else:
            print("Bounds set by Triscale: " + str(settings["bounds"]))
        print("Values:" + str(values.tolist()))

    return kpi

def add_kpi(kpis, metric,
              percentile=90,
              confidence=95,
              bounds=[],
              bound_lower=True,
              bound_upper=True,
              default=False):

    new_kpi = {"metric" : metric,
               "settings":{"percentile": percentile,
                           "confidence": confidence
               }}
    if bounds:
        new_kpi["settings"]["bounds"] = bounds
    if default:
        new_kpi["default"] = True
    if bound_lower:
        new_kpi["settings"]["bound"] = "lower"
        kpis.append(copy.deepcopy(new_kpi))
    if bound_upper:
        new_kpi["settings"]["bound"] = "upper"
        kpis.append(new_kpi)

def analyze_scenario(runs_df, scenario_name, plots_triscale_dir):
    scenario_entry = {"scenario": scenario_name}

    # Add KPIs
    kpis = []

    # Default ones (see add_kpi() for default values)
    #add_kpi(kpis, "pdr", bound_upper=False, default=True)
    #add_kpi(kpis, "latency", bounds=[0.01,70], bound_lower=False, default=True)
    #add_kpi(kpis, "duty_cycle", bound_lower=False, default=True)
    #add_kpi(kpis, "duty_cycle_tx", bound_lower=False, default=True)
    #add_kpi(kpis, "duty_cycle_rx", bound_lower=False, default=True)
    #add_kpi(kpis, "queue_fill", bound_lower=False, default=True)

    # More specialized ones
    adhoc_percentile = 85
    adhoc_confidence = 95

    add_kpi(kpis, "latency",
            percentile=adhoc_percentile, confidence=adhoc_confidence,
            bounds=[0.001,120])
    add_kpi(kpis, "pdr",
            percentile=adhoc_percentile, confidence=adhoc_confidence,
            bounds=[0.001,120])
    add_kpi(kpis, "mac_app_tx_etx",
            percentile=adhoc_percentile, confidence=adhoc_confidence,
            bounds=[1,20])
    add_kpi(kpis, "app_cell_etx",
            percentile=adhoc_percentile, confidence=adhoc_confidence,
            bounds=[1,20])
    add_kpi(kpis, "app_selected_cell_etx",
            percentile=adhoc_percentile, confidence=adhoc_confidence,
            bounds=[1,20])

    #add_kpi(kpis, "hop_count",
    #        percentile=50, confidence=95)

    # Add names according to the settings
    for kpi in kpis:
        if "name" in kpi:
            continue
        if kpi["settings"]["bound"] == "lower":
            bound = "_lower"
        else:
            bound = "_upper"
        # KPIs marked as default get special static naming for easier handling
        if kpi.get("default") == True:
            kpi["name"] = \
                "_default" + \
                bound
        else:
            kpi["name"] = \
                "_perc" + \
                str(kpi["settings"]["percentile"]) + \
                "_conf" + \
                str(kpi["settings"]["confidence"]) + \
                bound

    # Calculate KPIs and add to scenario-dict
    for metric in runs_df.columns:
        for kpi in kpis:
            if kpi["metric"] in metric:
                entry_name = metric + kpi['name']
                scenario_entry[entry_name] = \
                    calculate_kpi(runs_df[metric].values,
                                  kpi["settings"], metric,
                                  scenario_name + "_" + entry_name,
                                  plots_triscale_dir)

    # Now do only converged runs for selected metrics
    metrics_for_converged = ["mac_app_tx_etx", "app_cell_etx"]
    #metrics_for_converged = ["mac_app_tx_etx", "app_cell_etx", "pdr", "latency"]
    runs_converged_df = runs_df.copy()
    runs_converged_df = runs_converged_df[runs_converged_df["converged"] == True]
    for metric in runs_converged_df.columns:
        for kpi in kpis:
            if kpi["metric"] in metric:
                if kpi["metric"] in metrics_for_converged:
                    entry_name = "converged_" + metric + kpi['name']
                    scenario_entry[entry_name] = \
                        calculate_kpi(runs_converged_df[metric].values,
                                      kpi["settings"],
                                      metric, entry_name,
                                      plots_triscale_dir)

    return pd.DataFrame([scenario_entry])

def stats_for_scenario(scenario, plots_metrics_dir, plots_kpis_dir,
                       write_runs_csv = False):

    # Get stats per run (which are typically not very interesting)
    runs_df = analyze_runs(scenario['raw_dfs'], scenario['name'], plots_metrics_dir)

    if write_runs_csv:
        runs_df_csv = scenario["path"] + "runs_df.csv"
        print("Saving csv of all runs at", runs_df_csv)
        runs_df.to_csv(runs_df_csv)

    # Add the runs_df to the scenario structure
    scenario["runs_df"] = runs_df
    #print("Analyzed runs: " + str(scenario['raw_dfs']['raw_packets_dfs'].keys()))
    #print("Analyzed runs: " + str(runs_df.columns))

    # Analyze the run-stats to get scenario-stats
    scenario_df = analyze_scenario(scenario["runs_df"],
                                   scenario['name'],
                                   plots_kpis_dir)

    return scenario_df

# WIP unused
def ad_hoc_etx_per_node(raw_mac_tx_dfs, cell_dfs):
    for run in raw_mac_tx_dfs.keys():
        run_mac_tx_df = raw_mac_tx_dfs[run][raw_mac_tx_dfs[run]["app_started"] == 1]
        run_cell_df = cell_dfs[run][cell_dfs[run]["app_started"] == 1]

        groups = run_mac_tx_df.groupby("node")["transmissions"]
        for name, group in groups:
            print(name)
            num_tx = group.sum()
            node_df = run_mac_tx_df[run_mac_tx_df["node"] == name]
            num_success = len(node_df[node_df["result"] == "ok"])
            node_etx = num_tx / num_success
            #print("%d / %d : %.4f" % (num_tx, num_success, node_etx))

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

def meta_last_events(
        scenarios, event_dfs_name, description, plot_name_postfix, plots_dir):
    last_events = []
    last_events_per_scenario = []
    for scenario in scenarios:
        event_all_runs_df = scenario['raw_dfs'][event_dfs_name]
        last_events_in_scenario = []
        for run in event_all_runs_df.keys():
            event_df = event_all_runs_df[run]
            if len(event_df) == 0:
                continue
            # Multi-variable histograms (multiple scenarios) gave us problems
            # so we therefore use a different approach below which we also
            # use for single-variable histogram.

            # Fetch time of last event
            last_event = event_df.iloc[-1:].index

            # Problem is that this is datatype TimeDelta which does not play
            # well when we try to plot histograms with multiple variables,
            # which expects an array of arrays of numbers.
            # Convert from timedelta:
            # I don't understand this one, but we get a Float64Index
            # (which is basically a list, and then we get a Float64 by fetching first value.
            # From https://stackoverflow.com/questions/23543909/plotting-pandas-timedelta/54729327
            last_event = last_event / pd.Timedelta(minutes=1)
            last_events.append(last_event.values[0])
            last_events_in_scenario.append(last_event.values[0])

        last_events_per_scenario_array = np.array(last_events_in_scenario)
        last_events_per_scenario.append(last_events_per_scenario_array)

    # Last switch for all runs
    plt.hist(last_events, bins=20, stacked=False)
    plt.locator_params(axis='y', integer=True)
    plt.xlabel("Duration of experiment (minutes)")
    plt.ylabel("Number of runs with last " + description)
    plt.savefig(plots_dir + "meta_last_" + plot_name_postfix + ".pdf")
    plt.close()

    # Last switch per scenario
    plt.hist(last_events_per_scenario, bins=20, stacked=False)
    scenario_names = []
    for scenario in scenarios:
        scenario_names.append(scenario["name"])
    plt.legend(scenario_names)
    plt.locator_params(axis='y', integer=True)
    plt.xlabel("Duration of experiment (minutes)")
    plt.ylabel("Number of runs with last " + description)
    plt.savefig(plots_dir + "meta_last_" + plot_name_postfix + "_per_scenario.pdf")
    plt.close()

def meta_all_parent_switches(scenarios, plots_dir):
    # Distribution of all parent switches
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
        plt.savefig(plots_dir +
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
    plt.savefig(plots_dir + "meta_parent_switch.pdf")
    plt.close()

# Make timeline for field_name of all runs of given df-name.
# Note that it filters app packets if applicable
def meta_timeline_all_runs(scenarios, dfs_name, field_name,
                           name, warn_limit, plots_dir):
    for scenario in scenarios:
        all_runs_df = scenario['raw_dfs'][dfs_name]
        fig, ax = plt.subplots()
        for run in all_runs_df.keys():
            run_df = all_runs_df[run]

            if "app" in run_df:
                run_df = run_df[run_df["app"] == 1]

            # Resample so that we get one row per 30 second
            # Comments for ETX:
            # TODO using transmissions only does not handle failed TXs
            # TODO we also do all cells and not just the spatial reused
            run_df = run_df[field_name].resample('30s').agg({field_name:'mean'})

            # Convert the index to minutes instead of nanoseconds
            # (also changes the datatype from TimeDelta to Float64)
            run_df.index = run_df.index / pd.Timedelta(minutes=1)

            line, = ax.plot(run_df)

            if run_df[field_name].max() > warn_limit:
                print("High " + name + " (" + str(run_df[field_name].max()) +
                      ") in " + scenario['name'] + " " + run)
                # Add legend only for the violating runs
                line.set_label(run)
                plt.legend()

        plt.xlabel("Duration of experiment (minutes)")
        plt.ylabel("Mean " + name)
        plt.savefig(plots_dir + "meta_" + scenario['name'] + \
                     "_all_" + name + "_timeline.pdf")
        plt.close()

def meta_non_converged_run_etx_timelines(scenarios, plots_dir):
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
            plt.savefig(plots_dir + "meta_" + scenario['name'] + \
                         "_" + run + "_etx_timeline.pdf")
            plt.close()

def meta_channel_performance_overview(scenarios, plots_dir):
    channels_high_etx = {}
    nodes_high_etx = {}
    make_plot = False

    for scenario in scenarios:
        mac_cell_all_runs_df = scenario['raw_dfs']["raw_mac_cell_dfs"]
        scenario_channel_perf_dfs = []

        # Go through each run
        for run in mac_cell_all_runs_df.keys():
            mac_cell_df = mac_cell_all_runs_df[run]
            # We are only interested in app-packets
            mac_cell_app_all_runs_df = mac_cell_df[mac_cell_df["app_started"] == 1]
            mac_cell_app_df = mac_cell_df[mac_cell_df["app"] == 1]
            #if len(mac_cell_app_df) == 0:
            #    continue

            # Select the columns we are interested in
            channel_perf_df = mac_cell_app_df[["channel", "result", "node"]]

            # Treat each node
            for node in channel_perf_df["node"].unique():
                node_channel_perf_df = \
                    channel_perf_df[channel_perf_df["node"] == node]

                # Calculate ETX per channel
                groups = node_channel_perf_df.groupby("channel")["result"]
                add_node = False
                for channel, result in groups:
                    # 0 indicate success
                    num_success = len(result[result == 0])
                    num_total = len(result)
                    if num_success == 0:
                        etx = 8
                    else:
                        etx = num_total / num_success

                    # High ETX. Add this channel and node to list
                    if etx > 5:
                        make_plot = True
                        add_node = True
                        if channel in channels_high_etx:
                            channels_high_etx[channel] += 1
                        else:
                            channels_high_etx[channel] = 1

                if add_node:
                    if node in nodes_high_etx:
                        nodes_high_etx[node] += 1
                    else:
                        nodes_high_etx[node] = 1

    if not make_plot:
        return

    # Make DFs out of the dicts
    channels_perf_df = pd.DataFrame(channels_high_etx.items(), columns=['channel', "count"])
    channels_perf_df = channels_perf_df.sort_values("channel", ascending=True)
    nodes_perf_df = pd.DataFrame(nodes_high_etx.items(), columns=['node', "count"])
    nodes_perf_df = nodes_perf_df.sort_values("node", ascending=True)

    # Plot channels
    plt.bar(channels_perf_df["channel"], channels_perf_df["count"])
    plt.xticks(channels_perf_df["channel"])
    plt.xlabel("Physical channel")
    plt.ylabel("Num. nodes who experience high ETX on channel")
    plt.locator_params(axis='y', integer=True)
    plt.savefig(plots_dir + "meta_all_runs_channels_etx_count.pdf")
    plt.close()

    # Plot nodes
    plt.bar(nodes_perf_df["node"], nodes_perf_df["count"])
    plt.xticks(nodes_perf_df["node"])
    plt.xlabel("Node")
    plt.ylabel("Num. runs node experience high ETX on any channel")
    plt.locator_params(axis='y', integer=True)
    plt.savefig(plots_dir + "meta_all_runs_node_etx_count.pdf")
    plt.close()

def meta_channel_performance_per_node(
        scenarios, plots_dir, node_field, plot_name, plot_only_problems):
    for scenario in scenarios:
        mac_cell_all_runs_df = scenario['raw_dfs']["raw_mac_cell_dfs"]
        scenario_channel_perf_dfs = []
        for run in mac_cell_all_runs_df.keys():
            mac_cell_df = mac_cell_all_runs_df[run]
            # We are only interested in app-packets
            mac_cell_app_all_runs_df = mac_cell_df[mac_cell_df["app_started"] == 1]
            mac_cell_app_df = mac_cell_df[mac_cell_df["app"] == 1]
            #if len(mac_cell_app_df) == 0:
            #    continue

            # Select the columns we are interested in
            channel_perf_df = mac_cell_app_df[["channel", "result", node_field]]
            #scenario_channel_perf_dfs.append(channel_perf_df)
            #print(scenario_channel_perf_dfs)

            # Create one large DF out of the list of run DFs
            #scenario_channel_perf_df = \
            #    pd.concat(scenario_channel_perf_dfs, ignore_index=True)

            number_of_nodes = channel_perf_df[node_field].nunique()

            # Treat each node
            make_plot = False
            nodes_data = []
            for node in channel_perf_df[node_field].unique():
                node_channel_perf_df = \
                    channel_perf_df[channel_perf_df[node_field] == node]

                # Calculate ETX per channel
                groups = node_channel_perf_df.groupby("channel")["result"]
                channels = []
                etxs = []
                high_etx = False
                for channel, result in groups:
                    # 0 indicate success
                    num_success = len(result[result == 0])
                    num_total = len(result)

                    # Include only if there is enough traffic
                    if num_total < 75:
                        continue

                    if num_success == 0:
                        etx = 8
                    else:
                        etx = num_total / num_success

                    if etx > 4:
                        # Make plot for this run only if anyone has high ETX
                        make_plot = True
                        high_etx = True

                    etxs.append(etx)
                    channels.append(channel)

                # Make plot for this node if there is data for it
                if etxs:
                    # If plot_only_problems, add node only if high ETX
                    if plot_only_problems and not high_etx:
                        continue
                    else:
                        nodes_data.append({"node": node,
                                           "etxs": etxs,
                                           "channels": channels,
                                           "high_etx": high_etx})

            if nodes_data and make_plot:
                # Define and calculate subplot positions
                num_nodes = len(nodes_data)
                num_columns = 3
                num_rows = num_nodes // num_columns + 1
                position = range(1, num_nodes + 1)
                fig = plt.figure(1)

                for num, node_data in enumerate(nodes_data):
                    node_channel_perf_df = \
                        pd.DataFrame({'channel':node_data["channels"],
                                      'etxs':node_data["etxs"]})
                    ax = fig.add_subplot(num_rows, num_columns, position[num])
                    ax.set_ylim(0, 10) # Ad-hoc value. Difficult to do dynamically.
                    ax.bar(node_channel_perf_df["channel"],
                           node_channel_perf_df["etxs"])
                    ax.set_xticks(node_channel_perf_df["channel"])
                    ax.set_title('Node ' + str(node_data["node"]))
                    ax.label_outer()
                    if node_data["high_etx"]:
                        ax.set_facecolor('red')

                fig.supylabel("ETX (ALL application packet " + plot_name + ")")
                fig.supxlabel("Physical channel")
                plt.tight_layout()
                plt.savefig(plots_dir + "meta_" + scenario['name'] + \
                          "_" + run + "_all_" + plot_name + "_nodes_channels_etx.pdf")
                plt.close()

# TODO to make temp-folder
import os
def meta_channel_performance(scenarios, plots_dir):
    for scenario in scenarios:
        mac_cell_all_runs_df = scenario['raw_dfs']["raw_mac_cell_dfs"]
        scenario_channel_perf_dfs = []
        for run in mac_cell_all_runs_df.keys():
            mac_cell_df = mac_cell_all_runs_df[run]
            # We are only interested in app-packets
            mac_cell_app_all_runs_df = mac_cell_df[mac_cell_df["app_started"] == 1]
            mac_cell_app_df = mac_cell_df[mac_cell_df["app"] == 1]
            #if len(mac_cell_app_df) == 0:
            #    continue

            # Select the columns we are interested in
            channel_perf_df = mac_cell_app_df[["channel", "result"]]
            scenario_channel_perf_dfs.append(channel_perf_df)
            #print(scenario_channel_perf_dfs)

        # Create one large DF out of the list of run DFs
        scenario_channel_perf_df = pd.concat(scenario_channel_perf_dfs, ignore_index=True)
        groups = scenario_channel_perf_df.groupby("channel")["result"]
        channels = []
        etxs = []
        for name, group in groups:
            # 0 indicate success
            num_success = len(group[group == 0])
            num_total = len(group)
            if num_success == 0:
                etx = 8
            else:
                etx = num_total / num_success

            etxs.append(etx)
            channels.append(name)

#        scenario_channel_perf_df = scenario_channel_perf_df.groupby("channel")["transmissions"].mean()
#        scenario_channel_perf_df = scenario_channel_perf_df.reset_index()
        scenario_channel_perf_df = pd.DataFrame({'channel':channels, 'etxs':etxs})
        plt.bar(scenario_channel_perf_df["channel"], scenario_channel_perf_df["etxs"])
        plt.xticks(scenario_channel_perf_df["channel"])
        plt.xlabel("Physical channel")
        plt.ylabel("ETX (ALL application packet TXes)")
        plt.savefig(plots_dir + "meta_" + scenario['name'] + \
                  "_channels_etx.pdf")
        plt.close()

    # Make plots with all nodes, per run
    temp_dir = plots_dir + "temp/"
    os.mkdir(temp_dir)
    # ETX per transmitting node
    meta_channel_performance_per_node(scenarios, temp_dir, "node", "tx", False)
    # ETX per receiving node
    meta_channel_performance_per_node(scenarios, temp_dir, "node_dest", "rx", True)

def print_meta_info(scenarios):
    for scenario in scenarios:
        scenario_meta_df = scenario["meta_df"]
        total_runs = len(scenario_meta_df)
        parsed_runs_df = scenario_meta_df[scenario_meta_df["result"] == "ok"]
        parsed_runs = len(parsed_runs_df)
        skipped_runs_spatial = \
            len(scenario_meta_df[scenario_meta_df["result"] == "spatial"])
        skipped_runs_switch = \
            len(scenario_meta_df[scenario_meta_df["result"] == "switch"])
        skipped_runs_error = \
            len(scenario_meta_df[scenario_meta_df["result"] == "error"])
        converged_runs = \
            len(parsed_runs_df[parsed_runs_df["parent_swith_during_app"] == 0])

        print("Scenario " + scenario["name"] + ":")
        print("\tParsed " + str(parsed_runs) + " out of " + str(total_runs))
        print("\tSkips due to spatial: " + str(skipped_runs_spatial) +
              ", parent switch: " + str(skipped_runs_switch) +
              ", errors: " + str(skipped_runs_error))
        print("\tRPL converged: " + str(converged_runs) + " out of " + str(parsed_runs))
        print("\tTriscale metrics converged:")
        print(scenario["runs_df"].notnull().sum(axis=0).to_string(dtype=False))

def meta_stats(scenarios, plots_meta_dir, plots_time_dir):

    meta_non_converged_run_etx_timelines(scenarios, plots_time_dir)

    meta_timeline_all_runs(scenarios, "raw_mac_tx_dfs", "transmissions", "ETX", 4, plots_meta_dir)
    meta_timeline_all_runs(scenarios, "raw_packets_dfs", "latency", "latency", 7, plots_meta_dir)
    meta_timeline_all_runs(scenarios, "raw_packets_dfs", "pdr", "PDR", 100, plots_meta_dir)

    meta_all_parent_switches(scenarios, plots_meta_dir)

    meta_last_events(scenarios,
                     "raw_switches_dfs",
                     "parent switch",
                     "parent_switch",
                     plots_meta_dir)

    meta_last_events(scenarios,
                     "raw_dag_inits_dfs",
                     "network join",
                     "network_join",
                     plots_meta_dir)

    meta_channel_performance(scenarios, plots_meta_dir)

    meta_channel_performance_overview(scenarios, plots_meta_dir)

    #ad_hoc_etx_per_node_all(scenarios)

    for scenario in scenarios:
        print("Meta for scenario " + scenario['name'] + ":")
        print(scenario["meta_df"])

def stats_for_scenarios(scenarios, plots_dir, write_runs_csv = False):

    # Populate list of links with spatial reuse
    global spatial_reuse_links
    spatial_reuse_links = generate_list_of_links_with_spatial_reuse(scenarios)

    # Make directories for plots
    plots_meta_dir = plots_dir + PLOT_META_FOLDER_NAME + "/"
    plots_timeseries_dir = plots_dir + PLOT_TIMESERIES_FOLDER_NAME + "/"
    plots_triscale_dir = plots_dir + PLOT_TRISCALE_FOLDER_NAME + "/"
    plots_triscale_metrics_dir = plots_triscale_dir + "metrics/"
    plots_triscale_kpis_dir = plots_triscale_dir + "kpis/"
    dirs = [plots_meta_dir, plots_timeseries_dir, plots_triscale_dir,
            plots_triscale_metrics_dir, plots_triscale_kpis_dir]
    for dir in dirs:
        os.mkdir(dir)

    scenarios_df_list = []
    for scenario in scenarios:
        scenarios_df_list.append(
            stats_for_scenario(scenario, plots_triscale_metrics_dir,
                               plots_triscale_kpis_dir, write_runs_csv))

    # Make one DF from the list of scenario DFs
    scenarios_df = pd.concat(scenarios_df_list)
    scenarios_df.set_index("scenario", inplace=True)

    meta_stats(scenarios, plots_meta_dir, plots_timeseries_dir)

    print_meta_info(scenarios)

    #print("Analyzed scenarios: " + str(scenarios))
    #print(scenarios_df)

    return scenarios_df
