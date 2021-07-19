#!/usr/bin/env python

# Based on
# https://github.com/contiki-ng/contiki-ng/blob/develop/examples/benchmarks/rpl-req-resp/parse.py

import re
import os
import fileinput
import math
import yaml
import pandas as pd
from pandas import *
from numpy import *
#from pylab import *
from datetime import *
from collections import OrderedDict
from collections import defaultdict
#from IPython import embed
#import matplotlib as mpl
import logging
import glob
from pathlib import Path

# Constants
SCRIPT_LOG_PATTERN = '*.scriptlog'  # For simulations run by simexec.sh
# SCRIPT_LOG_PATTERN = '*.testlog' # For simulations run directly

# Global variable to replace print for quiet mode
print

network_formation_time_ms = None
parents = {}
first_unixtime = None
application_done_count = 0

metrics = ["packets", "energest", "ranks", "hop_count", "nbr_count", "app_parent_switch",
               "trickle", "switches", "dag_inits", "topology", "queue", "mac_tx"]

def calculateHops(node):
    hops = 0
    while(parents[node] != None):
        node = parents[node]
        hops += 1
        # safeguard, in case of scrambled logs
        if hops > 50:
            return hops
    return hops

def calculateChildren(node):
    children = 0
    for n in parents.keys():
        if(parents[n] == node):
            children += 1
    return children

def updateTopology(child, parent):
    #print("Updating topology!")
    global parents
    if not child in parents:
        parents[child] = {}
    if not parent in parents:
        parents[parent] = None
    parents[child] = parent

def parseMain(log):
    res = re.compile('Node ID: (\d+)').match(log)
    if res:
        mac = int(res.group(1))
        return mac
    return None

def parseRPL(log):
    res = re.compile('.*? rank (\d*).*?dioint (\d*).*?nbr count (\d*)').match(log)
    if res:
        rank = int(res.group(1))
        trickle = (2 ** int(res.group(2))) / (60 * 1000.)
        nbr_count = int(res.group(3))
        #  uint8_t route_hop_count = ((rpl_dag->rank / RPL_MIN_HOPRANKINC) - 1) / 3;
        hop_count = ((rank / 256) - 1) / 3
        return {'event': 'rpl_stats', 'rank': rank, 'trickle': trickle,
                'hop_count': hop_count, 'nbr_count': nbr_count}

    res = re.compile('parent switch: .*? -> .*?-(\d*)$').match(log)
    if res:
        parent = int(res.group(1))
        #print("Parent switch!")
        return {'event': 'switch', 'pswitch': parent }

    res = re.compile('sending a (.+?) ').match(log)
    if res:
        message = res.group(1)
        return {'event': 'sending', 'message': message }

    res = re.compile('links: 6G-([0-9a-fA-F]+)\s*to 6G-([0-9a-fA-F]+)').match(log)
    if res:
        child = int(res.group(1))
        parent = int(res.group(2))
        updateTopology(child, parent)
        return None

    res = re.compile('links: end of list').match(log)
    if res:
        # This was the last line, commit full topology
        return {'event': 'topology' }

    res = re.compile('initialized DAG').match(log)
    if res:
        return {'event': 'DAGinit' }

    return None

def parseEnergest(log):
    res = re.compile('Radio Tx\s*:\s*(\d*)/\s*(\d+)').match(log)
    if res:
        tx = float(res.group(1))
        total = float(res.group(2))
        return {'duty_cycle_tx': 100.*tx / total }

    res = re.compile('Radio Rx\s*:\s*(\d*)/\s*(\d+)').match(log)
    if res:
        rx = float(res.group(1))
        total = float(res.group(2))
        return {'duty_cycle_rx': 100.*rx / total }

    res = re.compile('Radio total\s*:\s*(\d*)/\s*(\d+)').match(log)
    if res:
        radio = float(res.group(1))
        total = float(res.group(2))
        return {'duty_cycle': 100.*radio / total }
    return None

def parseApp(log):
    global application_done_count

    res = re.compile('TX (.+?) num (\d+) tick (\d+) to 6G-([0-9a-fA-F]+)').match(log)
    if res:
        type = res.group(1)
        id = int(res.group(2))
        tick = int(res.group(3))
        dest = int(res.group(4), 16)
        return {'event': 'send',
                'type': type,
                'tick':tick,
                'id': id,
                'dest': dest }

    res = re.compile('RX (.+?) num (\d+) oTick (\d+) tick (\d+) from 6G-([0-9a-fA-F]+)').match(log)
    if res:
        type = res.group(1)
        id = int(res.group(2))
        oTick = int(res.group(3))
        tick = int(res.group(4))
        src = int(res.group(5), 16)
        return {'event': 'recv',
                'type': type,
                'oTick': oTick,
                'tick':tick,
                'id': id,
                'src': src }

    res = re.compile('Parent switch').match(log)
    if res:
        return {'event': 'app_parent_switch'}

    res = re.compile('Done').match(log)
    if res:
        application_done_count += 1

    return None

def parseTSCH(log):
    res = re.compile('! can\'t send packet to LL-([0-9a-fA-F]+) with seqno (\d+), queue (\d+)\/(\d+) (\d+)\/(\d+)').match(log)
    if res:
        queue_num = int(res.group(5))
        queue_size = int(res.group(6))
        queue_fill = (queue_num / queue_size) * 100
        return {'event': 'mac',
                'type': 'overflow',
                'queue_num': queue_num,
                'queue_size': queue_size,
                'queue_fill':queue_fill}

    res = re.compile('TX to LL-([0-9a-fA-F]+) seqno (\d+), queue (\d+)\/(\d+) (\d+)\/(\d+)').match(log)
    if res:
        queue_num = int(res.group(5))
        queue_size = int(res.group(6))
        queue_fill = (queue_num / queue_size) * 100
        return {'event': 'mac',
                'type': 'send',
                'queue_num': queue_num,
                'queue_size': queue_size,
                'queue_fill':queue_fill}

    res = re.compile('sf \d+, cell (\d+)\/(\d+), normal: (\d+), shared: (\d+), tx: (\d+)').match(log)
    if res:
        timeslot = int(res.group(1))
        channel = int(res.group(2))
        normal = int(res.group(3))
        shared = int(res.group(4))
        transmissions = int(res.group(5))
        retransmissions = transmissions - 1
        return {'event': 'mac',
                'type': 'mac_tx',
                'timeslot': timeslot,
                'channel': channel,
                'normal': normal,
                'shared': shared,
                'transmissions':transmissions,
                'retransmissions':retransmissions}

    return None

def parseLine(line, testbed):
    global first_unixtime
    #print("Parsing line: " + line)

    if testbed:
        # "1623007554.333982;m3-358;[INFO: Main      ] <log>"
        prefix = '(\d+\.\d+);\w+\-(\d+);'
    else:
        # "119682    ID:2    [WARN: TSCH      ] <log>"
        prefix = '\s*([.\d]+)\tID:(\d+)\t'

    pattern_log_os = '\[(.*?):(.*?)\](.*)$'
    res = re.compile(prefix + pattern_log_os).match(line)

    if res:
        if testbed:
            time_abs = float(res.group(1))

            # Adjust for unixtime used in testbed
            if first_unixtime is None:
                first_unixtime = time_abs

            time = int((time_abs - first_unixtime) * 1000)
        else:
            time = int(res.group(1))

        nodeid = int(res.group(2))
        level = res.group(3).strip()
        module = res.group(4).strip()
        log = res.group(5).strip()

        return time, nodeid, level, module, log

    return None, None, None, None, None

def doParse(file, testbed):
    global network_formation_time_ms
    unknown_line_count = 0
    time = None
    arrays = {}

    for name in metrics:
        arrays[name] = []

    mac_to_node_id_map = {}

#    print("\nProcessing %s" %(file))
    # Filter out non-printable chars from log file
    #os.system("cat %s | tr -dc '[:print:]\n\t' | sponge %s" %(file, file))
    for line in open(file, 'r').readlines():
        # match time, id, module, log; The common format for all log lines
        if "TEST FAILED" in line:
            print("SIMULATION FAILED!")
            return -1

        time, nodeid, level, module, log = parseLine(line, testbed)

        if time == None:
            #print("Unknown line: " + line.rstrip())
            unknown_line_count += 1
            continue

        entry = {
            "timestamp": timedelta(milliseconds=time),
            "node": nodeid,
        }

        try:
            if module == "App":
                #print("nodeid is: " + str(nodeid) + " module is " + str(module))
                ret = parseApp(log)

                if(ret == None):
                    continue

                entry.update(ret)
                if(ret['event'] == 'send' and ret['type'] == 'data'):
                    # populate series of sent requests
                    entry['pdr'] = 0.
                    arrays["packets"].append(entry)
                    if network_formation_time_ms == None:
                        network_formation_time_ms = time
                elif(ret['event'] == 'recv' and ret['type'] == 'data'):

                    # Testbed uses MAC-nodeid instead of the node-id in the log
                    if testbed:
                        if mac_to_node_id_map[ret['src']] != None:
                            #print("src changed from " + str(ret['src']) +
                            #      " to " + str(mac_to_node_id_map[ret['src']]))
                            ret['src'] = mac_to_node_id_map[ret['src']]
                        else:
                            print("Missing mapping for " + str(ret['src']))

                    # Update sent request series with latency and PDR
                    # First find the row
                    txElement = [x for x in arrays["packets"] if x['event'] == 'send' and x['node'] == ret['src'] and x['id'] == ret['id']][0]

                    # Calculate and add latency
                    txElement['latency'] = (entry['timestamp'] - txElement['timestamp']).total_seconds()
                    txElement['pdr'] = 100.

                    # Sanity check tick at transmission matches the packet oTick
                    if txElement['tick'] != ret['oTick']:
                        print("Tick mismatch. Tick " + str(txElement['tick']) + " sent at " +
                              str(txElement['timestamp']) + " vs. oTick " + str(ret['oTick']) +
                              " received at " + str(entry['timestamp']))
                        return -1

                    # We don't use ASN because
                    # 1. We cannot guarantee it is correct
                    #    (TSCH does not maintain "current_asn" all the time)
                    # 2. Cannot be trusted on z1
                    #    (most likely interrupts cause ASN to change between
                    #     printing and writing in packet)

                    # Add latency as ticks as well (we don't use it yet)
                    txElement['rx_tick'] = ret['tick']
                    txElement['latency_tick'] = ret['tick'] - txElement['tick']

                elif ret['event'] == 'app_parent_switch':
                    arrays['app_parent_switch'].append(entry)

            if module == "Energest":
                ret = parseEnergest(log)
                if(ret == None):
                    continue

                entry.update(ret)
                arrays["energest"].append(entry)

            if module == "RPL":
                ret = parseRPL(log)
                if(ret == None):
                    continue

                entry.update(ret)
                if(ret['event'] == 'rpl_stats'):
                    arrays["ranks"].append(entry)
                    arrays["trickle"].append(entry)
                    arrays["hop_count"].append(entry)
                    arrays["nbr_count"].append(entry)
                elif(ret['event'] == 'switch'):
                    arrays["switches"].append(entry)
                elif(ret['event'] == 'DAGinit'):
                    arrays["dag_inits"].append(entry)
                elif(ret['event'] == 'sending'):
                    if not ret['message'] in arrays:
                        arrays[ret['message']] = []
                    arrays[ret['message']].append(entry)
                elif(ret['event'] == 'topology'):
                    for n in parents.keys():
                        nodeEntry = entry.copy()
                        nodeEntry["node"] = n
                        nodeEntry["hops"] = calculateHops(n)
                        nodeEntry["children"] = calculateChildren(n)
                        arrays["topology"].append(nodeEntry)

            if module == "TSCH" or module == "TSCH Queue":
                ret = parseTSCH(log)
                if(ret == None):
                    continue

                entry.update(ret)
                #print("entry: ", str(entry))
                if ret['type'] == 'mac_tx':
                    arrays['mac_tx'].append(entry)
                else:
                    arrays["queue"].append(entry)

            if module == "Main" and testbed:
                mac = parseMain(log)
                if mac != None:
                    mac_to_node_id_map[mac] = nodeid;

        except Exception as e:  # typical exception: failed str conversion to int, due to lossy logs
            print(str(e))
            continue

    # Remove last few packets -- might be in-flight when test stopped
    # arrays["packets"] = arrays["packets"][0:-10]
    # Not necessary since we send a fixed num packets and then idle for a while

    # Remove first packets such that we only get steady-state
    #arrays["packets"] = arrays["packets"][100:]

    if testbed:
        print("Mac-to-node-id map: " + str(mac_to_node_id_map))

    print("Unknown line count: " + str(unknown_line_count))

    if unknown_line_count > 100:
        print("ERR! Too many unknown lines")
        return -1

    return arrays

def outputStats(dfs, key, metric, agg, name, metricLabel=None):
    if not key in dfs:
        return

    df = dfs[key]
    perNode = getattr(df.groupby("node")[metric], agg)()
    perTime = getattr(df.groupby([pd.Grouper(freq="2Min")])[metric], agg)()

    print("  %s:" % (metricLabel if metricLabel != None else metric))
    print("    name: %s" % (name))
    print("    per-node:")
    print("      x: [%s]" % (", ".join(["%u" % x for x in sort(df.node.unique())])))
    print("      y: [%s]" % (', '.join(["%.4f" % (x) for x in perNode])))
    print("    per-time:")
    print("      x: [%s]" % (", ".join(["%u" % x for x in range(0, 2 * len(df.groupby([pd.Grouper(freq="2Min")]).mean().index), 2)])))
    print("      y: [%s]" % (', '.join(["%.4f" % (x) for x in perTime]).replace("nan", "null")))

def is_fitiotlab(file):
    with open(file, 'r') as f:
        first_line = f.readline()
        # The start of FIT iot-lab logs are: "1623007554.335971;m3-358;<log>"
        res = re.compile('\d{10}\.\d{6};\w+\-\w+;').match(first_line)
        if res:
            return True

    return False

def convert_data_arrays_to_dfs(arrays):
    dfs = {}
    for key in arrays.keys():
        if(len(arrays[key]) > 0):
            df = DataFrame(arrays[key])
            #print("DF is: ", df)
            #print("New DF: " + key)
            dfs[key] = df.set_index("timestamp")

    return dfs

def parse_logfile(file, quiet=False):
    # Stop output. This solution is a mess and I dont understand it. TODO
    global print
    print = logging.info
    logging.basicConfig(level=logging.WARNING if quiet else logging.INFO,
                    format="%(message)s")

    # Check if logfile is from FIT iot-lab
    if is_fitiotlab(file):
        print("Log is from testbed")
        testbed = True
    else:
        print("Log is from simulator")
        testbed = False

    data_arrays = doParse(file, testbed)

    dfs = convert_data_arrays_to_dfs(data_arrays)

    # Verify application has finished on all nodes
    num_tx_nodes = dfs["energest"].node.nunique() - 1
    if application_done_count != num_tx_nodes:
        print("Application not finished! " +
              str(application_done_count) + "/" + str(num_tx_nodes))
        return

    #print(dfs)

    if len(dfs) == 0:
        return

    packets_sent = dfs["packets"]["pdr"].count();
    # A packet which is not received is stored with PDR = 0
    packets_received = dfs["packets"]["pdr"].sum() / 100

    # There are some rpoblems with the queue-stuff:
    # 1. All packets are counted, thus the queue overflow is larger than
    #    lost applicaiton packets
    # 2. The queue size is onluy printed when sending or sending failed
    #    TODO Add a print at every manipulatio of queue to have a proper stat.
    # Needed?

    # Drops (This does not take transmissions failures into account)
    overflows = dfs["queue"][dfs["queue"]["type"] == "overflow"]["type"].count()

    # seriesObj = dfs["queue"].apply(lambda x: True if x["type"] == "drop" else False, axis = 1)
    # numRows = len(seriesObj[seriesObj == True].index)

    print("global-stats:")
    print("  pdr: %.4f" % (dfs["packets"]["pdr"].mean()))
    print("  loss-rate: %.e" % (1 - (dfs["packets"]["pdr"].mean() / 100)))
    print("  packets-sent: %u" % (packets_sent))
    print("  packets-received: %u" % (packets_received))
    print("  packets-lost: %u" % (packets_sent - packets_received))
    print("  queue-overflows %u" % (overflows))

    print("  latency mean: %.4f" % (dfs["packets"]["latency"].mean()))
    print("  latency max: %.4f" % (dfs["packets"]["latency"].max()))
    print("  duty-cycle: %.2f" % (dfs["energest"]["duty_cycle"].mean()))
    print("  duty-cycle tx: %.2f" % (dfs["energest"]["duty_cycle_tx"].mean()))
    print("  duty-cycle rx: %.2f" % (dfs["energest"]["duty_cycle_rx"].mean()))
    print("  network-formation-time: %.3f" % (network_formation_time_ms / 1000))
    print("stats:")

    # Output relevant metrics
    outputStats(dfs, "packets", "pdr", "mean", "Round-trip PDR (%)")
    outputStats(dfs, "packets", "latency", "mean", "Round-trip latency (s)")
    outputStats(dfs, "queue", "queue_fill", "mean", "Queue fill")
    outputStats(dfs, "app_parent_switch", "app_parent_switch", "count", "Parent switch during application")

    # outputStats(dfs, "energest", "duty_cycle", "mean", "Radio duty cycle (%)")
    outputStats(dfs, "ranks", "rank", "mean", "RPL rank (ETX-128)")
    outputStats(dfs, "ranks", "hop_count", "max", "Hop count max")
    outputStats(dfs, "ranks", "hop_count", "min", "Hop count min")
    outputStats(dfs, "ranks", "hop_count", "mean", "Hop count mean")
    outputStats(dfs, "switches", "pswitch", "count", "RPL parent switches (#)")
    outputStats(dfs, "dag_inits", "event", "count", "RPL joining DAG (#)")
    outputStats(dfs, "trickle", "trickle", "mean", "RPL Trickle period (min)")

    outputStats(dfs, "DIS", "message", "count", "RPL DIS sent (#)", "rpl-dis")
    outputStats(dfs, "unicast-DIO", "message", "count", "RPL uDIO sent (#)", "rpl-udio")
    outputStats(dfs, "multicast-DIO", "message", "count", "RPL mDIO sent (#)", "rpl-mdio")
    outputStats(dfs, "DAO", "message", "count", "RPL DAO sent (#)", "rpl-dao")
    outputStats(dfs, "DAO-ACK", "message", "count", "RPL DAO-ACK sent (#)", "rpl-daoack")

    #outputStats(dfs, "topology", "hops", "mean", "RPL hop count (#)")
    #outputStats(dfs, "topology", "children", "mean", "RPL children count (#)")

    outputStats(dfs, "mac_tx", "retransmissions", "sum", "Total retransmission")
    outputStats(dfs, "ranks", "nbr_count", "max", "Max. neighbor count")

    # Return the packet and queue DF
    return dfs

# Inspired by http://www.randalolson.com/2012/06/26/using-pandas-dataframes/
# Parses all logs in directory into a dict of DFs
def parse_logs_dir(directory):
    directory = directory.rstrip('/') + "/*"

    # A ditionary of metrics containing dictionaries of DF from each run
    all_runs_dfs = defaultdict(dict)

    # Iterate all folders containing different runs in the directory
    for folder in glob.glob(directory):
        # Iterate and parse all log files in the folder
        # We have only one file pr run at the moment, but this might change
        for logfile in glob.glob(folder + "/" + SCRIPT_LOG_PATTERN):
            name_of_run = os.path.basename(folder)
            print("Parsing " + logfile)

            run_dfs = parse_logfile(logfile, logging.getLogger() == logging.INFO)

            for df_name in run_dfs:
                # Add this DF to the dictionary of DFs
                all_runs_dfs[df_name][name_of_run] = run_dfs[df_name]
                # Save as CSV
                csv_name = str(Path(logfile).parent) + "/" + df_name + ".csv"
                run_dfs[df_name].to_csv(csv_name)

    return all_runs_dfs

def parse_logs_scenario(scenario_dir, scenario_name):

    dfs = parse_logs_dir(scenario_dir)

    print("Parsed runs: " + str(dfs["energest"].keys()))
    return dfs

def parse_logs_scenarios(scenarios, quiet=False):
    # Stop output. This solution is a mess and I dont understand it. TODO
    global print
    print = logging.info
    if quiet:
        print("Getting stats for scenarios in quiet mode")
    logging.basicConfig(level=logging.WARNING if quiet else logging.INFO,
                    format="%(message)s")

    for scenario in scenarios:
        raw_dfs = parse_logs_scenario(scenario['path'], scenario['name'])

        # Add the raw DFs to the scenario dict in the scenarios list
        for df_name in raw_dfs:
            metric_df_name = "raw_" + df_name + "_dfs"
            scenario[metric_df_name] = raw_dfs[df_name]
