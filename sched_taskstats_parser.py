#!/usr/bin/python3
# SPDX-License-Identifer: GPL-2.0-only
# Copyright (C) 2022 Advanced Micro Devices, Inc.
#
# Authors: Wyes Karny <wyes.karny@amd.com>,
#          Gautham R Shenoy <gautham.shenoy@amd.com>,
#          K Prateek Nayak <kprateek.nayak@amd.com>

import json
import operator
from optparse import OptionParser

topology = {}
domain_names = {}

class Task:
    def __init__(self, pid):
        self.pid = pid;
        self.wakeup_migrations = {};
        self.lb_migrations = {};
        self.wakers  = {};
        self.wakees = {};

        for domain in topology["cpu0"].keys():
            self.wakeup_migrations[domain] = 0
            self.lb_migrations[domain] = 0

    def update_migration_count(self, orig_cpu, dest_cpu, is_waking, count):
        orig_cpu_key = "%s%s" %("cpu",orig_cpu)

        for domain in topology[orig_cpu_key].keys():
            if dest_cpu in topology[orig_cpu_key][domain]:
                if is_waking == 0:
                    self.lb_migrations.update({domain:count+self.lb_migrations[domain]})
                else:
                    self.wakeup_migrations.update({domain:count+self.wakeup_migrations[domain]})

    def __print_dict_descending(self, opname, dictobj):
        sorted_dict = dict(sorted(dictobj.items(), key=operator.itemgetter(1), reverse=True))
        for othername in sorted_dict.keys():
            print("%25s %11s %25s , %9d times" %(self.pid, opname, othername, sorted_dict[othername]))

    def print_wakers(self):
        self.__print_dict_descending("woken up by", self.wakers)

    def print_wakees(self):
        self.__print_dict_descending("woke up", self.wakees)

    def print_migration_count(self):
        wakeup_counts = ""
        for domain in sorted(self.wakeup_migrations.keys()):
            wakeup_counts = wakeup_counts + str(self.wakeup_migrations[domain]) +", "

        lb_counts = ""
        for domain in sorted(self.lb_migrations.keys()):
             lb_counts = lb_counts + str(self.lb_migrations[domain]) +", "

        migrations = self.pid + " ," + wakeup_counts + lb_counts
        migrations = migrations.rstrip(migrations[-1])
        return migrations

    def print_details(self):
        print("--------------- %25s --------------------" %(self.pid))

        self.print_wakers()
        print("")
        self.print_wakees()
        print("")

tasks = {};

def get_task(taskpid):
    if taskpid not in tasks:
        tasks[taskpid] = Task(taskpid);

    return tasks[taskpid]

def parse_migration(taskpid, orig_cpu, dest_cpu, is_waking, count):
    task = get_task(taskpid)

    task.update_migration_count(orig_cpu, dest_cpu, is_waking, count)

def split_line(s):
    first_split = s.split('[')
    second_split=first_split[1].split(']')
    inner_split = second_split[0].split(',')
    outer_split = second_split[1].split(':')

    taskpid =  inner_split[0].strip()
    orig_cpu = inner_split[1].strip()
    dest_cpu  = inner_split[2].strip()
    is_waking = int(inner_split[3].strip())
    count = int(outer_split[1].strip())

    return (taskpid, orig_cpu, dest_cpu, is_waking, count)

def split_waking_graph_lines(s):
    first_split = s.split('[')
    second_split=first_split[1].split(']')
    inner_split = second_split[0].split(',')
    outer_split = second_split[1].split(':')

    waker_name = inner_split[0].strip()
    waker_pid  = inner_split[1].strip()

    wakee_name = inner_split[2].strip()
    wakee_pid  = inner_split[3].strip()

    count = int(outer_split[1].strip())

    waker = get_task(waker_pid)
    wakee = get_task(wakee_pid)

    return (waker, wakee, count)

def parse_waking_graph(s):
    (waker, wakee, count) = split_waking_graph_lines(s)
    waker.wakees[wakee.pid] = count
    wakee.wakers[waker.pid] = count

def parse(s):
    if "waking_graph" in s:
        return parse_waking_graph(s)

    if "@migrations" in s:
        (taskpid, orig_cpu, dest_cpu, is_waking, count) = split_line(s)
        parse_migration(taskpid, orig_cpu, dest_cpu, is_waking, count)

def intervals_extract(iterable):
    iterable = sorted(set(iterable))
    iterable.append(iterable[-1]+2)
    i = 0
    left = iterable[0]
    intervals_list = []
    for i in range(1, len(iterable)):
        if iterable[i] != iterable[i-1]+1:
            intervals_list.append([left, iterable[i-1]])
            left = iterable[i]
    return intervals_list

def intervals(cpu_interval_list):
    interval_list = []
    for interval in cpu_interval_list:
        if interval[0] == interval[1]:
            interval_list.append(interval[0])
        else:
            interval_list.append(str(interval[0])+"-"+str(interval[1]))
    return str(interval_list)

def get_topology(logdir):
    fin = open(logdir+"/schedstat-before", "r")
    fout = open(logdir+"/topology-info", "w")
    fin_domain_map = open(logdir+"/domain_map.cfg", "r")

    domain_map = {}
    domain_name_seen = {}
    for line in fin_domain_map.readlines():
        tokens = line.split(':')
        domain_name = tokens[1].strip()
        if domain_name in domain_name_seen:
            domain_name_seen[domain_name] += 1
            domain_map[tokens[0]] = "%s%d" % (domain_name, domain_name_seen[domain_name])
        else:
            domain_name_seen.update({domain_name:1})
            domain_map[tokens[0]] = domain_name

    top = {}
    domains = {}
    domain_interval = {}
    cur_cpu = str

    for line in fin.readlines():
        tokens = line.split()

        if tokens[0].startswith('cpu'):
            cur_cpu = tokens[0]
            domains = {}
            domain_interval = {}

        elif tokens[0].startswith('domain'):

            cpumask_tokens = tokens[1].split(',')
            factor = 0
            cpus = []

            for token in reversed(cpumask_tokens):
                cpumask_bin = "{0:032b}".format(int(token, 16))

                index = 0
                for ones in reversed(cpumask_bin):
                    if ones == "1":
                        cpus.append(32*factor+index)
                    index += 1

                factor += 1
            domains.update({domain_map[tokens[0]]:str(cpus)})
            domain_interval.update({domain_map[tokens[0]]:str(intervals(list(intervals_extract(cpus))))})
            top.update({cur_cpu:domain_interval})
            topology.update({cur_cpu: domains})

    for cpu_info in top.items():
        json_object = json.dumps(cpu_info, indent = 4)
        fout.write(json_object)

    fout.close()
    fin.close()

if __name__ == "__main__":
    parser = OptionParser()
    parser.add_option("-d", "--logdir", dest="log_dir", type=str, help="path to logdir")

    (options, args) = parser.parse_args()

    logdir=options.log_dir

    f = open(logdir+"/sched-category.bpftrace.output", "r")
    lines = f.readlines()
    f.close()

    get_topology(logdir)

    fout = open(logdir+"/migrations.csv", "w")
    migrations_header = "pid ,"

    wp_header = ""
    lb_header = ""
    for domain in topology["cpu0"].keys():
        wp_header = wp_header + domain + "_wakeup_migrations ,"
        lb_header = lb_header + domain + "_load_balance_migrations ,"

    migrations_header = migrations_header + wp_header + lb_header
    fout.write(migrations_header + "\n" )

    for line in lines:
        parse(line)

    for key in sorted(tasks.keys()):
        task = tasks[key]
        fout.write(task.print_migration_count() + "\n")
        task.print_details()

    fout.close()
