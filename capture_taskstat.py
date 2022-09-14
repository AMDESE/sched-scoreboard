#!/usr/bin/python3

import os
import sys
import shutil

tasks = os.listdir("/proc")

for task in tasks:
    if task.isdigit():
        source = os.path.join("/proc", task, "sched")
        dest = os.path.join(sys.argv[1], task)
        shutil.copyfile(source, dest)
