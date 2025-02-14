#!/usr/bin/python3
# SPDX-License-Identifer: GPL-2.0-only
# Copyright (C) 2022 Advanced Micro Devices, Inc.
#
# Authors: Wyes Karny <wyes.karny@amd.com>,
#          Gautham R Shenoy <gautham.shenoy@amd.com>,
#          K Prateek Nayak <kprateek.nayak@amd.com>

import sys
import json
import os.path
from optparse import OptionParser

banner_width = 100
help_text  = ''
help_text += 'pct within the CPU represented by [...]\n'
help_text += 'avg period in jiffies represented by $...$\n'

keys_ver_map = None
domain_map = {}
cpu_stats_show_list = None
domain_stats_show_list = None
domains_show_list = None

keys_category_info = {
    'idle'    : "count",
    'busy'    : "count",
    'newidle' : "count",
    'alb'     : "show",
    'sbe'     : "skip",
    'sbf'     : "skip",
    'ttwu'    : "skip",
}

def percentage(val, total):
    if total == 0:
        return 0

    return (100.0 * float(val) / float(total))

def writen(out, w_str):
    out.write(w_str + '\n')

def get_keys_ver_map(schedstat_ver):
    filename = "v" + schedstat_ver + ".json"
    ver_filename = os.path.join(os.path.dirname(__file__), filename)

    if os.path.exists(ver_filename):
        with open(ver_filename, "r") as json_file:
            keys_ver_map = json.loads(json_file.read())
    else:
        print('Error: Schedstat file not supported : ', tokens[1])
        return -1

    return keys_ver_map

class Stats:
    def __init__(self, ver='unknown', name=None, timestamp=None):
        if name:
            self.name = name
        else:
            self.name = ""

        if timestamp:
            self.timestamp = timestamp
        else:
            self.timestamp = 0

        self.version = ver
        self.num_stats = 0
        self.stats_map = {}

        if not self.type:
            self.type = 'unknown'

    def __repr__(self):
        return self.name

    def parse(self, keys, desc, values):
        self.stats_map = dict(zip(keys, values))
        self.desc_map = dict(zip(keys, desc))

    def copy_keys(self, b):
        keys = b.stats_map.keys()
        self.timestamp = b.timestamp
        self.stats_map = dict(zip(keys, [0] * len(keys)))

    def add(self, b):
        if len(self.stats_map) != len(b.stats_map):
            print("Error: Addition failed, length mismatch")
            return -1

        for k in self.stats_map.keys():
            self.stats_map[k] += b.stats_map[k]

        return 0

    def subtract(self, b):
        if len(self.stats_map) != len(b.stats_map):
            print("Error: subtract failed, length mismatch")
            return -1

        self.timestamp -= b.timestamp

        for k in self.stats_map.keys():
            self.stats_map[k] -= b.stats_map[k]

        return 0

    def scaler_div(self, b):
        for k in self.stats_map.keys():
            self.stats_map[k] = int(self.stats_map[k] / b)

        return 0

    def display(self):
        for k in self.stats_map.keys():
            print(k, " : ", self.stats_map[k])

class CPUStats(Stats):
    def __init__(self, ver='unknown', name=None, timestamp=None):
        self.type = 'cpu'
        super().__init__(ver, name, timestamp)

    def parse(self, line):
        tokens = line.split()
        self.name = tokens[0]
        cpu_values = list(map(int,tokens[1:len(tokens)]))
        keys_array = []
        desc_array = []
        only_inbuild_keys = []

        for k in keys_ver_map['cpu_keys']:
            if k['is_derived'] == 0:
                only_inbuild_keys.append(k)

        sorted_cpu_list = sorted(only_inbuild_keys, key=lambda item : item['input_pos'])

        for s in sorted_cpu_list:
            keys_array.append(s['key'])
            desc_array.append(s['desc'])

        super().parse(keys_array, desc_array, cpu_values)

    def get_desc(self, key):
        return self.desc_map[key]

    def checkCPUId(self, cpuid):
        num = int(self.name.split('u')[1])

        if num == cpuid:
            return True

        return False

    def displayCategories(self, out):
        writen(out, banner_width * "-")
        writen(out, "cpu:  " + self.name,)
        writen(out, banner_width * "-")

        for k in keys_ver_map['cpu_keys']:
            if cpu_stats_show_list:
                templist = [x for x in cpu_stats_show_list if k['key'].find(x) != -1]
                if (len(templist) == 0):
                    continue

            if k['is_derived'] == 0:
                v = self.stats_map[k['key']]
            else:
                func_args = []
                for args in k['values']:
                    func_args.append(self.stats_map[args])

                fn = lambda a: eval(k['function'])
                v = fn(func_args)

            p_str = ''
            p_str += k['desc'] + ' : ' + f"{v:20d}"

            if 'pct_on' in k:
                p1 = percentage(v, self.stats_map[k['pct_on']])
                p_str += '  ( ' + f"{p1:5.2f}" + ' )'

            writen(out, p_str)

class DomainStats(Stats):
    def __init__(self, ver='unknown', name=None, timestamp=None):
        self.cpumask = '0'
        self.type = 'domain'
        super().__init__(ver, name, timestamp)

    def parse(self, line):
        tokens = line.split()

        dname_idx = 0
        if int(self.version) >= 17:
            dname_idx = 1

        self.name = tokens[dname_idx + 0]
        self.cpumask = tokens[dname_idx + 1]
        domain_values = list(map(int, tokens[dname_idx + 2 : len(tokens)]))
        keys_array = []
        desc_array = []
        only_inbuild_keys = []

        for k in keys_ver_map['domain_keys']:
            if k['is_derived'] == 0:
                only_inbuild_keys.append(k)

        sorted_domain_set = sorted(only_inbuild_keys, key=lambda item : item['input_pos'])

        for s in sorted_domain_set:
            keys_array.append(s['key'])
            desc_array.append(s['desc'])

        super().parse(keys_array, desc_array, domain_values)

    def get_desc(self, key):
        return self.desc_map[key]

    def calculate_category_totals(self):
        self.category_lb_count = {}
        self.domain_lb_count = 0
        curr_cat = ''

        for k, v in self.stats_map.items():
            category = k.split('_')[0]
            if category not in keys_category_info.keys():
                print('Error: Error parsing category')
                return -1

            if keys_category_info[category] != "count":
                continue

            if curr_cat != category:
                curr_cat = category
                self.category_lb_count[category] = v
                self.domain_lb_count += v

    def get_freq(self, val):
         if val:
             return  (self.timestamp / val)

         return 0

    def intervals_extract(self, iterable):
        iterable = sorted(set(iterable))
        iterable.append(iterable[-1] + 2)
        i = 0
        left = iterable[0]
        intervals_list = []

        for i in range(1, len(iterable)):
            if iterable[i] != iterable[i-1]+1:
                intervals_list.append([left, iterable[i-1]])
                left = iterable[i]

        return intervals_list

    def get_cpus_list(self, cpumask):
        cpumask_tokens = cpumask.split(',')
        factor = 0
        cpus = []

        for token in reversed(cpumask_tokens):
            cpumask_bin = "{0:032b}".format(int(token, 16))
            index = 0
            for ones in reversed(cpumask_bin):
                if ones == "1":
                    cpus.append(32 * factor + index)
                index += 1
            factor += 1

        cpu_interval_list = list(self.intervals_extract(cpus))
        interval_list = []

        for interval in cpu_interval_list:
            if interval[0] == interval[1]:
                interval_list.append(interval[0])
            else:
                interval_list.append(str(interval[0]) + "-" + str(interval[1]))

        return str(interval_list)

    def displayCategories(self, out, cmp_data_1=None, cmp_data_2=None, cmp_data_3=None):
        domain_name = self.name

        if domain_name in domain_map:
            domain_name = domain_map[domain_name]

        if domains_show_list:
            templist = [x for x in domains_show_list if domain_name.find(x) != -1]
            if (len(templist) == 0):
                return

        writen(out, banner_width * "-")
        cpulist_str = ''

        if self.cpumask != '0':
            cpulist_str = '  | cpulist:  ' +  self.get_cpus_list(self.cpumask)

        writen(out, "domain:  " + domain_name + cpulist_str)
        writen(out, banner_width * "-")
        last_cat = ''

        for k in keys_ver_map['domain_keys']:
            if domain_stats_show_list:
                templist = [x for x in domain_stats_show_list if k['key'].find(x) != -1]
                if (len(templist) == 0):
                    continue

            drop_stats = False

            if k['is_derived'] == 0:
                v = self.stats_map[k['key']]
            else:
                func_args = []
                for args in k['values']:
                    func_args.append(self.stats_map[args])
                fn = lambda a: eval(k['function'])
                v = fn(func_args)

            category = k['key'].split('_')[0]

            if 'drop_stats' in k.keys():
                drop_stats = True

            if keys_category_info[category] == "skip":
                continue

            if category != last_cat:
                writen(out, "< " + int((banner_width - 20) / 2) * "-" + "  Category:  " + category + ' ' + int((banner_width - 20) / 2) * "-" + " >")
                last_cat = category

            if keys_category_info[category] == "count":
                p1 = percentage(v,self.category_lb_count[category])
                p2 = percentage(v, self.domain_lb_count)
                ext_cmp = []
                for cmp_data in cmp_data_1, cmp_data_2, cmp_data_3:
                    if cmp_data:
                        p3_symb, p3_total = cmp_data
                        p3_symb_open = p3_symb[0]
                        p3_symb_close = p3_symb[1]
                        p3 = percentage(v, p3_total)
                        t_str = '    ' + str(p3_symb_open) + ' ' + f"{p3:10.5f}" + ' ' +str(p3_symb_close)
                        ext_cmp.append(t_str)

            p_str = ''
            p_str += k['desc'] + ' : '

            if float(v).is_integer():
                v = int(v)
                p_str += f"{v:10d}"
            else:
                p_str += f"{v:>10.5f}"

            if not drop_stats and keys_category_info[category] == "count":
                p_str += '    $ ' + f"{self.get_freq(v):10.3f}" +' $'
                for s in ext_cmp:
                    p_str += s

            writen(out, p_str)

class SchedStatNode:
    def __init__(self, ver='unknown', name=None):
        if name:
            self.name = name

        self.version = ver
        self.cpu_info = None
        self.domain_info_list = []

    def addCPUInfo(self, line, ts):
        if line.startswith('cpu') == False:
            print("Error: SchedStatNode.addCPUInfo : invalid string provided")
            return -1

        self.cpu_info = CPUStats(self.version, timestamp=ts)
        self.cpu_info.parse(line)
        return 0

    def checkCPUId(self, cpuid):
        return self.cpu_info.checkCPUId(cpuid)

    def addDomainInfo(self, line, ts):
        if line.startswith('domain') == False:
            print("Error: SchedStatNode.addDomainInfo : invalid string provided")
            return -1

        domain_info = DomainStats(self.version, timestamp=ts)
        domain_info.parse(line)
        self.domain_info_list.append(domain_info)
        return 0

    def numDomainInfo(self):
        return len(self.domain_info_list)

    def display(self):
        self.cpu_info.display()

        for domain_node in self.domain_info_list:
            domain_node.display()

    def calculate_domain_totals(self):
        self.inter_domain_lb_count = 0

        for domain_node in self.domain_info_list:
            domain_node.calculate_category_totals()
            self.inter_domain_lb_count += domain_node.domain_lb_count

    def print_node_info(self, out):
        total_wakeup = self.cpu_info.stats_map['ttwu_count']
        writen(out, "< " + int((banner_width - 20) / 2) * "-" + "  Wakeup info:  " + int((banner_width - 20) / 2) * "-" +  " >")
        val = self.cpu_info.stats_map['l_ttwu_count']
        p1 = percentage(val, total_wakeup)
        name = "CPU"
        writen(out, 'Wakeups on same         ' + f"{name:>10s}" + " \t:  " + f"{val:20d}" + ' \t(  ' + f"{p1:8.5f}" + '  )')

        for domain_node in self.domain_info_list:
            name = domain_node.name
            if name in domain_map:
                name = domain_map[name]

            val = domain_node.stats_map['ttwu_awoke_task_dcsd']
            p1 = percentage(val, total_wakeup)
            writen(out, 'Wakeups on same         ' + f"{name:>10s}" + " \t:  " + f"{val:20d}" + ' \t(  ' + f"{p1:8.5f}" + '  )')

        writen(out, '')

        for domain_node in self.domain_info_list:
            name = domain_node.name

            if name in domain_map:
                name = domain_map[name]

            val = domain_node.stats_map['ttwu_mv_task_cc']
            p1 = percentage(val, total_wakeup)
            writen(out, 'Affine wakeups on same  ' + f"{name:>10s}" + " \t:  " + f"{val:20d}" + ' \t(  ' + f"{p1:8.5f}" + '  )')

    def displayCategories(self, out, extra_param=None):
        next_paren = '<>'

        if not extra_param:
            next_paren = '[]'

        self.cpu_info.displayCategories(out)

        for domain_node in self.domain_info_list:
            domain_node.displayCategories(out, (next_paren, self.inter_domain_lb_count), extra_param)

        self.print_node_info(out)

    def add(self, b):
        self.cpu_info.add(b.cpu_info)

        if (len(self.domain_info_list) != len(b.domain_info_list)):
            print("Error: domain_info_list incompatible")
            return -1

        for dn1, dn2 in zip(self.domain_info_list, b.domain_info_list):
            dn1.add(dn2)

        return 0

    def subtract(self, b):
        self.cpu_info.subtract(b.cpu_info)

        if (len(self.domain_info_list) != len(b.domain_info_list)):
            print("Error: domain_info_list incompatible")
            return -1

        for dn1, dn2 in zip(self.domain_info_list, b.domain_info_list):
            dn1.subtract(dn2)

        return 0

class SchedStatNodes:
    def __init__(self, name=None):
        if name:
            self.name = name

        self.sched_nodes = []
        self.version = 'unknown'

    def parse(self, file_path):
        global keys_ver_map
        sched_file = open(file_path, 'r')
        curr_node = -1

        for line in sched_file:
            tokens = line.split()

            if tokens[0].startswith('version'):
                keys_ver_map = get_keys_ver_map(tokens[1].strip())
                self.version = tokens[1]

            elif tokens[0].startswith('timestamp'):
                self.timestamp = int(tokens[1])

            elif tokens[0].startswith('cpu'):
                if self.version == 'unknown':
                    print('Error: version info missing')
                    return -1

                curr_node += 1
                node = SchedStatNode(self.version)
                self.sched_nodes.append(node)
                self.sched_nodes[curr_node].addCPUInfo(line, self.timestamp)

            elif tokens[0].startswith('domain'):
                if self.version == 'unknown':
                    print('Error: version info missing')
                    return -1
                if curr_node < 0:
                    print("Error: invalid node number")
                    return -1
                self.sched_nodes[curr_node].addDomainInfo(line, self.timestamp)

        return 0

    def getNodeByCPUId(self, cpuid):
        for n in self.sched_nodes:
            if n.checkCPUId(cpuid):
                return n

        return None

    def calculate_node_totals(self, cpuset=None):
        self.inter_nodes_lb_count = 0

        if cpuset:
            self.nodes_to_consider = []

            for i in cpuset:
                n = self.getNodeByCPUId(i)

                if n != None:
                    self.nodes_to_consider.append(n)

        else:
            self.nodes_to_consider = self.sched_nodes

        for node in self.nodes_to_consider:
            node.calculate_domain_totals()
            self.inter_nodes_lb_count += node.inter_domain_lb_count

    def display(self):
        for node in self.sched_nodes:
            node.display()

    def displayCategories(self, out):
        for node in self.nodes_to_consider:
            node.displayCategories(out)

    def add(self, b):
        if len(self.sched_nodes) != len(b.sched_nodes):
            print("Error: sched_nodes incompatible")
            return -1

        for n1, n2 in zip(self.sched_nodes, b.sched_nodes):
            n1.add(n2)

        return 0

    def subtract(self, b):
        if len(self.sched_nodes) != len(b.sched_nodes):
            print("Error: sched_nodes incompatible")
            return -1

        for n1, n2 in zip(self.sched_nodes, b.sched_nodes):
            n1.subtract(n2)

        return 0

def parse_cpuset(cpuset):
    cs_str = cpuset.split(',')
    cs = []

    for s in cs_str:
        if '-' in s:
            s_range = [int(x) for x in s.split('-')]

            for i in range(s_range[0], s_range[1] + 1):
                cs.append(i)
        else:
            cs.append(int(s))

    return cs

def main(before_file, after_file, out_file, domain_map_file=None, cpuset_str=None, cpu_stats_str=None, domain_stats_str=None, domains_str=None, list_cpustats=None, list_domainstats=None, schedstats_ver=None):
    global cpu_stats_show_list
    global domain_stats_show_list
    global domains_show_list

    if list_cpustats:
        if not schedstat_ver:
            print("Error: Passing of schedstat version is must with -v option to list cpustat fileds")
            exit(1)

        temp_key_ver_map = get_key_ver_map(schedstat_ver)

        print(banner_width*"-")
        print("Cpu Stats List")
        print(banner_width*"-")
        for k in keys_ver_map['cpu_keys']:
            if k['is_derived'] == 0:
                key_desc = "%-30s:%s" %(k['key'], k['desc'])
                print(key_desc)

        print(banner_width*"-")
        print("Derived CPU stats list")
        print(banner_width*"-")
        for k in keys_ver_map['cpu_keys']:
            if k['is_derived'] == 1:
                key_desc = "%-30s:%s" %(k['key'], k['desc'])
                print(key_desc)
        exit(0)

    if list_domainstats:
        if not schedstat_ver:
            print("Error: Passing of schedstat version is must with -v option to list domainstat fileds")
            exit(1)

        temp_key_ver_map = get_key_ver_map(schedstat_ver)

        print(banner_width*"-")
        print("Domain stats list")
        print(banner_width*"-")
        for k in keys_ver_map['domain_keys']:
            if k['is_derived'] == 0:
                key_desc = "%-30s:%s" %(k['key'], k['desc'])
                print(key_desc)

        print(banner_width*"-")
        print("Derived domain stats list")
        print(banner_width*"-")
        for k in keys_ver_map['domain_keys']:
            if k['is_derived'] == 1:
                key_desc = "%-30s:%s" %(k['key'], k['desc'])
                print(key_desc)
        exit(0)

    if not before_file or not after_file:
        print("Error: Need at least 2 schedstat files")
        exit(1)

    if domain_map_file:
        domain_map_path = domain_map_file
        for line in open(domain_map_path):
            tokens = line.split(':')
            domain_map[tokens[0]] = tokens[1].strip()

    cpuset = None
    if cpuset_str:
        cpuset = parse_cpuset(cpuset_str)

    if cpu_stats_str:
        cpu_stats_show_list = cpu_stats_str.split(',')

    if domain_stats_str:
        domain_stats_show_list = domain_stats_str.split(',')

    if (out_file != ""):
        out_file_p = open(out_file, "w")
    else:
        out_file_p = sys.stdout

    file1 = before_file
    file1_nodes = SchedStatNodes('file1')
    file1_nodes.parse(file1)

    file2 = after_file
    file2_nodes = SchedStatNodes('file2')
    file2_nodes.parse(file2)

    file2_nodes.subtract(file1_nodes)

    if cpuset:
        nodes_to_consider = []

        for i in cpuset:
            n = file2_nodes.getNodeByCPUId(i)

            if n != None:
                nodes_to_consider.append(n)
    else:
        nodes_to_consider = file2_nodes.sched_nodes

    if cpu_stats_str:
        cpu_stats_show_list = list(map(str.strip, cpu_stats_str.split(',')))

    if domain_stats_str:
        domain_stats_show_list = list(map(str.strip, domain_stats_str.split(',')))

    if domains_str:
        domains_show_list = list(map(str.strip, domains_str.split(',')))

    system_level_desc_str = 'all_cpus (avg)'
    if cpuset:
        system_level_desc_str = cpuset_str + ' (avg)'

    system_level_node = SchedStatNode('system_level_node')
    system_level_node.cpu_info = CPUStats(file2_nodes.sched_nodes[0].cpu_info.version, system_level_desc_str)
    system_level_node.cpu_info.copy_keys(file2_nodes.sched_nodes[0].cpu_info)

    for d in file2_nodes.sched_nodes[0].domain_info_list:
        d_name = d.name

        if d_name in domain_map:
            d_name = domain_map[d_name]

        new_domain = DomainStats(d.version, d_name + ' cpus = ' + system_level_desc_str)
        new_domain.copy_keys(d)
        system_level_node.domain_info_list.append(new_domain)

    for node in nodes_to_consider:
        system_level_node.cpu_info.add(node.cpu_info)

        for i in range(0, len(node.domain_info_list)):
            domain = node.domain_info_list[i]
            system_level_node.domain_info_list[i].add(domain)

    system_level_node.cpu_info.scaler_div(len(nodes_to_consider))

    for i in range(0, len(system_level_node.domain_info_list)):
        system_level_node.domain_info_list[i].scaler_div(len(nodes_to_consider))

    system_level_node.calculate_domain_totals()
    file2_nodes.calculate_node_totals(cpuset)

    writen(out_file_p, help_text)
    writen(out_file_p, banner_width * "-")
    writen(out_file_p, "System level info:")
    writen(out_file_p, banner_width * "-")
    time_elapsed = "%21s" %(str(file2_nodes.timestamp - file1_nodes.timestamp))
    writen(out_file_p, "Time elapsed (in jiffies)                                  :" + time_elapsed)

    system_level_node.displayCategories(out_file_p)

    writen(out_file_p, banner_width * "-")
    writen(out_file_p, "CPU level info:")
    writen(out_file_p, banner_width * "-")

    file2_nodes.displayCategories(out_file_p)

if __name__ == "__main__":
    parser = OptionParser()
    parser.add_option("-b", "--before", dest="before_file", type=str, help="schedstat before file")
    parser.add_option("-a", "--after", dest="after_file", type=str, help="schedstat after file")
    parser.add_option("-d", "--domainmap", dest="domain_map_file", type=str, help="domain map file")
    parser.add_option("-o", "--out", dest="out_file", type=str, help="output file name. Default: stdout", default="")
    parser.add_option("-l", "--cpulist", dest="cpu_list", type=str, help="list of CPUs for which schedstats need to be printed. Default: All CPUs")
    parser.add_option("-s", "--cpustats", dest="cpu_stats_str", type=str, help="Comma separated list of CPU statistics to print")
    parser.add_option("-g", "--domainstats", dest="domain_stats_str", type=str, help="Comma separated list of DOMAIN statistics to print")
    parser.add_option("-n", "--domains", dest="domains_str", type=str, help="Comma separated list of DOMAINs whose details are to be printed (Default : All Domains)")
    parser.add_option("-C", "--list-cpustats", dest="list_cpustats", action="store_true", default=False,  help="list of available cpu statistics (Passing schedstat version is must)")
    parser.add_option("-D", "--list-domainstats", dest="list_domainstats", action="store_true", default=False,  help="list of available domainstats (Passing schedstat version is must)")
    parser.add_option("-v", "--schedstat-version", dest="schedstat_ver", type=int, help="schedstat version")

    (options, args) = parser.parse_args()

    main(options.before_file, options.after_file, options.out_file, options.domain_map_file, options.cpu_list, options.cpu_stats_str, options.domain_stats_str, options.domains_str, options.list_cpustats, options.list_domainstats, options.schedstat_ver)
