#!/usr/bin/python3

import sys
import argparse
import math

class StateCounter:
    def __init__(self, bits, init_value):
        self.bits = bits
        self.max_val = 2**self.bits
        self.init_value = init_value

        self.state = self.init_value

    def was_taken(self):
        if (self.state + 1) >= self.max_val:
            return
        self.state += 1

    def was_not_taken(self):
        if self.state == 0:
            return
        self.state -= 1

    def get_state(self):
        if self.state > (self.max_val / 2):
            return 1    # Taken
        if self.state < ((self.max_val / 2) - 1):
            return 0    # Not Taken
        else:
            return None # No Prediction (Weak)

class ShiftRegister:
    def __init__(self, bits):
        self.max_bits = bits
        self.register = [0 for i in range(bits)]
    
    def shift_in(self, bit):
        self.register.pop(0)
        self.register.append(bit)

    def get_current_val(self):
        return int("".join(map(str, self.register)), 2)

class BranchPredictor:
    def __init__(self, num_state_bits, init_state_val, pht_size):
        offset = 0
        self.pht_numbits = math.frexp(pht_size)[1] - 1
        self.cut_pc = [self.pht_numbits + offset, offset]
        self.pattern_history_table = [StateCounter(num_state_bits, init_state_val) 
                for i in range(pht_size)]

        self.num_state_bits = num_state_bits
        self.init_state_val = init_state_val
        self.pht_size = pht_size
        self.mispredictions = 0
        self.good_predictions = 0
        self.no_predictions = 0

    def print_stats(self):
        total = self.no_predictions + self.good_predictions + self.mispredictions
        print("\n\n\n\t\t---Sim Result---")
        print("Type\t", "Counter Bits\t", "Counter init\t","PHT entries")
        print(self.get_method_type(), "\t", self.num_state_bits, "\t\t", self.init_state_val,"\t\t", self.pht_size, "\n")
        print("Mispredictions:\t\t", self.mispredictions)
        print("No Predictions:\t\t", self.no_predictions)
        print("Hit Predictions:\t", self.good_predictions)
        print("Total:\t\t\t", total)
        print("Hit rate:\t\t", '{0:.04f}'.format(self.good_predictions / (total - self.no_predictions) * 100), "%")
        print("Miss rate:\t\t", '{0:.04f}'.format(self.mispredictions / total * 100), "%\n")

    def predict(self, pc, actual_branch):
        cutpc = get_from_bitrange(self.cut_pc, pc)

        prediction = self.prediction_method(cutpc, actual_branch)

        if prediction == actual_branch:
            self.good_predictions += 1
        elif prediction is not None:
            self.mispredictions += 1
        if prediction is None:
            self.no_predictions += 1

    def prediction_method(self, cutpc, actual_branch):
        pass
    
    def get_method_type(self):
        return type(self).__name__.rstrip()

class OneLevel(BranchPredictor):
    def __init__(self, num_state_bits, init_state_val, pht_size):
        super().__init__(num_state_bits, init_state_val, pht_size)
    
    def prediction_method(self, cutpc, actual_branch):
        pht_address = cutpc
        prediction = self.pattern_history_table[pht_address].get_state()

        if actual_branch is 1:
            self.pattern_history_table[pht_address].was_taken()
        elif actual_branch is 0:
            self.pattern_history_table[pht_address].was_not_taken()

        return prediction

class TwoLevelGlobal(BranchPredictor):
    def __init__(self, num_state_bits, init_state_val, pht_size):
        super().__init__(num_state_bits, init_state_val, pht_size)

        self.g_hist_reg_width = self.pht_numbits
        self.global_branch_history = ShiftRegister(self.g_hist_reg_width)

    def prediction_method(self, cutpc, actual_branch):
        pht_address = self.addressing_method(cutpc, actual_branch)
        prediction = self.pattern_history_table[pht_address].get_state()

        self.global_branch_history.shift_in(actual_branch)
        if actual_branch is 1:
            self.pattern_history_table[pht_address].was_taken()
        elif actual_branch is 0:
            self.pattern_history_table[pht_address].was_not_taken()

        return prediction
    
    def addressing_method(self, cutpc, actual_branch):
        return self.global_branch_history.get_current_val()


class GShare(TwoLevelGlobal):
    def __init__(self, num_state_bits, init_state_val, pht_size):
        super().__init__(num_state_bits, init_state_val, pht_size)
        
    def addressing_method(self, cutpc, actual_branch):
        return cutpc ^ self.global_branch_history.get_current_val()

    def print_debug_stats(self):
        print("\n---Debug---")
        print("Bits in history register:\t\t", self.g_hist_reg_width)
        print("Current values in global history reg:\t", self.global_branch_history.register)
        print("Value of global history reg:\t\t", self.global_branch_history.get_current_val())

class TwoLevelLocal(BranchPredictor):
    def __init__(self, num_state_bits, init_state_val, pht_size):
        super().__init__(num_state_bits, init_state_val, pht_size)
        self.g_hist_reg_width = self.pht_numbits

        self.local_hist_reg_table_size =  128

        self.reg_table_numbits = math.frexp(self.local_hist_reg_table_size)[1] - 1
        self.cut_pc = [32, 32 - self.reg_table_numbits]

        self.local_hist_reg_table = [ShiftRegister(self.g_hist_reg_width) 
                for i in range(self.local_hist_reg_table_size)]

    def prediction_method(self, cutpc, actual_branch):
        pht_address = self.local_hist_reg_table[cutpc].get_current_val()
        prediction = self.pattern_history_table[pht_address].get_state()

        self.local_hist_reg_table[cutpc].shift_in(actual_branch)
        if actual_branch is 1:
            self.pattern_history_table[pht_address].was_taken()
        elif actual_branch is 0:
            self.pattern_history_table[pht_address].was_not_taken()
        
        return prediction

def norm_branch(branch):
    return 1 if branch.rstrip() is 'T' else 0

def get_from_bitrange(bit_range, dec_val):
    left_bit, right_bit = bit_range
    binary_string = "{0:032b}".format(int(dec_val))
    left_bit = len(binary_string) - left_bit
    right_bit = len(binary_string) - right_bit
    cut_string = binary_string[left_bit:right_bit]
    return 0 if left_bit == right_bit else int(cut_string, 2)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-method", help="Prediction method", choices=[ 
        'one-level','two-level-global','gshare','two-level-local'],required=True)
    parser.add_argument("-cbits", help="How many bits for the state counters",default=2,type=int,required=False)
    parser.add_argument("-cinit", help="Initial state counter value",default=0,type=int,required=False)
    parser.add_argument("-phtsize", help="Number of pattern history table entries",type=int,required=True)
    parser.add_argument("-trace", help="Input trace file",required=True)
    args = parser.parse_args()

    methods = {
            'one-level':        OneLevel,
            'two-level-global': TwoLevelGlobal,
            'gshare':           GShare,
            'two-level-local':  TwoLevelLocal
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

    bp.print_stats()
    #bp.print_debug_stats()

if __name__ == "__main__":
    main()
