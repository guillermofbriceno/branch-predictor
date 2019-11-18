#!/usr/bin/python3

import sys
import argparse

from predictors import *
from prediction_elements import *

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-method", help="Prediction method", choices=[ 
        'one-level','two-level-global','gshare','two-level-local', 'tournament', 'tage'],required=True)
    parser.add_argument("-cbits", help="How many bits for the state counters",default=2,type=int,required=False)
    parser.add_argument("-cinit", help="Initial state counter value",default=0,type=int,required=False)
    parser.add_argument("-phtsize", help="Number of pattern history table entries",type=int,required=True)
    parser.add_argument("-trace", help="Input trace file",required=True)
    args = parser.parse_args()

    methods = {
            'one-level':        OneLevel,
            'two-level-global': TwoLevelGlobal,
            'gshare':           GShare,
            'two-level-local':  TwoLevelLocal,
            'tournament':       TournamentPredictor,
            'tage':             TAGEPredictor
            }

    bp = methods[args.method](args.cbits, args.cinit, args.phtsize)

    with open(args.trace) as trace:
        print("Simulating...\n")
        trace = list(trace)
        for index,request in enumerate(trace):
            if index % 10000 == 0:
                sys.stdout.write('\r')
                sys.stdout.write(str( '{0:.0f}'.format(index / len(trace) * 100)) + "% complete")
                sys.stdout.flush()

            pc, branch = request.split(" ")
            bp.predict(pc, norm_branch(branch))

    print_stats(bp)
    #bp.print_debug_stats()

if __name__ == "__main__":
    main()
