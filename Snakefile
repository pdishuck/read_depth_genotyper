import csv
import os
import pandas as pd

configfile: "config.json"

COORDS = list(config.get("bedfiles").values())
REGION_NAMES = list(config.get("bedfiles").keys())

TABLE_DIR = config["table_dir"]
PLOT_DIR = config["plot_dir"]

REFERENCE = config["reference"]
DATASETS = config["datasets"]
DATATYPES = config["data_types"]

ds_manifest = pd.read_table(config["ref_files"][REFERENCE]["datasets"], header=0)
ds_manifest.index = ds_manifest.dataset

DIRS_TO_MAKE = ["log", TABLE_DIR, PLOT_DIR]

genotyper = config.get("genotyper")

if genotyper == "wssd_cc":
    include: "workflows/wssd_cc_genotyper.snake"
elif genotyper == "gglob":
    include: "workflows/gglob_genotyper.snake"

for folder in DIRS_TO_MAKE:
    if not os.path.exists(folder):
        os.makedirs(folder)

GENE_GRAM_SETTINGS = config.get("gene_gram_settings", "")
SPP = config.get("spp", 500)

def get_region_names(coord_files):
    names = []
    for coord_file in coord_files:
        with open(coord_file, 'r') as reader:
            for line in reader:
                names.append(line.rstrip().split()[3])
    return names

def get_coords_and_size_from_name(name, coord_files):
     for coord_file in coord_files:
        with open(coord_file, 'r') as reader:
            for line in reader:
                dat = line.rstrip().split()
                if dat[3] == name:
                    chr, start, end = dat[0], int(dat[1]), int(dat[2])
                    return ("%s:%d-%d" % (chr, start, end), str(end - start))

def get_family_from_name(name, coord_files):
    for coord_file in coord_files:
        with open(coord_file, 'r') as reader:
            for line in reader:
                test_name = line.rstrip().split()[3]
                if test_name == name:
                    return coord_file.split("/")[1].split(".")[0]

def get_n_samples(region_file):
    with open(region_file, 'r') as reader:
        line = next(reader)
        nsamples = len(line.rstrip().split()) - 4
    return nsamples

def get_n_plots(region_file, spp):
    nsamples = get_n_samples(region_file)
    nplots = 0
    while nsamples > 0:
        nsamples -= spp
        nplots += 1
    return map(str, range(nplots))

rule all:   
    input:  "%s/num_suns.table.tab" % (TABLE_DIR),
            expand("%s/gene_grams/{fam}_{dataset}_{datatype}.0.{file_type}" % (PLOT_DIR),
            fam = REGION_NAMES, dataset = DATASETS, datatype = DATATYPES, file_type = config["plot_file_type"]),
            expand("%s/violin/{name}_{dataset}_violin_{datatype}.{file_type}" % (PLOT_DIR),
            dataset = config["main_dataset"], name = get_region_names(COORDS), datatype = DATATYPES, file_type = config["plot_file_type"]),
            expand("%s/{plottype}_{datatype}.pdf" % PLOT_DIR, plottype=["violin", "scatter", "superpop"], datatype = DATATYPES)
    params: sge_opts=""

rule get_cn_wssd_variance:
    input:  gts = expand("{fam}/{dataset}/{dataset}.wssd.genotypes.tab", fam = REGION_NAMES, dataset = DATASETS),
            suns = "%s/num_suns.table.tab" % (TABLE_DIR)
    output: "%s/wssd_stats_by_family.tab" % (TABLE_DIR)
    params: sge_opts = "-l mfree=2G -N get_var", families = REGION_NAMES
    run:
        wssd_stats = pd.DataFrame(columns=["name"])
        datasets = DATASETS
        size = []
        for i, dataset in enumerate(datasets):
            wssd_mean, wssd_std, cn_two = [], [], []
            sample_dat = pd.read_csv(ds_manifest.loc[dataset]["manifest"], sep="\t", header=0)
            samples = sample_dat["sample"].tolist()
            for j, fam in enumerate(REGION_NAMES):
                data = pd.read_csv("%s/%s/%s_wssd_genotypes.tab" % (fam, dataset, dataset), sep="\t", header=0)
                common_samples = [sample for sample in samples if sample in data.columns]
                cns = data[common_samples]
                wssd_mean.append(cns.mean(axis=1).mean(axis=0))
                wssd_std.append(cns.std(axis=1).mean(axis=0))
                cn_two.append(cns.applymap(lambda x: x < 2.5).sum(axis=1).sum(axis=0))
                if i == 0:
                    size.append(int((data["end"] - data["start"]).mean()))
            wssd_stats[dataset + "_mean"] = wssd_mean
            wssd_stats[dataset + "_std"] = wssd_std
            wssd_stats[dataset + "_cn2"] = cn_two
        wssd_stats["name"] = list(params.families)
        wssd_stats["size"] = size
        wssd_stats.to_csv(output[0], index=False, sep="\t")

rule get_cn_sunk_variance:
    input:  gts = expand("{fam}/{dataset}/{dataset}.sunk.genotypes.tab", fam = REGION_NAMES, dataset = DATASETS), 
            suns = "%s/num_suns.table.tab" % (TABLE_DIR)
    output: "%s/sunk_stats_by_region.tab" % TABLE_DIR
    params: sge_opts = "-l mfree=2G -N get_var", families = REGION_NAMES
    run:
        sunk_stats = pd.DataFrame(columns = ["name"])
        names = []
        for i, dataset in enumerate(DATASETS):
            sample_dat = pd.read_table(ds_manifest.loc[dataset]["manifest"], header=0)
            samples = sample_dat["sample"].tolist()
            sunk_mean, sunk_std, cn_zero = [], [], []
            for j, fam in enumerate(params.families):
                data = pd.read_csv("%s/%s/%s_sunk_genotypes.tab" % (fam, dataset, dataset), sep="\t", header=0)
                common_samples = [sample for sample in samples if sample in data.columns]
                cns = data[common_samples]
                sunk_mean.extend(cns.mean(axis=1).tolist())
                sunk_std.extend(cns.std(axis=1).tolist())
                cn_zero.extend(cns.applymap(lambda x: x < 0.5).sum(axis=1).tolist())
                if i == 0:
                    names.extend(data["name"].tolist())
            sunk_stats[dataset + "_mean"] = sunk_mean
            sunk_stats[dataset + "_std"] = sunk_std
            sunk_stats[dataset + "_cn<0.5"] = cn_zero
        sunk_stats["name"] = names
        num_suns = pd.read_csv(input.suns, sep="\t", header=0)
        sunk_stats = num_suns.merge(sunk_stats, on = "name")
        sunk_stats.to_csv(output[0], index=False, sep="\t")

rule get_suns:
    input: COORDS
    output: "%s/num_suns.table.tab" % (TABLE_DIR)
    params: sge_opts = "-l mfree=2G -N get_SUNs", suns = "/net/eichler/vol5/home/bnelsj/projects/gene_grams/hg19_suns.no_repeats_36bp_flanking.bed"
    run:
        for i, fam in enumerate(REGION_NAMES):
            if i == 0:
                shell("""module load bedtools/2.21.0; bedtools intersect -a {fam}/{fam}.coords.bed -b {params.suns} -wao | groupBy -g 1,2,3,4 -c 6,6 -o first,count | 
                         awk 'OFS="\t" {{print $1, $2, $3, $4, $3-$2, $5 != "-1" ? $6 : 0}}' > {output[0]}""")
            else:
                shell("""module load bedtools/2.21.0; bedtools intersect -a {fam}/{fam}.coords.bed -b {params.suns} -wao | groupBy -g 1,2,3,4 -c 6,6 -o first,count | 
                         awk 'OFS="\t" {{print $1, $2, $3, $4, $3-$2, $5 != "-1" ? $6 : 0}}' >> {output[0]}""")
        shell("""sed -i '1ichr\tstart\tend\tname\tsize\tnSUNs' {output[0]}""")

rule plot_gene_grams:
    input: expand("{fam}/{fam}.{dataset}.combined.{datatype}.bed", fam = REGION_NAMES, dataset = DATASETS, datatype = DATATYPES)
    output: "%s/gene_grams/{fam}_{dataset}_{datatype}.0.{file_type}" % (PLOT_DIR)
    params: sge_opts = "-l mfree=8G -N gene_grams"
    run:
        manifest = ds_manifest.loc[wildcards.dataset]["manifest"]
        shell("""python scripts/gene_gram.py {wildcards.fam}/{wildcards.fam}.{wildcards.dataset}.combined.{wildcards.datatype}.bed {manifest} {PLOT_DIR}/gene_grams/{wildcards.fam}_{wildcards.dataset}_{wildcards.datatype} --plot_type {wildcards.file_type} --spp {SPP} {GENE_GRAM_SETTINGS}""")

rule get_combined_pdfs:
    input: expand("%s/violin_{datatype}.pdf" % PLOT_DIR, datatype = DATATYPES)
    params: ""

rule combine_violin_pdfs:
    input: expand("%s/{plottype}/{name}_{dataset}_{plottype}_{datatype}.pdf" % (PLOT_DIR), plottype = ["violin", "scatter", "superpop"], name = get_region_names(COORDS), dataset = config["main_dataset"], datatype = DATATYPES)
    output: "%s/violin_{datatype}.pdf" % PLOT_DIR, "%s/scatter_{datatype}.pdf" % PLOT_DIR, "%s/superpop_{datatype}.pdf" % PLOT_DIR
    params: sge_opts = "-l mfree=8G -N pdf_combine"
    run:
        for pt in ["violin", "scatter", "superpop"]:
            shell("""gs -dBATCH -dNOPAUSE -q -sDEVICE=pdfwrite -sOutputFile={PLOT_DIR}/{pt}_{wildcards.datatype}.pdf plots/{pt}/*{pt}_{wildcards.datatype}.pdf""")

rule plot_violins:
    input: expand("%s/{fam}_{{dataset}}_{{datatype}}.genotypes.df" % (TABLE_DIR), fam = REGION_NAMES)
    output: "%s/violin/{name}_{dataset}_violin_{datatype}.{file_type}" % (PLOT_DIR), "%s/scatter/{name}_{dataset}_scatter_{datatype}.{file_type}" % (PLOT_DIR), "%s/superpop/{name}_{dataset}_superpop_{datatype}.{file_type}" % (PLOT_DIR)
    params: sge_opts = "-l mfree=8G -N plot_violins"
    run:
        family = get_family_from_name(wildcards.name, COORDS)
        (coords, size) = get_coords_and_size_from_name(wildcards.name, COORDS)
        title = "_".join([wildcards.name, coords, size, config["reference"], wildcards.dataset, wildcards.datatype])
        shell("""Rscript scripts/genotype_violin.R {TABLE_DIR}/{family}_{wildcards.dataset}_{wildcards.datatype}.genotypes.df {output[0]} {wildcards.name} {wildcards.file_type} {title} 3 violin; touch {output[0]}""")
        shell("""Rscript scripts/genotype_violin.R {TABLE_DIR}/{family}_{wildcards.dataset}_{wildcards.datatype}.genotypes.df {output[1]} {wildcards.name} {wildcards.file_type} {title} 3; touch {output[1]}""")
        shell("""Rscript scripts/genotype_violin.R {TABLE_DIR}/{family}_{wildcards.dataset}_{wildcards.datatype}.genotypes.df {output[2]} {wildcards.name} {wildcards.file_type} {title} 3 super_pop_only; touch {output[2]}""")

rule get_long_table:
    input: regions = "{fam}/{fam}.{dataset}.combined.{datatype}.bed"
    output: "%s/{fam}_{dataset}_{datatype}.genotypes.df" % (TABLE_DIR)
    params: sge_opts = "-l mfree=8G -N make_long_table"
    run:
        master_manifest = config["master_manifest"]
        pop_codes = config["pop_codes"]
        shell("""Rscript scripts/transform_genotypes.R {input.regions} {master_manifest} {pop_codes} {wildcards.dataset} {output}""")

rule combine_genotypes:
    input: expand("{{fam}}/{{fam}}.{ds}.{{datatype}}.genotypes.tab", ds = DATASETS)
    output: "{fam}/{fam}.{dataset}.combined.{datatype}.bed"
    params: sge_opts="-l mfree=2G -N combine_gt"
    run:
        fam = wildcards.fam
        dt = wildcards.datatype
        ds = wildcards.dataset
        main_ds = pd.read_table(input[0], na_values="NA")
        for app_ds in config["append_dataset"]:
            if app_ds != ds:
                append_dataset = pd.read_csv("{fam}/{fam}.{app_ds}.{dt}.genotypes.tab".format(fam=fam, app_ds=app_ds, dt=dt), header=0, sep="\t", index_col=False)
                main_ds = main_ds.merge(append_dataset, on=["chr", "start", "end", "name"])
        main_ds.to_csv("{fam}/{fam}.{ds}.combined.{dt}.bed".format(fam=fam, ds=ds, dt=dt), index=False, sep="\t", na_rep="NA")
