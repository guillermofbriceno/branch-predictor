import sys
import math
import random

from prediction_elements import *

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
        base_predictor = TAGEBimodalBase(num_state_bits, init_state_val, 4096)

        # Init tagged predictors
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
        tagged_predictors_index_tag = [self.index_tag_hash(pc, present_ghr_binstr, i) for i in range(1,5)]

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
        altpred_provider_index = 0
        for i in range(provider_index-1,0,-1):
            if check_equal[i - 1]:
                altpred = predictions[i]
                altpred_provider_index = i
                break
        else:
            altpred = predictions[0]

        if provider_index == 0:
            self.T[0].update(pc, actual_branch)
        else:
            self.T[provider_index].update(tagged_predictors_index_tag[provider_index - 1][0], actual_branch)

        # Update useful counter
        if (altpred != overall_prediction) & (provider_index != 0):
            if overall_prediction == actual_branch:
                self.T[provider_index].useful_bits[tagged_predictors_index_tag[provider_index - 1][0]].was_taken()
            elif overall_prediction is not None:
                self.T[provider_index].useful_bits[tagged_predictors_index_tag[provider_index - 1][0]].was_not_taken()

        if overall_prediction == actual_branch:
            self.good_predictions += 1
        elif overall_prediction is not None:
            self.mispredictions += 1

            # Replacement Policy
            T_k_index = 0
            T_j_index = 0
            if provider_index != 4:
                for i in range(4,provider_index,-1):
                    u_counter = self.T[i].useful_bits[tagged_predictors_index_tag[i-1][0]].state
                    if u_counter == 0:
                        T_k_index = i
                        break
                else:
                    for tagged_component in self.T[1:]:
                        for u_counter in tagged_component.useful_bits:
                            u_counter.was_not_taken()

            if T_k_index >= 1:
                for i in range(T_k_index - 1, 0,-1):
                    u_counter = self.T[i].useful_bits[tagged_predictors_index_tag[i-1][0]].state
                    if u_counter == 0:
                        T_j_index = i
                        break
                else:
                    self.T[T_k_index].tags[tagged_predictors_index_tag[T_k_index-1][0]] = tagged_predictors_index_tag[T_k_index-1][1]
                    self.T[T_k_index].useful_bits[tagged_predictors_index_tag[T_k_index-1][0]].state = 0
                    self.T[T_k_index].counters[tagged_predictors_index_tag[T_k_index-1][0]].state = 4
                
                if T_j_index is not 0:
                    rand_num = random.randint(1,3)
                    if rand_num == 3:
                        self.T[T_j_index].tags[tagged_predictors_index_tag[T_j_index-1][0]] = tagged_predictors_index_tag[T_j_index-1][1]
                        self.T[T_j_index].useful_bits[tagged_predictors_index_tag[T_j_index-1][0]].state = 0
                        self.T[T_j_index].counters[tagged_predictors_index_tag[T_j_index-1][0]].state = 4
                    else:
                        self.T[T_k_index].tags[tagged_predictors_index_tag[T_k_index-1][0]] = tagged_predictors_index_tag[T_k_index-1][1]
                        self.T[T_k_index].useful_bits[tagged_predictors_index_tag[T_k_index-1][0]].state = 0
                        self.T[T_k_index].counters[tagged_predictors_index_tag[T_k_index-1][0]].state = 4

        else:
            self.no_predictions += 1

        self.count += 1

        if self.count == (256 * 1024):
            if self.msb_flip:
                for tagged_component in self.T[1:]:
                    for u_counter in tagged_component.useful_bits:
                        u_counter.state &= 1
            else:
                for tagged_component in self.T[1:]:
                    for u_counter in tagged_component.useful_bits:
                        u_counter.state &= 2

            self.count = 0
            self.msb_flip = not self.msb_flip
        
        self.global_history_register.shift_in(actual_branch)

    def index_tag_hash(self, pc, ghr_binstr, comp):
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

    def get_method_type(self):
        return type(self).__name__.rstrip()
