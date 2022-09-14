#!/usr/bin/python3
# SPDX-License-Identifer: GPL-2.0-only
# Copyright (C) 2022 Advanced Micro Devices, Inc.
#
# Authors: Wyes Karny <wyes.karny@amd.com>,
#          Gautham R Shenoy <gautham.shenoy@amd.com>,
#          K Prateek Nayak <kprateek.nayak@amd.com>

import sys
from optparse import OptionParser
import os.path

comp_help_text = 'pct increase of a schedstat metric of the other run with respect to the corresponding metric of the baseline run is indicating within the |  | pair'
usage="python3 %prog -b baseline_logdir -c compare_logdir -o out_file [-f baseline_cpu_list] [-s compare_cpu_list]"
parser = OptionParser(usage)
parser.add_option("-b", "--basedir", dest="baseline_log_dir", type=str, help="sched-scoreboard log directory of the run that should be considered as the baseline")
parser.add_option("-c", "--compdir", dest="compare_log_dir", type=str, help="sched-scoreboard log directory of some other run that should be compared against the baseline")
parser.add_option("-o", "--out", dest="out_file", type=str, help="Output file to store the schedstat comparison output")
parser.add_option("-f", "--firstlist", dest="baseline_cpu_list", type=str, help="Restrict the comparison to the schedstats of this list of CPUs from the baseline run. Default : all cpus")
parser.add_option("-s", "--secondlist", dest="compare_cpu_list", type=str, help="Restrict the comparison to the schedstats of this list of CPUs from the other run. Default : all cpus")

(options, args) = parser.parse_args()

def perct_diff(a, b):
    a = float(a)
    b = float(b)
    if (a == 0.0):
        return 0.0
    c = (b / a) * 100.0 - 100.0
    c = round(c, 2)
    return c

##########################################################
# This function returns true if the float number has some
# value after decimal point.
##########################################################
def true_float(a):
    int_a = int(a)
    float_a = float(a)
    if (float_a - int_a) > 0:
        return True
    return False

#########################################################
# This function aligns floats and integers in uniform
# manner.
#########################################################
def write_align(a, extended_digits=None):
    line = ""
    if extended_digits:
        if true_float(a):
            line += f"{a:>12.5f}"
        else:
            line += f"{int(a):>12d}"
    else:
        if true_float(a):
            line += f"{a:>6.2f}"
        else:
            line += f"{int(a):>6d}"
    return line

def split_by_cpu(fp):
    cpu = {}
    lines = fp.readlines()
    cpu_start = False
    last_cpu_number = -1
    last_cpu_start = -1
    for i in range(0, len(lines)):
        if lines[i].find("cpu:  cpu") == 0:
            if cpu_start:
                cpu[last_cpu_number] = lines[last_cpu_start:i]
            cpu_start = True
            last_cpu_start = i
            last_cpu_number +=1
    if cpu_start:
        cpu[last_cpu_number] = lines[last_cpu_start:len(lines)]
    return cpu

def side_by_side(file1_lines, file2_lines):
    out_lines = []
    for j in range(0, len(file1_lines)):
        l1 = file1_lines[j]
        l2 = file2_lines[j]
        if ":" in l1 and "Category:" not in l1 and "cpumask:" not in l1 and "cpu:" not in l1 and "domain:" not in l1 and "Wakeup info:" not in l1 and "level info" not in l1:
            arr_start_index_l1 = l1.rindex(":") + 1
            arr_start_index_l2 = l2.rindex(":") + 1
            out_str = ""
            out_str += l1[0: arr_start_index_l1]
            arr1 = ' '.join(l1.rstrip()[arr_start_index_l1:].split()).split(' ')
            arr2 = ' '.join(l2.rstrip()[arr_start_index_l2:].split()).split(' ')
            for i in range(0, len(arr1)):
                out_str += "  "
                if arr1[i].replace('.', '', 1).isdigit():
                    try:
                        stat1 = float(arr1[i].strip())
                        stat2 = float(arr2[i].strip())
                        exteneded_digits = None
                        if (i == 0):
                            exteneded_digits = True
                        out_str += write_align(stat1, exteneded_digits)
                        out_str += ", "
                        out_str += write_align(stat2, exteneded_digits)
                        if (i == 0):
                            diff = perct_diff(arr1[i].rstrip().lstrip().strip("$(){}[]<>"), arr2[i].rstrip().lstrip().strip("$(){}[]<>"))
                            if abs(diff) >= 5.0:
                                out_str += "  |"
                                out_str += f"{diff:7.2f}"
                                out_str += "|"
                            else:
                                out_str += " "*11
                    except ValueError:
                        print('Error in parsing input files: \n', 'base file line: ' + l1, 'comp file line: ' + l2)
                        exit(1)
                else:
                    out_str += arr1[i].rstrip()
            out_lines.append(out_str + '\n')
        elif ":" in l1 and ("cpu:" in l1 or 'domain:' in l1):
            out_lines.append(l1.replace('\n','') + ' vs ' + l2.replace('\n', '') + '\n')
        elif ":" in l1 and "CPU level info:" in l1:
            break
        else:
            out_lines.append(l1)
    return out_lines

def parse_cpulist(cpulist):
    cs_str = cpulist.split(',')
    cs = []
    for s in cs_str:
        if '-' in s:
            s_range = [int(x) for x in s.split('-')]
            for i in range(s_range[0], s_range[1] + 1):
                cs.append(i)
        else:
            cs.append(int(s))
    return cs

if __name__ == "__main__":
    base_file = options.baseline_log_dir + '/schedstat-summary'
    comp_file = options.compare_log_dir + '/schedstat-summary'
    if options.baseline_cpu_list:
        try:
            fs = parse_cpulist(options.baseline_cpu_list)
        except ValueError:
            print('Error: baseline cpu list not valid')
            print(usage)
            exit(1)
        fs_mask = 0
        for i in fs:
            fs_mask |= 1 << i
        base_file += '-' + hex(fs_mask)
    if options.compare_cpu_list:
        try:
            ss = parse_cpulist(options.compare_cpu_list)
        except ValueError:
            print('Error: comapare cpu list not valid')
            print(usage)
            exit(1)
        ss_mask = 0
        for i in ss:
            ss_mask |= 1 << i
        comp_file += '-' + hex(ss_mask)
    import schedstat_parser
    schedstat_parser.main(options.baseline_log_dir + '/schedstat-before', options.baseline_log_dir + '/schedstat-after',
            base_file, options.baseline_log_dir + '/domain_map.cfg', options.baseline_cpu_list)
    schedstat_parser.main(options.compare_log_dir + '/schedstat-before', options.compare_log_dir + '/schedstat-after',
            comp_file, options.compare_log_dir + '/domain_map.cfg', options.compare_cpu_list)
    with open(base_file, "r") as sf1, open(comp_file, "r") as sf2, open(options.out_file, "w") as sf3:
        file1_lines = sf1.readlines()
        file2_lines = sf2.readlines()
        sf3.writelines('comparison results : base_file : ' + base_file + ' vs '+ 'comp_file : ' + comp_file + '\n')
        sf3.writelines(comp_help_text + '\n')
        out_lines = side_by_side(file1_lines, file2_lines)
        sf3.writelines(out_lines)
