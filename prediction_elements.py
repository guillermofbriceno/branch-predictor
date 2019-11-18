import sys
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
        self.count = 0

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


class TAGEBimodalBase(BranchPredictor):
    def __init__(self, num_state_bits, init_state_val, pht_size):
        super().__init__(num_state_bits, init_state_val, pht_size)
        self.pattern_history_table = [StateCounter(num_state_bits, init_state_val) 
                    for i in range(pht_size)]

    def prediction_method(self, cutpc, actual_branch):
        pht_address = cutpc
        prediction = self.pattern_history_table[pht_address].get_state()
        return prediction

    def update(self, pc, actual_branch):
        cutpc = get_from_bitrange(self.cut_pc, pc)
        pht_address = cutpc
        if actual_branch is 1:
            self.pattern_history_table[pht_address].was_taken()
        elif actual_branch is 0:
            self.pattern_history_table[pht_address].was_not_taken()


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
        return prediction

    def update(self, index, actual_branch):
        if actual_branch == 1:
            self.counters[index].was_taken()
        else:
            self.counters[index].was_not_taken()

    def get_tag_at(self, index):
        return self.tags[index]

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
        print("Miss rate:\t\t", '{0:.04f}'.format((predictor.mispredictions + predictor.no_predictions) / total * 100), "%\n")

        #disp_big_list(predictor.T[1].tags)
        #disp_big_list(predictor.T[2].tags)
        #disp_big_list(predictor.T[3].tags)
        #disp_big_list(predictor.T[4].tags)

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
    binary_string = "{0:064b}".format(int(dec_val))
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

def disp_big_list(lst, rows = 50):
    table_list = [[] for _ in range(rows)]
    
    for index, item in enumerate(lst):
        row_index = index % rows
        table_list[row_index].append("%6d" % item)

    table_str = "\n".join(["\t".join(i) for i in table_list])
    
    print(table_str)
