from __future__ import print_function
import sys
import numpy as np
import matplotlib.pyplot as plt

from util import read_records, preprocess, get_intervals


def plot_CDF(filename, start_selector, end_selector, start_index=None, end_index=None, **kwargs):
    records = read_records(filename)
    lineages = preprocess(records, cmd_of_interest='', send_only=False)
    intervals = get_intervals(lineages, start_selector, end_selector, start_index=start_index, end_index=end_index, **kwargs)

    sortedtime = np.sort(intervals.values())
    p = 1. * np.arange(len(intervals.values())) / (len(intervals.values()) - 1)
    plt.plot(sortedtime, p, **kwargs)


if __name__ == '__main__':
    if len(sys.argv) != 3:
        print('usage: %s log_file start_keyword end_keyword' % sys.argv[0], file=sys.stderr)
        sys.exit(1)
    plot_CDF(sys.argv, lambda _, r: sys.argv[1] in r['msg'], lambda _, r: sys.argv[2] in r['msg'])
    plt.grid(which='both')
    plt.legend()
    plt.show()
