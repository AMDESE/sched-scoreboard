#!/usr/bin/python3
import os
import sys
import json
import sched_taskstats_parser
from optparse import OptionParser

stats_map = {
    "exec_start"                     :"first",
    "vruntime"                       :"last",
    "sum_exec_runtime"               :"diff",
    "nr_migrations"                  :"diff",
    "sum_sleep_runtime"              :"diff",
    "sum_block_runtime"              :"diff",
    "wait_start"                     :"last",
    "sleep_start"                    :"last",
    "block_start"                    :"last",
    "sleep_max"                      :"last",
    "block_max"                      :"last",
    "exec_max"                       :"last",
    "slice_max"                      :"last",
    "wait_max"                       :"last",
    "wait_sum"                       :"diff",
    "wait_count"                     :"diff",
    "iowait_sum"                     :"diff",
    "iowait_count"                   :"diff",
    "nr_migrations_cold"             :"diff",
    "nr_failed_migrations_affine"    :"diff",
    "nr_failed_migrations_running"   :"diff",
    "nr_failed_migrations_hot"       :"diff",
    "nr_forced_migrations"           :"diff",
    "nr_wakeups"                     :"diff",
    "nr_wakeups_sync"                :"diff",
    "nr_wakeups_migrate"             :"diff",
    "nr_wakeups_local"               :"diff",
    "nr_wakeups_remote"              :"diff",
    "nr_wakeups_affine"              :"diff",
    "nr_wakeups_affine_attempts"     :"diff",
    "nr_wakeups_passive"             :"diff",
    "nr_wakeups_idle"                :"diff",
    "avg_atom"                       :"last",
    "avg_per_cpu"                    :"last",
    "core_forceidle_sum"             :"diff",
    "nr_switches"                    :"diff",
    "nr_voluntary_switches"          :"diff",
    "nr_involuntary_switches"        :"diff",
    "weight"                         :"last",
    "dur_avg"                        :"last",
    "load_sum"                       :"last",
    "runnable_sum"                   :"last",
    "util_sum"                       :"last",
    "load_avg"                       :"last",
    "runnable_avg"                   :"last",
    "util_avg"                       :"last",
    "last_update_time"               :"last",
    "ewma"                           :"last",
    "policy"                         :"last",
    "prio"                           :"last",
    "numa_pages_migrated"            :"diff",
    "numa_preferred_nid"             :"last",
    "total_numa_faults"              :"diff"
}

def compute_sum_idle_runtime(sum_sleep_runtime, sum_block_runtime):
    sum_block_runtime_value = float(sum_block_runtime)
    if sum_block_runtime_value == 0.0:
        return "-1"
    return str(float(sum_sleep_runtime)/sum_block_runtime_value)

def compute_avg_idle_runtime(sum_idle_runtime, nr_voluntary_switches):
    nr_voluntary_switches_value = float(nr_voluntary_switches)
    if nr_voluntary_switches_value == 0:
        return "-1"
    return str(float(sum_idle_runtime)/nr_voluntary_switches_value)

def compute_avg_wait_time(wait_sum, wait_count):
    wait_count_value = float(wait_count)
    if wait_count_value == 0.0:
        return "-1"
    return str(float(wait_sum)/wait_count_value)

class Task:
    def __init__(self, taskpid, comm):
        self.taskpid = taskpid
        self.comm = comm
        self.stats = {}

def diff(value1, value2):
    v1 = float(value1.strip())
    v2 = float(value2.strip())
    return str(v2-v1)

def last(value1, value2):
    return value2

def first(value1, value2):
    return value1

def split_line(line):
    first_split = line.split(':')
    key = first_split[0].strip()
    value = first_split[1].strip()
    return (key, value)

def parse_data(lines):
    import taskstat_fields
    stats = {}
    for line in lines:
        if ":" in line:
            (key, value) = split_line(line)
            for stat_key in taskstat_fields.stats_map.keys():
                if key.endswith(stat_key):
                    stats[stat_key] = value
                    break

    return stats

def update_derived_stats(tasks):
    for taskpid, task in tasks.items():
        if 'sum_sleep_runtime' in task.stats and 'sum_block_runtime' in task.stats:
            sum_sleep_runtime = task.stats['sum_sleep_runtime']
            sum_block_runtime = task.stats['sum_block_runtime']
            sum_idle_runtime = compute_sum_idle_runtime(sum_sleep_runtime, sum_block_runtime)
            task.stats.update({'sum_idle_runtime': sum_idle_runtime})
            if 'nr_voluntary_switches' in task.stats:
                nr_voluntary_switches = task.stats['nr_voluntary_switches']
                avg_idle_runtime = compute_avg_idle_runtime(sum_idle_runtime,  nr_voluntary_switches)
                task.stats.update({'avg_idle_runtime': avg_idle_runtime})
        if 'wait_sum' in task.stats and 'wait_count' in task.stats:
            wait_sum = task.stats['wait_sum']
            wait_count = task.stats['wait_count']
            avg_wait_time = compute_avg_wait_time(wait_sum, wait_count)
            task.stats.update({'avg_wait_time': avg_wait_time})

def updateTaskReport(taskpid, fin1, fin2 = None):
    line1 = fin1.readline()
    comm = line1.split()[0]
    lines1 = fin1.readlines()[0:]

    task = Task(taskpid, comm)
    task.stats = parse_data(lines1)

    if fin2 != None:
        lines2 = fin2.readlines()[1:]
        stats2 = parse_data(lines2)
        for key, value in stats2.items():
            if key in stats_map:
                pvalue = func_map[stats_map[key]](task.stats[key], value)
                task.stats.update({key: pvalue})

    return task

func_map = {
    "first" :   first,
    "last"  :   last,
    "diff"  :   diff
}

def append_migrations_counts(tasks, fin_migrations):
    keys = []
    migrations = {}

    for line in fin_migrations.readlines():
        tokens = line.split(',')
        if line.startswith("pid"):
            keys = tokens[1:]
        else:
            key = tokens[0]
            i = 0
            counts = {}
            for value in tokens[1:]:
                counts.update({keys[i].strip() : value.strip()})
                i += 1
            migrations.update({key.strip() : counts})

    for task in tasks.keys():
        if task in migrations.keys():
            for domain, count in migrations[task].items():
                tasks[task].stats.update({domain: count})
        else:
            for key in keys:
                tasks[task].stats.update({key.strip(): 0})

def update_to_json(tasks, taskstat_workload_copy, departed_tasks_flag):
     fout = open(logdir+"/report.json", "w")

     for key, value in tasks.items():
         if departed_tasks_flag and value.taskpid not in taskstat_workload_copy:
             continue
         k = "%s-%s" %(value.comm, value.taskpid)
         dict_task = {k:value.stats}
         json_object = json.dumps(dict_task, indent = 4)
         fout.write(json_object)
     fout.close()

def update_to_csv(tasks, taskstat_workload_copy, departed_tasks_flag):
    fout = open(logdir+"/report.csv", "w")

    print_header = False
    for taskpid, task in tasks.items():
        if not print_header:
            fout.write("pid,comm")
            for stat in sorted(task.stats.keys()):
                fout.write(",%s" %(stat.strip(":").strip()))
            fout.write("\n")
            print_header = True
        print_line = "{},{}".format(taskpid, task.comm.replace(",", "_"))
        if departed_tasks_flag and taskpid not in taskstat_workload_copy:
            continue
        for stat in sorted(task.stats.keys()):
            value = task.stats[stat]
            print_line += "," + str(value)
        fout.write("%s\n" %(print_line))
    fout.close()

if __name__ == "__main__":
    parser = OptionParser()
    parser.add_option("-d", "--logdir", dest="log_dir", type=str, help="path to logdir")
    parser.add_option("-D", "--departed-tasks", dest="departed_tasks", action="store_true", default=False, help="Generate report for only those tasks that exited during monitoring  period (Default complete report)")

    (options, args) = parser.parse_args()

    logdir = options.log_dir
    taskstat_before = os.listdir(logdir+"/taskstat-before")
    taskstat_workload = os.listdir(logdir+"/taskstat-workload")
    taskstat_after = os.listdir(logdir+"/taskstat-after")

    sys.path.insert(0, logdir)

    taskstat_workload_copy = taskstat_workload
    tasks = {}

    for file in taskstat_before:
        fin1 = open(os.path.join(logdir, "taskstat-before", file), "r")
        fin2 = None
        if file in taskstat_after:
            fin2 = open(os.path.join(logdir, "taskstat-after", file), "r")
            taskstat_after.remove(file)
        elif file in taskstat_workload:
            fin2 = open(os.path.join(logdir, "taskstat-workload", file), "r")
            taskstat_workload.remove(file)
        tasks[file] = updateTaskReport(file, fin1, fin2)
        fin1.close()
        if fin2 != None:
            fin2.close()

    for file in taskstat_workload:
        fin = open(os.path.join(logdir, "taskstat-workload", file), "r")
        tasks[file] = updateTaskReport(file, fin)
        fin.close()

    for file in taskstat_after:
        fin = open(os.path.join(logdir, "taskstat-after", file), "r")
        tasks[file] = updateTaskReport(file, fin)
        fin.close()

    update_derived_stats(tasks)

    departed_tasks_flag = False
    if options.departed_tasks:
        departed_tasks_flag = True

    if os.path.exists(logdir+"/migrations.csv"):
        fin_migrations = open(logdir+"/migrations.csv", "r")
        append_migrations_counts(tasks, fin_migrations)
        fin_migrations.close()
    else:
        sched_taskstats_parser.get_topology(logdir)

    update_to_json(tasks, taskstat_workload_copy, departed_tasks_flag)
    update_to_csv(tasks, taskstat_workload_copy, departed_tasks_flag)
