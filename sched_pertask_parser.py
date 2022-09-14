#!/usr/bin/python3
import os
import sys
from optparse import OptionParser

stats_map = {
    "exec_start"                  :"ms",
    "vruntime"                    :"ms",
    "sum_exec_runtime"            :"ms",
    "nr_migrations"               :"count",
    "sum_sleep_runtime"           :"ms",
    "sum_block_runtime"           :"ms",
    "wait_start"                  :"ms",
    "sleep_start"                 :"ms",
    "block_start"                 :"ms",
    "sleep_max"                   :"ms",
    "block_max"                   :"ms",
    "exec_max"                    :"ms",
    "slice_max"                   :"ms",
    "wait_max"                    :"ms",
    "wait_sum"                    :"ms",
    "wait_count"                  :"count",
    "iowait_sum"                  :"ms",
    "iowait_count"                :"count",
    "nr_migrations_cold"          :"count",
    "nr_failed_migrations_affine" :"count",
    "nr_failed_migrations_running":"count",
    "nr_failed_migrations_hot"    :"count",
    "nr_forced_migrations"        :"count",
    "nr_wakeups"                  :"count",
    "nr_wakeups_sync"             :"count",
    "nr_wakeups_migrate"          :"count",
    "nr_wakeups_local"            :"count",
    "nr_wakeups_remote"           :"count",
    "nr_wakeups_affine"           :"count",
    "nr_wakeups_affine_attempts"  :"count",
    "nr_wakeups_passive"          :"count",
    "nr_wakeups_idle"             :"count",
    "core_forceidle_sum"          :"ms",
    "nr_voluntary_switches"       :"count",
    "nr_involuntary_switches"     :"count",
    "weight"                      :"count",
    "load_sum"                    :"count",
    "runnable_sum"                :"count",
    "util_sum"                    :"count",
    "load_avg"                    :"count",
    "runnable_avg"                :"count",
    "util_avg"                    :"count",
    "last_update_time"            :"count",
    "ewma"                        :"count",
    "policy"                      :"count",
    "prio"                        :"count",
    "numa_pages_migrated"         :"count",
    "numa_preferred_nid"          :"count",
    "total_numa_faults"           :"count",
}

def compute_nr_switches(voluntary_switches, involuntary_switches):
    return int(voluntary_switches) + int(involuntary_switches)

def compute_avg_atom(sum_exec_runtime, nr_switches):
    switches = int(nr_switches)
    if switches == 0:
        return "-1"
    return "%1.6f" %(float(sum_exec_runtime)/switches)

def compute_avg_per_cpu(sum_exec_runtime, nr_migrations):
    migrations = int(nr_migrations)
    if migrations == 0:
        return "-1"
    return "%1.6f" %(float(sum_exec_runtime)/migrations)

derived_stats_map = {
    "nr_switches"  :"count",
    "avg_atom"     :"ms",
    "avg_per_cpu"  :"ms",
}

tasks = {};

class Task:
    def __init__(self, taskpid):
        self.taskpid = taskpid
        self.info = {}
        self.stats = {}

def split_line(s):
    stripped_s = s.strip()
    map_key_start_index = stripped_s.strip().index('[')
    map_key_end_index = stripped_s.index(']')
    map_value_start_index = stripped_s.index(':')

    key = stripped_s[:map_key_start_index].replace('@', '')
    taskpid = stripped_s[map_key_start_index + 1: map_key_end_index].strip()
    value = stripped_s[map_value_start_index + 1:].strip()

    return (key, taskpid, value)

def get_task(taskpid):
    if taskpid not in tasks:
        tasks[taskpid] = Task(taskpid);
    return tasks[taskpid]

def parse_data(lines):
    for line in lines:
        if "Attaching" in line:
            continue
        elif "@" in line:
            (key, taskpid, value) = split_line(line)
            tasks[taskpid] = get_task(taskpid)
            if key == "comm":
                tasks[taskpid].info[key] = value
            else:
                tasks[taskpid].stats[key] = value

def update_derived_stats():
    for taskpid, task in tasks.items():
        nr_switches_value = 0
        if 'nr_voluntary_switches' in task.stats and 'nr_involuntary_switches' in task.stats:
            voluntary_switches = task.stats['nr_voluntary_switches']
            involuntary_switches = task.stats['nr_involuntary_switches']
            nr_switches_value = compute_nr_switches(voluntary_switches, involuntary_switches)
            task.stats.update({"nr_switches": str(nr_switches_value)})

        if 'sum_exec_runtime' in task.stats:
            sum_exec_runtime = task.stats['sum_exec_runtime']

            avg_atom = compute_avg_atom(sum_exec_runtime, nr_switches_value)
            task.stats.update({"avg_atom": avg_atom})

            if 'nr_migrations' in task.stats:
                nr_migrations = task.stats['nr_migrations']
                avg_per_cpu = compute_avg_per_cpu(sum_exec_runtime, nr_migrations)
                task.stats.update({"avg_per_cpu": avg_per_cpu})

def print_data(taskstat_workload_path):
    import taskstat_fields
    for taskpid, task in tasks.items():
        output_file = taskstat_workload_path +"/"+ taskpid
        fout = open(output_file, "w")
        fout.write("%s %s\n" %(task.info["comm"], taskpid))
        fout.write("-------------------------------------------------------------------\n")
        for stat, value in task.stats.items():
            if stat in taskstat_fields.stats_map.keys():
                name = taskstat_fields.stats_map[stat]
                unit = ""
                if stat in stats_map.keys():
                    unit = stats_map[stat]
                elif stat in derived_stats_map.keys():
                    unit = derived_stats_map[stat]
                if unit == "ms":
                    pvalue = str(float(value) / 1000000)
                else:
                    pvalue = value
                fout.write("%-47s:%21s\n" %(name, pvalue))
        fout.close()

if __name__ == "__main__":
    parser = OptionParser()
    parser.add_option("-d", "--logdir", dest="log_dir", type=str, help="path to logdir")

    (options, args) = parser.parse_args()

    logdir = options.log_dir

    sys.path.insert(0, logdir)

    bpftrace_output_path = os.path.join(logdir, "pertask.bpftrace.output")
    fin = open(bpftrace_output_path, "r")
    lines = fin.readlines()
    fin.close

    taskstat_workload_path = os.path.join(logdir, "taskstat-workload")
    os.makedirs(taskstat_workload_path, exist_ok = True)

    parse_data(lines)
    update_derived_stats()
    print_data(taskstat_workload_path)
