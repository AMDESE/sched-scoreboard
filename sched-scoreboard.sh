#!/bin/bash
# SPDX-License-Identifer: GPL-2.0-only
# Copyright (C) 2022 Advanced Micro Devices, Inc.
#
# Authors: Wyes Karny <wyes.karny@amd.com>,
#          Gautham R Shenoy <gautham.shenoy@amd.com>,
#          K Prateek Nayak <kprateek.nayak@amd.com>,
#          Swapnil Sapkal <swapnil.sapkal@amd.com>,

POSITIONAL_ARGS=()

TIMESTAMP=`date +%Y-%m-%d-%H-%M-%S`
LOGDIR=/tmp/sched-scoreboard-$TIMESTAMP
command="sleep 1"

TASK_STATS_DISABLE=0
TASK_STATS_FORCE_ENABLE=0
RQLEN_ENABLE=0
MIGRATION_STATS_ENABLE=0

DEPARTED_TASKS_ONLY=0
RQLEN_PROFILE_TIME=100

DEFAULT_MAX_PIDS=65536
BPF_NEEDED=1
MAX_PIDS=$DEFAULT_MAX_PIDS

while [[ $# -gt 0 ]]; do
    case $1 in
        -l | --logdir)
            LOGDIR="$2"
            shift # past argument
            shift # past value
            ;;
        -D | --task-disable)
            BPF_NEEDED=0
            TASK_STATS_DISABLE=1
            shift
            ;;
        -e | --task-enable)
            BPF_NEEDED=1
            TASK_STATS_FORCE_ENABLE=1
            shift
            ;;
        -q | --rqlen-enable)
            BPF_NEEDED=1
            RQLEN_ENABLE=1
            shift
            ;;
        -m | --migrate-enable)
            BPF_NEEDED=1
            MIGRATION_STATS_ENABLE=1
            shift
            ;;
        -d | --departed-tasks)
            DEPARTED_TASKS_ONLY=1
            shift
            ;;
        -t | --rqlen-profile-time)
            RQLEN_PROFILE_TIME="$2"
            shift
            shift
            ;;
        -p | --max-pids)
            MAX_PIDS="$2"
            shift
            shift
            ;;
        -W | --workload)
            shift
            POSITIONAL_ARGS=$@ # save positional arg
            break
            ;;
        -h | --help | *)
            echo ""
            echo "Usage : $0 [options] -W command"
            echo "where options are:"
            echo " -l | --logdir               : The directory where logs should be stored"
            echo " -h | --help                 : Will print this message"
            echo " -D | --task-disable         : Disable collection of per-task statistics. (Default is enabled)"
            echo " -e | --task-enable          : Enable collection of per-task statistics even if config BTF option is not sure"
            echo " -q | --rqlen-enable         : Collect per-cpu runqlen data (Default is disabled)"
            echo " -m | --migrate-enable       : Collect the task migration data (Default is disabled)"
            echo " -d | --departed-tasks       : Generate report for only those tasks that exited during monitoring period (Default complete report)"
            echo " -t | --rqlen-profile-time   : Time in ms for capturing of runq length (Default 100 ms)"
            echo " -p | --max-pids             : Maximum number of PIDs that may be active during the period of monitoring (Default $DEFAULT_MAX_PIDS)"
            echo " -W | --workload             : Workload"
            exit 1
            ;;
        esac
done

set -- "${POSITIONAL_ARGS}" # restore positional parameters

command=`echo ${POSITIONAL_ARGS}`
echo "LOGDIR  = ${LOGDIR}"

if [ "$command" == "" ]
then
    command="sleep 10"
    echo "No command specified. Executing $command"
else
    echo "command to be executed : $command"
fi

SCRIPTDIR=`dirname "$0"`;

mkdir -p $LOGDIR

if [ -d /sys/kernel/debug/sched/domains/cpu0 ]
then
    grep . /sys/kernel/debug/sched/domains/cpu0/domain*/name | sed -e 's/\/sys\/kernel\/debug\/sched\/domains\/cpu0\///g' | sed -e 's/\/name//g' > $LOGDIR/domain_map.cfg
elif [ -d /proc/sys/kernel/sched_domain/cpu0 ]
then
    grep . /proc/sys/kernel/sched_domain/cpu0/domain*/name | sed -e 's/\/proc\/sys\/kernel\/sched_domain\/cpu0\///g' | sed -e 's/\/name//g' > $LOGDIR/domain_map.cfg
fi

TIMESTAMP=`date +%Y-%m-%d\ %H:%M:%S`
echo "[$TIMESTAMP] Snapshotting schedstats before..."
old_schedstats=`cat /proc/sys/kernel/sched_schedstats`
echo 1 > /proc/sys/kernel/sched_schedstats
cat /proc/schedstat > $LOGDIR/schedstat-before

if  [ $TASK_STATS_DISABLE == 0 ]
then
    TIMESTAMP=`date +%Y-%m-%d\ %H:%M:%S`
    echo "[$TIMESTAMP] Snapshotting taskstats before..."
    mkdir $LOGDIR/taskstat-before
    $SCRIPTDIR/capture_taskstat.py $LOGDIR/taskstat-before
fi

if [ $BPF_NEEDED == 1 ]
then
    export BPFTRACE_MAP_KEYS_MAX=$MAX_PIDS

    command -v bpftrace >/dev/null 2>&1 && ln -s $(which bpftrace) bpftrace
    if [ ! -f $SCRIPTDIR/bpftrace ]
    then
	    echo "Downloading bpftrace v0.16.0...."
	    wget https://github.com/iovisor/bpftrace/releases/download/v0.16.0/bpftrace
	    mv bpftrace $SCRIPTDIR
	    chmod +x $SCRIPTDIR/bpftrace
    fi

    if [ $TASK_STATS_DISABLE == 0 ]
    then
        VERSION=`uname -r`

        ORIG_CONFIG_FILE=""
        CONFIG_FILE=""
        if [ -f /proc/config.gz ]
        then
            cp /proc/config.gz $LOGDIR
            cd $LOGDIR
            gunzip config.gz
            mv -f config config-$VERSION
            CONFIG_FILE=$LOGDIR/config-$VERSION
            ORIG_CONFIG_FILE="/proc/config.gz"
        elif [ -f /boot/config-$VERSION ]
        then
            CONFIG_FILE=/boot/config-$VERSION
            ORIG_CONFIG_FILE=$CONFIG_FILE
            cp $CONFIG_FILE $LOGDIR/
        elif [ $TASK_STATS_FORCE_ENABLE == 0 ]
	then
            echo "Warning : Couldn't find the kernel config file for the current kernel"
            echo "        : Cound't determine if CONFIG_DEBUG_INFO_BTF is enabled"
            echo "        : Disabling per-task accounting. Use -e option to force it."
            exit 1
        fi

	RET=0
	if [ $TASK_STATS_FORCE_ENABLE == 0 ]
	then
	    echo "Checking for CONFIG_DEBUG_INFO_BTF in config $ORIG_CONFIG_FILE..."
            grep "CONFIG_DEBUG_INFO_BTF=y" $CONFIG_FILE
            RET=$?
	fi

        if [ $RET -ne 0 ] && [ $TASK_STATS_FORCE_ENABLE == 0 ]
        then
            echo "Error : CONFIG_DEBUG_INFO_BTF is not set in kernel config $ORIG_CONFIG_FILE"
            echo "      : Disabling per-task accounting"
	    TASK_STATS_DISABLE=1
        else
            TIMESTAMP=`date +%Y-%m-%d\ %H:%M:%S`
            if  [ $TASK_STATS_FORCE_ENABLE == 1 ]
            then
                echo "[$TIMESTAMP] Force-enabling taskstats collection"
            fi
            TIMESTAMP=`date +%Y-%m-%d\ %H:%M:%S`
            echo "[$TIMESTAMP] Beginning profiling of tasks..."
            python3 $SCRIPTDIR/generate_pertask_bpftrace.py $SCRIPTDIR
	    cp $SCRIPTDIR/taskstat_fields.py $LOGDIR/taskstat_fields.py
            $SCRIPTDIR/bpftrace $SCRIPTDIR/sched-pertask-stat.bt -o $LOGDIR/pertask.bpftrace.output&
        fi
    fi

    if [ $RQLEN_ENABLE == 1 ]
    then
        NPROC=`nproc`
        python3 $SCRIPTDIR/generate_runqlen_bpftrace.py $SCRIPTDIR $NPROC $RQLEN_PROFILE_TIME
        TIMESTAMP=`date +%Y-%m-%d\ %H:%M:%S`
        echo "[$TIMESTAMP] Beginning capturing rqlen for `nproc` cpus (Period $RQLEN_PROFILE_TIME ms)..."
        $SCRIPTDIR/bpftrace $SCRIPTDIR/runqlen.bt -o $LOGDIR/runqlen.csv&
    fi

    if [ $MIGRATION_STATS_ENABLE == 1 ]
    then
        TIMESTAMP=`date +%Y-%m-%d\ %H:%M:%S`
        echo "[$TIMESTAMP] Beginning profiling of task migration..."
        $SCRIPTDIR/bpftrace $SCRIPTDIR/sched-category-full.bt -o $LOGDIR/sched-category.bpftrace.output&
    fi
fi

function handle_signal () {
    echo "killing pid $COMMAND_PID"
    kill $COMMAND_PID
}

TIMESTAMP=`date +%Y-%m-%d\ %H:%M:%S`
echo "[$TIMESTAMP] Kickstarting the test with : $command"
trap 'handle_signal' SIGINT
$command&
COMMAND_PID=$!
wait $COMMAND_PID

if [ $TASK_STATS_DISABLE == 0 ]
then
    TIMESTAMP=`date +%Y-%m-%d\ %H:%M:%S`
    echo "[$TIMESTAMP] Snapshotting taskstats after..."
    mkdir $LOGDIR/taskstat-after
    $SCRIPTDIR/capture_taskstat.py $LOGDIR/taskstat-after
fi

if [ $BPF_NEEDED == 1 ]
then
    TIMESTAMP=`date +%Y-%m-%d\ %H:%M:%S`
    echo "[$TIMESTAMP] Stopping profiling of tasks"
    killall -w bpftrace
fi

TIMESTAMP=`date +%Y-%m-%d\ %H:%M:%S`
echo "[$TIMESTAMP] Snapshotting schedstats after..."
cat /proc/schedstat > $LOGDIR/schedstat-after
echo $old_schedstats > /proc/sys/kernel/sched_schedstats
wait

if [ $MIGRATION_STATS_ENABLE == 1 ]
then
    TIMESTAMP=`date +%Y-%m-%d\ %H:%M:%S`
    echo "[$TIMESTAMP] Generating migrate tasks report..."
    python3 $SCRIPTDIR/sched_taskstats_parser.py -d $LOGDIR > $LOGDIR/tasks-summary.log
fi

if [ $TASK_STATS_DISABLE == 0 ]
then
    TIMESTAMP=`date +%Y-%m-%d\ %H:%M:%S`
    echo "[$TIMESTAMP] Generating taskstats report..."
    python3 $SCRIPTDIR/sched_pertask_parser.py -d $LOGDIR
    if [ $DEPARTED_TASKS_ONLY == 1 ]
    then
        python3 $SCRIPTDIR/sched_pertask_report.py -d $LOGDIR -D
    else
        python3 $SCRIPTDIR/sched_pertask_report.py -d $LOGDIR
    fi
fi

TIMESTAMP=`date +%Y-%m-%d\ %H:%M:%S`
echo "[$TIMESTAMP] Computing schedstats summary..."
if [ -f $LOGDIR/domain_map.cfg ]
then
    python3 $SCRIPTDIR/schedstat_parser.py -b $LOGDIR/schedstat-before -a $LOGDIR/schedstat-after  -d $LOGDIR/domain_map.cfg  -o $LOGDIR/schedstat-summary
else
    python3 $SCRIPTDIR/schedstat_parser.py -b $LOGDIR/schedstat-before -a $LOGDIR/schedstat-after -o $LOGDIR/schedstat-summary
fi

TIMESTAMP=`date +%Y-%m-%d\ %H:%M:%S`
echo "[$TIMESTAMP] Tests complete. Results in : $LOGDIR"
