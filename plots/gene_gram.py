import argparse
import csv
import numpy as np
import pandas as pd
from pandas import DataFrame

import matplotlib as mpl
import matplotlib.pyplot as plt
from scipy.cluster.hierarchy import linkage, dendrogram
from scipy.spatial.distance import pdist

def get_nplots(nsamples, spp):
    """Return number of plots given number of samples and samples per plot (spp)"""
    nplots = 0
    while nsamples > 0:
        nsamples -= spp
        nplots += 1
    return nplots

def plot_heatmap(df, pop_info, output_filename, color_column, hclust, annotate_index, first_index = "pop", second_index = "super_pop", sample_names = True, sample_range = [0, 0]):
    """
    Plot the given DataFrame as a heatmap.
    """
    if color_column is not None:
        color_indivs = True

    pop_to_num = {}
    pop_to_color = {'AFR': 'red', 'AMR': 'y', 'EAS': 'g', 'EUR': 'b', 'SAS': 'purple'}
    for pop in pop_info.super_pop:
        if pop in pop_to_num:
            pop_to_num[pop] += 1
        else:
            pop_to_num[pop] = 1

    col_labels = []
    color_order = ["red", "y", "g", "b", "purple", "k", "orange", "c", "firebrick", "gray"]
    unique_pops = []

    if hclust:
        cns = df[df.columns[4:]].T
        df_dist = pdist(cns)
        df_link = linkage(df_dist, method='average')
        df_dendro = dendrogram(df_link, labels = cns.index)
        df_leaves = df_dendro['leaves']
        sample_order = [cns.index[i] for i in df_leaves]
        df = df[["chr", "start", "end", "name"] + sample_order]

    if not color_indivs:
        pop_name, super_pop_name = "", ""
        for col in df.columns[4:]:
            out_label = ""
            if pop_info.loc[col][first_index] != pop_name:
                pop_name = pop_info.loc[col][first_index]
                out_label = pop_name
            if second_index is not None:
                if pop_info.loc[col][second_index] != super_pop_name:
                    super_pop_name = pop_info.loc[col][second_index]
                    out_label += "_" + super_pop_name
            col_labels.append(out_label)
    else:
        col_colors = {}
        color_dict = {group: color_order[i] for i, group in enumerate(pop_info[color_column].unique())}
        for col in df.columns[4:]:
            pop_name = pop_info.loc[col][color_column]
            if annotate_index:
                col_label = col + "_" + pop_name
            else:
                col_label = col
            col_labels.append(col_label)
            if pop_name not in unique_pops:
                unique_pops.append(pop_name)
            col_colors[col_label] = color_dict[pop_name]

    if not sample_names:
        col_labels = ["|" for x in col_labels]

    colors = mpl.colors.ListedColormap(['w', 'gray', 'k', (0, 0, 0.5), (0, 0, 1), 'c', 'g', 'y', 'orange', 'red', 'firebrick'], name='cp_colormap')
    bounds = [x - 0.5 for x in range(12)]
    norm = mpl.colors.BoundaryNorm(bounds, colors.N)

    ### Try dendrogram from example: http://nbviewer.ipython.org/github/OxanaSachenkova/hclust-python/blob/master/hclust.ipynb ###

    fig = plt.figure(figsize=(24,15))

    # Set size for subpanels
    xmin, ymin = 0.04, 0.05
    hmap_w, hmap_h = 0.8, 0.6
    dendro_h = 0.25
    cbar_w = 0.02
    legend_w = 0.1
    xspace, yspace = 0.05, 0.07

    # [xmin, ymin, width, height]
    heatmap_dims = [xmin, ymin, hmap_w, hmap_h]
    sample_dendro_dims = [xmin, ymin + hmap_h + yspace, hmap_w, dendro_h]
    colorbar_dims = [xmin + hmap_w + xspace, ymin, cbar_w, hmap_h]
    sample_legend_dims = [xmin + hmap_w + xspace, ymin + hmap_h + yspace, cbar_w, dendro_h]

    # Plot legend
    legend_axis = fig.add_axes(sample_legend_dims)
    legend_axis.set_axis_off()
    legend_entries = []
    for pop in unique_pops:
        pop_entry = mpl.patches.Patch(color=color_dict[pop], label=pop)
        legend_entries.append(pop_entry)

    plt.legend(handles=legend_entries, bbox_to_anchor=sample_legend_dims, borderaxespad=0.)

    Y = linkage(df_dist, method='average')

    ### This is where a region dendrogram should be added if needed (untested)
    cluster_regions = False

    if cluster_regions:
        region_dendro = fig.add_axes([0.05,0.1,0.2,0.6])
        Z1 = dendrogram(Y, orientation='right',labels=cns.index) # adding/removing the axes
        ax1.set_yticks([])
        ax1.set_xticks([])
    ###


    # Compute and plot sample dendrogram.
    sample_dendro = fig.add_axes(sample_dendro_dims)
    Z2 = dendrogram(df_link)
    sample_dendro.set_yticks([])
    sample_dendro.set_xticklabels(col_labels, rotation=90, fontsize=4)

    # Add grey box to indicate included samples if plotting a subset
    if sample_range[0] != 0 or sample_range[1] != len(col_labels):
        xlocs = sample_dendro.xaxis.get_majorticklocs()
        xmin = xlocs[sample_range[0]]
        xmax = xlocs[sample_range[1] - 1]
        ymax = sample_dendro.get_ylim()[1]
        sample_dendro.add_patch(mpl.patches.Rectangle((xmin, 0), xmax - xmin, ymax, facecolor="grey", edgecolor="none"))

    #Compute and plot the heatmap
    axmatrix = fig.add_axes(heatmap_dims)
    heatmap = axmatrix.imshow(df[df.columns[sample_range[0] + 4:sample_range[1] + 4]], aspect='auto', origin='lower', norm=norm, cmap=colors, interpolation='nearest')
    axmatrix.set_yticks(range(len(df.index)))
    axmatrix.set_yticklabels(df.index)
    axmatrix.set_xticks(range(sample_range[1] - sample_range[0]))
    axmatrix.xaxis.tick_top()
    if sample_names:
        if hclust:
            axmatrix.set_xticklabels([])
        else:
            axmatrix.set_xticklabels(col_labels[sample_range[0]:sample_range[1]], rotation=90, fontsize=4)
    else:
        if hclust:
            axmatrix.set_xticklabels([])
        else:
            axmatrix.set_xticklabels(col_labels[sample_range[0]:sample_range[1]])
    map(lambda x: x.set_visible(False), axmatrix.xaxis.get_majorticklines())
    map(lambda x: x.set_visible(False), axmatrix.yaxis.get_majorticklines())

    # Plot colorbar.
    axcolor = fig.add_axes(colorbar_dims)
    cbar = plt.colorbar(heatmap, cax=axcolor, ticks=range(11))
    cbar.ax.set_yticklabels([str(x) for x in range(10)] + ['>9'])

    ######
    if color_indivs:
        if hclust:
            map(lambda x: x.set_color(col_colors[x.get_text()]), sample_dendro.get_xticklabels())
        else:
            map(lambda x: x.set_color(col_colors[x.get_text()]), axmatrix.get_xticklabels())

        

    plt.savefig(output_filename)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("input_file")
    parser.add_argument("pop_file")
    parser.add_argument("output_file_prefix")
    parser.add_argument("--plot_type", default="png", choices=["pdf","png"], help = "Plot file format")
    parser.add_argument("--spp", default=None, type=int, help="Number of samples per plot (Default: all)")
    parser.add_argument("--color_column", default=None, help="Label every sample and color by specified column from pop file (e.g. super_pop)")
    parser.add_argument("--hclust", action="store_true", help="Group samples using hierarchical clustering")
    parser.add_argument("--exclude_sample_names", action="store_true", help="Use '-' instead of sample name")
    parser.add_argument("--annotate_index", action="store_true", help="Append index (e.g. super_pop) to sample name")
    args = parser.parse_args()

    df = pd.read_table(args.input_file)
    pop_info = pd.read_csv(args.pop_file, sep='\t')
    pop_info.sort(columns=["super_pop", "pop"], inplace=True, axis=0)

    sample_order = [sample for sample in pop_info.sample if sample in df.columns]

    if args.spp is None:
        args.spp = len(sample_order)

    pop_info.index = pop_info.sample
    pop_info = pop_info.ix[sample_order, :]

    df = df[["chr", "start", "end", "name"] + sample_order]
    df["name"] = df.name.map(lambda x: "_".join(sorted(x.split(","))))
    df.sort(columns=["name"], inplace=True, axis=0)
    df.index = df.name
    df[sample_order].applymap(lambda x: 10 if x > 10 else x)

    sample_names = not args.exclude_sample_names

    # Plot heatmap
    nsamples = len(sample_order)
    nplots = get_nplots(nsamples, args.spp)

    for i in range(nplots):
        start_sample = i * args.spp
        end_sample = min(i * args.spp + args.spp, nsamples)
        if nplots > 1:
            plot_name = ".".join([args.output_file_prefix, str(i), args.plot_type])
        else:
            plot_name = ".".join([args.output_file_prefix, args.plot_type])
        plot_heatmap(df, pop_info, plot_name, args.color_column, args.hclust, args.annotate_index, sample_names = sample_names, sample_range = [start_sample, end_sample])

