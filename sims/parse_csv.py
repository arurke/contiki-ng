#!/usr/bin/env python

# Based on
# https://github.com/contiki-ng/contiki-ng/blob/develop/examples/benchmarks/rpl-req-resp/parse.py

import os
import pandas as pd
import glob
from pathlib import Path
from collections import defaultdict

# Constants
CSV_PATTERN = '*.csv'

def parse_csvfile(csv):
    df = pd.read_csv(csv)

    # Set timestamp as index
    df.set_index("timestamp", inplace = True)

    # Convert timestamp from string to TimeDelta
    df.index = pd.to_timedelta(df.index)

    return df

# Inspired by http://www.randalolson.com/2012/06/26/using-pandas-dataframes/
# Parses all csv in directory into a dict of DFs
def parse_csvs_dir(directory, scenario_name):

    # Ad hoc handling of meta DF
    meta_csv = directory + scenario_name + "_meta_df.csv"
    meta_df = pd.read_csv(meta_csv)
    meta_df.set_index("name", inplace = True)

    directory = directory.rstrip('/') + "/*"

    # A dictionary of metrics containing dictionaries of DF from each run
    all_runs_dfs = defaultdict(dict)

    # Iterate all folders containing different runs in the directory
    for folder in glob.glob(directory):
        name_of_run = os.path.basename(folder)

        # Iterate and parse all log files in the folder
        # We have only one file pr run at the moment, but this might change
        for csvfile in glob.glob(folder + "/" + CSV_PATTERN):

            df_name = os.path.splitext(os.path.basename(csvfile))[0]
            run_dfs = parse_csvfile(csvfile)

            # Add this DF to the dictionary of DFs
            all_runs_dfs[df_name][name_of_run] = run_dfs

    return meta_df, all_runs_dfs

def parse_csv_scenario(scenario_dir, scenario_name):

    meta_df, all_runs_dfs = parse_csvs_dir(scenario_dir, scenario_name)

    #print("Parsed runs: " + str(all_runs_dfs["energest"].keys()))
    return meta_df, all_runs_dfs

def parse_csv_scenarios(scenarios):
    print("Parsing data from CSV files")
    for scenario in scenarios:
        meta_df, raw_dfs = parse_csv_scenario(scenario['path'], scenario['name'])

        scenario["meta_df"] = meta_df
        scenario["raw_dfs"] = {}
        # Add the raw DFs to the scenario dict in the scenarios list
        for df_name in raw_dfs:
            metric_df_name = "raw_" + df_name + "_dfs"
            #print("DF: " + metric_df_name)
            scenario["raw_dfs"][metric_df_name] = raw_dfs[df_name]
