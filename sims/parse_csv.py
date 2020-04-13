#!/usr/bin/env python

# Based on
# https://github.com/contiki-ng/contiki-ng/blob/develop/examples/benchmarks/rpl-req-resp/parse.py

import os
import pandas as pd
import glob
from pathlib import Path

# Constants
CSV_PATTERN = '*.csv'

def parse_csv(csv):
    df = pd.read_csv(csv)

    # Set timestamp as index
    df.set_index("timestamp", inplace = True)

    # Convert timestamp from string to TimeDelta
    df.index = pd.to_timedelta(df.index)

    return df

# Inspired by http://www.randalolson.com/2012/06/26/using-pandas-dataframes/
# Parses all csv in directory into a dict of DFs
def parse_csvs(directory):
    directory = directory.rstrip('/') + "/*"
    dfs_packets = {}
    dfs_queue = {}
    dfs_energest = {}

    # Iterate all folders containing different runs in the directory
    for folder in glob.glob(directory):
        # Iterate and parse all csv files in the folder
        # This is hijacked from parse_log so it is quite hackish
        for csvfile in glob.glob(folder + "/" + CSV_PATTERN):
            name_of_run = os.path.basename(folder)
            #print("Parsing " + csvfile)

            packets_csv = str(Path(csvfile).parent) + "\packets_" + name_of_run + ".csv"
            queue_csv = str(Path(csvfile).parent) + "\queue_" + name_of_run + ".csv"
            energest_csv = str(Path(csvfile).parent) + "\energest_" + name_of_run + ".csv"
            dfs_packets[name_of_run] = parse_csv(packets_csv)
            dfs_queue[name_of_run] = parse_csv(queue_csv)
            dfs_energest[name_of_run] = parse_csv(energest_csv)

    return dfs_packets, dfs_queue, dfs_energest

def parse_csv_scenario(scenario_dir, scenario_name):
    runs_raw_packet_dfs, runs_raw_queue_dfs, runs_raw_energest = \
        parse_csvs(scenario_dir)

    #print("Parsed runs: " + str(runs_raw_packet_dfs.keys()))
    return runs_raw_packet_dfs, runs_raw_queue_dfs, runs_raw_energest

def parse_csv_scenarios(scenarios):
      for scenario in scenarios:
        scenario_raw_packet_dfs, scenario_raw_queue_dfs, scenario_raw_energest_dfs = \
            parse_csv_scenario(scenario['path'], scenario['name'])

        # Add the raw DFs to the scenario dict in the scenarios list
        scenario['raw_packet_dfs'] = scenario_raw_packet_dfs
        scenario['raw_queue_dfs'] = scenario_raw_queue_dfs
        scenario['raw_energest_dfs'] = scenario_raw_energest_dfs
