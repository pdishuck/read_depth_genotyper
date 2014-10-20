from optparse import OptionParser 
import numpy as np
import pandas as pd
import csv
import pysam
import pdb
from bx.intervals.intersection import Interval, IntervalTree
import cluster
import genotyper as gt
from GC_data import GC_data

def get_regions_per_subset(regions, subset, total_subsets):
    subset_size = regions / total_subsets
    nremaining = regions - subset_size * total_subsets
    first_region = subset_size * (subset - 1) + min(nremaining, subset - 1)
    if subset <= nremaining:
        subset_size += 1
    last_region = first_region + subset_size - 1
    
    return (first_region, last_region)

def is_dup(row):
    gts = row.values[3:]
    gts = gts[gts!=-1]
    if np.sum(gts>2) != 0:
        return True
    return False


def bp(t, d = 1):
    return np.sum(t['end'].values - t['start'].values)/d

def overlap(s1, e1, s2, e2):
    l1 = e1 - s1
    l2 = e2 - s2
    mx_s = max(s1, s2)
    mn_e = min(e1, e2)
    o = float(mn_e - mx_s)
    of = min(o/l1, o/l2)
    return min(1.0, of)  


def merge_X_tables(X_M, X_F):
    
    X_files = [X_F, X_M]
    X_intervals = []
    X_tables = []
    for fn_X in X_files:
        i_tree = IntervalTree()
        t_gts = pd.read_csv(fn_X, header=0, delimiter="\t", index_col=None)
        X_tables.append(t_gts)
        for i, row in t_gts.iterrows():
            i_tree.insert_interval(Interval(row['start'], row['end'], i))
        X_intervals.append(i_tree) 
    
    calls = []
    
    added_from_table_2 = {}
    genotypes = []

    for i, row in X_tables[0].iterrows():
        s, e = row['start'], row['end']
        intersections = X_intervals[1].find(s,e)
        overlaps = np.array([overlap(s, e, interval.start, interval.end) for interval in intersections])
        #print s, e, overlaps, overlaps.shape[0]
        arg = overlaps.shape[0] == 0 and -1 or np.argmax(overlaps)
        if overlaps.shape[0]!=0 and overlaps[arg] >0.95:
            added_from_table_2[tuple([intersections[arg].start, intersections[arg].end])] = {'contig': "chrX", "start":s, "end":e}
        calls.append({'contig':"chrX", "start":s, "end":e})
            
    for i, row in X_tables[1].iterrows():
        s, e = row['start'], row['end']
        if not tuple([s,e]) in added_from_table_2:
            calls.append({'contig':"chrX", "start":s, "end":e})
    
    t = pd.DataFrame(calls)
    
    indivs = list(X_tables[0].columns[3:]) + list(X_tables[1].columns[3:])
    
    return t, indivs

def get_cps(t):
    indivs = t['indiv'].values
    inc = np.where(indivs != "WEA_Polish_ND15865_M") 
    cps =  t['cp'].values
    cps = cps[inc]
    indivs = indivs[inc]
    cps[np.isnan(cps)] = 0.0
    return cps, indivs

def genotype(gt, t, keystr, FOUT, FOUT_all, ordered_indivs):
    cps, indivs = get_cps(t) 
    cps = np.reshape(cps,(-1,1))
    gX = gt.GMM_genotype(cps, overload_indivs = indivs)
    #gX.simple_plot("./genotype_plots/%s.png"%keystr)
    
    mu = np.mean(cps)
    gts_by_indiv, gts_to_label, labels_to_gt = gX.get_gts_by_indiv()
    all_gts = np.array([gt for indiv, gt in gts_by_indiv.iteritems()])  
    
    n_0s = 0
    outstr = keystr

    if np.all(all_gts[0]==all_gts) and mu>=0.25: 
        for indiv in ordered_indivs:
            outstr = "%s\t2"%(outstr)
    else:
        for indiv in ordered_indivs:
            if gts_by_indiv[indiv] ==0: n_0s+=1
            outstr = "%s\t%d"%(outstr,gts_by_indiv[indiv])
    
    if n_0s!=len(indivs):
        FOUT.write("%s\n"%outstr)

    FOUT_all.write("%s\n"%outstr)
    #gt.output(FOUT, V_VCF, gX, 

if __name__=="__main__":

    opts = OptionParser()
    opts.add_option("","--contig", dest="contig", default="chrX")
    opts.add_option("","--regions", dest="fn_regions", default="/net/eichler/vol2/eee_shared/assemblies/hg19/genes/refGene.bed")
    opts.add_option("","--X_male_genotypes", dest="X_M_genotypes") 
    opts.add_option("","--X_female_genotypes", dest="X_F_genotypes") 
    opts.add_option("","--output", dest="fn_out") 
    opts.add_option("","--gglob_dir", dest="gglob_dir") 
    opts.add_option("","--plot_dir", dest="plot_dir", default = "plots") 
    opts.add_option("","--fn_fa", dest="fn_fa", default="/net/eichler/vol7/home/psudmant/genomes/annotations/hg19/superdups/superdups.merged.bed.gz") 
    opts.add_option('','--genome_fa',dest='fn_fa', default="/net/eichler/vol7/home/psudmant/genomes/fastas/hg19_1kg_phase2_reference/human_g1k_v37.fasta")
    opts.add_option('','--GC_DTS',dest='fn_GC_DTS', default="/net/eichler/vol7/home/psudmant/genomes/GC_tracks/windowed_DTS/HG19/500_bp_slide_GC")
    opts.add_option('','--DTS_contigs',dest='fn_DTS_contigs', default="/net/eichler/vol7/home/psudmant/EEE_Lab/1000G/1000genomesScripts/windowed_analysis/DTS_window_analysis/windows/hg19_slide/500_bp_windows.pkl.contigs")
    opts.add_option('','--dup_tabix',dest='fn_dup_tabix', default="/net/eichler/vol7/home/psudmant/genomes/annotations/hg19/superdups/superdups.merged.bed.gz")
    opts.add_option('','--max_cp', dest='max_cp', default=12)
    opts.add_option('','--header', dest='header', action='store_true', default=False)

    (o, args) = opts.parse_args()
    
    max_cp = int(o.max_cp)

    tbx_dups = pysam.Tabixfile(o.fn_dup_tabix)
    GC_inf = GC_data(o.fn_GC_DTS, o.contig, o.fn_DTS_contigs)
    indivs = list(pd.read_json("%s/gglob.idx" % o.gglob_dir).indivs)
    #X_loci, indivs = merge_X_tables(o.X_M_genotypes, o.X_F_genotypes)
    # GENOTYPE TIME!
    
    g = gt.genotyper(o.contig, gglob_dir = o.gglob_dir, plot_dir = o.plot_dir, subset_indivs = indivs, fn_fa=o.fn_fa, dup_tabix = tbx_dups, GC_inf = GC_inf)
    
    regions = pd.read_csv(o.fn_regions, header=None, delimiter="\t", index_col=None)
    regions.columns = ["contig", "start", "end", "name"]
    regions_by_contig = regions[regions['contig'] == o.contig]
    nregions = regions_by_contig.shape[0]

    FOUT = open(o.fn_out, 'w')
    if o.header:
        FOUT.write("contig\tstart\tend\tname\t%s\n"%("\t".join(indivs)))

    for i, row in regions_by_contig.iterrows():
        contig, s, e, name = row['contig'], row['start'], row['end'], row['name']
        X, idx_s, idx_e = g.get_gt_matrix(contig, s, e)
            #raw_cps = np.mean(X, 1)
        gts_by_indiv = g.simple_GMM_genotype(X, max_cp=max_cp)
            #gts_by_indiv, gts_to_label, labels_to_gt = gX.get_gts_by_indiv(correct_for_odd_major=False)
            #gX.simple_plot("./plots/%s_%d_%d.pdf"%(contig,s,e))
        gts = "\t".join(["%d"%(gts_by_indiv[i]) for i in indivs])
        FOUT.write("%s\t%d\t%d\t%s\t%s\n"%(contig, s, e, name, gts))
        print i, "%s\t%d\t%d\t%s\t%s\n"%(contig, s, e, name, gts)
