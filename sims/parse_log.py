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
import traceback

# Constants
SCRIPT_LOG_PATTERN = '*.scriptlog'  # For simulations run by simexec.sh
# SCRIPT_LOG_PATTERN = '*.testlog' # For simulations run directly
TIME_TO_SKIP_AT_END = "1 Min"

# Global variable to replace print for quiet mode
print

parents = {}
first_unixtime = None
application_start = None
application_done_count = 0
final_time = 0
log_order_error = 0

metrics = ["packets", "energest", "rpl_stats", "app_parent_switch",
           "switches", "dag_inits", "topology", "queue", "mac_tx",
           "mac_err", "mac_stats", "mac_cell", "skipped_app_packets"]

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
    res = re.compile('.*? rank (\d*).*?dioint (\d*).*?nbr count (\d*), depth (\d*)').match(log)
    if res:
        rank = int(res.group(1))
        trickle = (2 ** int(res.group(2))) / (60 * 1000.)
        nbr_count = int(res.group(3))
        #  uint8_t route_hop_count = ((rpl_dag->rank / RPL_MIN_HOPRANKINC) - 1) / 3;
        #hop_count = ((rank / 256) - 1) / 3
        hop_count = int(res.group(4))
        return {'event': 'rpl_stats', 'rank': rank, 'trickle': trickle,
                'hop_count': hop_count, 'nbr_count': nbr_count}

    # Parent switch (broad regexp to catch both NULL and 6L-xxxx
    res = re.compile('parent switch: .*? -> (.*?)$').match(log)
    if res:
        parent = res.group(1)
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

    # For RPL-classic this means the node has joined the RPL network
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

    res = re.compile('TX (.+?) num (\d+) tick (\d+) to 6G-([0-9a-fA-F]+) from depth (\d+)').match(log)
    if res:
        type = res.group(1)
        packet_id = int(res.group(2))
        origin_tick = int(res.group(3))
        dest = int(res.group(4), 16)
        depth = int(res.group(5))
        return {'event': 'send',
                'type': type,
                'origin_tick': origin_tick,
                'packet_id': packet_id,
                'dest': dest,
                'depth': depth}

    res = re.compile('RX (.+?) num (\d+) oTick (\d+) tick (\d+) from 6G-([0-9a-fA-F]+)').match(log)
    if res:
        type = res.group(1)
        packet_id = int(res.group(2))
        origin_tick = int(res.group(3))
        rx_tick = int(res.group(4))
        src = int(res.group(5), 16)
        return {'event': 'recv',
                'type': type,
                'origin_tick': origin_tick,
                'rx_tick': rx_tick,
                'packet_id': packet_id,
                'src': src }

    # This might be completely redundant and covered by RPL logs
    # (maybe useful if want to disable RPL logging?)
    res = re.compile('Parent switch').match(log)
    if res:
        return {'event': 'app_parent_switch'}

    res = re.compile('Lost conn! Skipping packet!').match(log)
    if res:
        return {'event': 'lost_conn_skip_packet'}

    res = re.compile('Done').match(log)
    if res:
        application_done_count += 1

    return None

def parseTSCH(log):
    # Parse TSCH-LOG: Only unicast TX
    # A lot of variable amount of whitespaces, hence the usage of \s+
    res = re.compile('{asn \d+.([0-9a-fA-F]+) link\s+\d\s+\d+\s+\d+\s+(\d+)\s+(\d+) ch\s+(\d+)} uc-\d-(\d) tx LL-([0-9a-fA-F]+)->LL-([0-9a-fA-F]+), len\s+\d+, seq\s+\d+, st (\d)\s+(\d+)').match(log)
    if res:
        asn = res.group(1)
        timeslot = int(res.group(2))
        channel_offset = int(res.group(3))
        channel = int(res.group(4))
        security_enabled = int(res.group(5))
        app_packet = security_enabled # When Layered, hijacked for packet type
        node_src = res.group(6)
        node_dest = res.group(7)
        result = int(res.group(8))
        if result == 0:
            prr = 100
        else:
            prr = 0 # All failures
        transmissions = int(res.group(9))
        return {'event': 'mac',
                'type': 'cell',
                'asn': asn,
                'timeslot': timeslot,
                'channel_offset': channel_offset,
                'channel': channel,
                'app': app_packet,
                'node_src': node_src,
                'node_dest': node_dest,
                'result': result,
                'prr': prr,
                'transmissions': transmissions
                }

    # Error log when using layered hack
    res = re.compile('Timing err: (\d+), hack mism: (\d+), hack err: (\d+), hack del: (\d+)').match(log)
    if res:
        timing_errors = int(res.group(1))
        hack_mismatch = int(res.group(2))
        hack_errors = int(res.group(3))
        hack_deletions = int(res.group(4))
        return {'event': 'mac',
                'type': 'stats',
                'timing_err': timing_errors,
                'hack_mismatch': hack_mismatch,
                'hack_err': hack_errors,
                'hack_deletions': hack_deletions}

    # Error log when using layered flow queues
    res = re.compile('Timing err: (\d+), miss nei: (\d+), lay err: (\d+)').match(log)
    if res:
        timing_errors = int(res.group(1))
        missing_neighbor = int(res.group(2))
        layered_err = int(res.group(3))
        return {'event': 'mac',
                'type': 'stats',
                'timing_err': timing_errors,
                'missing_neighbor': missing_neighbor,
                'layered_err': layered_err}


    res = re.compile('.+? !dl-miss .+? err:1').match(log)
    if res:
        return {'event': 'mac',
                'type': 'dl_miss_err'}

    res = re.compile('! can\'t send packet to LL-([0-9a-fA-F]+).* with seqno (\d+), queue (\d+)\/(\d+) (\d+)\/(\d+) app (\d+)').match(log)
    if res:
        queue_num = int(res.group(5))
        queue_size = int(res.group(6))
        queue_fill = (queue_num / queue_size) * 100
        app = int(res.group(7))
        return {'event': 'mac',
                'type': 'overflow',
                'queue_num': queue_num,
                'queue_size': queue_size,
                'queue_fill': queue_fill,
                'app': app}

    res = re.compile('TX to LL-([0-9a-fA-F]+).* seqno (\d+), queue (\d+)\/(\d+) (\d+)\/(\d+)').match(log)
    if res:
        queue_num = int(res.group(5))
        queue_size = int(res.group(6))
        queue_fill = (queue_num / queue_size) * 100
        return {'event': 'mac',
                'type': 'send',
                'queue_num': queue_num,
                'queue_size': queue_size,
                'queue_fill':queue_fill}

    res = re.compile('sf \d+, cell (\d+)\/(\d+), normal: (\d+), shared: (\d+), tx: (\d+), asn: (\d+), app: (\d+), res: (.*)').match(log)
    if res:
        timeslot = int(res.group(1))
        channel = int(res.group(2))
        normal = int(res.group(3))
        shared = int(res.group(4))
        transmissions = int(res.group(5))
        retransmissions = transmissions - 1
        asn = int(res.group(6))
        app = int(res.group(7))
        result = res.group(8)
        return {'event': 'mac',
                'type': 'mac_tx',
                'timeslot': timeslot,
                'channel': channel,
                'normal': normal,
                'shared': shared,
                'transmissions':transmissions,
                'retransmissions':retransmissions,
                'asn':asn,
                'app':app,
                'result':result}

    # Simplified version of above
    res = re.compile('cell (\d+)\/(\d+), tx: (\d+), app: (\d+), res: (.*)').match(log)
    if res:
        timeslot = int(res.group(1))
        channel = int(res.group(2))
        transmissions = int(res.group(3))
        retransmissions = transmissions - 1
        app = int(res.group(4))
        result = res.group(5)
        return {'event': 'mac',
                'type': 'mac_tx',
                'timeslot': timeslot,
                'channel': channel,
                'transmissions':transmissions,
                'retransmissions':retransmissions,
                'app':app,
                'result':result}

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

            time_ms = int((time_abs - first_unixtime) * 1000)
        else:
            time_ms = int(res.group(1))

        nodeid = int(res.group(2))
        level = res.group(3).strip()
        module = res.group(4).strip()
        log = res.group(5).strip()

        return time_ms, nodeid, level, module, log

    return None, None, None, None, None

def calculate_testbed_latency_in_sec(tx_tick, rx_tick):
    # 1 tick on FIT IoT-lab m3 is 10 ms
    # + 10 ms below as that is the resolution and we want to
    # be pessimistic, which avoids e.g. latency being zero.
    return (((rx_tick - tx_tick) * 10) + 10) / 1000

def doParse(file, app_warmup, testbed):
    global application_start
    global parents
    global final_time
    global log_order_error
    parent = {}
    application_start = None
    unknown_line_count = 0
    log_order_error = 0
    packet_multiple_rx = 0
    time = None
    arrays = {}

    for name in metrics:
        arrays[name] = []

    # Node ID is the log-line identifier (typical m3-xxx)
    # While mac-id is the node internal id (typical set by deployment module)
    node_id_to_mac_id_map = {}

#    print("\nProcessing %s" %(file))
    # Filter out non-printable chars from log file
    #os.system("cat %s | tr -dc '[:print:]\n\t' | sponge %s" %(file, file))
    with open(file, 'r') as f:
        for line in f:
   # for line in open(file, 'r').readlines():
            # match time, id, module, log; The common format for all log lines
            if "TEST FAILED" in line:
                print("EXPERIMENT FAILED!")
                return None

            time_ms, nodeid, level, module, log = parseLine(line, testbed)

            if time_ms == None:
                #print("Unknown line: " + line.rstrip())
                unknown_line_count += 1
                continue

            # app_warmup is given in minutes
            app_start_time_ms = app_warmup * 60 * 1000

            # Final time will be used to filter end of log
            time_ms_timedelta = timedelta(milliseconds=time_ms)
            final_time = time_ms_timedelta

            entry = {
                "timestamp": time_ms_timedelta,
                "node": nodeid,
                "app_started": 0 if time_ms < app_start_time_ms else 1
            }

            try:
                if module == "App":
                    ret = parseApp(log)

                    if(ret == None):
                        continue

                    entry.update(ret)

                    if ret['event'] == 'lost_conn_skip_packet':
                        arrays['skipped_app_packets'].append(entry)
                        continue

                    if ret['event'] == 'app_parent_switch':
                        arrays['app_parent_switch'].append(entry)
                        continue

                    if not testbed:
                        print("Only testbed support ID- and latency-calculations")
                        return None

                    # Three corner cases must be covered:
                    # 1. TX event for a packet already RXed
                    # 2. RX event for a packet not TXed
                    # 3. RX twice due to missed ACK

                    # First find the packet source
                    # If it is a send-event we simply see who printed the log
                    if entry['event'] == 'send':
                        # The log line id is different than the node mac IDs
                        # so convert it first
                        # TODO should we rather conver the "nodeid" to the
                        # internal mac ids for everything?
                        # Also, this could be avoided if the sending mac id was
                        # included in the log content
                        if entry['node'] in node_id_to_mac_id_map:
                            #print("ID changed from " + str(entry['node']) +
                            #      " to " + str(node_id_to_mac_id_map[entry['node']]))
                            packet_src = node_id_to_mac_id_map[entry['node']]
                        else:
                            print("No ID-mapping for node " + str(entry['node']))
                            return None

                    # If it is receive-event, we get it from the log content
                    elif entry['event'] == 'recv':
                        packet_src = entry['src']
                    else:
                        print("Unsupported event! " + str(entry['event']))
                        return None

                    entry['src'] = packet_src

                    # Check if this packet has an existing entry
                    existing_entry = False
                    for packet in arrays["packets"]:
                        if packet['packet_id'] == entry['packet_id'] and \
                            packet['src'] == entry['src']:

                            existing_entry = True

                            # If this was a TX it means it was a
                            # TX event for a packet already RXed (corner-case 1)
                            # If so, convert to a send event and
                            # fill in missing info
                            if entry['event'] == 'send':
                                packet['event'] = 'send'
                                packet['dest'] = entry['dest']
                                packet['depth'] = entry['depth']
                                break

                            # If this was a RX it meant it was
                            # 1. RX of a TX (normal), or
                            # 2. RX of a TX already RXed (corner-case 2)
                            if entry['event'] == 'recv':
                                if "latency" not in packet:
                                    # 1. RX of a TX (normal). Fill in info.
                                    # Calculate latency. Only FIT IoT-lab testbed
                                    # supported, catched by earlier if.
                                    latency_sec = \
                                        calculate_testbed_latency_in_sec(
                                            entry["origin_tick"], entry["rx_tick"])
                                    packet["latency"] = latency_sec

                                    packet["pdr"] = 100.
                                    packet["rx_tick"] = entry["rx_tick"]
                                    break
                                else:
                                    # 2. RX of a TX already RXed (ACK has been missed)
                                    # Simply do nothing
                                    #print("RX of already RX:")
                                    #print(packet)
                                    packet_multiple_rx += 1
                                    break

                    if existing_entry:
                        continue

                    # No existing entry

                    # If this was a TX we simply add it
                    if entry['event'] == 'send':
                        entry['pdr'] = 0.
                        arrays["packets"].append(entry)
                        continue

                    # If this was a RX it means we got RX before TX (corner-case 3)
                    # Add what we have, it will completed when the TX comes,
                    # and if not corrected it will raise error
                    elif entry['event'] == 'recv':
                        latency_sec = \
                            calculate_testbed_latency_in_sec(
                                entry["origin_tick"], entry["rx_tick"])
                        entry["latency"] = latency_sec
                        entry["pdr"] = 100.
                        arrays["packets"].append(entry)
                        log_order_error += 1
                        continue
                    else:
                        print("Unsupported new event!")
                        return None

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
                        arrays["rpl_stats"].append(entry)
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

                if module == "TSCH" or module == "TSCH Queue" or module == "TSCH-LOG" or module == "TSCH Sched":
                    ret = parseTSCH(log)
                    if(ret == None):
                        continue
                    entry.update(ret)
                    if ret['type'] == 'mac_tx':
                        # Note that although only application use non-shared
                        # normal cells, there are exceptions when cells are
                        # removed/added after packet has been assigned ts/ch
                        arrays['mac_tx'].append(entry)
                    elif ret['type'] == 'dl_miss_err':
                        arrays['mac_err'].append(entry)
                    elif ret['type'] == 'stats':
                        arrays['mac_stats'].append(entry)
                    elif ret['type'] == 'cell':
                        arrays['mac_cell'].append(entry)
                    else:
                        arrays["queue"].append(entry)

                if module == "Main" and testbed:
                    mac_node_id = parseMain(log)
                    if mac_node_id != None:
                        node_id_to_mac_id_map[nodeid] = mac_node_id

            except Exception as e:  # typical exception: failed str conversion to int, due to lossy logs
                print(traceback.format_exc())
                #print(arrays["packets"])
                continue

    # Remove last few packets -- might be in-flight when test stopped
    # arrays["packets"] = arrays["packets"][0:-10]
    # Not necessary since we send a fixed num packets and then idle for a while

    # Remove first packets such that we only get steady-state
    #arrays["packets"] = arrays["packets"][100:]

    #if testbed:
        #print("Mac-to-node-id map: " + str(mac_to_node_id_map))

    #print("Unknown line count: " + str(unknown_line_count))

    if unknown_line_count > 300:
        print("ERR! Too many unknown lines, " + str(unknown_line_count))
        return None

    for packet in arrays["packets"]:
        if packet["event"] == "recv":
            print("ERR! Missing TX for RXed packet!")
            print(str(packet))
            return None

    if packet_multiple_rx > 0:
        print("Number of duplicate RXs: " + str(packet_multiple_rx))
        # A large amount of duplicate RX is possible with Layered
        # because the L2 duplication detection mechanism does not work
        # well when nodes are sending from different queues (with
        # different sequence numbers).
        if packet_multiple_rx > 10000:
            print("ERR! Too many duplicate RXes")
            return None

    if log_order_error > 0:
        print("Number of log-lines out of order: " + str(log_order_error))
        if log_order_error > 100:
            print("ERR! Too many log-lines out of order")
            return None

    return arrays, len(node_id_to_mac_id_map)

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
    print("      y: [%s]" % (', '.join(["%.2f" % (x) for x in perNode])))
    print("    per-time:")
    print("      x: [%s]" % (", ".join(["%u" % x for x in range(0, 2 * len(df.groupby([pd.Grouper(freq="2Min")]).mean().index), 2)])))
    print("      y: [%s]" % (', '.join(["%.2f" % (x) for x in perTime]).replace("nan", "null")))

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

def parse_logfile(file, app_warmup, has_spatial,
                  num_expected_nodes, quiet=False):
    # Stop output. This solution is a mess and I dont understand it. TODO
    global print
    print = logging.info
    logging.basicConfig(level=logging.WARNING if quiet else logging.INFO,
                    format="%(message)s")

    # Reset global resources
    global first_unixtime
    global application_done_count
    global final_time
    first_unixtime = None
    application_done_count = 0
    final_time = 0

    # Check if logfile is from FIT iot-lab
    if is_fitiotlab(file):
        print("Log is from testbed")
        testbed = True
    else:
        print("Log is from simulator")
        testbed = False

    meta = {"result": "ok"}

    data_arrays, num_nodes_in_log = doParse(file, app_warmup, testbed)
    if data_arrays is None:
        print("Error when parsing!")
        meta["result"] = "error-parsing"
        return None, meta

    dfs = convert_data_arrays_to_dfs(data_arrays)

    if len(dfs) == 0:
        print("Empty DFs!")
        meta["result"] = "error-no-df"
        return None, meta

    # Verify all nodes are running and outputting log
    if num_expected_nodes != 0:
        if num_expected_nodes != num_nodes_in_log:
            print("Node(s) missing! Expected %d, was %d" % \
                  (num_expected_nodes, num_nodes_in_log))
            print("All nodes:" + str(num_nodes_in_log))
            meta["result"] = "error-miss-nodes"
            return None, meta

    # Verify application has finished on all nodes
    if "packets" not in dfs:
        print("No packets sent!")
        meta["result"] = "error-no-packets"
        return None, meta

    # Set app_started to 0 at end of all logs to remove e.g. packets in flight
    last_valid_time = final_time - pd.Timedelta(TIME_TO_SKIP_AT_END)
    for df_name in dfs:
        df = dfs[df_name]
        df.loc[df.index > last_valid_time, "app_started"] = 0

    num_tx_nodes = dfs["packets"].node.nunique()
    #if application_done_count != num_tx_nodes:
    #    print("Application not finished! " +
    #          str(application_done_count) + "/" + str(num_tx_nodes))
    #    return None

#    print("Application finished! " +
#          str(application_done_count) + "/" + str(num_tx_nodes))

    # Verify all nodes have joined the DAG
    num_non_root_nodes = dfs["energest"].node.nunique() - 1
    num_joined_nodes = dfs["dag_inits"].node.nunique()
    if num_joined_nodes != num_non_root_nodes:
        print("Not all nodes joined DAG! " +
              str(num_joined_nodes) + "/" + str(num_non_root_nodes))
        meta["result"] = "error-missing-rpl"
        return None, meta

    # Last joining of the DAG
    network_formation_time = dfs["dag_inits"].tail(1).index[0].total_seconds()

    # Topology changes after app started
    #if "app_parent_switch" in dfs:
    #    print("Parent switch during application!")
    #    outputStats(dfs, "app_parent_switch", "node", "count", "Parent switch during application")
    #    return None

    # Topology changes after app started
    parent_switch_df = dfs["switches"]
    parent_switch_count = len(parent_switch_df[parent_switch_df["app_started"] == 1])
    meta["parent_switch_app"] = parent_switch_count
    if parent_switch_count > 0:
        print("Parent switches during application: " + parent_switch_count)
        #meta["result"] = "switch"
        #return None, meta
        #outputStats(dfs, "switches", "pswitch", "count", "RPL parent switches (#)")

    # There are some problems with the queue-stuff:
    # 1. All packets are counted, thus the queue overflow is larger than
    #    lost applicaiton packets
    # 2. The queue size is onluy printed when sending or sending failed
    #    TODO Add a print at every manipulatio of queue to have a proper stat.
    # Needed?

    # App overflows (This does not take transmissions failures into account)
    if "queue" in dfs:
        queue_df = dfs["queue"]
        overflows_df = queue_df[queue_df["type"] == "overflow"]
        overflows_df = overflows_df[overflows_df["app_started"] == 1]
        overflows = len(overflows_df)
        if "app" in overflows_df:
            app_overflows = len(overflows_df[overflows_df["app"] == 1])
        else:
            app_overflows = 0


    packets_df = dfs["packets"]
    app_packets_df = packets_df[packets_df["app_started"] == 1]
    packets_sent = len(app_packets_df);
    # A packet which is not received is stored with PDR = 0
    packets_received = app_packets_df["pdr"].sum() / 100

    # Abort if there are almost no eligible packets sent
    if packets_sent < 100:
        print("Too few eligible app. packets! (" + str(packets_sent) + ")")
        meta["result"] = "error-app-packets"
        return None, meta

    # Check how many app packets were skipped
    if "skipped_app_packets" in dfs:
        skipped_app_packets_df = dfs["skipped_app_packets"]
        skipped_app_packets = len(
            skipped_app_packets_df[skipped_app_packets_df["app_started"] == 1])
        if skipped_app_packets > 0:
            print("App packets skipped due to lost connection: " +
                  str(skipped_app_packets))
            if skipped_app_packets > (packets_sent / 2):
                print("ERR! Too many skipped app packets")
                meta["result"] = "error-skip-app-packets"
                return None, meta


    # Abort if packets are sent too shallow
    # This test is redundant as the problem is catched by the spatial reuse test
    #too_shallow_tx = len(app_packets_df[app_packets_df["depth"] < 6])

    # Max. hop count after app started
    rpl_stats_df = dfs["rpl_stats"]
    # Remove rows where not attached to network
    hop_count_df = rpl_stats_df[rpl_stats_df["hop_count"] != 65535]
    app_max_hop_count = hop_count_df[hop_count_df["app_started"] == 1]["hop_count"].max()

    # ETX for application cells
    if "mac_tx" in dfs:
        mac_tx_df = dfs["mac_tx"]
        app_tx = mac_tx_df[mac_tx_df["app"] == 1]
        app_tx = app_tx[app_tx["app_started"] == 1]
        app_tx_etx = app_tx["transmissions"].sum() / \
            len(app_tx["transmissions"][app_tx["result"] == "ok"])

    if "mac_cell" in dfs and False:
        # Find ETX for spatial reused cells. Only supported when running Layered! (due to app field)
        mac_cell_df = dfs["mac_cell"]
        # Note that there might be slightly more TX here than with the "mac_tx"
        # approach above. This is because the mac_tx is printed only at either
        # success or timeout (reached max rtx). Thus those transmissions which
        # has not reached that state at the end of experiment will not be included
        app_cell_df = mac_cell_df[mac_cell_df["app"] == 1]
        app_cell_df = app_cell_df[app_cell_df["app_started"] == 1]

        # Spatial reuse
        # Find spatial reuse via groupby and filter
        spatial_reuse_df = app_cell_df.groupby(["asn", "channel"]).filter(lambda x: len(x) >= 2)

        # Find non-spatial reuse via drop_duplicates
        # (could have done merge of spatial-reuse)
        no_spatial_reuse_df = app_cell_df.drop_duplicates(subset=["asn", "channel"], keep=False)

        spatial_reuse_total = len(spatial_reuse_df)
        if spatial_reuse_total != 0:
            # 0 indicates success
            spatial_reuse_success = len(spatial_reuse_df[spatial_reuse_df["result"] == 0])
            if spatial_reuse_success != 0:
                spatial_reuse_etx = spatial_reuse_total / spatial_reuse_success
            else:
                spatial_reuse_etx = 8
            spatial_reuse_ratio = len(spatial_reuse_df) / len(app_cell_df) * 100
            print("Spatial reuse ratio: %.4f %% (%d/%d)",
                  spatial_reuse_ratio,
                  len(spatial_reuse_df),
                  len(app_cell_df))

            # TODO
            #dfs["spatial"] = spatial_reuse_df
            #dfs["no_spatial"] = no_spatial_reuse_df

            # Skip if this was a spatial reuse scenario, but
            # there is still not more than 40 % spatial reuse
            if has_spatial and spatial_reuse_ratio < 40: # TODO
                print("Too little spatial reuse for scenario!")
                meta["result"] = "spatial"
                return None, meta

            print("ETX for spatial reuse cells: %.4f", spatial_reuse_etx)
            print("ETX for no-spatial reuse cells: %.4f",
                  len(no_spatial_reuse_df) /
                  len(no_spatial_reuse_df[no_spatial_reuse_df["result"] == 0]))
        else:
            print("No spatial reuse")

    # dl-miss with error # redundant with the new MAC stats
    #if "mac_err" in dfs:
    #    mac_err_df = dfs["mac_err"]
    #    dl_miss_err = len(mac_err_df[mac_err_df["type"] == "dl_miss_err"])
    #else:
    #    dl_miss_err = 0
    #print("  dl-miss w/err: " + str(dl_miss_err))

    # Check MAC stats
    if "mac_stats" in dfs:
        mac_stats_df = dfs["mac_stats"]
        mac_stats_app_df = mac_stats_df[mac_stats_df["app_started"] == 1]

        # app_warmup is given in minutes
        app_start_time_ms = app_warmup * 60 * 1000
        mac_stats_before_app_df = \
            mac_stats_df[mac_stats_df.index < timedelta(milliseconds=app_start_time_ms)]

        timing_err_total_app = \
            mac_stats_app_df.groupby('node')["timing_err"].max().sum() - \
            mac_stats_before_app_df.groupby('node')["timing_err"].max().sum()
        #hack_mismatch_total_app = \
        #    mac_stats_app_df.groupby('node')["hack_mismatch"].max().sum() - \
        #    mac_stats_before_app_df.groupby('node')["hack_mismatch"].max().sum()
        #hack_err_total_app = \
        #    mac_stats_app_df.groupby('node')["hack_err"].max().sum() - \
        #    mac_stats_before_app_df.groupby('node')["hack_err"].max().sum()
        #hack_deletions_total_app = \
        #    mac_stats_app_df.groupby('node')["hack_deletions"].max().sum() - \
        #    mac_stats_before_app_df.groupby('node')["hack_deletions"].max().sum()
        missing_neighbor_total_app = \
            mac_stats_app_df.groupby('node')["missing_neighbor"].max().sum() - \
            mac_stats_before_app_df.groupby('node')["missing_neighbor"].max().sum()
        layered_err_total_app = \
            mac_stats_app_df.groupby('node')["layered_err"].max().sum() - \
            mac_stats_before_app_df.groupby('node')["layered_err"].max().sum()

        #hack_mismatch_total_app = 0
        #hack_err_total_app = 0
        #hack_deletions_total_app = 0

        # TODO
        #timing_err_total_app = 0
        #missing_neighbor_total_app = 0
        #layered_err_total_app = 0

        meta["timing_err_app"] = timing_err_total_app
        #meta["hack_mismatch_during_app"] = hack_mismatch_total_app
        #meta["hack_errors_during_app"] = hack_err_total_app
        #meta["hack_deletions_during_app"] = hack_deletions_total_app
        meta["queue_err_app"] = missing_neighbor_total_app
        meta["layered_err_app"] = layered_err_total_app

        print("MAC errors: timing-error: %d, " \
              "missing-neighbor: %d, layered-error %d" % \
              (timing_err_total_app, missing_neighbor_total_app,
               layered_err_total_app))
        #print("MAC errors: timing-error: %d, hack-mismatch: %d, " \
        #      "hack-error %d, hack-deletions: %d, missing-neighbor: %d, layered-error %d" % \
        #      (timing_err_total_app, hack_mismatch_total_app,
        #      hack_err_total_app, hack_deletions_total_app,
        #      missing_neighbor_total_app, layered_err_total_app))
        if timing_err_total_app > 10:
            print("Too many timing errors!")
            outputStats(dfs, "mac_stats", "timing_err", "max", "Missed TSCH timings")
            meta["result"] = "error-mac-timing"
            return None, meta
        #if hack_mismatch_total_app > 10:
        #    print("Too many hack mismatches!")
        #    outputStats(dfs, "mac_stats", "hack_mismatch", "max", "Hack mismatch")
        #    meta["result"] = "error"
        #    return None, meta
        #if hack_err_total_app > 10:
        #    print("Too many hack errors!")
        #    outputStats(dfs, "mac_stats", "hack_err", "max", "Hack errors")
        #    meta["result"] = "error"
        #    return None, meta
        #if hack_deletions_total_app > 10:
        #    print("Too many hack deletions!")
        #    outputStats(dfs, "mac_stats", "hack_deletions", "max", "Hack deleted packets")
        #    meta["result"] = "error"
        #    return None, meta
        if missing_neighbor_total_app > 2:
            print("Missing neighbor!")
            outputStats(dfs, "mac_stats", "missing_neighbor", "max", "Missing neighbor")
            meta["result"] = "error-mac-neigh"
            return None, meta
        if layered_err_total_app > 2:
            print("Layered error!")
            outputStats(dfs, "mac_stats", "layered_err", "max", "Layered error")
            meta["result"] = "error-mac-layered"
            return None, meta

    if "mac_cell" in dfs:
        mac_cell_df = dfs["mac_cell"]
        mac_cell_app_df = mac_cell_df[mac_cell_df["app_started"] == 1]

        # Get the number of MAC cell TX errors
        # Exclude success and no ack
        cell_tx_errors_df = mac_cell_app_df[mac_cell_app_df["result"] != 0]
        cell_tx_errors_df = cell_tx_errors_df[cell_tx_errors_df["result"] != 2]
        cell_tx_errors_total_app = len(cell_tx_errors_df)
        meta["cell_tx_err_app"] = cell_tx_errors_total_app
        if cell_tx_errors_total_app > 10:
            print("Cell TX errors!", cell_tx_errors_total_app)
            meta["result"] = "error-mac-tx"
            return None, meta

    if "mac_tx" in dfs:
        print("Num tx: " + str(app_tx["transmissions"].sum()))
        print("Num ok tx: " + str(len(app_tx["transmissions"][app_tx["result"] == "ok"])))

    print("global-stats:")
    print("  pdr: %.4f" % (app_packets_df["pdr"].mean()))
    if "mac_cell" in dfs:
        print("  prr: %.4f" % (mac_cell_app_df["prr"].mean()))
    print("  loss-rate: %.e" % (1 - (app_packets_df["pdr"].mean() / 100)))
    print("  packets-sent: %u" % (packets_sent))
    print("  packets-received: %u" % (packets_received))
    print("  packets-lost: %u" % (packets_sent - packets_received))
    print("  overflows app/all %u/%u" % (app_overflows,overflows))

    print("  latency mean: %.4f" % (app_packets_df["latency"].mean()))
    print("  latency max: %.4f" % (app_packets_df["latency"].max()))
    print("  duty-cycle: %.2f" % (dfs["energest"]["duty_cycle"].mean()))
    print("  duty-cycle tx: %.2f" % (dfs["energest"]["duty_cycle_tx"].mean()))
    print("  duty-cycle rx: %.2f" % (dfs["energest"]["duty_cycle_rx"].mean()))
    print("  network-formation-time: %.2f" % (network_formation_time))
    if "mac_tx" in dfs:
        print("  application-cells ETX: " + str(app_tx_etx))
    print("  Max. hop count during app: " + str(app_max_hop_count))

    print("stats (includes before App):")

    #outputStats(dfs, "mac_stats", "timing_err", "max", "Missed TSCH timings")
    #outputStats(dfs, "mac_stats", "hack_mismatch", "max", "Hack mismatch")
    #outputStats(dfs, "mac_stats", "hack_err", "max", "Hack errors")
    #outputStats(dfs, "mac_stats", "hack_deletions", "max", "Hack deleted packets")

    # Output relevant metrics
    outputStats(dfs, "packets", "pdr", "mean", "Round-trip PDR (%)")
    outputStats(dfs, "packets", "latency", "mean", "Latency mean (s)")
    outputStats(dfs, "packets", "latency", "max", "Latency max (s)")
    #outputStats(dfs, "queue", "queue_fill", "mean", "Queue fill")
    #outputStats(dfs, "app_parent_switch", "app_parent_switch", "count", "Parent switch during application")

    # outputStats(dfs, "energest", "duty_cycle", "mean", "Radio duty cycle (%)")
    #outputStats(dfs, "rpl_stats", "rank", "mean", "RPL rank (ETX-128)")
    outputStats(dfs, "rpl_stats", "hop_count", "max", "Hop count max")
    #outputStats(dfs, "rpl_stats", "hop_count", "min", "Hop count min")
    #outputStats(dfs, "rpl_stats", "hop_count", "mean", "Hop count mean")
    outputStats(dfs, "switches", "pswitch", "count", "RPL parent switches (#)")
    #outputStats(dfs, "dag_inits", "event", "count", "RPL joining DAG (#)")
    #outputStats(dfs, "rpl_stats", "trickle", "mean", "RPL Trickle period (min)")

    outputStats(dfs, "DIS", "message", "count", "RPL DIS sent (#)", "rpl-dis")
    outputStats(dfs, "unicast-DIO", "message", "count", "RPL uDIO sent (#)", "rpl-udio")
    outputStats(dfs, "multicast-DIO", "message", "count", "RPL mDIO sent (#)", "rpl-mdio")
    outputStats(dfs, "DAO", "message", "count", "RPL DAO sent (#)", "rpl-dao")
    outputStats(dfs, "DAO-ACK", "message", "count", "RPL DAO-ACK sent (#)", "rpl-daoack")

    #outputStats(dfs, "topology", "hops", "mean", "RPL hop count (#)")
    #outputStats(dfs, "topology", "children", "mean", "RPL children count (#)")

    outputStats(dfs, "mac_tx", "retransmissions", "sum", "Total retransmission")
    outputStats(dfs, "rpl_stats", "nbr_count", "max", "Max. neighbor count")

    # All dfs for this run
    return dfs, meta

# Inspired by http://www.randalolson.com/2012/06/26/using-pandas-dataframes/
# Parses all logs in directory into a dict of DFs
def parse_logs_dir(directory, app_warmup, has_spatial, num_nodes):
    directory = directory.rstrip('/') + "/*"

    # A dictionary of metrics containing dictionaries of DF from each run
    all_runs_dfs = defaultdict(dict)

    # Metadata about the scenario
    scenario_metadata = []

    # Iterate all folders containing different runs in the directory
    # Sorting to keep the order of runs (run00, run01, etc.)
    # Order of runs impacts statistical independence tests
    for folder in sorted(glob.glob(directory)):

        # Delete any existing parsed data (.csvs)
        for csv_file in glob.glob(folder + "/*.csv"):
            os.remove(csv_file)

        # Iterate and parse all log files in the folder
        # We have only one file pr run at the moment, but this might change
        for logfile in glob.glob(folder + "/" + SCRIPT_LOG_PATTERN):
            name_of_run = os.path.basename(folder)

            print("Parsing " + logfile)

            run_dfs, meta = \
                parse_logfile(logfile, app_warmup, has_spatial, num_nodes,
                              logging.getLogger() == logging.INFO)

            # Metadata
            run_metadata = {"name": name_of_run}
            run_metadata.update(meta)
            scenario_metadata.append(run_metadata)

            if meta["result"] == "spatial":
                print("Skipped " + name_of_run + ": Lacking spatial reuse!")
                continue
            elif meta["result"] == "switch":
                print("Skipped " + name_of_run + ": Parent switch during app!")
                continue
            elif meta["result"] != "ok":
                print("Unexpected situation: " + meta["result"] +
                      " in " + name_of_run + "!")
                continue

            for df_name in run_dfs:
                # Add this DF to the dictionary of DFs
                all_runs_dfs[df_name][name_of_run] = run_dfs[df_name]
                # Save as CSV
                csv_name = str(Path(logfile).parent) + "/" + df_name + ".csv"
                run_dfs[df_name].to_csv(csv_name)

    # Make DF from the metadata
    scenario_meta_df = pd.DataFrame(scenario_metadata)
    scenario_meta_df = scenario_meta_df.set_index("name")

    total_runs = len(scenario_meta_df)
    parsed_runs_df = scenario_meta_df[scenario_meta_df["result"] == "ok"]
    parsed_runs = len(parsed_runs_df)
    skipped_runs_spatial = \
        len(scenario_meta_df[scenario_meta_df["result"] == "spatial"])
    skipped_runs_switch = \
        len(scenario_meta_df[scenario_meta_df["result"] == "switch"])
    skipped_runs_error = \
        len(scenario_meta_df[scenario_meta_df["result"] != "ok"]) - \
            skipped_runs_spatial - skipped_runs_switch
    converged_runs = \
        len(parsed_runs_df[parsed_runs_df["parent_switch_app"] == 0])

    print("Parsed " + str(parsed_runs) + " out of " + str(total_runs))
    print("Skips due to spatial: " + str(skipped_runs_spatial) +
          ", parent switch: " + str(skipped_runs_switch) +
          ", errors: " + str(skipped_runs_error))
    print("Converged: " + str(converged_runs) + " out of " + str(parsed_runs))
    return scenario_meta_df, all_runs_dfs

def parse_logs_scenario(scenario_dir, scenario_name, app_warmup,
                        has_spatial, num_nodes):
    print("\n\nNow parsing scenario " + scenario_name)
    scenario_meta_df, dfs = parse_logs_dir(scenario_dir, app_warmup,
                                           has_spatial, num_nodes)
    print(scenario_meta_df)
    print("Done parsing scenario " + scenario_name + "\n\n")
    return scenario_meta_df, dfs

def number_of_nodes_in_scenario(scenario):
    # Ugly heuristic to find number of nodes in config
    # String of "nodes" is e.g. "358+356+354+351+348+346"
    # Note, only testbed supported
    if "nodes" in scenario:
        return scenario["nodes"].count('+') + 1
    else:
        return 0

def parse_logs_scenarios(scenarios, quiet=False):
    # Stop output. This solution is a mess and I dont understand it. TODO
    global print
    print = logging.info
    if quiet:
        print("Getting stats for scenarios in quiet mode")
    logging.basicConfig(level=logging.WARNING if quiet else logging.INFO,
                    format="%(message)s")

    for scenario in scenarios:
        num_nodes = number_of_nodes_in_scenario(scenario)
        scenario_meta_df, raw_dfs = parse_logs_scenario(scenario['path'],
                                      scenario['name'],
                                      int(scenario['app_warmup']),
                                      scenario['has_spatial'],
                                      num_nodes)

        scenario["meta_df"] = scenario_meta_df
        # Add the raw DFs to the scenario dict in the scenarios list
        scenario["raw_dfs"] = {}
        for df_name in raw_dfs:
            metric_df_name = "raw_" + df_name + "_dfs"
            scenario["raw_dfs"][metric_df_name] = raw_dfs[df_name]
