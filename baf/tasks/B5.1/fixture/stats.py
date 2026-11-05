import csv, statistics, sys
values = [int(row[0]) for row in csv.reader(open(sys.argv[1]))]
print(statistics.median(values))
