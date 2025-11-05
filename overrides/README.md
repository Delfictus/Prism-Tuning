# Experiment Overrides

This directory contains TOML override files for tuning experiments.

## How to Use

### Option 1: Use Pre-configured Experiments

```bash
# Run a specific experiment
./tools/run_wr_toml.sh overrides/exp1_deep_exploration.toml

# Combine multiple experiments (they merge in order)
./tools/run_wr_toml.sh overrides/exp1_deep_exploration.toml overrides/exp3_gpu_optimized.toml
```

### Option 2: Create Your Own

```bash
# Copy the template
cp overrides/experiment_template.toml overrides/my_experiment.toml

# Edit it (remove quotes from numbers and booleans!)
nano overrides/my_experiment.toml

# Run it
./tools/run_wr_toml.sh overrides/my_experiment.toml
```

## Pre-configured Experiments

### exp1_deep_exploration.toml
**Strategy:** More thorough search with slower exploration decay and deeper thermodynamic annealing

**Best for:** When you have time and want comprehensive search

**Parameters:**
- Slower epsilon decay (0.997)
- Higher minimum exploration (0.05)
- Double thermodynamic steps (10000)
- More temperature levels (64)

---

### exp2_te_heavy.toml
**Strategy:** Rely more on Transfer Entropy for vertex ordering

**Best for:** Testing if TE-based ordering outperforms Kuramoto

**Parameters:**
- 90% Transfer Entropy, 10% Kuramoto
- More geodesic influence (0.3)
- Lower neuromorphic phase threshold (0.3)

---

### exp3_gpu_optimized.toml
**Strategy:** Maximize GPU utilization

**Best for:** Getting the most out of your RTX 5070

**Parameters:**
- 4 concurrent CUDA streams
- Larger batch size (2048)
- Max safe replicas and temperatures (56 each)

---

### exp4_aggressive.toml
**Strategy:** Push all limits for maximum effort

**Best for:** Long runs when you want to throw everything at the problem

**Parameters:**
- Higher target (85 colors)
- 72-hour runtime
- More quantum iterations (50)
- Larger memetic population (512)
- Deeper search everywhere

---

### exp5_reproducible.toml
**Strategy:** Fixed seed for fair comparison

**Best for:** A/B testing different configs

**Parameters:**
- Deterministic mode enabled
- Fixed seed (42)

---

## TOML Syntax Rules

**CRITICAL:** Wrong quotes will break the config!

✅ **Correct:**
```toml
target_chromatic = 88              # Integer, no quotes
max_runtime_hours = 96.0           # Float, no quotes
deterministic = true               # Boolean, no quotes
profile = "experiment_name"        # String, use quotes
```

❌ **Wrong:**
```toml
target_chromatic = "88"            # DON'T quote numbers!
deterministic = "true"             # DON'T quote booleans!
```

## Monitoring Your Experiments

```bash
# Monitor live
./tools/monitor_wr.sh results/logs/wr_hyper_<timestamp>.log

# Summarize after completion
./tools/summarize_wr_log.sh results/logs/wr_hyper_<timestamp>.log

# View all results
cat results/summaries/wr_hyper_summary.csv
```

## Tips

1. **Start small:** Test with shorter runtime first (90m)
   ```bash
   TIMEOUT=90m ./tools/run_wr_toml.sh overrides/exp1_deep_exploration.toml
   ```

2. **Combine experiments:** Layer multiple overrides
   ```bash
   ./tools/run_wr_toml.sh overrides/exp1_deep_exploration.toml overrides/exp3_gpu_optimized.toml
   ```

3. **Check ignored keys:** Some keys don't work yet
   ```bash
   cat tools/IGNORED_KEYS.txt
   ```

4. **Lint before running:** Make sure you didn't override ignored keys
   ```bash
   ./tools/lint_overrides.sh overrides/my_experiment.toml
   ```