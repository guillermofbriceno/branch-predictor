#!/usr/bin/python3

import sys

def main():
    trace_list = []
    with open('branches_0.out','r') as trace:
        print("Normalizing...\n")
        for request in trace:
            temp = request.split()
            taken = temp[1]
            cond = temp[2]
            PC =  temp[7]
            if cond is '1':
                if taken is '1':
                    taken_str = 'T'
                else:
                    taken_str = 'N'

                trace_list.append(str(int(PC, 16)) + " " + taken_str)

    with open('normed-branches.out','w') as trace:
        print("Printing...\n")
        for branch in trace_list:
            trace.write(branch)
            trace.write("\n")

if __name__ == "__main__":
    main()

