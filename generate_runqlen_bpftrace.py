import sys

start = [
    "BEGIN\n",
    "{\n",
    "\t$i = 0;\n",
    "\tprintf(\"[%12s],\", \"Timestamp\");\n",
]

mid1 = [
    "\t\tprintf(\"CPU%3d,\", $i);\n",
    "\t\t$i = $i + 1;\n",
    "\t}\n",
    "\tprintf(\"\\n\");\n",
    "}\n",
    "\n",
    "kprobe:scheduler_tick\n",
    "{\n",
    "\t@runqlen[curtask->wake_cpu] =  curtask->se.cfs_rq->rq->nr_running;\n",
    "}\n",
    "\n",
    "tracepoint:power:cpu_idle\n",
    "{\n",
    "\t@runqlen[curtask->wake_cpu] = 0;\n",
    "}\n",
    "\n",
]

mid2 = [
    "{\n",
    "\t$i = 0;\n"
    "\tprintf(\"[%12lld],\", elapsed);\n",
]

end = [
    "\t\tprintf(\"%3d,\", @runqlen[$i]);\n",
    "\t\t$i = $i + 1;\n",
    "\t}\n",
    "\tprintf(\"\\n\");\n",
    "}\n",
    "\n",
    "END\n",
    "{\n",
    "\tclear(@runqlen);\n",
    "}\n"
]

if __name__ == "__main__":
    scriptdir = sys.argv[1]
    nr_cpus = int(sys.argv[2])
    profile_time = int(sys.argv[3])
    profile_hz = 1000//profile_time

    fout = open(scriptdir+"/runqlen.bt", "w")

    condition = "\t%s%d%s" % ("while ($i < ",nr_cpus,") \n\t{\n")
    interval_probe = "%s%d\n" %("interval:hz:", profile_hz)

    for s in start:
        fout.write(s)

    fout.write(condition)

    for s in mid1:
        fout.write(s)

    fout.write(interval_probe)

    for s in mid2:
        fout.write(s)

    fout.write(condition)

    for s in end:
        fout.write(s)

    fout.close()
