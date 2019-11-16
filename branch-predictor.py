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
        if self.state >= (self.max_val / 2):
            return 1
        else:
            return 0

class PredictorCounter(StateCounter):
    def __init__(self, bits, init_value):
        super().__init__(bits, init_value)

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
    
    def get_current_val_as_binstr(self):
        return str("".join(map(str, self.register)))

class BranchPredictor:
    def __init__(self, num_state_bits, init_state_val, pht_size):
        offset = 0
        self.pht_numbits = math.frexp(pht_size)[1] - 1
        self.cut_pc = [self.pht_numbits + offset, offset]
        self.pattern_history_table = [PredictorCounter(num_state_bits, init_state_val) 
                for i in range(pht_size)]

        init_basic_vars(self, num_state_bits, init_state_val, pht_size)

    def predict(self, pc, actual_branch):
        cutpc = get_from_bitrange(self.cut_pc, pc)

        prediction = self.prediction_method(cutpc, actual_branch)

        if prediction == actual_branch:
            self.good_predictions += 1
        elif prediction is not None:
            self.mispredictions += 1
        if prediction is None:
            self.no_predictions += 1

        return prediction

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

class TournamentPredictor:
    def __init__(self, num_state_bits, init_state_val, pht_size):
        offset = 0
        self.pht_numbits = math.frexp(pht_size)[1] - 1
        self.cut_pc = [self.pht_numbits + offset, offset]

        gshare_predictor = GShare(num_state_bits, init_state_val, pht_size)
        one_level_predictor = OneLevel(num_state_bits, init_state_val, pht_size)
        self.predictors = [gshare_predictor, one_level_predictor]
        self.meta_predictor = [StateCounter(num_state_bits, init_state_val)
                for i in range(pht_size)]

        init_basic_vars(self, num_state_bits, init_state_val, pht_size)

    def predict(self, pc, actual_branch):
        cutpc = get_from_bitrange(self.cut_pc, pc)
        choosen_predictor = self.meta_predictor[cutpc].get_state()
        predictions = [self.predictors[0].predict(pc, actual_branch), self.predictors[1].predict(pc, actual_branch)]
        chosen_prediction = predictions[choosen_predictor]

        if chosen_prediction == actual_branch:
            self.good_predictions += 1
        elif chosen_prediction is not None:
            self.mispredictions += 1
        elif chosen_prediction is None:
            self.no_predictions += 1

        if (predictions[0] == predictions[1]):
            pass
        elif (predictions[0] == actual_branch):
            self.meta_predictor[cutpc].was_not_taken()
        elif (predictions[1] == actual_branch):
            self.meta_predictor[cutpc].was_taken()

    def get_method_type(self):
        return type(self).__name__.rstrip()

class TAGEPredictor:
    def __init__(self, num_state_bits, init_state_val, num_base_entries):
        base_predictor = OneLevel(num_state_bits, init_state_val, num_base_entries)

        # Init tagged predictors specifying history lengths as geometric series
        tagged_predictors = []
        for i in range (4):
            tagged_predictors.append(TaggedTable(num_state_bits, init_state_val))

        self.T = [base_predictor,  tagged_predictors[0], tagged_predictors[1], #Predictor components, Ti
                                   tagged_predictors[2], tagged_predictors[3]]

        self.global_history_register = ShiftRegister(80)
        init_basic_vars(self, num_state_bits, init_state_val, num_base_entries)

        self.count = 0
        self.msb_flip = True

    def predict(self, pc, actual_branch):
        predictions = []
        tagged_predictors_index_tag = []
        present_ghr_binstr = self.global_history_register.get_current_val_as_binstr()

        # Base predictor 0
        predictions.append(self.T[0].predict(pc, actual_branch))

        # Tagged predictors 1-4
        check_equal = []
        tagged_predictors_index_tag = [index_tag_hash(pc, present_ghr_binstr, i) for i in range(1,5)]

        for i in range(1,5):
            predictions.append(self.T[i].predict(tagged_predictors_index_tag[i - 1][0], actual_branch))
            equal = self.T[i].get_tag_at(tagged_predictors_index_tag[i - 1][0]) == tagged_predictors_index_tag[i - 1][1]
            check_equal.append(equal)

        provider_index = 0
        for i in range(4,0,-1):
            if check_equal[i - 1]:
                overall_prediction = predictions[i]
                provider_index = i
                break
        else:
            overall_prediction = predictions[0]

        altpred = 0
        for i in range(provider_index,-1,-1):
            if check_equal[i - 1]:
                altpred = predictions[i]
                break

        #update useful counter
        if (altpred != overall_prediction) & (provider_index != 0):
            if overall_prediction == actual_branch:
                self.T[provider_index].useful_bits[tagged_predictors_index_tag[provider_index][0]].was_taken()
            elif overall_prediction is not None:
                self.T[provider_index].useful_bits[tagged_predictors_index_tag[provider_index][0]].was_not_taken()

        if overall_prediction == actual_branch:
            self.good_predictions += 1
            return
        elif overall_prediction is not None:
            self.mispredictions += 1

            # Update Policy

            if provider_index != 4:
                for i in range(3,provider_index,-1):
                    u_counter = self.T[i].useful_bits[tagged_predictors_index_tag[i][0]].state
                    if u_counter == 0:
                        self.T[i].tags[tagged_predictors_index_tag[i][0]] = tagged_predictors_index_tag[i][1]
                        self.T[i].useful_bits[tagged_predictors_index_tag[i][0]].state = 2
                        break
                else:
                    for tagged_component in self.T[1:]:
                        for u_counter in tagged_component.useful_bits:
                            u_counter.was_not_taken()

        else:
            self.no_predictions += 1

        self.count += 1

        if self.count == (256 * 1024):
            if self.msb_flip:
                for tagged_component in self.T[T:]:
                    for u_counter in tagged_component.useful_bits:
                        u_counter.state &= 1
            else:
                for tagged_component in self.T[T:]:
                    for u_counter in tagged_component.useful_bits:
                        u_counter.state &= 2

            self.count = 0
            msb_flip = not msb_flip

    def get_method_type(self):
        return type(self).__name__.rstrip()

class TaggedTable:
    def __init__(self, num_state_bits, init_state_val):
        self.index_bits = 10
        num_entries = 2**self.index_bits
        self.tag_width = 8

        self.counters = [StateCounter(num_state_bits, init_state_val)
                for i in range(num_entries)]
        self.tags = [0 for i in range(num_entries)]
        self.useful_bits = [StateCounter(2, 0) for i in  range(num_entries)]

        offset = 0
        self.entries_numbits = math.frexp(num_entries)[1] - 1 
        self.cut_index_pc = [self.entries_numbits + offset, offset]

    def predict(self, index, actual_branch):
        prediction = self.counters[index].get_state()

        if actual_branch == 1:
            self.counters[index].was_taken()
        else:
            self.counters[index].was_not_taken()

        #wrong
        if prediction == actual_branch:
            self.useful_bits[index].was_taken()
        elif prediction is not None:
            self.useful_bits[index].was_not_taken()

        return prediction

    def get_tag_at(self, index):
        return self.tags[index]

def index_tag_hash(pc, ghr_binstr, comp):
    index_pc = get_from_bitrange([10,0], pc) ^ get_from_bitrange([20,10], pc)
    index_ghr = binstr_get_from_bitrange([10,0],ghr_binstr)

    tag_pc = get_from_bitrange([8,0], pc)
    tag_R1 = binstr_get_from_bitrange([8,0], ghr_binstr)
    tag_R2 = binstr_get_from_bitrange([7,0], ghr_binstr)

    for i in range(1, 2**(comp - 1)):
        index_ghr ^= binstr_get_from_bitrange([(i+1)*10,i*10],ghr_binstr)

    for i in range(1, math.floor( ( (2**(comp - 1) * 10) / 8) ) ):
        tag_R1 ^= binstr_get_from_bitrange([(i+1)*8,i*8],ghr_binstr)

    for i in range(1, math.floor( ( (2**(comp - 1) * 10) / 7) ) ):
        tag_R2 ^= binstr_get_from_bitrange([(i+1)*7,i*7],ghr_binstr)

    index = index_pc ^ index_ghr
    tag = tag_pc ^ tag_R1 ^ (tag_R2 << 1)

    return [index, tag]

def print_stats(predictor):
        total = predictor.no_predictions + predictor.good_predictions + predictor.mispredictions
        print("\n\n\n\t\t---Sim Result---")
        print("Type\t\t", "Counter Bits\t", "Counter init\t","PHT entries")
        print(predictor.get_method_type(), "\t", predictor.num_state_bits, "\t\t", predictor.init_state_val,"\t\t", predictor.pht_size, "\n")
        print("Mispredictions:\t\t", predictor.mispredictions)
        print("No Predictions:\t\t", predictor.no_predictions)
        print("Hit Predictions:\t", predictor.good_predictions)
        print("Total:\t\t\t", total)
        #print("Hit rate:\t\t", '{0:.04f}'.format(self.good_predictions / (total - self.no_predictions) * 100), "%")
        print("Hit rate:\t\t", '{0:.04f}'.format(predictor.good_predictions / (total) * 100), "%")
        print("Miss rate:\t\t", '{0:.04f}'.format(predictor.mispredictions / total * 100), "%\n")

def init_basic_vars(predictor, num_state_bits, init_state_val, pht_size):
    predictor.num_state_bits = num_state_bits
    predictor.init_state_val = init_state_val
    predictor.pht_size = pht_size
    predictor.mispredictions = 0
    predictor.good_predictions = 0
    predictor.no_predictions = 0

def norm_branch(branch):
    return 1 if branch.rstrip() is 'T' else 0

def get_from_bitrange(bit_range, dec_val):
    left_bit, right_bit = bit_range
    binary_string = "{0:032b}".format(int(dec_val))
    left_bit = len(binary_string) - left_bit
    right_bit = len(binary_string) - right_bit
    cut_string = binary_string[left_bit:right_bit]
    return 0 if left_bit == right_bit else int(cut_string, 2)

def binstr_get_from_bitrange(bit_range, binary_string):
    left_bit, right_bit = bit_range
    left_bit = len(binary_string) - left_bit
    right_bit = len(binary_string) - right_bit
    cut_string = binary_string[left_bit:right_bit]
    return 0 if left_bit == right_bit else int(cut_string, 2)

def main():

    #pc = 135051251
    #ghr_binstr = "10110101011011011101101101010100111101010011010111111101010100111101011111111101"
    #intag = index_tag_hash(pc, ghr_binstr, 1)
    #print(intag[0])
    #print(intag[1])

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
