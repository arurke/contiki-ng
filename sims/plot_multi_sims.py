# Here we do multi-sim plots, e.g. make plots from a orchestra and layered run
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D
# For plot to show up in IPython
%matplotlib inline

base_dir = "test-orchestra/executions/"
scenarios_csv = "scenarios_df.csv"
sim_9_node = {"name": "8_hop",
              "orch_dir": base_dir + "linear_9_20200519_1_orch60_used_v3/",
              "lay_dir": base_dir + "linear_9_20200519_0_lay60_used_v3/"}
sim_3_node =  {"name": "2_hop",
               "orch_dir": base_dir + "orchestra_test_20200518_3_orch60_used_v3/",
               "lay_dir": base_dir + "orchestra_test_20200518_4_lay60_used_v3/"
}

def plot_pdr_latency_multi_sims(df_orch, df_lay, name, save, title=False):
    fig_name = "pdr_latency_orch_lay_" + name
    fig_dir = base_dir

    fig, ax1 = plt.subplots(figsize=(6,2.5))
    #fig, ax1 = plt.subplots()
    
    # Markers
    orch_marker = 'o'
    lay_marker = '^'

    # Latency
    color = 'tab:red'
    ax1.set_xlabel('traffic intensity, as % of node schedule capacity')
    ax1.set_ylabel('latency (s)', color=color)
    test1 = ax1.plot(df_orch.index, df_orch["ss_latency_99.9"], color=color, marker=orch_marker)
    ax1.plot(df_lay.index, df_lay["ss_latency_99.9"], color=color, marker=lay_marker)
    ax1.set_ylim(bottom=0)
    ax1.tick_params(axis='y', labelcolor=color)
    
    # Arrow
    if name is "8_hop":
        ax1.arrow(2,20,-1,0, color=color, head_width=3.5, head_length=0.5)
    else:
        ax1.arrow(1.3,5.5,-1,0, color=color, head_width=0.7, head_length=0.5)

    # Loss
    # TODO naming of PDR is quite messed up. pdr_mean means CI of percentile of mean
    # Mean is the only thing that makes sense with pdr since values are either 100 or 0.
    ax2 = ax1.twinx()  # instantiate a second axes that shares the same x-axis
    color = 'tab:blue'
    ax2.set_ylabel('packet delivery ratio (%)', color=color)  # we already handled the x-label with ax1
    ax2.plot(df_orch.index, df_orch.ss_pdr_mean, color=color, marker=orch_marker)
    ax2.plot(df_lay.index, df_lay.ss_pdr_mean, color=color, marker=lay_marker)
    ax2.set_ylim(bottom=0, top=105)
    ax2.tick_params(axis='y', labelcolor=color)
    
    # Arrow
    if name is "8_hop":
        ax2.arrow(7.7,25,1,0, color=color, head_width=3.5, head_length=0.5)
    else:
        ax2.arrow(7.7,35,1,0, color=color, head_width=3.5, head_length=0.5)
    
    # Legend
    markers = [Line2D([0], [0], marker=orch_marker, color='w', markersize=8, markerfacecolor="black"),
                Line2D([0], [0], marker=lay_marker, color='w', markersize=10, markerfacecolor="black")]
    
    if name is "2_hop":
        legend_location = "center left"
    else:
        legend_location = "center right"
    
    plt.legend(markers, ["Orchestra", "Layered"], loc=legend_location)
    
    fig.tight_layout()  # otherwise the right y-label is slightly clipped
    if title:
        plt.title(fig_name)
    fig_path = fig_dir + fig_name + '.pdf'
    if save:
        plt.savefig(fig_path, bbox_inches='tight')
        print("Made figure", fig_path)
    else:
        plt.show()
    plt.close()

def plot_duty_cycle_multi_sims(df_orch, df_lay, name, save, title=False):
    fig_name = "duty_cycle_orch_lay_" + name
    fig_dir = base_dir

    fig, ax1 = plt.subplots(figsize=(6,2))
    
    # Markers
    orch_marker = 'o'
    lay_marker = '^'
    
    # Duty cycle
    plt.plot(df_orch.index, df_orch["ss_duty_cycle_mean"], 
             marker=orch_marker, label="Orchestra")
    plt.plot(df_lay.index, df_lay["ss_duty_cycle_mean"], 
             marker=lay_marker, label="Layered")

    # Channel utilization
    #color = 'tab:blue'
    #plt.plot(scenarios_df.index, scenarios_df["ss_channel_utilization_50"], color=color,
    #         marker='o', label="Channel utilization")

    fig.tight_layout()  # otherwise the right y-label is slightly clipped
    plt.xlabel('traffic intensity, as % of node schedule capacity')
    plt.ylabel('(%)')
    if name is "2_hop":
        ax1.set_ylim(bottom=1, top=2)
    else:
        ax1.set_ylim(bottom=0)
    plt.legend()
    if title:
        plt.title(fig_name)
    fig_path = fig_dir + fig_name + '.pdf'
    if save:
        plt.savefig(fig_path, bbox_inches='tight')
        print("Made figure", fig_path)
    else:
        plt.show()
    plt.close()

def plot_duty_cycle_per_pdr_multi_sims(df_orch, df_lay, name, save, title=False):
    fig_name = "duty_cycle_per_pdr_orch_lay_" + name
    fig_dir = base_dir

    fig, ax1 = plt.subplots(figsize=(6,2))
    
    # Markers
    orch_marker = 'o'
    lay_marker = '^'
    
    # Duty cycle
    plt.plot(df_orch.index, df_orch["ss_duty_cycle_mean"] / df_orch["ss_pdr_mean"], 
             marker=orch_marker, label="Orchestra DC per PDR")
    plt.plot(df_lay.index, df_lay["ss_duty_cycle_mean"]  / df_lay["ss_pdr_mean"], 
             marker=lay_marker, label="Layered DC per PDR")

    #plt.figure(figsize=(30,10))
    fig.tight_layout()  # otherwise the right y-label is slightly clipped
    plt.xlabel('traffic intensity, as % of node schedule capacity')
    plt.ylabel('(%)')
    ax1.set_ylim(bottom=0)
    plt.legend()
    if title:
        plt.title(fig_name)
    fig_path = fig_dir + fig_name + '.pdf'
    if save:
        plt.savefig(fig_path, bbox_inches='tight')
        print("Made figure", fig_path)
    else:
        plt.show()
    plt.close()


def read_csvs(sim):
    df_orch = pd.read_csv(sim["orch_dir"] + scenarios_csv)
    df_orch.set_index("scenario", inplace = True)
    df_lay = pd.read_csv(sim["lay_dir"] + scenarios_csv)
    df_lay.set_index("scenario", inplace = True)
    return df_orch, df_lay
    
# Select sim    
sim = sim_3_node
#sim = sim_9_node

df_orch, df_lay = read_csvs(sim)

#print(df_orch)

#plot_duty_cycle_per_pdr_multi_sims(df_orch, df_lay, sim["name"], save=True)
#plot_pdr_latency_multi_sims(df_orch, df_lay, sim["name"], save=True)
plot_duty_cycle_multi_sims(df_orch, df_lay, sim["name"], save=True)
