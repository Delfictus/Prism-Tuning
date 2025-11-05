# Prism-Tuning: PRISM Hyper-Tuning Harness (Includes Binary)

## Overview

Minimal harness for tuning PRISM's DSJC1000.5 pipeline. Includes the PRISM binary (`bin/world_record_dsjc1000`), dataset (`data/benchmarks/dimacs/DSJC1000.5.col`), layered TOML overrides, run scripts, summarizer, and advisor.

## Requirements

- Linux x86_64; for GPU: NVIDIA driver + CUDA runtime compatible with the bundled binary
- `toml-cli`: `cargo install toml-cli`
- Python 3.8+
- ripgrep (`rg`)

## Quick Start

1. **Verify binary:**
   ```bash
   file bin/world_record_dsjc1000
   chmod +x bin/world_record_dsjc1000
   ```

2. **Run a 90-minute shakedown:**
   ```bash
   tools/run_wr_toml.sh
   ```

3. **Monitor:**
   ```bash
   tools/monitor_wr.sh results/logs/<timestamped_log>.log
   ```

4. **Summarize:**
   ```bash
   tools/summarize_wr_log.sh results/logs/<log> configs/base/wr_sweep_D_aggr_seed_9001.v1.1.toml
   ```

5. **Get next-run advice:**
   ```bash
   tools/advise_next_overrides.sh results/logs configs/base/wr_sweep_D_aggr_seed_9001.v1.1.toml
   cp configs/global_hyper.next.toml configs/global_hyper.toml
   ```

## Layered Overrides

Merge order: BASE + LAYER1 + LAYER2 … → active `configs/wr_hyper_active.toml`

Example:
```bash
tools/run_wr_toml.sh overrides/20_global_hyper.toml overrides/30_experiment.toml
```

## Common Knobs

- **ADP**: `adp.epsilon_decay`, `adp.epsilon_min`
- **Thermo**: `thermo.steps_per_temp`, `t_min`, `t_max`, `num_temps`
- **TE blend**: `transfer_entropy.te_vs_kuramoto_weight`
- **Orchestrator thresholds**: `orchestrator.adp_min_history_for_*`
- **Neuromorphic**: `neuromorphic.phase_threshold`

## Notes

- The runner sets a working directory shim so the binary finds DSJC1000.5 via the example's relative path
- GPU support requires the system's CUDA libraries to match the binary

## Container (Optional)

Build:
```bash
docker build -t prism-tuning:latest .
```

Run with host GPU and mounted binary (if you rebuild):
```bash
docker run --rm -it --gpus all -v $(pwd):/work -w /work prism-tuning:latest bash
```