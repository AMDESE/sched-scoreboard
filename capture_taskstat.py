#!/usr/bin/python3

import os
import sys
import shutil

tasks = os.listdir("/proc")

for task in tasks:
    if not task.isdigit():
        continue

    task_dir = os.path.join("/proc", task)
    thread_dir = os.path.join(task_dir, "task")
    threads = os.listdir(thread_dir)
    for thread in threads:
        if not thread.isdigit():
            continue

        source = os.path.join(thread_dir, thread, "sched")
        dest = os.path.join(sys.argv[1], thread)
        shutil.copyfile(source, dest)
