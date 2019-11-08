# branch-predictor

Currently implements one-level, two-level global, two-level local and gshare prediction methods, and prints misprediction information.

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


