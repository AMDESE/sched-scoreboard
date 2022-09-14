# Scheduler Scoreboard

## What it is.
Scheduler scoreboard is a single toolkit to capture and report all the data related to the Linux Kernel Scheduler which can help analyze performance issues potentially caused due to modelling or the heuristics adopted by the Linux Kernel Scheduler. Currently the scoreboard is intended for any AMD EPYC platforms. However it can be modified in order to made be applicable to other architectures

## Where is it available.

The scoreboard is currently made available via AMDESE github.

``` 
git clone https://github.com/AMDESE/sched-scoreboard.git
cd  sched-scoreboard/
```

## How to use it

The scoreboard can be triggered using the top level script that has been unimaginatively named as `sched-scoreboard.sh`.

```
#pwd
/path/to/sched-scoreboard
amd@amd:~/sched-scoreboard$ ./sched-scoreboard.sh -h

Usage : ./sched-scoreboard.sh [options] -W command
where options are:
 -l | --logdir               : The directory where logs should be stored
 -h | --help                 : Will print this message
 -D | --task-disable         : Disable collection of per-task statistics. (Default is enabled)
 -e | --task-enable          : Enable collection of per-task statistics even if config BTF option is not sure
 -q | --rqlen-enable         : Collect per-cpu runqlen data (Default is disabled)
 -m | --migrate-enable       : Collect the task migration data (Default is disabled)
 -d | --departed-tasks       : Generate report for only those tasks that exited during monitoring period (Default complete report)
 -t | --rqlen-profile-time   : Time in ms for capturing of runq length (Default 100 ms)
 -p | --max-pids             : Maximum number of PIDs that may be active during the period of monitoring (Default 65536)
 -W | --workload             : Workload

```

**Example 1:**
The scoreboard can be triggered from any location in the system. For example, if you want to run SpecJBB whose runner script is in `/path/to/specjbb/`. Then to run the SpecJBB via the Scheduler-Scoreboard, the commmand is
```
# cd /path/to/specjbb
# /path/to/sched-scoreboard/sched-scoreboard.sh \
  --logdir /tmp/specjbb-scoreboard \
  --workload ./specjbbrunner.sh
```
This will kickstart the SpecJBB workload and the scheduler-scoreboard logs for per-CPU scheduler metrics will be collected in `/tmp/specjbb-scoreboard`.


**Example 2:**
At times there may be a requirement to capture the per-task scheduler statistics even if config BTF option is not sure. This can be achieved with the `-e` option. However, it must be noted that
this can cause a slight drop in the performance of the workload since the per-task statistics are extracted and summarized on every task-wakeup and task-migration.

```
# cd /path/to/specjbb
# /path/to/sched-scoreboard//sched-scoreboard.sh \
  --logdir /tmp/specjbb-scoreboard \
  -e \
  -W ./specjbbrunner.sh
```

## What are the output files and how do I interpret them.

`config-6.2.0`              : The kernel config of the kernel you are running on

`domain_map.cfg`            : The mapping of the scheduler-domains to their names

`pertask.bpftrace.output`   : Output of the bpftrace script which captures the scheduler statistics of exiting tasks

`report.csv`                : Report of the scheduler statistics of all the tasks during the period of observation, in the CSV format.

`report.json`               : Same as above, except in json format.

`schedstat-after`           : Snapshot of /proc/schedstats after kickstarting the test

`schedstat-before`          : Snapshot of /proc/schedstats before kickstarting the test

`schedstat-summary`         : Summary of the systemwide and per-cpu scheduling statistics in a human readable format.

`taskstat-after`            : Directory containing the snapshot of /proc/<pid>/task/<tid>/sched for all processes and their threads after finishing the test

`taskstat-before`           : Directory containing the snapshot of /proc/<pid>/task/<tid>/sched for all processes and their threads before starting the test

`taskstat-workload`         : Directory containing the details of the processes and their threads that exited during the period of observation.

`topology-info`             : CPU topology as observed by the scheduler.

# Interpreting schedstat-summary
Schedstat summary is derived from the schedstat counters which are present in 
the linux kernel which are exposed through the file `/proc/schedstat`. These 
counters are enabled or disabled via the sysctl governed by the file 
`/proc/sys/kernel/sched_schedstats`. These counters accounts for many 
scheduler events such as `schedule()` calls, load-balancing events, 
`try_to_wakeup()` calls among others.

A detailed description of the schedstats can be found in the Kernel Documentation: https://www.kernel.org/doc/html/latest/scheduler/sched-stats.html

We structure the output under two broad headings :
1. All CPU average
2. Per CPU

All CPUs average statistics are obtained by taking the ratio of the sum of corresponding metrics from across all the CPUs to the number of CPUs. These can be useful to understand what is going on in the system as a whole if the workload that is being investigated is expected to be spread out uniformly across the full system.

Per CPU statistics are parsed from `/proc/schedstat`

Under each of these two headings, we provide details for the CPU Statistics and the per sched-domain statistics.

### CPU Scheduling Statistics

This corresponds to the first line of the per-cpu statistics in `/proc/schedstat`. The fields are self-explanatory. 

For some of the statistics, we provide a percentage value relative to the corresponding baseline. This is shown in `()`. 

In the example below, the number of times `schedule left the processor idle` was 38.18% of the number of times `schedule called` on this cpu. 
Similarly, the number of times `try_to_wake_up was called to wake up the local cpu` was 7.64% of the number of times `try_to_wake_up` was called. 
Finally the `total waittime by tasks on this processor` is 83.46% of `the total runtime by tasks on this processor`.

**Example**
``` 
------------------------------------------------------------------------------------------------------------------------------------------------------
cpu:  cpu0
------------------------------------------------------------------------------------------------------------------------------------------------------
sched_yield count                                          :                    0
Legacy counter can be ignored                              :                    0
schedule called                                            :                63289
schedule left the processor idle                           :                24166  ( 38.18 )
try_to_wake_up was called                                  :                39260
try_to_wake_up was called to wake up the local cpu         :                 3001  (  7.64 )
total runtime by tasks on this processor (in jiffies)      :            898085785
total waittime by tasks on this processor (in jiffies)     :            749517087  ( 83.46 )
total timeslices run on this cpu                           :                39111
------------------------------------------------------------------------------------------------------------------------------------------------------
```

### Load balancing Statistics

For each of the scheduling domains (Eg: `SMT, MC, DIE...`), the scheduler computes statistics under the following categories:

1. *New Idle Balance*: Load-balancing performed when a CPU just became idle.
2. *Busy Load Balance*: Load-balancing performed when the CPU was busy.
3. *Idle Load Balance*: Load Balancing performed on behalf of a long idling CPU by some other CPU.

Under each of these three categories, we provide the different load balancing related statistics. They are self explanatory. However next to their values, the schedstat summary also provides percentages relative to the counts in this category, this sched-domain, this CPU and the full-system. This is explained using the example below. 

We see the load-balancing statistics for the SMT domain of a CPU. The `cpumask` indicates that the constituent CPUs in this domain are `CPU 0` and `CPU 128`. We see various statistics for each of the three categories where load-balance is performed. 

```
------------------------------------------------------------------------------------------------------------------------------------------------------
domain:  SMT  | cpumask:  00000000,00000001,00000000,00000001
------------------------------------------------------------------------------------------------------------------------------------------------------
< -----------------------------------------------------------------  Category:  idle ----------------------------------------------------------------- >
load_balance count on cpu idle                             :       1559    $   22.38335 $    [    0.06251 ]
load_balance found balanced on cpu idle                    :       1540    $   22.11055 $    [    0.06175 ]
  ->load_balance failed to find busier queue on cpu idle   :          0    $    0.00000 $    [    0.00000 ]
  ->load_balance failed to find busier group on cpu idle   :       1540    $   22.11055 $    [    0.06175 ]
load_balance move task failed on cpu idle                  :          1    $    0.01436 $    [    0.00004 ]
*load_balance success count on cpu idle                    :         18    $    0.25844 $    [    0.00072 ]
imbalance sum on cpu idle                                  :        214
pull_task count on cpu idle                                :         19
*avg task pulled per sucessfull lb attempt (cpu idle)      :    1.05556
  ->pull_task when target task was cache-hot on cpu idle   :          0
< -----------------------------------------------------------------  Category:  busy ----------------------------------------------------------------- >
load_balance count on cpu busy                             :          6    $    0.08615 $    [    0.00024 ]
load_balance found balanced on cpu busy                    :          4    $    0.05743 $    [    0.00016 ]
  ->load_balance failed to find busier queue on cpu busy   :          0    $    0.00000 $    [    0.00000 ]
  ->load_balance failed to find busier group on cpu busy   :          4    $    0.05743 $    [    0.00016 ]
load_balance move task failed on cpu busy                  :          1    $    0.01436 $    [    0.00004 ]
*load_balance success cnt on cpu busy                      :          1    $    0.01436 $    [    0.00004 ]
imbalance sum on cpu busy                                  :         52
pull_task count on cpu busy                                :          1
*avg task pulled per sucessfull lb attempt (cpu busy)      :          1
  ->pull_task when target task was cache-hot on cpu busy   :          0
< -----------------------------------------------------------------  Category:  newidle ----------------------------------------------------------------- >
load_balance cnt on cpu newly idle                         :      10400    $  149.31802 $    [    0.41700 ]
load_balance found balanced on cpu newly idle              :       8848    $  127.03518 $    [    0.35477 ]
  ->load_balance failed to find bsy q on cpu newly idle    :          0    $    0.00000 $    [    0.00000 ]
  ->load_balance failed to find bsy grp on cpu newly idle  :       8537    $  122.56999 $    [    0.34230 ]
load_balance move task failed on cpu newly idle            :        148    $    2.12491 $    [    0.00593 ]
*load_balance success cnt on cpu newidle                   :       1404    $   20.15793 $    [    0.05630 ]
imbalances sum on cpu idle                                 :       1595
pull_task count on cpu newly idle                          :       1404
*avg task pulled per sucessfull lb attempt (cpu newidle)   :          1
  ->pull_task whn target task was cache-hot on cpu newidle :          0


```

Consider the following line
```
load_balance found balanced on cpu newly idle              :       8848    $  127.03518 $    [    0.35477 ]
```

This states that the total number of time when the load-balancer on a `newly idle` CPU 0 found the load-to be balanced was `8848`. 
* `$127.03518` : Every 100 jiffies, on an average `127.03518` instances the load-balancer on a `newly-idle` `CPU 0` found the load load was balanced.
* `[  0.35477]` indicates the percentage of this petric with respect to the load-balancing attempts across all the CPUs.


In addition to the schedstat counters, schedstat summary for the domains has some derived metrics. These are prefixed with "*".

**Example:**
```
*load_balance success cnt on cpu newidle                   :       1404    $   20.15793 $    [    0.05630 ]
```

### Wakeup statistics

For every CPU, the sched-scoreboard also lists task-wakeup statistics. This is based on information parsed from `/proc/schedstat`. It is listed under the head `Wakeup info` in the scoreboard output. The fields are describedd using the example below.

```
< -----------------------------------------------------------------  Wakeup info:  ----------------------------------------------------------------- >
Wakeups on same                SMT 	:                  2033 	(   5.17830  )
Wakeups on same                 MC 	:                 32202 	(  82.02241  )
Wakeups on same                DIE 	:                  2024 	(   5.15537  )
Affine wakeups on same         SMT 	:                  1566 	(   3.98879  )
Affine wakeups on same          MC 	:                 20012 	(  50.97300  )
Affine wakeups on same         DIE 	:                  1779 	(   4.53133  )
```

The first three metrics are from the perspective of this CPU which is performing the task wakeup. `Wakeups on the same SMT` (resp. `MC` and `DIE`)  : Denotes the number of task-wakeups where the tasks were woken up on a CPU in the same `SMT` (resp. `MC` and `DIE`) domain as this CPU. The numbers within the `()` on each line represents the percentage of the wakeups on the corresponding sched-domain.

The next three metrics are related to affine wakeups where we wakeup the task on the LLC where the relevant data is likely to be present. 
Thus, `Affine wakeups on same         SMT 	` (resp. `MC` and `DIE`) denotes the number of affine wakeups performed when the lowest sched-domain containing the task's previous CPU and this CPU is the `SMT` (resp. `MC` and `DIE`) domain. 

# Comparing Schedstat Summaries

Often it is useful to compare the schedstat summaries of two different runs of the same workloads, especially when one of them is good and the other one is bad. The `schedstat_comparator.py` script helps us compute the average of the schedstats of a set of cpus from the first run with the average of the schedstats of a set of cpus of the second run and present them in a side-by-side manner. Whenever a schedstat metrics of the second run differs from the corresponding schedstat metric of the first run by a significant amount, the `schedstat_comparator.py` script prints the percentage increase of the metric of the second run with respect to the first run.


```
python3 schedstat_comparator.py -h
Usage: python3 schedstat_comparator.py -b baseline_logdir -c compare_logdir -o out_file [-f baseline_cpu_list] [-s compare_cpu_list]

Options:
  -h, --help            show this help message and exit
  -b BASELINE_LOG_DIR, --basedir=BASELINE_LOG_DIR
                        sched-scoreboard log directory of the run that should
                        be considered as the baseline
  -c COMPARE_LOG_DIR, --compdir=COMPARE_LOG_DIR
                        sched-scoreboard log directory of some other run that
                        should be compared against the baseline
  -o OUT_FILE, --out=OUT_FILE
                        Output file to store the schedstat comparison output
  -f BASELINE_CPU_LIST, --firstlist=BASELINE_CPU_LIST
                        Restrict the comparison to the schedstats of this list
                        of CPUs from the baseline run. Default : all cpus
  -s COMPARE_CPU_LIST, --secondlist=COMPARE_CPU_LIST
                        Restrict the comparison to the schedstats of this list
                        of CPUs from the other run. Default : all cpus
```
**Example**

Suppose we want to compare the schedstat summaries of two hackbench runs whose scoreboard outputs are housed in `/tmp/hackbench-1` and `/tmp/hackbench-2` respectively. The following command will generate the comparison output in the file `/tmp/hackbench-compare-1-2

```
$ python3 schedstat_comparator.py -b /tmp/hackbench-1  -c /tmp/hackbench-2  -o /tmp/hackbench-compare-1-2
$ cat /tmp/hackbench-compare-1-2 
comparison results : base_file : /tmp/hackbench-1/schedstat-summary vs comp_file : /tmp/hackbench-2/schedstat-summary
pct increase of a schedstat metric of the other run with respect to the corresponding metric of the baseline run is indicating within the |  | pair
pct within this category represented by (...)
pct within this domain represented by {...}
pct inter domain represented by <...>
pct within the system represented by [...]
avg value per 100 jiffies represented by $...$
------------------------------------------------------------------------------------------------------------------------------------------------------
System level info:
------------------------------------------------------------------------------------------------------------------------------------------------------
------------------------------------------------------------------------------------------------------------------------------------------------------
cpu:  all_cpus (avg) vs cpu:  all_cpus (avg)
------------------------------------------------------------------------------------------------------------------------------------------------------
sched_yield count                                          :             0,            0           
Legacy counter can be ignored                              :             0,            0           
schedule called                                            :        753947,       735841           
schedule left the processor idle                           :        272314,       259537             (   36.12,  35.27  )
try_to_wake_up was called                                  :        412146,       403423           
try_to_wake_up was called to wake up the local cpu         :         77647,        82842  |   6.69|  (   18.84,  20.53  )
total runtime by tasks on this processor (in jiffies)      :   40526576243,  40514834804           
total waittime by tasks on this processor (in jiffies)     :    5989638368,   5875018998             (   14.78,  14.50  )
total timeslices run on this cpu                           :        480595,       475073           
------------------------------------------------------------------------------------------------------------------------------------------------------
domain:  SMT cpus = all_cpus (avg) vs domain:  SMT cpus = all_cpus (avg)
------------------------------------------------------------------------------------------------------------------------------------------------------
< -----------------------------------------------------------------  Category:  idle ----------------------------------------------------------------- >
load_balance count on cpu idle                             :          5982,         5461  |  -8.71|  $   31.51,  29.70  $  [    1.84,   1.48  ]
load_balance found balanced on cpu idle                    :          5870,         5351  |  -8.84|  $   30.92,  29.10  $  [    1.80,   1.45  ]
  ->load_balance failed to find busier queue on cpu idle   :             0,            0             $       0,      0  $  [       0,      0  ]
  ->load_balance failed to find busier group on cpu idle   :          5870,         5351  |  -8.84|  $   30.92,  29.10  $  [    1.80,   1.45  ]
load_balance move task failed on cpu idle                  :             7,            7             $    0.04,   0.04  $  [    0.00,   0.00  ]
*load_balance success count on cpu idle                    :           105,          103             $    0.55,   0.56  $  [    0.03,   0.03  ]
imbalance sum on cpu idle                                  :           124,          122           
pull_task count on cpu idle                                :           115,          112           
*avg task pulled per sucessfull lb attempt (cpu idle)      :       1.09524,      1.08738           
  ->pull_task when target task was cache-hot on cpu idle   :             0,            0           
< -----------------------------------------------------------------  Category:  busy ----------------------------------------------------------------- >
load_balance count on cpu busy                             :           631,          645             $    3.32,   3.51  $  [    0.19,   0.18  ]
load_balance found balanced on cpu busy                    :           611,          624             $    3.22,   3.39  $  [    0.19,   0.17  ]
  ->load_balance failed to find busier queue on cpu busy   :             0,            0             $       0,      0  $  [       0,      0  ]
  ->load_balance failed to find busier group on cpu busy   :           610,          623             $    3.21,   3.39  $  [    0.19,   0.17  ]
load_balance move task failed on cpu busy                  :             3,            3             $    0.02,   0.02  $  [    0.00,   0.00  ]
*load_balance success cnt on cpu busy                      :            17,           18  |   5.88|  $    0.09,   0.10  $  [    0.01,   0.00  ]
imbalance sum on cpu busy                                  :            50,           48           
pull_task count on cpu busy                                :            19,           20  |   5.26|
*avg task pulled per sucessfull lb attempt (cpu busy)      :       1.11765,      1.11111           
  ->pull_task when target task was cache-hot on cpu busy   :             0,            0           
< -----------------------------------------------------------------  Category:  newidle ----------------------------------------------------------------- >
load_balance cnt on cpu newly idle                         :        131966,       141976  |   7.59|  $  695.18, 772.20  $  [   40.56,  38.58  ]
load_balance found balanced on cpu newly idle              :        128250,       137359  |   7.10|  $  675.60, 747.08  $  [   39.42,  37.32  ]
  ->load_balance failed to find bsy q on cpu newly idle    :             0,            0             $       0,      0  $  [       0,      0  ]
  ->load_balance failed to find bsy grp on cpu newly idle  :        127294,       135934  |   6.79|  $  670.57, 739.33  $  [   39.13,  36.94  ]
load_balance move task failed on cpu newly idle            :           415,          529  |  27.47|  $    2.19,   2.88  $  [    0.13,   0.14  ]
*load_balance success cnt on cpu newidle                   :          3301,         4088  |  23.84|  $   17.39,  22.23  $  [    1.01,   1.11  ]
imbalances sum on cpu idle                                 :          3868,         4820  |  24.61|
pull_task count on cpu newly idle                          :          3300,         4088  |  23.88|
*avg task pulled per sucessfull lb attempt (cpu newidle)   :       0.99970,            1           
  ->pull_task whn target task was cache-hot on cpu newidle :             0,            0           
< -----------------------------------------------------------------  Category:  alb ----------------------------------------------------------------- >
active_load_balance count                                  :             0,            0           
active_load_balance move task failed                       :             0,            0           
active_load_balance successfully moved a task              :             0,            0           
------------------------------------------------------------------------------------------------------------------------------------------------------
.
.
.
.
< -----------------------------------------------------------------  Wakeup info:  ----------------------------------------------------------------- >
Wakeups on same         SMT cpus = all_cpus (avg) 	:         11991,        10700  | -10.77|  (    2.91,   2.65  )
Wakeups on same         MC cpus = all_cpus (avg) 	:        259626,       238761  |  -8.04|  (   62.99,  59.18  )
Wakeups on same         DIE cpus = all_cpus (avg) 	:         52823,        54821             (   12.82,  13.59  )
Wakeups on same         NUMA cpus = all_cpus (avg) 	:         10058,        16297  |  62.03|  (    2.44,   4.04  )
Affine wakeups on same  SMT cpus = all_cpus (avg) 	:          9476,         8900  |  -6.08|  (    2.30,   2.21  )
Affine wakeups on same  MC cpus = all_cpus (avg) 	:        134379,       122021  |  -9.20|  (   32.60,  30.25  )
Affine wakeups on same  DIE cpus = all_cpus (avg) 	:        128203,       131680             (   31.11,  32.64  )
Affine wakeups on same  NUMA cpus = all_cpus (avg) 	:         13872,        15024  |   8.30|  (    3.37,   3.72  )
------------------------------------------------------------------------------------------------------------------------------------------------------
```

For instance in the following line, 

```
try_to_wake_up was called to wake up the local cpu         :         77647,        82842  |   6.69|  (   18.84,  20.53  )
```
`| 6.69|` means that the number of times `try_to_wake_up` was called to wake up on the local cpu is `6.69%` greater in the second run when compared to the first run.

Similarly, in the line 
```
*load_balance success cnt on cpu newidle                   :          3301,         4088  |  23.84|  $   17.39,  22.23  $  [    1.01,   1.11  ]
```
`|23.84|` implies that the number of successful load-balancing attempts when the cpus were newly idle was 23.84% greater in the second run when compared to the first run.

The remaining fields are side-by-side representations of the corresponding fields from the schedstat-summary.

