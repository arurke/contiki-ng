import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from dataclasses import dataclass
import itertools
import copy
# For plot to show up in IPython
#%matplotlib inline

#df_packets = pd.read_csv('outP.csv')
#df_queue = pd.read_csv('outQ.csv')

plt.rcParams.update({'font.size': 10})

# Must match that in stats_triscale. TODO
DEFAULT_PERC = 50
ADHOC_PERC = 80

def percentile_to_integer(percentile):
    if isinstance(percentile, str):
        if percentile == "adhoc":
            percentile = ADHOC_PERC
        elif percentile == "default":
            percentile = DEFAULT_PERC
        else:
            print("Error!", percentile)
            return None
    return percentile

def make_kpi_field_percentile(prefix, postfix, bound, percentile):
    if bound == 'upper':
        corrected_perc = percentile
    else:
        corrected_perc = 100 - percentile

    return prefix + "_perc" + str(corrected_perc) + "_conf95_" + postfix

def make_kpi_field(prefix, postfix, percentile, bound):
    return make_kpi_field_percentile(prefix, postfix, bound,
                                     percentile_to_integer(percentile))

# For backwards compatibility, this defaults to adhoc percentile
def make_kpi_name(prefix, postfix, bound):
    adhoc_percentile = 70
    return make_kpi_field_internal(prefix, postfix, bound, adhoc_percentile)

def make_spatial_kpi_name(prefix, postfix):
    return prefix + "_perc30_conf95_" + postfix # This does not work for non-median values

def plot_etx_details(scenarios_df, plot_dir, title=False):
    return
    # Data
    spatial_reuse_row = scenarios_df.loc["spatial_reuse"]
    no_spatial_reuse_row = scenarios_df.loc["no_spatial_reuse"]

    # Setup the dataframe
    categories = ['Spatial reuse', 'No spatial reuse']

    converged_data_max = [
        spatial_reuse_row[make_kpi_name('converged_app_cell_etx_absolute_spatial', 'upper', 'lower')],
        no_spatial_reuse_row[make_kpi_name('converged_mac_app_tx_etx_absolute', 'upper', 'lower')]]
    converged_data_min = [
        spatial_reuse_row[make_kpi_name('converged_app_cell_etx_absolute_spatial', 'lower', 'lower')],
        no_spatial_reuse_row[make_kpi_name('converged_mac_app_tx_etx_absolute', 'lower', 'lower')]]
    converged_data_mean = [
        (converged_data_max[0] + converged_data_min[0]) / 2,
        (converged_data_max[1] + converged_data_min[1]) / 2]

    all_data_max = [
        spatial_reuse_row[make_kpi_name('app_cell_etx_absolute_spatial', 'upper', 'lower')],
        no_spatial_reuse_row[make_kpi_name('mac_app_tx_etx_absolute', 'upper', 'lower')]]
    all_data_min = [
        spatial_reuse_row[make_kpi_name('app_cell_etx_absolute_spatial','lower', 'lower')],
        no_spatial_reuse_row[make_kpi_name('mac_app_tx_etx_absolute', 'lower', 'lower')]]
    all_data_mean = [
        (all_data_max[0] + all_data_min[0]) / 2,
        (all_data_max[1] + all_data_min[1]) / 2]

    # the label locations
    x = np.arange(len(categories))

    # width of the bars
    width = 0.2

    fig, ax = plt.subplots()
    rects2 = ax.bar(x-width/2, all_data_mean, width, capsize=10,
                    yerr=[np.array(all_data_mean) - np.array(all_data_min),
                          np.array(all_data_max) - np.array(all_data_mean)],
                    label="All runs", color='green')
    rects1 = ax.bar(x+width/2, converged_data_mean, width, capsize=10,
                    yerr=[np.array(converged_data_mean) - np.array(converged_data_min),
                          np.array(converged_data_max) - np.array(converged_data_mean)],
                    label="Converged runs", color='red')

    # ax.bar_label would not work for some reason. So we found this online.
    for rect in itertools.chain(rects1, rects2):
        height = rect.get_height()
        ax.text(rect.get_x()+rect.get_width()/6, 1.0*height,
                '%.2f' % height,
                ha='center', va='bottom')

    ax.set_ylabel('ETX')
    ax.set_xticks(x)
    ax.set_xticklabels(categories)
    ax.legend()
    #ax.legend(loc='upper right')
    fig.tight_layout()

    fig_name = "etx_details"
    if title:
        plt.title(fig_name)
    fig_dir = plot_dir
    fig_path = fig_dir + fig_name + '.pdf'
    plt.savefig(fig_path, bbox_inches='tight')
    plt.close()
    print("Made figure", fig_path)


#scenarios = [{"name": "spatial_reuse", "desc": "With spatial reuse"},
#         {"name": "no_spatial_reuse", "desc": "Without spatial reuse"}]
#
#kpis = [{"field": "prr_mean", "name": "PRR", "bound": "lower"},
#        {"field": "pdr_mean", "name": "PDR", "bound": "lower"}]
def plot_compare_kpis(scenarios_df, scenarios_info, kpis,
                      name, plot_dir, title=False, special=False):

    @dataclass
    class DataPoint:
        lower: float
        upper: float

        @classmethod
        def from_row(cls, row, name, percentile, bound):
            lower = row[make_kpi_field(name, 'lower', percentile, bound)]
            upper = row[make_kpi_field(name, 'upper', percentile, bound)]
            return cls(lower, upper)

    #@dataclass
    #class DataPoint2:
    #    lower: float # Actual lower bound value
    #    upper: float # Actual upper  bound value
    #    value: float # Top of bar in plot
    #    error_lower: float # Lower error in plot
    #    error_upper: float # Upper error in plot
    #
    #    @classmethod
    #    def from_row(cls, row, kpi, bound):
    #        lower = row[make_spatial_kpi_name(kpi, 'lower')]
    #        upper = row[make_spatial_kpi_name(kpi, 'upper')]
    #        if kpi["bound"] == "upper":
    #            value = upper
    #            error_lower = upper - lower
    #            error_upper = 0
    #        else:
    #            value = lower
    #            error_lower = 0
    #            error_upper = upper - lower
    #        return cls(lower, upper, value, error_lower, error_upper)

    scenarios = copy.deepcopy(scenarios_info)

    for scenario in scenarios:
        row = scenarios_df.loc[scenario["name"]]
        kpis_data = []
        for kpi in kpis:

            datapoint = DataPoint.from_row(row, kpi["name"],
                                           kpi['percentile'], kpi["bound"])

            # A stupid ad-hoc handling for spatial reuse comparison
            # Needed because it requires comparing two different metrics
            # For spatial scenario, the prr_spatial_mean is used (prr of all spatial links)
            # While non-spatial uses the app_selected_cell_prr_mean
            # (prr of all links which had spatial traffic in earlier scenario).
            # TODO long-term solution is to change the input into this function
            if special:
                if scenario["name"] == "no_spatial_reuse":
                    if kpi["name"] == "spatial_cell_prr_mean":
                        datapoint = \
                            DataPoint.from_row(row, "selected_cell_prr_mean",
                                               kpi["percentile"], kpi["bound"])
                    if kpi["name"] == "converged_spatial_cell_prr_mean":
                        datapoint = \
                            DataPoint.from_row(row,
                                               "converged_selected_cell_prr_mean",
                                               kpi["percentile"], kpi["bound"])

            if kpi["bound"] == "upper":
                value = datapoint.upper
                error_lower = datapoint.upper - datapoint.lower
                error_upper = 0
            else:
                value = datapoint.lower
                error_lower = 0
                error_upper = datapoint.upper - datapoint.lower
            kpis_data.append({"name": kpi["name"],
                              "datapoint": datapoint,
                              "value": value,
                              "error_lower": error_lower,
                              "error_upper": error_upper})

        scenario["kpis_data"] = kpis_data

    #print(scenarios)

    # Make arrays of all lower and all upper KPIs per scenario
    for scenario in scenarios:
        scenario["values"] = []
        scenario["error_lowers"] = []
        scenario["error_uppers"] = []
        for kpi_data in scenario["kpis_data"]:
            scenario["values"].append(kpi_data["value"])
            scenario["error_lowers"].append(kpi_data["error_lower"])
            scenario["error_uppers"].append(kpi_data["error_upper"])

    kpi_list = []
    for kpi in kpis:
        kpi_list.append(kpi["desc"])

    # the label locations
    x = np.arange(len(kpi_list))

    # width of the bars
    width = 0.3

    fig, ax = plt.subplots()
    #ax.set_ylim([50, 120])

    rects = []
    x_pos = []

    # I can't be bothered to find something better here
    if len(scenarios) == 1:
        x_pos = [1]
    if len(scenarios) == 2:
        x_pos = [x - width/2, x + width/2]
    if len(scenarios) == 3:
        x_pos = [x - width, x, x + width]

    for idx, scenario in enumerate(scenarios):
        rect = ax.bar(x_pos[idx], scenario["values"], width, capsize=5,
                      yerr=[scenario["error_lowers"], scenario["error_uppers"]],
                      label=scenario["desc"])
        rects.append(rect)

    # ax.bar_label would not work for some reason. So we found this online.
    for rect in itertools.chain(rects[0], rects[-1]):
        height = rect.get_height()
        ax.text(rect.get_x()+rect.get_width()/6, 1.0*height,
                '%.2f' % height,
                ha='center', va='bottom')

    # Add some decoration. AD HOC TODO
    if "latency" in kpi_list[0]:
        ax.set_ylabel('Latency (s)')
    else:
        ax.set_ylabel("%")
    #ax.set_title('Key metrics, normalized to without spatial reuse')
    ax.set_xticks(x)
    ax.set_xticklabels(kpi_list)
    ax.legend()

    fig.tight_layout()

    fig_name = ""
    if name:
        fig_name += name + "_"
    fig_name += "comparison"
    if title:
        plt.title(fig_name)
    fig_dir = plot_dir
    fig_path = fig_dir + fig_name + '.pdf'
    if "PDR" in kpi_list:
        plt.ylim(80, 101)
    plt.savefig(fig_path, bbox_inches='tight')
    plt.close()
    print("Made figure", fig_path)


def plot_spatial_absolute_comparison_kpis(scenarios_df,
                                 kpi_etx_no_spatial, kpi_etx_spatial,
                                 kpi_pdr_no_spatial, kpi_pdr_spatial,
                                 kpi_latency_no_spatial, kpi_latency_spatial,
                                 name, plot_dir, title=False):

    #print(scenarios_df.index)
    #print(str(scenarios_df))
    #print(str(scenarios_df.loc["spatial_reuse"]))
    #print(str(scenarios_df.loc["spatial_reuse"]['mac_app_tx_etx_absolute_etx_L']))

    @dataclass
    class DataPoint:
        min: float
        max: float
        mean: float

    @dataclass
    class DataSet:
        etx: DataPoint
        latency: DataPoint
        pdr: DataPoint

    # data
    spatial_reuse_row = scenarios_df.loc["spatial_reuse"]
    no_spatial_reuse_row = scenarios_df.loc["no_spatial_reuse"]

    no_spatial_etx_min = no_spatial_reuse_row[make_spatial_kpi_name(kpi_etx_no_spatial,'lower')]
    no_spatial_etx_max = no_spatial_reuse_row[make_spatial_kpi_name(kpi_etx_no_spatial,'upper')]
    no_spatial_etx = (no_spatial_etx_max + no_spatial_etx_min) / 2

    # Use etx from all packets in the run
    #spatial_etx_min = spatial_reuse_row['mac_app_tx_etx_absolute_etx_L']
    #spatial_etx_max = spatial_reuse_row['mac_app_tx_etx_absolute_etx_U']

    # Use etx from the spatial reuse cells only
    spatial_etx_min = spatial_reuse_row[make_spatial_kpi_name(kpi_etx_spatial,'lower')]
    spatial_etx_max = spatial_reuse_row[make_spatial_kpi_name(kpi_etx_spatial,'upper')]
    spatial_etx = (spatial_etx_max + spatial_etx_min) / 2

    no_spatial_pdr_min = no_spatial_reuse_row[make_spatial_kpi_name(kpi_pdr_no_spatial,'lower')]
    no_spatial_pdr_max = no_spatial_reuse_row[make_spatial_kpi_name(kpi_pdr_no_spatial,'upper')]
    no_spatial_pdr = (no_spatial_pdr_max + no_spatial_pdr_min) / 2

    spatial_pdr_min = spatial_reuse_row[make_spatial_kpi_name(kpi_pdr_spatial,'upper')]
    spatial_pdr_max = spatial_reuse_row[make_spatial_kpi_name(kpi_pdr_spatial,'upper')]
    spatial_pdr = (spatial_pdr_max + spatial_pdr_min) / 2

    no_spatial_latency_min = no_spatial_reuse_row[make_spatial_kpi_name(kpi_latency_no_spatial,'lower')]
    no_spatial_latency_max = no_spatial_reuse_row[make_spatial_kpi_name(kpi_latency_no_spatial,'upper')]
    no_spatial_latency = (no_spatial_latency_max + no_spatial_latency_min) / 2

    spatial_latency_min = spatial_reuse_row[make_spatial_kpi_name(kpi_latency_spatial,'lower')]
    spatial_latency_max = spatial_reuse_row[make_spatial_kpi_name(kpi_latency_spatial, 'upper')]
    spatial_latency = (spatial_latency_max + spatial_latency_min) / 2

    no_spatial_reuse_data = DataSet(
        (DataPoint(
            no_spatial_etx_min,
            no_spatial_etx_max,
            no_spatial_etx)
        ),
        (DataPoint(
            no_spatial_latency_min,
            no_spatial_latency_max,
            no_spatial_latency)
        ),
        (DataPoint(
            no_spatial_pdr_min,
            no_spatial_pdr_max,
            no_spatial_pdr)
        ),
    )

    spatial_reuse_data = DataSet(
        (DataPoint(
            spatial_etx_min,
            spatial_etx_max,
            spatial_etx)
        ),
        (DataPoint(
            spatial_latency_min,
            spatial_latency_max,
            spatial_latency)
        ),
        (DataPoint(
            spatial_pdr_min,
            spatial_pdr_max,
            spatial_pdr)
        )
    )

    ## Sooo tired, TODO verify this math
    #spatial_reuse_data_normalized = DataSet(
    #    (DataPoint(
    #        spatial_reuse_data.etx.min / no_spatial_reuse_data.etx.mean * 100,
    #        spatial_reuse_data.etx.max / no_spatial_reuse_data.etx.mean * 100,
    #        spatial_reuse_data.etx.mean / no_spatial_reuse_data.etx.mean * 100)
    #    ),
    #    (DataPoint(
    #        spatial_reuse_data.latency.min / no_spatial_reuse_data.latency.mean * 100,
    #        spatial_reuse_data.latency.max / no_spatial_reuse_data.latency.mean * 100,
    #        spatial_reuse_data.latency.mean / no_spatial_reuse_data.latency.mean * 100)
    #    ),
    #    (DataPoint(
    #        spatial_reuse_data.pdr.min / no_spatial_reuse_data.pdr.mean * 100,
    #        spatial_reuse_data.pdr.max / no_spatial_reuse_data.pdr.mean * 100,
    #        spatial_reuse_data.pdr.mean / no_spatial_reuse_data.pdr.mean * 100)
    #    )
    #)
    #
    #no_spatial_reuse_data_normalized = DataSet(
    #    (DataPoint(
    #        no_spatial_reuse_data.etx.min / no_spatial_reuse_data.etx.mean * 100,
    #        no_spatial_reuse_data.etx.max / no_spatial_reuse_data.etx.mean * 100,
    #        100)
    #    ),
    #    (DataPoint(
    #        no_spatial_reuse_data.latency.min / no_spatial_reuse_data.latency.mean * 100,
    #        no_spatial_reuse_data.latency.max / no_spatial_reuse_data.latency.mean * 100,
    #        100)
    #    ),
    #    (DataPoint(
    #        no_spatial_reuse_data.pdr.min / no_spatial_reuse_data.pdr.mean * 100,
    #        no_spatial_reuse_data.pdr.max / no_spatial_reuse_data.pdr.mean * 100,
    #        100)
    #    )
    #)

    #print(no_spatial_reuse_data_normalized)
    #print(spatial_reuse_data_normalized)

    # setup the dataframe
    metrics = ['ETX', 'E2E Latency', 'PDR']

    no_spatial_reuse_means = [
        no_spatial_reuse_data.etx.mean,
        no_spatial_reuse_data.latency.mean,
        no_spatial_reuse_data.pdr.mean]
    spatial_reuse_means = [
        no_spatial_reuse_data.etx.mean,
        no_spatial_reuse_data.latency.mean,
        no_spatial_reuse_data.pdr.mean]

    no_spatial_reuse_min = [
        no_spatial_reuse_data.etx.min,
        no_spatial_reuse_data.latency.min,
        no_spatial_reuse_data.pdr.min]
    no_spatial_reuse_max = [
        no_spatial_reuse_data.etx.max,
        no_spatial_reuse_data.latency.max,
        no_spatial_reuse_data.pdr.max]

    spatial_reuse_min = [
        spatial_reuse_data.etx.mean - spatial_reuse_data.etx.min,
        spatial_reuse_data.latency.mean - spatial_reuse_data.latency.min,
        spatial_reuse_data.pdr.mean - spatial_reuse_data.pdr.min]
    spatial_reuse_max = [
        spatial_reuse_data.etx.max - spatial_reuse_data.etx.mean,
        spatial_reuse_data.latency.max - spatial_reuse_data.latency.mean,
        spatial_reuse_data.pdr.max - spatial_reuse_data.pdr.mean]

    print("No spatial reuse:")
    print("Min (etx, latency, pdr): " + str(no_spatial_reuse_min))
    print("Mean (etx, latency, pdr): " + str(no_spatial_reuse_means))
    print("Max (etx, latency, pdr): " + str(no_spatial_reuse_max))

    print("Spatial reuse:")
    print("Min (etx, latency, pdr): " + str(spatial_reuse_min))
    print("Mean (etx, latency, pdr): " + str(spatial_reuse_means))
    print("Max (etx, latency, pdr): " + str(spatial_reuse_max))

    # the label locations
    x = np.arange(len(metrics))

    # width of the bars
    width = 0.3

    fig, ax = plt.subplots()
    #ax.set_ylim([50, 120])
    rects1 = ax.bar(x-width/2, no_spatial_reuse_means, width,
                    yerr=[no_spatial_reuse_min, no_spatial_reuse_max], capsize=5,
                    label="Without spatial reuse")
    rects2 = ax.bar(x+width/2, spatial_reuse_means, width,
                    yerr=[spatial_reuse_min, spatial_reuse_max], capsize=5,
                    label="With spatial reuse")

        # ax.bar_label would not work for some reason. So we found this online.
    for rect in itertools.chain(rects1, rects2):
        height = rect.get_height()
        ax.text(rect.get_x()+rect.get_width()/6, 1.0*height,
                '%.1f' % height,
                ha='center', va='bottom')

    # Add some decoration
    ax.set_ylabel('Percentage of metric, normalized to "without spatial reuse" (%)')
    #ax.set_title('Key metrics, normalized to without spatial reuse')
    ax.set_xticks(x)
    ax.set_xticklabels(metrics)
    ax.legend()

    #ax.bar_label(rects1, padding=3)
    #ax.bar_label(rects2, padding=3, label_type='center', fmt='%.2f')
    #ax.bar_label(rects2, fmt='%.2f')

    fig.tight_layout()

    fig_name = "spatial_reuse_abs_"
    if name:
        fig_name += name + "_"
    fig_name += "comparison"
    if title:
        plt.title(fig_name)
    fig_dir = plot_dir
    fig_path = fig_dir + fig_name + '.pdf'
    plt.savefig(fig_path, bbox_inches='tight')
    plt.close()
    print("Made figure", fig_path)

def plot_spatial_comparison_kpis(scenarios_df,
                                 kpi_etx_no_spatial, kpi_etx_spatial,
                                 kpi_pdr_no_spatial, kpi_pdr_spatial,
                                 kpi_latency_no_spatial, kpi_latency_spatial,
                                 name, plot_dir, title=False):

    #print(scenarios_df.index)
    #print(str(scenarios_df))
    #print(str(scenarios_df.loc["spatial_reuse"]))
    #print(str(scenarios_df.loc["spatial_reuse"]['mac_app_tx_etx_absolute_etx_L']))

    @dataclass
    class DataPoint:
        min: float
        max: float
        mean: float

        @classmethod
        def from_row(cls, row, kpi):
            min = row[make_spatial_kpi_name(kpi, 'lower')]
            max = row[make_spatial_kpi_name(kpi, 'upper')]
            mean = (min + max) / 2
            return cls(min, max, mean)

    @dataclass
    class DataSet:
        etx: DataPoint
        latency: DataPoint
        pdr: DataPoint

    # data
    spatial_reuse_row = scenarios_df.loc["spatial_reuse"]
    no_spatial_reuse_row = scenarios_df.loc["no_spatial_reuse"]

    no_spatial_etx = DataPoint.from_row(no_spatial_reuse_row, kpi_etx_no_spatial)

    # Use etx from all packets in the run
    #spatial_etx_min = spatial_reuse_row['mac_app_tx_etx_absolute_etx_L']
    #spatial_etx_max = spatial_reuse_row['mac_app_tx_etx_absolute_etx_U']

    # Use etx from the spatial reuse cells only
    spatial_etx = DataPoint.from_row(spatial_reuse_row, kpi_etx_spatial)

    no_spatial_pdr = DataPoint.from_row(no_spatial_reuse_row, kpi_pdr_no_spatial)
    spatial_pdr = DataPoint.from_row(spatial_reuse_row, kpi_pdr_spatial)

    no_spatial_latency = DataPoint.from_row(no_spatial_reuse_row, kpi_latency_no_spatial)
    spatial_latency = DataPoint.from_row(spatial_reuse_row, kpi_latency_spatial)

    no_spatial_reuse_data = DataSet(
        no_spatial_etx,
        no_spatial_latency,
        no_spatial_pdr
    )

    spatial_reuse_data = DataSet(
        spatial_etx,
        spatial_latency,
        spatial_pdr
    )

    # Sooo tired, TODO verify this math
    spatial_reuse_data_normalized = DataSet(
        (DataPoint(
            spatial_reuse_data.etx.min / no_spatial_reuse_data.etx.mean * 100,
            spatial_reuse_data.etx.max / no_spatial_reuse_data.etx.mean * 100,
            spatial_reuse_data.etx.mean / no_spatial_reuse_data.etx.mean * 100)
        ),
        (DataPoint(
            spatial_reuse_data.latency.min / no_spatial_reuse_data.latency.mean * 100,
            spatial_reuse_data.latency.max / no_spatial_reuse_data.latency.mean * 100,
            spatial_reuse_data.latency.mean / no_spatial_reuse_data.latency.mean * 100)
        ),
        (DataPoint(
            spatial_reuse_data.pdr.min / no_spatial_reuse_data.pdr.mean * 100,
            spatial_reuse_data.pdr.max / no_spatial_reuse_data.pdr.mean * 100,
            spatial_reuse_data.pdr.mean / no_spatial_reuse_data.pdr.mean * 100)
        )
    )

    no_spatial_reuse_data_normalized = DataSet(
        (DataPoint(
            no_spatial_reuse_data.etx.min / no_spatial_reuse_data.etx.mean * 100,
            no_spatial_reuse_data.etx.max / no_spatial_reuse_data.etx.mean * 100,
            100)
        ),
        (DataPoint(
            no_spatial_reuse_data.latency.min / no_spatial_reuse_data.latency.mean * 100,
            no_spatial_reuse_data.latency.max / no_spatial_reuse_data.latency.mean * 100,
            100)
        ),
        (DataPoint(
            no_spatial_reuse_data.pdr.min / no_spatial_reuse_data.pdr.mean * 100,
            no_spatial_reuse_data.pdr.max / no_spatial_reuse_data.pdr.mean * 100,
            100)
        )
    )

    #print(no_spatial_reuse_data_normalized)
    #print(spatial_reuse_data_normalized)

    # setup the dataframe
    metrics = ['ETX', 'E2E Latency', 'PDR']

    no_spatial_reuse_means = [
        no_spatial_reuse_data_normalized.etx.mean,
        no_spatial_reuse_data_normalized.latency.mean,
        no_spatial_reuse_data_normalized.pdr.mean]
    spatial_reuse_means = [
        spatial_reuse_data_normalized.etx.mean,
        spatial_reuse_data_normalized.latency.mean,
        spatial_reuse_data_normalized.pdr.mean]

    no_spatial_reuse_min = [
        100 - no_spatial_reuse_data_normalized.etx.min,
        100 - no_spatial_reuse_data_normalized.latency.min,
        100 - no_spatial_reuse_data_normalized.pdr.min]
    no_spatial_reuse_max = [
        no_spatial_reuse_data_normalized.etx.max - 100,
        no_spatial_reuse_data_normalized.latency.max - 100,
        no_spatial_reuse_data_normalized.pdr.max - 100]

    spatial_reuse_min = [
        spatial_reuse_data_normalized.etx.mean - spatial_reuse_data_normalized.etx.min,
        spatial_reuse_data_normalized.latency.mean - spatial_reuse_data_normalized.latency.min,
        spatial_reuse_data_normalized.pdr.mean - spatial_reuse_data_normalized.pdr.min]
    spatial_reuse_max = [
        spatial_reuse_data_normalized.etx.max - spatial_reuse_data_normalized.etx.mean,
        spatial_reuse_data_normalized.latency.max - spatial_reuse_data_normalized.latency.mean,
        spatial_reuse_data_normalized.pdr.max - spatial_reuse_data_normalized.pdr.mean]

    print("No spatial reuse:")
    print("Min (etx, latency, pdr): " + str(no_spatial_reuse_min))
    print("Mean (etx, latency, pdr): " + str(no_spatial_reuse_means))
    print("Max (etx, latency, pdr): " + str(no_spatial_reuse_max))

    print("Spatial reuse:")
    print("Min (etx, latency, pdr): " + str(spatial_reuse_min))
    print("Mean (etx, latency, pdr): " + str(spatial_reuse_means))
    print("Max (etx, latency, pdr): " + str(spatial_reuse_max))

    # the label locations
    x = np.arange(len(metrics))

    # width of the bars
    width = 0.3

    fig, ax = plt.subplots()
    ax.set_ylim([50, 120])
    rects1 = ax.bar(x-width/2, no_spatial_reuse_means, width,
                    yerr=[no_spatial_reuse_min, no_spatial_reuse_max], capsize=5,
                    label="Without spatial reuse")
    rects2 = ax.bar(x+width/2, spatial_reuse_means, width,
                    yerr=[spatial_reuse_min, spatial_reuse_max], capsize=5,
                    label="With spatial reuse")

        # ax.bar_label would not work for some reason. So we found this online.
    for rect in itertools.chain(rects1, rects2):
        height = rect.get_height()
        ax.text(rect.get_x()+rect.get_width()/6, 1.0*height,
                '%.1f' % height,
                ha='center', va='bottom')

    # Add some decoration
    ax.set_ylabel('Percentage of metric, normalized to "without spatial reuse" (%)')
    #ax.set_title('Key metrics, normalized to without spatial reuse')
    ax.set_xticks(x)
    ax.set_xticklabels(metrics)
    ax.legend()

    #ax.bar_label(rects1, padding=3)
    #ax.bar_label(rects2, padding=3, label_type='center', fmt='%.2f')
    #ax.bar_label(rects2, fmt='%.2f')

    fig.tight_layout()

    fig_name = "spatial_reuse_"
    if name:
        fig_name += name + "_"
    fig_name += "comparison"
    if title:
        plt.title(fig_name)
    fig_dir = plot_dir
    fig_path = fig_dir + fig_name + '.pdf'
    plt.savefig(fig_path, bbox_inches='tight')
    plt.close()
    print("Made figure", fig_path)

def plot_comparison(scenarios, scenarios_df, plot_dir, title=False):
    rpl_convergence_comparison = False
    for scenario in scenarios:
        if scenario["rpl_convergence_comparison"]:
            rpl_convergence_comparison = True

    scenarios_to_plot = []
    for scenario in scenarios:
        scenarios_to_plot.append(
            {"name": scenario['name'], "desc": scenario['description']})

    kpis = [{"desc": "PRR", "name": "prr_mean",
             "percentile": "default", "bound": "lower"},
            {"desc": "PDR", "name": "pdr_mean",
             "percentile": "default", "bound": "lower"}]
    plot_compare_kpis(scenarios_df, scenarios_to_plot, kpis,
                      str(DEFAULT_PERC) + "p_reliability",
                      plot_dir)
    kpis = [{"desc": "PRR", "name": "prr_mean",
             "percentile": "adhoc", "bound": "lower"},
            {"desc": "PDR", "name": "pdr_mean",
             "percentile": "adhoc", "bound": "lower"}]
    plot_compare_kpis(scenarios_df, scenarios_to_plot, kpis,
                      str(ADHOC_PERC) + "p_reliability",
                      plot_dir)

    kpis = [{"desc": "Median latency", "name": "latency_50",
             "percentile": "default", "bound": "upper"}]
    plot_compare_kpis(scenarios_df, scenarios_to_plot, kpis,
                      str(DEFAULT_PERC) + "p_latency_50",
                      plot_dir)
    kpis = [{"desc": "Median latency", "name": "latency_50",
             "percentile": "adhoc", "bound": "upper"}]
    plot_compare_kpis(scenarios_df, scenarios_to_plot, kpis,
                      str(ADHOC_PERC) + "p_latency_50",
                      plot_dir)

    kpis = [{"desc": "Maximum latency", "name": "latency_maximum",
             "percentile": "adhoc", "bound": "upper"}]
    plot_compare_kpis(scenarios_df, scenarios_to_plot, kpis,
                      str(ADHOC_PERC) + "p_latency_max",
                      plot_dir)
    kpis = [{"desc": "Maximum latency", "name": "latency_maximum",
             "percentile": "default", "bound": "upper"}]
    plot_compare_kpis(scenarios_df, scenarios_to_plot, kpis,
                      str(DEFAULT_PERC) + "p_latency_max",
                      plot_dir)
    
    kpis = [{"desc": "99 percentile latency", "name": "latency_99",
             "percentile": "default", "bound": "upper"}]
    plot_compare_kpis(scenarios_df, scenarios_to_plot, kpis,
                      str(DEFAULT_PERC) + "p_latency_99",
                      plot_dir)
    kpis = [{"desc": "99 percentile latency", "name": "latency_99",
             "percentile": "adhoc", "bound": "upper"}]
    plot_compare_kpis(scenarios_df, scenarios_to_plot, kpis,
                      str(ADHOC_PERC) + "p_latency_99",
                      plot_dir)

    kpis = [{"desc": "Median duty cycle", "name": "duty_cycle_50",
             "percentile": "default", "bound": "upper"}]
    plot_compare_kpis(scenarios_df, scenarios_to_plot, kpis,
                      str(DEFAULT_PERC) + "p_duty_cycle_50",
                      plot_dir)
    kpis = [{"desc": "Median duty cycle", "name": "duty_cycle_50",
             "percentile": "adhoc", "bound": "upper"}]
    plot_compare_kpis(scenarios_df, scenarios_to_plot, kpis,
                      str(ADHOC_PERC) + "p_duty_cycle_50",
                      plot_dir)

    kpis = [{"desc": "Mean duty cycle", "name": "duty_cycle_mean",
             "percentile": "default", "bound": "upper"}]
    plot_compare_kpis(scenarios_df, scenarios_to_plot, kpis,
                      str(DEFAULT_PERC) + "p_duty_cycle_mean",
                      plot_dir)
    kpis = [{"desc": "Mean duty cycle", "name": "duty_cycle_mean",
             "percentile": "adhoc", "bound": "upper"}]
    plot_compare_kpis(scenarios_df, scenarios_to_plot, kpis,
                      str(ADHOC_PERC) + "p_duty_cycle_mean",
                      plot_dir)

    kpis = [{"desc": "Median queue utilization", "name": "queue_fill_50",
             "percentile": "default", "bound": "upper"}]
    plot_compare_kpis(scenarios_df, scenarios_to_plot, kpis,
                      str(DEFAULT_PERC) + "p_queue_utilization_50",
                      plot_dir)

    kpis = [{"desc": "RPL parent switches", "name": "parent_switches_count",
             "percentile": "default", "bound": "upper"}]
    plot_compare_kpis(scenarios_df, scenarios_to_plot, kpis,
                      str(DEFAULT_PERC) + "p_parent_switches",
                      plot_dir)

    if rpl_convergence_comparison:
        # Same as above, but only converged runs
        kpis = [{"desc": "PRR", "name": "converged_prr_mean",
                 "percentile": "default", "bound": "lower"},
                {"desc": "PDR", "name": "converged_pdr_mean",
                 "percentile": "default", "bound": "lower"}]
        plot_compare_kpis(scenarios_df, scenarios_to_plot, kpis,
                          "converged_" + str(DEFAULT_PERC) + "p_reliability",
                          plot_dir)

        kpis = [{"desc": "Median latency", "name": "converged_latency_50",
                 "percentile": "default", "bound": "upper"}]
        plot_compare_kpis(scenarios_df, scenarios_to_plot, kpis,
                          "converged_" + str(DEFAULT_PERC) + "p_latency_50",
                          plot_dir)
        kpis = [{"desc": "Median latency", "name": "converged_latency_50",
                 "percentile": "adhoc", "bound": "upper"}]
        plot_compare_kpis(scenarios_df, scenarios_to_plot, kpis,
                          "converged_" + str(ADHOC_PERC) + "p_latency_50",
                          plot_dir) # TODO this naming can be done inside compare_kpis?

        #kpis = [{"desc": "Median queue utilization", "name": "converged_queue_fill_50",
        #         "percentile": "default", "bound": "upper"}]
        #plot_compare_kpis(scenarios_df, scenarios_to_plot, kpis,
        #                  "converged_" + str(DEFAULT_PERC) + "p_queue_utilization",
        #                  plot_dir)

    return

def plot_spatial_comparison(scenarios_df, plot_dir, title=False):

    scenarios = [{"name": "no_spatial_reuse", "desc": "Without spatial reuse"},
                 {"name": "spatial_reuse", "desc": "With spatial reuse"}]

    # selected spatial links 80 p
    kpis = [{"desc": "PRR", "name": "spatial_cell_prr_mean",
             "percentile": "adhoc", "bound": "lower"},
            {"desc": "PDR", "name": "pdr_mean",
             "percentile": "adhoc", "bound": "lower"}]
    plot_compare_kpis(scenarios_df, scenarios, kpis,
                      "reliability_" + str(ADHOC_PERC) + "p_selected_links",
                      plot_dir, special=True)
    # Same but converged
    kpis = [{"desc": "PRR", "name": "converged_spatial_cell_prr_mean",
             "percentile": "adhoc", "bound": "lower"},
            {"desc": "PDR", "name": "converged_pdr_mean",
             "percentile": "adhoc", "bound": "lower"}]
    plot_compare_kpis(scenarios_df, scenarios, kpis,
                      "converged_reliability_" + str(ADHOC_PERC) + "p_selected_links",
                      plot_dir, special=True)


     # selected spatial links 50 p
    kpis = [{"desc": "PRR", "name": "spatial_cell_prr_mean",
             "percentile": "default", "bound": "lower"},
            {"desc": "PDR", "name": "pdr_mean",
             "percentile": "default", "bound": "lower"}]
    plot_compare_kpis(scenarios_df, scenarios, kpis,
                      "reliability_" + str(DEFAULT_PERC) + "p_selected_links",
                      plot_dir, special=True)
    # Same but converged
    kpis = [{"desc": "PRR", "name": "converged_spatial_cell_prr_mean",
             "percentile": "default", "bound": "lower"},
            {"desc": "PDR", "name": "converged_pdr_mean",
             "percentile": "default", "bound": "lower"}]
    plot_compare_kpis(scenarios_df, scenarios, kpis,
                      "converged_reliability_" + str(DEFAULT_PERC) + "p_selected_links",
                      plot_dir, special=True)

    return

    # Use only links which had spatial reuse
    plot_spatial_comparison_kpis(scenarios_df,
                                 'app_selected_cell_etx_absolute', 'app_cell_etx_absolute_spatial',
                                 'prr_mean', 'prr_mean',
                                 'pdr_mean', 'pdr_mean',
                                 'latency_mean', 'latency_mean',
                                 "selected_links", plot_dir, title)

    # Use only links which had spatial reuse
    plot_spatial_absolute_comparison_kpis(scenarios_df,
                                 'app_selected_cell_etx_absolute', 'app_cell_etx_absolute_spatial',
                                 'pdr_mean', 'pdr_mean',
                                 'latency_mean', 'latency_mean',
                                 "selected_links", plot_dir, title)

def plot_queue_util_selected_nodes(scenarios_df, plot_dir, title=False):

    if "ss2_queue_fill_mean" not in scenarios_df.columns:
        return
    if "ss3_queue_fill_mean" not in scenarios_df.columns:
        return

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
    fig_dir = plot_dir
    fig_path = fig_dir + fig_name + '.pdf'
    plt.savefig(fig_path, bbox_inches='tight')
    plt.close()
    print("Made figure", fig_path)

def plot_duty_cycle(scenarios_df, plot_dir, title=False):
    # Duty cycle
    color = 'tab:red'
    plt.plot(scenarios_df.index, scenarios_df["duty_cycle_mean_default_upper"], color=color,
             marker='o', label="Duty cycle")

    # Duty cycle TX
    color = 'tab:blue'
    plt.plot(scenarios_df.index, scenarios_df["duty_cycle_tx_mean_default_upper"], color=color,
             marker='o', label="Duty cycle TX")

    # Duty cycle RX
    color = 'tab:green'
    plt.plot(scenarios_df.index, scenarios_df["duty_cycle_rx_mean_default_upper"], color=color,
             marker='o', label="Duty cycle RX")

    plt.tight_layout()  # otherwise the right y-label is slightly clipped
    plt.xlabel('traffic intensity, as % of node schedule capacity')
    plt.ylabel('(%)')
    plt.legend()
    fig_name = "duty_cycle_all_scenarios"
    if title:
        plt.title(fig_name)
    fig_dir = plot_dir
    fig_path = fig_dir + fig_name + '.pdf'
    plt.savefig(fig_path, bbox_inches='tight')
    plt.close()
    print("Made figure", fig_path)

def plot_pdr_latency(scenarios_df, plot_dir, title=False):
    pdr_df = scenarios_df
    latency_df = scenarios_df
    fig_name = "pdr_latency_all_scenarios"
    fig_dir = plot_dir

    fig, ax1 = plt.subplots()

    # Latency
    color = 'tab:red'
    ax1.set_xlabel('traffic intensity, as % of node schedule capacity')
    ax1.set_ylabel('Latency (s)', color=color)
    ax1.plot(latency_df.index, latency_df["latency_99_default_upper"], color=color, marker='o')
    ax1.set_ylim(bottom=0)
    #ax1.plot(latency_df.index, latency_df.latency_maximum, color=color, marker='o')
    ax1.tick_params(axis='y', labelcolor=color)

    # Loss
    # TODO naming of PDR is quite messed up. pdr_mean means CI of percentile of mean
    # Mean is the only thing that makes sense with pdr since values are either 100 or 0.
    ax2 = ax1.twinx()  # instantiate a second axes that shares the same x-axis
    color = 'tab:blue'
    ax2.set_ylabel('packet delivery ratio (%)', color=color)  # we already handled the x-label with ax1
    ax2.plot(pdr_df.index, pdr_df["pdr_mean_default_lower"], color=color, marker='o')
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
    if run_id not in scenario['raw_dfs']['raw_packets_dfs']:
        return

    # Copy the DF so that we can make changes without messing up the original
    df = scenario['raw_dfs']['raw_packets_dfs'][run_id].copy()
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
    queue_df = scenario['raw_dfs']['raw_queue_dfs'][run_id].copy()

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
    dc_df = scenario['raw_dfs']['raw_energest_dfs'][run_id].copy()

    # Switch timestamp from absolute to relative to first packet and
    # convert to float (i.e. seconds since t0) using total_seconds()
    dc_df.index = [(index - dc_df.index[0]).total_seconds() for index in dc_df.index]

    # Get only the interesting node
    if nodeid != 0:
        dc_df = dc_df[dc_df.node == nodeid]

    # Remove any rows containig Nan
    # Lines in line plots are not drawn between values and Nan-values
    duty_cycle_df = dc_df[dc_df['duty_cycle'].notna()].copy()
    duty_cycle_tx_df = dc_df[dc_df['duty_cycle_tx'].notna()].copy()
    duty_cycle_rx_df = dc_df[dc_df['duty_cycle_rx'].notna()].copy()

    color = 'tab:red'
    plt.plot(duty_cycle_df.index,
             duty_cycle_df['duty_cycle'],
             color=color,
             marker='o', label="Duty cycle")

    # Duty cycle TX
    color = 'tab:blue'
    plt.plot(duty_cycle_tx_df.index,
             duty_cycle_tx_df['duty_cycle_tx'],
             color=color,
             marker='o', label="Duty cycle TX")

    # Duty cycle RX
    color = 'tab:green'
    plt.plot(duty_cycle_rx_df.index,
             duty_cycle_rx_df['duty_cycle_rx'],
             color=color,
             marker='o', label="Duty cycle RX")

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

    # Retransmissions
    retx_df = scenario['raw_dfs']['raw_mac_tx_dfs'][run_id].copy()

    # Set timestamp as index
    #retx_df.set_index("timestamp", inplace=True)

    # Convert timestamp from string to TimeDelta
    #retx_df.index = pd.to_timedelta(retx_df.index)

    # Switch timestamp from absolute to relative to first packet and
    # convert to float (i.e. seconds since t0) using total_seconds()
    retx_df.index = [(index - retx_df.index[0]).total_seconds() for index in retx_df.index]

    # Retransmissions time-series
    color = 'tab:red'
    ax1.set_xlabel('time (s)')
    ax1.set_ylabel('retransmissions all nodes (cumulative)', color=color)
    ax1.plot(retx_df.index, retx_df.retransmissions.cumsum(), color=color, marker='o')
    ax1.tick_params(axis='y', labelcolor=color)

    fig.tight_layout()  # otherwise the right y-label is slightly clipped
    fig_name = 'retransmissions_timeseries_all_nodes' + '_' + scenario['name'] + \
        '_' + run_id
    plt.title(fig_name)
    fig_path = scenario['path'] + fig_name + '.pdf'
    plt.savefig(fig_path, bbox_inches='tight')
    plt.close()
    print("Made figure", fig_path)

    # Retransmissions bar chart
    sums_df = retx_df.groupby(["node"])["retransmissions"].sum()

    fig = sums_df.plot.bar(x="node", y="retransmissions")
    #fig.tight_layout()  # otherwise the right y-label is slightly clipped
    fig_name = 'retransmissions_all_nodes' + '_' + scenario['name'] + \
        '_' + run_id
    fig_path = scenario['path'] + fig_name + '.pdf'
    fig.set_ylabel('Retransmissions')
    plt.savefig(fig_path, bbox_inches='tight')
    plt.close()
    print("Made figure", fig_path)

    # Hop count bar chart
    hop_df = scenario['raw_dfs']['raw_hop_count_dfs'][run_id].copy()

    # Set timestamp as index
    #hop_df.set_index("timestamp", inplace=True)

    # Convert timestamp from string to TimeDelta
    #hop_df.index = pd.to_timedelta(hop_df.index)

    # Switch timestamp from absolute to relative to first packet and
    # convert to float (i.e. seconds since t0) using total_seconds()
    hop_df.index = [(index - hop_df.index[0]).total_seconds() for index in hop_df.index]

    max_df = hop_df.groupby(["node"])["hop_count"].max()

    fig = max_df.plot.bar(x="node", y="hop_count")
    #fig.tight_layout()  # otherwise the right y-label is slightly clipped
    fig_name = 'max_hop_count_all_nodes' + '_' + scenario['name'] + \
        '_' + run_id
    fig_path = scenario['path'] + fig_name + '.pdf'
    fig.set_ylabel('Hop count')
    plt.savefig(fig_path, bbox_inches='tight')
    plt.close()
    print("Made figure", fig_path)

    # Neighbor count bar chart
    nbr_df = scenario['raw_dfs']['raw_nbr_count_dfs'][run_id].copy()

    # Set timestamp as index
    #nbr_df.set_index("timestamp", inplace=True)

    # Convert timestamp from string to TimeDelta
    #nbr_df.index = pd.to_timedelta(nbr_df.index)

    # Switch timestamp from absolute to relative to first packet and
    # convert to float (i.e. seconds since t0) using total_seconds()
    nbr_df.index = [(index - nbr_df.index[0]).total_seconds() for index in nbr_df.index]

    max_df = nbr_df.groupby(["node"])["nbr_count"].max()

    fig = max_df.plot.bar(x="node", y="nbr_count")
    #fig.tight_layout()  # otherwise the right y-label is slightly clipped
    fig_name = 'max_nbr_count_all_nodes' + '_' + scenario['name'] + \
        '_' + run_id
    fig_path = scenario['path'] + fig_name + '.pdf'
    fig.set_ylabel('Max. neighbor count')
    plt.savefig(fig_path, bbox_inches='tight')
    plt.close()
    print("Made figure", fig_path)
