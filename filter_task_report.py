import os
import sys
import csv
import json
import pandas as pd
from optparse import OptionParser

def available_fields_to_filter(df):
    for field in df.columns:
        print(field)

def available_tasks_to_filter(df):
    tasknames = set(df["comm"])
    for task in tasknames:
        print(task)

def filter_task_fields(df, filter_keys):
    keys_array = filter_keys.split(',')
    columns = df.columns

    filtered_fields = ["pid", "comm"]
    for key in keys_array:
        for column in columns:
            if key in column and key not in filtered_fields:
                column = column.strip()
                filtered_fields.append(column)

    df = df[filtered_fields]
    return df

def filter_task_by_name(df, filter_rows):
    tasknames = list(set(df["comm"]))
    tasks_array = filter_rows.split(',')
    filtered_tasks = []

    for task in tasks_array:
        if task in tasknames:
            filtered_tasks.append(task)

    df = df.loc[df["comm"].isin(filtered_tasks)]
    return df

if __name__ == "__main__":
    usage = "python3 %prog -d log_dir [-f filter_fields] [-t filter_tasks] [-L list_fields] [-T list_tasks]"
    parser = OptionParser(usage)
    parser.add_option("-d", "--logdir", dest="log_dir", type=str, help="path to logdir(should contain report.csv).")
    parser.add_option("-o", "--outdir", dest="out_dir", type=str, help="path of dir to store output")
    parser.add_option("-f", "--fields", dest="filter_fields", type=str, help="list of comma separated  task_struct fields to filter. Default : all fields")
    parser.add_option("-t", "--tasks", dest="filter_tasks", type=str, help="list of comma separated  task names to filter. Default : all tasks")
    parser.add_option("-L", "--list-fields", dest="list_fields", action="store_true", default=False, help="list of available fields to filter")
    parser.add_option("-T", "--list-tasks", dest="list_tasks", action="store_true", default=False, help="list of available tasks to filter")

    (options, args) = parser.parse_args()

    logdir = options.log_dir
    outdir = options.out_dir
    os.makedirs(outdir, exist_ok = True)

    report_path = os.path.join(logdir, "report.csv")

    try:
        df = pd.read_csv(report_path)
    except OSError as error:
        print("Report is not available")

    if options.list_fields:
        available_fields_to_filter(df)
    if options.list_tasks:
        available_tasks_to_filter(df)

    if options.filter_fields:
        df = filter_task_fields(df, options.filter_fields)

    if options.filter_tasks:
        df = filter_task_by_name(df, options.filter_tasks)

    result_path = os.path.join(outdir, "filter_report.csv")
    df.to_csv(result_path, index=False)

    filtered_csv = open(result_path, encoding='utf-8')
    csvReader = csv.DictReader(filtered_csv)
    data = {}
    for line in csvReader:
        key = line['pid']
        data[key] = line

    fout = open(os.path.join(outdir, "filter_report.json"), "w")
    fout.write(json.dumps(data, indent = 4))
    fout.close()
