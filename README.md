# branch-predictor

Implements the following prediction methods:

*TAGE
*Tournament
*gshare
*Two-Level Global
*Two-Level Local
*One-Level 

and prints misprediction information.

Trace file format is the PC address of the conditional branch instruction followed by the branch itself:

```
3086629576 T
3086629604 T
3086629599 N
3086629604 T
```

## Usage

Use `./branch_predictor.py -h` for a detailed list of options. Example usage:

`./branch_predictor.py -method gshare -cbits 2 -cinit 0 -phtsize 1024 -trace <trace file>`

The script `format_trace.py` is used to isolate and format the conditional branches extracted using a PIN tool extractor [here](https://github.com/mbaharan/branchExtractor).

### Notices

The TAGE predictor is implemented with fixed table and counter sizes except for the base bimodal table, whose counter size can be set with the `-cbits` option. Setting the other options has no effect.

The Tournament predictor uses a meta-predictor to choose between gshare and one-level predictions. The table and counter sizes for the components are set equally according to the `-cbits`, `-cinit`, and `-phtsize` options.

