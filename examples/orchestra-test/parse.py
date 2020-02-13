#!/usr/bin/env python

# From https://github.com/contiki-ng/contiki-ng/blob/develop/examples/benchmarks/rpl-req-resp/parse.py

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
import matplotlib as mpl

pd.set_option('display.max_rows', 48)
pd.set_option('display.width', None)
pd.set_option('display.max_columns', None)

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
        return {'channel-utilization': 100.*tx/total }
    res = re.compile('Radio total\s*:\s*(\d*)/\s*(\d+)').match(log)
    if res:
        radio = float(res.group(1))
        total = float(res.group(2))
        return {'duty-cycle': 100.*radio/total }
    return None

def parseApp(log):
    res = re.compile('Sending (.+?) num (\d+) at ASN (\d+) tick (\d+) to 6G-(\d+)').match(log)
    if res:
        type = res.group(1)
        id = int(res.group(2))
        asn = int(res.group(3))
        tick = int(res.group(4))
        dest = int(res.group(5))
        return {'event': 'send', 'type': type, 'asn': asn, 'tick':tick, 'id': id, 'node': dest }
    res = re.compile('Received (.+?) num (\d+) oASN (\d+) oTick (\d+) at ASN (\d+) tick (\d+) from 6G-(\d+)').match(log)
    if res:
        type = res.group(1)
        id = int(res.group(2))
        oAsn = int(res.group(3))
        oTick = int(res.group(4))
        asn = int(res.group(5))
        tick = int(res.group(6))
        src = int(res.group(7))
        return {'event': 'recv', 'type': type, 'oAsn': oAsn, 'oTick': oTick, 'asn':asn, 'tick':tick, 'id': id, 'src': src }
    return None

def parseTSCH(log):
    res = re.compile('! overflow queue (\d+)\/(\d+) (\d+)\/(\d+)').match(log)
    if res:
        queue_fill = int(res.group(3))
        queue_size = int(res.group(4))
        return {'event': 'mac', 'type': 'overflow', 'queue_fill': queue_fill, 'queue_size': queue_size }
    
    res = re.compile('! can\'t send packet to LL-(\d+) with seqno (\d+), queue (\d+)\/(\d+) (\d+)\/(\d+)').match(log)
    if res:
        queue_fill = int(res.group(5))
        queue_size = int(res.group(6))
        return {'event': 'mac', 'type': 'drop', 'queue_fill': queue_fill, 'queue_size': queue_size }
    
    # Also catch broadcast drops
    res = re.compile('! can\'t send packet to LL-ffff with seqno (\d+), queue (\d+)\/(\d+) (\d+)\/(\d+)').match(log)
    if res:
        queue_fill = int(res.group(4))
        queue_size = int(res.group(5))
        return {'event': 'mac', 'type': 'drop', 'queue_fill': queue_fill, 'queue_size': queue_size }
    
    res = re.compile('send packet to LL-(\d+) with seqno (\d+), queue (\d+)\/(\d+) (\d+)\/(\d+)').match(log)
    if res:
        queue_fill = int(res.group(5))
        queue_size = int(res.group(6))
        return {'event': 'mac', 'type': 'send', 'queue_fill': queue_fill, 'queue_size': queue_size }
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
    print("Line did not match: " + line)
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
                #print("ret: " + str(ret))
                #print("entry: " + str(entry))
                #print(time)

                if(ret == None):
                    continue
                
                entry.update(ret)
                if(ret['event'] == 'send' and ret['type'] == 'data'):
                    # populate series of sent requests
                    entry['node'] = nodeid
                    entry['pdr'] = 0.
                   # print("appendingTX: " + str(entry))
                    arrays["packets"].append(entry)
                    if networkFormationTime == None:
                        networkFormationTime = time
                elif(ret['event'] == 'recv' and ret['type'] == 'data'):
                    # update sent request series with latency and PDR
                    #print("appendingRECV: " + str(entry))
                    txElement = [x for x in arrays["packets"] if x['event']=='send' and x['node']==ret['src'] and x['id']==ret['id']][0]
                    #print(time)
                    #print(txElement['timestamp'].seconds)
                    #print(txElement)
                    txElement['latency'] = time - txElement['timestamp'].seconds
                    txElement['pdr'] = 100.

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

                
        except: # typical exception: failed str conversion to int, due to lossy logs
            print("Exception: %s" %(str(sys.exc_info()[0])))
            continue


    # Remove last few packets -- might be in-flight when test stopped
    #arrays["packets"] = arrays["packets"][0:-10]
    # Not necessary since we send a fixed num packets and then idle for a while

    # Remove first packets such that we only get steady-state
    arrays["packets"] = arrays["packets"][100:]

    dfs = {}
    for key in arrays.keys():
        if(len(arrays[key]) > 0):
            df = DataFrame(arrays[key])
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

def main():
    if len(sys.argv) < 1:
        return
    else:
        file = sys.argv[1].rstrip('/')

    # Parse the original log
    dfs = doParse(file)

    print(dfs)

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
    #print("  duty-cycle: %.2f" %(dfs["energest"]["duty-cycle"].mean()))
    #print("  channel-utilization: %.2f" %(dfs["energest"]["channel-utilization"].mean()))
    print("  network-formation-time: %.2f" %(networkFormationTime))
    print("stats:")

    # Output relevant metrics
    outputStats(dfs, "packets", "pdr", "mean", "Round-trip PDR (%)")
    outputStats(dfs, "packets", "latency", "mean", "Round-trip latency (s)")
    outputStats(dfs, "queue", "queue_fill", "mean", "Queue fill")

    #outputStats(dfs, "energest", "duty-cycle", "mean", "Radio duty cycle (%)")
    #outputStats(dfs, "energest", "channel-utilization", "mean", "Channel utilization (%)")

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

main()
