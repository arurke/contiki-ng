import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
# For plot to show up in IPython
#%matplotlib inline

#df_packets = pd.read_csv('outP.csv')
#df_queue = pd.read_csv('outQ.csv')

plt.rcParams.update({'font.size': 8})

def plot_queue_util(scenarios_df, execution_dir, title=False):
    # Get a list of integers of equal length as number of scenarios
    # To be used to position the bars
    x = np.arange(len(scenarios_df.index))
    width = 0.35 # width of bars

    fig, ax = plt.subplots()
    p1 = ax.bar(x - width/2, scenarios_df.ss2_queue_fill_mean, width, label='Node 1')
    p2 = ax.bar(x + width/2, scenarios_df.ss3_queue_fill_mean, width, label='Node 2')

    ax.legend()
    ax.set_xticks(x)
    ax.set_xticklabels(scenarios_df.index)
    ax.autoscale_view()
    ax.set_ylim(top=100)
    plt.xlabel('traffic intensity, as % of node schedule capacity')
    plt.ylabel('Queue utilization (%)')
    fig.tight_layout()

    fig_name = "queue_util_all_scenarios"
    if title:
        plt.title(fig_name)
    fig_dir = execution_dir
    fig_path = fig_dir + fig_name + '.pdf'
    plt.savefig(fig_path, bbox_inches='tight')
    plt.close()
    print("Made figure", fig_path)

def plot_duty_cycle(scenarios_df, execution_dir, title=False):
    # Duty cycle
    color = 'tab:red'
    plt.plot(scenarios_df.index, scenarios_df["ss_duty_cycle_mean"], color=color,
             marker='o', label="Duty cycle")

    # Channel utilization
    color = 'tab:blue'
    plt.plot(scenarios_df.index, scenarios_df["ss_channel_utilization_mean"], color=color,
             marker='o', label="Channel utilization")

    plt.tight_layout()  # otherwise the right y-label is slightly clipped
    plt.xlabel('traffic intensity, as % of node schedule capacity')
    plt.ylabel('(%)')
    plt.legend()
    fig_name = "duty_cycle_all_scenarios"
    if title:
        plt.title(fig_name)
    fig_dir = execution_dir
    fig_path = fig_dir + fig_name + '.pdf'
    plt.savefig(fig_path, bbox_inches='tight')
    plt.close()
    print("Made figure", fig_path)

def plot_pdr_latency(scenarios_df, execution_dir, title=False):
    pdr_df = scenarios_df
    latency_df = scenarios_df
    fig_name = "pdr_latency_all_scenarios"
    fig_dir = execution_dir

    fig, ax1 = plt.subplots()

    # Latency
    color = 'tab:red'
    ax1.set_xlabel('traffic intensity, as % of node schedule capacity')
    ax1.set_ylabel('Latency (s)', color=color)
    ax1.plot(latency_df.index, latency_df["ss_latency_99.9"], color=color, marker='o')
    ax1.set_ylim(bottom=0)
    #ax1.plot(latency_df.index, latency_df.ss_latency_maximum, color=color, marker='o')
    ax1.tick_params(axis='y', labelcolor=color)

    # Loss
    # TODO naming of PDR is quite messed up. pdr_mean means CI of percentile of mean
    # Mean is the only thing that makes sense with pdr since values are either 100 or 0.
    ax2 = ax1.twinx()  # instantiate a second axes that shares the same x-axis
    color = 'tab:blue'
    ax2.set_ylabel('packet delivery ratio (%)', color=color)  # we already handled the x-label with ax1
    ax2.plot(pdr_df.index, pdr_df.ss_pdr_mean, color=color, marker='o')
    ax2.set_ylim(bottom=0)
    ax2.tick_params(axis='y', labelcolor=color)

    fig.tight_layout()  # otherwise the right y-label is slightly clipped
    if title:
        plt.title(fig_name)
    fig_path = fig_dir + fig_name + '.pdf'
    plt.savefig(fig_path, bbox_inches='tight')
    plt.close()
    print("Made figure", fig_path)

def plot_time_series(scenario, nodeid, run_id, skip_end = 0):
    if run_id not in scenario['raw_packet_dfs']:
        return

    # Copy the DF so that we can make changes without messing up the original
    df = scenario['raw_packet_dfs'][run_id].copy()
    if skip_end != 0:
        df = df[:-skip_end]

    # Convert timestamp from string to Datetime. (only needed if reading from csv)
    # This is needed because the strings are not interpreted as time,
    # so a plot will just
    # plot two sub-series after each other instead of at the correct time
    # (I don't fully understand it)
    # but we also need this so that we can do arithmetics on it (below)
    #df.index = pd.to_datetime(df.index)

    # Switch timestamp from absolute to relative to first packet and
    # convert to float (i.e. seconds since t0) using total_seconds()
    df.index = [(index - df.index[0]).total_seconds() for index in df.index]

    # Get only the interesting node
    if nodeid != 0:
        df = df[df.node == nodeid]

    # Latency
    # Remove any rows containig Nan (dropped packets don't have latency values)
    # Lines in line plots are not drawn between values and Nan-values
    df_latency = df.copy()
    df_latency = df_latency.dropna()

    fig, ax1 = plt.subplots()

    color = 'tab:red'
    ax1.set_xlabel('time (s)')
    ax1.set_ylabel('latency (s)', color=color)
    ax1.plot(df_latency.index, df_latency.latency, color=color, marker='o')
    ax1.tick_params(axis='y', labelcolor=color)

    # Loss
    # Add new column which counts losses
    df_loss = df.copy()
    df_loss['loss_counter'] = (df_loss['pdr'] == 0).cumsum()

    ax2 = ax1.twinx()  # instantiate a second axes that shares the same x-axis
    color = 'tab:blue'
    ax2.set_ylabel('cumulative packets lost', color=color)  # we already handled the x-label with ax1
    ax2.plot(df_loss.index, df_loss.loss_counter, color=color)
    ax2.tick_params(axis='y', labelcolor=color)

    fig.tight_layout()  # otherwise the right y-label is slightly clipped
    fig_name = 'timeseries_node' + str(nodeid) + '_' + scenario['name'] + \
        '_' + run_id
    plt.title(fig_name)
    fig_path = scenario['path'] + fig_name + '.pdf'
    plt.savefig(fig_path, bbox_inches='tight')
    plt.close()
    print("Made figure", fig_path)


    # Queue fill
    queue_df = scenario['raw_queue_dfs'][run_id].copy()

    # Switch timestamp from absolute to relative to first packet and
    # convert to float (i.e. seconds since t0) using total_seconds()
    queue_df.index = [(index - queue_df.index[0]).total_seconds() for index in queue_df.index]

    # Get only the interesting node
    if nodeid != 0:
        queue_df = queue_df[queue_df.node == nodeid]

    # Remove any rows containig Nan
    # Lines in line plots are not drawn between values and Nan-values
    queue_df = queue_df[queue_df['queue_fill'].notna()].copy()

    color = 'tab:red'
    plt.xlabel('time (s)')
    plt.ylabel('(%)')
    #plt.legend()
    fig_name = 'queue_fill_timeseries_node' + str(nodeid) + '_' + scenario['name'] + \
        '_' + run_id
    plt.title(fig_name)
    plt.plot(queue_df.index,
             queue_df['queue_fill'],
             color=color,
             marker='o', label="Queue fill")
    fig_path = scenario['path'] + fig_name + '.pdf'
    plt.savefig(fig_path, bbox_inches='tight')
    plt.close()
    print("Made figure", fig_path)


    # Duty cycle
    dc_df = scenario['raw_energest_dfs'][run_id].copy()

    # Switch timestamp from absolute to relative to first packet and
    # convert to float (i.e. seconds since t0) using total_seconds()
    dc_df.index = [(index - dc_df.index[0]).total_seconds() for index in dc_df.index]

    # Get only the interesting node
    if nodeid != 0:
        dc_df = dc_df[dc_df.node == nodeid]

    # Remove any rows containig Nan
    # Lines in line plots are not drawn between values and Nan-values
    duty_cycle_df = dc_df[dc_df['duty_cycle'].notna()].copy()
    ch_util_df = dc_df[dc_df['channel_utilization'].notna()].copy()

    color = 'tab:red'
    plt.plot(duty_cycle_df.index,
             duty_cycle_df['duty_cycle'],
             color=color,
             marker='o', label="Duty cycle")

    # Channel utilization
    color = 'tab:blue'
    plt.plot(ch_util_df.index,
             ch_util_df['channel_utilization'],
             color=color,
             marker='o', label="Channel utilization")

    #fig.tight_layout()  # otherwise the right y-label is slightly clipped
    plt.xlabel('time (s)')
    plt.ylabel('(%)')
    plt.legend()
    fig_name = 'duty_cycle_timeseries_node' + str(nodeid) + '_' + scenario['name'] + \
        '_' + run_id
    plt.title(fig_name)
    fig_path = scenario['path'] + fig_name + '.pdf'
    plt.savefig(fig_path, bbox_inches='tight')
    plt.close()
    print("Made figure", fig_path)
