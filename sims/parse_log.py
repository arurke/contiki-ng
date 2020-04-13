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

networkFormationTime = None
parents = {}

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
    global parents
    if not child in parents:
        parents[child] = {}
    if not parent in parents:
        parents[parent] = None
    parents[child] = parent

def parseRPL(log):
    res = re.compile('.*? rank (\d*).*?dioint (\d*).*?nbr count (\d*)').match(log)
    if res:
        rank = int(res.group(1))
        trickle = (2**int(res.group(2)))/(60*1000.)
        nbrCount = int(res.group(3))
        return {'event': 'rank', 'rank': rank, 'trickle': trickle }
    res = re.compile('parent switch: .*? -> .*?-(\d*)$').match(log)
    if res:
        parent = int(res.group(1))
        return {'event': 'switch', 'pswitch': parent }
    res = re.compile('sending a (.+?) ').match(log)
    if res:
        message = res.group(1)
        return {'event': 'sending', 'message': message }
    res = re.compile('links: 6G-(\d+)\s*to 6G-(\d+)').match(log)
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
        return {'channel_utilization': 100.*tx/total }

    res = re.compile('Radio total\s*:\s*(\d*)/\s*(\d+)').match(log)
    if res:
        radio = float(res.group(1))
        total = float(res.group(2))
        return {'duty_cycle': 100.*radio/total }
    return None

def parseApp(log):
    res = re.compile('TX (.+?) num (\d+) tick (\d+) to 6G-([0-9a-fA-F]+)').match(log)
    if res:
        type = res.group(1)
        id = int(res.group(2))
        tick = int(res.group(3))
        dest = int(res.group(4), 16)
        return {'event': 'send', 'type': type, 'tick':tick, 'id': id, 'node': dest }

    res = re.compile('RX (.+?) num (\d+) oTick (\d+) tick (\d+) from 6G-([0-9a-fA-F]+)').match(log)
    if res:
        type = res.group(1)
        id = int(res.group(2))
        oTick = int(res.group(3))
        tick = int(res.group(4))
        src = int(res.group(5), 16)
        return {'event': 'recv', 'type': type, 'oTick': oTick, 'tick':tick, 'id': id, 'src': src }
    return None

def parseTSCH(log):
    res = re.compile('! overflow queue (\d+)\/(\d+) (\d+)\/(\d+)').match(log)
    if res:
        queue_num = int(res.group(3))
        queue_size = int(res.group(4))
        queue_fill = (queue_num / queue_size) * 100
        return {'event': 'mac', 'type': 'overflow', 'queue_num': queue_num, 'queue_size': queue_size, 'queue_fill':queue_fill}
    
    res = re.compile('! can\'t send packet to LL-(\d+) with seqno (\d+), queue (\d+)\/(\d+) (\d+)\/(\d+)').match(log)
    if res:
        queue_num = int(res.group(5))
        queue_size = int(res.group(6))
        queue_fill = (queue_num / queue_size) * 100
        return {'event': 'mac', 'type': 'drop', 'queue_num': queue_num, 'queue_size': queue_size, 'queue_fill':queue_fill}
    
    # Also catch broadcast drops
    res = re.compile('! can\'t send packet to LL-ffff with seqno (\d+), queue (\d+)\/(\d+) (\d+)\/(\d+)').match(log)
    if res:
        queue_num = int(res.group(4))
        queue_size = int(res.group(5))
        queue_fill = (queue_num / queue_size) * 100
        return {'event': 'mac', 'type': 'drop', 'queue_num': queue_num, 'queue_size': queue_size, 'queue_fill':queue_fill}
    
    res = re.compile('TX to LL-(\d+) seqno (\d+), queue (\d+)\/(\d+) (\d+)\/(\d+)').match(log)
    if res:
        queue_num = int(res.group(5))
        queue_size = int(res.group(6))
        queue_fill = (queue_num / queue_size) * 100
        return {'event': 'mac', 'type': 'send', 'queue_num': queue_num, 'queue_size': queue_size, 'queue_fill':queue_fill}
    return None

def parseLine(line):
    #print("Parsing line: " + line)
    res = re.compile('\s*([.\d]+)\tID:(\d+)\t\[(.*?):(.*?)\](.*)$').match(line)
    if res:
        time = float(res.group(1)) / 1000
        nodeid = int(res.group(2))
        level = res.group(3).strip()
        module = res.group(4).strip()
        log = res.group(5).strip()
        return time, nodeid, level, module, log

    print("Unknown line: " + line.rstrip())
    return None, None, None, None, None

def doParse(file):
    global networkFormationTime

    time = None
    lastPrintedTime = 0

    arrays = {
        "packets": [],
        "energest": [],
        "ranks": [],
        "trickle": [],
        "switches": [],
        "DAGinits": [],
        "topology": [],
        "queue": [],
    }

#    print("\nProcessing %s" %(file))
    # Filter out non-printable chars from log file
    #os.system("cat %s | tr -dc '[:print:]\n\t' | sponge %s" %(file, file))
    for line in open(file, 'r').readlines():
        # match time, id, module, log; The common format for all log lines
        if "TEST FAILED" in line:
            print("SIMULATION FAILED!")
            return -1

        time, nodeid, level, module, log = parseLine(line)

        if time == None:
            # malformed line
            continue
        if time - lastPrintedTime >= 60:
#            print("%u, "%(time / 60),end='', flush=True)
            lastPrintedTime = time

        entry = {
            "timestamp": timedelta(seconds=time),
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
                    entry['node'] = nodeid
                    entry['pdr'] = 0.
                   #print("appendingTX: " + str(entry))
                    arrays["packets"].append(entry)
                    if networkFormationTime == None:
                        networkFormationTime = time
                elif(ret['event'] == 'recv' and ret['type'] == 'data'):
                    # Update sent request series with latency and PDR
                    # First find the row
                    txElement = [x for x in arrays["packets"] if x['event']=='send' and x['node']==ret['src'] and x['id']==ret['id']][0]

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
                if(ret['event'] == 'rank'):
                    arrays["ranks"].append(entry)
                    arrays["trickle"].append(entry)
                elif(ret['event'] == 'switch'):
                    arrays["switches"].append(entry)
                elif(ret['event'] == 'DAGinit'):
                    arrays["DAGinits"].append(entry)
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
                arrays["queue"].append(entry)

                
        except Exception as e: # typical exception: failed str conversion to int, due to lossy logs
            print("Exception: %s" %(str(sys.exc_info()[0])))
            print(str(e))
            continue


    # Remove last few packets -- might be in-flight when test stopped
    #arrays["packets"] = arrays["packets"][0:-10]
    # Not necessary since we send a fixed num packets and then idle for a while

    # Remove first packets such that we only get steady-state
    #arrays["packets"] = arrays["packets"][100:]

    dfs = {}
    for key in arrays.keys():
        if(len(arrays[key]) > 0):
            df = DataFrame(arrays[key])
            #print("DF is: ", df)
            print("New key: " + key)
            dfs[key] = df.set_index("timestamp")

    return dfs

def outputStats(dfs, key, metric, agg, name, metricLabel = None):
    if not key in dfs:
        return

    df = dfs[key]
    perNode = getattr(df.groupby("node")[metric], agg)()
    perTime = getattr(df.groupby([pd.Grouper(freq="2Min")])[metric], agg)()

    print("  %s:" %(metricLabel if metricLabel != None else metric))
    print("    name: %s" %(name))
    print("    per-node:")
    print("      x: [%s]" %(", ".join(["%u"%x for x in sort(df.node.unique())])))
    print("      y: [%s]" %(', '.join(["%.4f"%(x) for x in perNode])))
    print("    per-time:")
    print("      x: [%s]" %(", ".join(["%u"%x for x in range(0, 2*len(df.groupby([pd.Grouper(freq="2Min")]).mean().index), 2)])))
    print("      y: [%s]" %(', '.join(["%.4f"%(x) for x in perTime]).replace("nan", "null")))

def parse_logfile(file, quiet = False):
    # Stop output. This solution is a mess and I dont understand it. TODO
    global print
    print = logging.info
    logging.basicConfig(level=logging.WARNING if quiet else logging.INFO,
                    format="%(message)s")

    dfs = doParse(file)

    #print(dfs)

    if len(dfs) == 0:
        return

    packets_sent = dfs["packets"]["pdr"].count();
    # A packet which is not received is stored with PDR = 0
    packets_received = dfs["packets"]["pdr"].sum()/100
    
    
    # There are some rpoblems with the queue-stuff:
    # 1. All packets are counted, thus the queue overflow is larger than
    #    lost applicaiton packets
    # 2. The queue size is onluy printed when sending or sending failed
    #    TODO Add a print at every manipulatio of queue to have a proper stat.
    # Needed?
    
    # Drops (This does not take transmissions failures into account)
    drops = dfs["queue"][dfs["queue"]["type"] == "drop"]["type"].count()
    
    # Queue overflow
    overflows = dfs["queue"][dfs["queue"]["type"] == "overflow"]["type"].count()
    
    #seriesObj = dfs["queue"].apply(lambda x: True if x["type"] == "drop" else False, axis = 1)
    #numRows = len(seriesObj[seriesObj == True].index)
    
    print("global-stats:")
    print("  pdr: %.4f" %(dfs["packets"]["pdr"].mean()))
    print("  loss-rate: %.e" %(1-(dfs["packets"]["pdr"].mean()/100)))
    print("  packets-sent: %u" %(packets_sent))
    print("  packets-received: %u" %(packets_received))
    print("  packets-lost: %u" %(packets_sent - packets_received))
    print("  queue-fails %u" %(drops))
    print("  queue-overflow %u" %(overflows))
    
    print("  latency: %.4f" %(dfs["packets"]["latency"].mean()))
    print("  duty-cycle: %.2f" %(dfs["energest"]["duty_cycle"].mean()))
    print("  channel-utilization: %.2f" %(dfs["energest"]["channel_utilization"].mean()))
    print("  network-formation-time: %.2f" %(networkFormationTime))
    print("stats:")

    # Output relevant metrics
    outputStats(dfs, "packets", "pdr", "mean", "Round-trip PDR (%)")
    outputStats(dfs, "packets", "latency", "mean", "Round-trip latency (s)")
    outputStats(dfs, "queue", "queue_fill", "mean", "Queue fill")

    #outputStats(dfs, "energest", "duty_cycle", "mean", "Radio duty cycle (%)")
    #outputStats(dfs, "energest", "channel_utilization", "mean", "Channel utilization (%)")

    #outputStats(dfs, "ranks", "rank", "mean", "RPL rank (ETX-128)")
    #outputStats(dfs, "switches", "pswitch", "count", "RPL parent switches (#)")
    #outputStats(dfs, "DAGinits", "event", "count", "RPL joining DAG (#)")
    #outputStats(dfs, "trickle", "trickle", "mean", "RPL Trickle period (min)")

    #outputStats(dfs, "DIS", "message", "count", "RPL DIS sent (#)", "rpl-dis")
    #outputStats(dfs, "unicast-DIO", "message", "count", "RPL uDIO sent (#)", "rpl-udio")
    #outputStats(dfs, "multicast-DIO", "message", "count", "RPL mDIO sent (#)", "rpl-mdio")
    #outputStats(dfs, "DAO", "message", "count", "RPL DAO sent (#)", "rpl-dao")
    #outputStats(dfs, "DAO-ACK", "message", "count", "RPL DAO-ACK sent (#)", "rpl-daoack")

    #outputStats(dfs, "topology", "hops", "mean", "RPL hop count (#)")
    #outputStats(dfs, "topology", "children", "mean", "RPL children count (#)")
    
    #dfs["packets"].to_csv('outP.csv')
    #dfs["queue"].to_csv('outQ.csv')
    
    # Return the packet and queue DF
    return dfs["packets"], dfs["queue"], dfs["energest"]


# Inspired by http://www.randalolson.com/2012/06/26/using-pandas-dataframes/
# Parses all logs in directory into a dict of DFs
def parse_logs_dir(directory):
    directory = directory.rstrip('/') + "/*"
    dfs_packets = {}
    dfs_queue = {}
    dfs_energest = {}

    # Iterate all folders containing different runs in the directory
    for folder in glob.glob(directory):
        # Iterate and parse all log files in the folder
        # We have only one file pr run at the moment, but this might change
        for logfile in glob.glob(folder + "/" + SCRIPT_LOG_PATTERN):
            name_of_run = os.path.basename(folder)
            print("Parsing " + logfile)

            # Parse log-files
            dfs_packets[name_of_run], dfs_queue[name_of_run], dfs_energest[name_of_run] = \
                parse_logfile(logfile, logging.getLogger() == logging.INFO)

            # Save to CSV files
            packets_csv = str(Path(logfile).parent) + "/packets_" + name_of_run + ".csv"
            queue_csv = str(Path(logfile).parent) + "/queue_" + name_of_run + ".csv"
            energest_csv = str(Path(logfile).parent) + "/energest_" + name_of_run + ".csv"
            dfs_packets[name_of_run].to_csv(packets_csv)
            dfs_queue[name_of_run].to_csv(queue_csv)
            dfs_energest[name_of_run].to_csv(energest_csv)

    return dfs_packets, dfs_queue, dfs_energest

def parse_logs_scenario(scenario_dir, scenario_name):
    runs_raw_packet_dfs, runs_raw_queue_dfs, runs_raw_energest = \
        parse_logs_dir(scenario_dir)

    print("Parsed runs: " + str(runs_raw_packet_dfs.keys()))
    return runs_raw_packet_dfs, runs_raw_queue_dfs, runs_raw_energest

def parse_logs_scenarios(scenarios, quiet = False):
    # Stop output. This solution is a mess and I dont understand it. TODO
    global print
    print = logging.info
    if quiet:
        print("Getting stats for scenarios in quiet mode")
    logging.basicConfig(level=logging.WARNING if quiet else logging.INFO,
                    format="%(message)s")

    for scenario in scenarios:
        scenario_raw_packet_dfs, scenario_raw_queue_dfs, scenario_raw_energest_dfs = \
            parse_logs_scenario(scenario['path'], scenario['name'])

        # Add the raw DFs to the scenario dict in the scenarios list
        scenario['raw_packet_dfs'] = scenario_raw_packet_dfs
        scenario['raw_queue_dfs'] = scenario_raw_queue_dfs
        scenario['raw_energest_dfs'] = scenario_raw_energest_dfs
