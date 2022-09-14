import os
import sys

ignore = {
    "uclamp.min",
    "uclamp.max",
    "effective uclamp.min",
    "effective uclamp.max",
    "clock-delta",
    "mm->numa_scan_seq",
    "se.avg.util_est.enqueued"
}

derived = {
    "avg_atom",
    "avg_per_cpu",
    "nr_switches"
}

task_struct = {
    "prio",
    "policy",
    "numa_pages_migrated",
    "numa_preferred_nid",
    "total_numa_faults"
}

replace = {
    "nr_voluntary_switches"     :"nvcsw",
    "nr_involuntary_switches"   :"nivcsw"
}

start = [
        "tracepoint:sched:sched_process_exit {",
    "\tif(strncmp(comm, \"sched-scoreboar\", 15) != 0)",
    "\t{",
    "\t\t$cur_task = (struct task_struct *)curtask;",
    "\t\t@comm[$cur_task->pid] = comm;",
]

def parse_keys(lines):
    scriptdir = sys.argv[1]
    bpftrace_script_path = os.path.join(scriptdir, "sched-pertask-stat.bt")
    fout = open(bpftrace_script_path, "w")

    bpftrace_stats_map = os.path.join(scriptdir, "taskstat_fields.py")
    fout1 = open(bpftrace_stats_map, "w")

    fout1.write("stats_map = {\n")

    fields = []
    for line in lines:
        if ":" in line:
            fields.append(line.split(":")[0].strip())

    for s in start:
        fout.write(s+"\n")

    for fieldname in fields:
        field = fieldname
        key = fieldname
        if fieldname not in ignore:
            if fieldname in derived:
                fout1.write("\""+fieldname+"\":\""+fieldname+"\",\n")
            else:
                if "." in fieldname or fieldname in task_struct or fieldname in replace:
                    if "." in fieldname:
                        split_key = fieldname.split(".")
                        key = split_key[-1]
                    elif fieldname in replace.keys():
                        field = replace[fieldname]
                    field = "$cur_task->"+field
                else:
                    field = "$cur_task->stats."+field
                fout.write("\t\t@" + key + "[$cur_task->pid] = " + field + ";\n" )
                fout1.write("\""+key+"\":\""+fieldname+"\",\n")

    fout.write("\t}\n}\n")
    fout1.write("}\n")
    fout.close()
    fout1.close()

if __name__ == "__main__":
    fin = open("/proc/1/sched", "r")
    lines = fin.readlines()[2:-3]
    parse_keys(lines)
    fin.close()
