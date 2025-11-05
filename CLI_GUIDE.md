# PRISM CLI Dashboard Guide

## Quick Start

```bash
./prism
```

This launches the interactive CLI dashboard where you can:
- ✅ Configure all tunable parameters
- ✅ Create and manage experiments
- ✅ Run jobs in separate windows
- ✅ Monitor running jobs
- ✅ View logs and reports

## Main Menu

```
╔════════════════════════════════════════════╗
║       PRISM CLI Dashboard                  ║
║  Interactive Configuration & Job Management║
╚════════════════════════════════════════════╝

1. Configure Parameters       - Edit all tunable settings
2. Create New Experiment       - Build custom config files
3. Run Experiment              - Launch in new window
4. View Running Jobs           - Monitor active runs
5. View Logs & Reports         - Analyze results
6. Quick Parameter Adjust      - Fast single-param changes
7. Load Experiment Template    - Start from template
q. Quit
```

## Features

### 1. Configure Parameters

**Interactive parameter editor organized by category:**
- Top-Level (target, runtime, toggles)
- CPU (threads)
- GPU (device, streams, batch_size)
- ADP (exploration rates, learning)
- Thermodynamic (replicas, temps, steps)
- Quantum (iterations, retries)
- Memetic (population, generations)
- Transfer Entropy (TE/Kuramoto blend)
- Orchestrator (thresholds, depths)
- Neuromorphic (phase threshold)
- Geodesic (landmarks, weights)

**Type-safe input validation:**
- Integers: Validates whole numbers
- Floats: Validates decimals
- Booleans: Yes/No prompts
- Choices: Select from options

**No TOML syntax errors** - the CLI generates correct syntax automatically!

### 2. Create New Experiment

**Workflow:**
1. Enter experiment name (e.g., `deep_search`)
2. Select categories to configure
3. Set parameters interactively
4. Auto-saves to `overrides/<name>.toml`

**Example:**
```
Experiment name: my_test
→ Configure Top-Level
  target_chromatic: 88
  max_runtime_hours: 72.0
→ Configure Thermodynamic
  steps_per_temp: 10000
✓ Saved to overrides/my_test.toml
```

### 3. Run Experiment

**Launches jobs in separate terminal windows** so CLI stays responsive!

**Workflow:**
1. Select experiment from list
2. Set timeout (90m, 24h, 48h, etc.)
3. Job launches in new window
4. CLI remains interactive

**Terminal detection:**
- Tries `gnome-terminal` (Ubuntu default)
- Falls back to `xterm`
- Uses `tmux` if available
- Last resort: background process

**You can:**
- Launch multiple jobs in parallel
- Continue using CLI while jobs run
- Monitor jobs from menu option 4

### 4. View Running Jobs

Shows all active `world_record_dsjc1000` processes:
- PID
- Command line
- Live status

### 5. View Logs & Reports

**Lists recent log files:**
- Sorted by date (newest first)
- Shows size and timestamp
- Select log to summarize

**Auto-summarizes with:**
- Best colors achieved
- Improvement events
- TDA status
- Final results

### 6. Quick Parameter Adjust

**Fast track for common changes:**
1. Target chromatic number
2. Runtime (hours)
3. Thermodynamic steps per temp
4. TE vs Kuramoto weight
5. ADP epsilon decay
6. GPU batch size

**Saves to `overrides/quick_adjust.toml` and optionally runs immediately**

## Parameter Reference

### High-Impact Parameters

**`target_chromatic`** (int, default: 83)
- Target number of colors to achieve
- World record is 83
- Try: 85-88 for easier targets while tuning

**`steps_per_temp`** (int, default: 5000)
- Thermodynamic annealing steps per temperature
- Higher = slower but more thorough
- Try: 8000-10000 for deep search

**`te_vs_kuramoto_weight`** (float, default: 0.7)
- Blend between Transfer Entropy (TE) and Kuramoto ordering
- 0.7 = 70% TE, 30% Kuramoto
- Try: 0.8-0.9 for more TE influence

**`epsilon_decay`** (float, default: 0.995)
- ADP exploration decay rate
- Lower = explores longer
- Try: 0.997 for slower decay

**`batch_size`** (int, default: 1024)
- GPU kernel batch size
- Larger = better GPU utilization (if VRAM allows)
- Try: 2048 or 4096 (watch VRAM!)

### VRAM Safety Limits

**For 8GB GPUs (RTX 5070):**
- `replicas` ≤ 56
- `num_temps` ≤ 56

**Exceeding these may cause OOM errors!**

### Boolean Toggles

**`deterministic`** (bool, default: false)
- `false`: Random seed, different results each run
- `true`: Fixed seed, reproducible results

**`use_tda`** (bool, default: true)
- Enable Topological Data Analysis
- Keep `true` for best results

**`use_pimc`** (bool, default: false)
- Path Integral Monte Carlo (very slow!)
- Only enable for deep exploration runs

## Tips & Tricks

### 1. Test Before Long Runs

```bash
# Quick 90-minute test
./prism
→ 3. Run Experiment
→ Select experiment
→ Timeout: 90m
```

### 2. Compare Configs A/B

```bash
# Run 1: Use deterministic=true, seed=42
./prism
→ 2. Create New Experiment
→ Name: config_a
→ deterministic: true, seed: 42

# Run 2: Same seed, different params
./prism
→ 2. Create New Experiment
→ Name: config_b
→ deterministic: true, seed: 42
→ (change other params)
```

### 3. Monitor Multiple Jobs

Launch several experiments, then:
```bash
./prism
→ 4. View Running Jobs
```

### 4. Quick Iterations

```bash
./prism
→ 6. Quick Parameter Adjust
→ Adjust one param
→ Run immediately
```

### 5. Check VRAM Usage

While jobs run:
```bash
watch -n 1 nvidia-smi
```

## Troubleshooting

### "rich library not found"
The launcher auto-installs it, but you can manually install:
```bash
pip3 install --user rich
```

### "No new terminal window opened"
CLI falls back to background process. Check:
```bash
tail -f /tmp/prism_last_run.log
```

Or run manually:
```bash
./tools/run_wr_toml.sh overrides/your_experiment.toml
```

### "Job not showing in menu 4"
Jobs may have finished. Check logs:
```bash
./prism
→ 5. View Logs & Reports
```

### Parameters not taking effect
Make sure you're:
1. Creating/editing experiments via CLI (or manually with correct TOML syntax)
2. Running the experiment (menu 3)
3. Not editing `wr_hyper_active.toml` directly (it's regenerated!)

## Advanced Usage

### Command Line

The CLI can also be used non-interactively (future feature):
```bash
# Quick adjust and run (planned)
./prism --quick target_chromatic=88 --run --timeout=24h
```

### Integration with Scripts

You can still use the old tools directly:
```bash
# Manual run with override
./tools/run_wr_toml.sh overrides/my_experiment.toml

# Manual summarize
./tools/summarize_wr_log.sh results/logs/wr_hyper_*.log
```

## Keyboard Shortcuts

- `Ctrl+C`: Cancel current operation
- `q`: Quit from main menu
- `0`: Back/Cancel in submenus

## Examples

### Example 1: Quick Test Run
```
1. ./prism
2. Select "6" (Quick Parameter Adjust)
3. Select "3" (Thermodynamic steps)
4. Enter: 8000
5. Confirm "Run experiment"
6. Timeout: 90m
7. Job launches in new window!
```

### Example 2: Create Custom Experiment
```
1. ./prism
2. Select "2" (Create New Experiment)
3. Name: aggressive_search
4. Configure Top-Level:
   - target_chromatic: 85
   - max_runtime_hours: 48.0
5. Configure Thermodynamic:
   - steps_per_temp: 10000
   - replicas: 56
6. Configure ADP:
   - epsilon_decay: 0.997
7. Done!
8. Select "3" (Run Experiment)
9. Select "aggressive_search"
10. Timeout: 48h
11. Launches in new window!
```

### Example 3: Monitor and Analyze
```
1. Launch job (see examples above)
2. ./prism
3. Select "4" (View Running Jobs)
   → See PID and status
4. Select "5" (View Logs & Reports)
   → Select recent log
   → View summary
```

## Next Steps

- Try the pre-configured experiments in `overrides/exp*.toml`
- Create your own experiments via CLI
- Run multiple experiments in parallel
- Compare results in `results/summaries/wr_hyper_summary.csv`

Happy tuning! 🎯