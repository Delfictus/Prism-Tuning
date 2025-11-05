#!/usr/bin/env python3
"""
PRISM CLI Dashboard - Interactive Configuration and Job Management
"""
import os
import sys
import json
import subprocess
import copy
from pathlib import Path
from datetime import datetime

try:
    import tomllib  # Python 3.11+
except ImportError:  # pragma: no cover - fallback when tomllib missing
    tomllib = None

try:
    import toml as toml_module  # External library fallback for older Python
except ImportError:  # pragma: no cover - handled gracefully at runtime
    toml_module = None

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.prompt import Prompt, Confirm
    from rich import box
except ImportError:
    print("Error: 'rich' library required. Install with: pip3 install rich")
    sys.exit(1)

console = Console()

# Repository root
REPO_ROOT = Path(__file__).parent.parent.absolute()
os.chdir(REPO_ROOT)

# Paths
BASE_CONFIG = REPO_ROOT / "configs/base/wr_sweep_D_aggr_seed_9001.v1.1.toml"
GLOBAL_HYPER = REPO_ROOT / "configs/global_hyper.toml"
OVERRIDES_DIR = REPO_ROOT / "overrides"
LOGS_DIR = REPO_ROOT / "results/logs"
SUMMARIES_DIR = REPO_ROOT / "results/summaries"

# Parameter definitions with types and defaults
TUNABLE_PARAMS = {
    "Top-Level": {
        "target_chromatic": {
            "type": "int",
            "default": 83,
            "desc": "Target colors to achieve",
            "hint": "Raises the target; e.g. 85 pushes closer to WR attempts.",
        },
        "max_runtime_hours": {
            "type": "float",
            "default": 48.0,
            "desc": "Maximum runtime in hours",
            "hint": "Longer runs search deeper; 72.0 keeps the solver busy for three days.",
        },
        "deterministic": {
            "type": "bool",
            "default": False,
            "desc": "Reproducible run with fixed seed",
            "hint": "Enable for repeatable traces when comparing logs with teammates.",
        },
        "seed": {
            "type": "int",
            "default": 9001,
            "desc": "Random seed",
            "hint": "Controls the RNG sequence; 1337 explores a different path.",
        },
        "use_tda": {
            "type": "bool",
            "default": True,
            "desc": "Enable Topological Data Analysis",
            "hint": "Toggle TDA heuristics; disable if you need to save a bit of VRAM.",
        },
        "use_pimc": {
            "type": "bool",
            "default": False,
            "desc": "Enable Path Integral Monte Carlo (slow)",
            "hint": "Activates PIMC annealing; expect slower runs but deeper exploration.",
        },
    },
    "CPU": {
        "threads": {
            "type": "int",
            "default": 24,
            "desc": "Number of CPU threads",
            "hint": "Cap worker threads; set 32 on a 32-core host to saturate the CPU.",
        },
    },
    "GPU": {
        "device_id": {
            "type": "int",
            "default": 0,
            "desc": "GPU device ID (0, 1, 2...)",
            "hint": "Choose the GPU index; e.g. 1 binds to your second card.",
        },
        "streams": {
            "type": "int",
            "default": 1,
            "desc": "Concurrent CUDA streams",
            "hint": "Higher streams overlap kernels; 4 keeps modern GPUs busier.",
        },
        "batch_size": {
            "type": "int",
            "default": 1024,
            "desc": "Batch size for GPU kernels",
            "hint": "Larger batches raise occupancy; 4096 suits 24GB+ cards.",
        },
    },
    "ADP": {
        "epsilon": {
            "type": "float",
            "default": 1.0,
            "desc": "Initial exploration rate",
            "hint": "Starting exploration rate; drop to 0.5 to exploit sooner.",
        },
        "epsilon_decay": {
            "type": "float",
            "default": 0.995,
            "desc": "Exploration decay per episode",
            "hint": "Closer to 1.0 delays exploitation; 0.999 helps break plateaus.",
        },
        "epsilon_min": {
            "type": "float",
            "default": 0.03,
            "desc": "Minimum exploration rate",
            "hint": "Floor on exploration; 0.1 keeps trying new moves late in a run.",
        },
        "alpha": {
            "type": "float",
            "default": 0.1,
            "desc": "Learning rate",
            "hint": "Update rate; 0.05 slows learning when rewards are noisy.",
        },
        "gamma": {
            "type": "float",
            "default": 0.95,
            "desc": "Discount factor",
            "hint": "Reward discount; 0.99 emphasises long-term payoffs.",
        },
    },
    "Thermodynamic": {
        "replicas": {
            "type": "int",
            "default": 48,
            "desc": "Parallel replicas (max 56 for 8GB VRAM)",
            "hint": "More replicas smooth swaps; 56 is the safe max for 8GB cards.",
        },
        "num_temps": {
            "type": "int",
            "default": 48,
            "desc": "Temperature levels (max 56 for 8GB VRAM)",
            "hint": "Match replicas (e.g. 56) for a balanced temperature ladder.",
        },
        "steps_per_temp": {
            "type": "int",
            "default": 5000,
            "desc": "Steps per temperature",
            "hint": "Extra steps per level stabilise the phase; 20000 helps on stubborn graphs.",
        },
        "t_min": {
            "type": "float",
            "default": 0.001,
            "desc": "Minimum temperature",
            "hint": "Lowest temperature; 0.0005 tightens the endgame search.",
        },
        "t_max": {
            "type": "float",
            "default": 10.0,
            "desc": "Maximum temperature",
            "hint": "Highest temperature; 20.0 boosts exploration when stuck.",
        },
    },
    "Quantum": {
        "iterations": {
            "type": "int",
            "default": 30,
            "desc": "Quantum-classical iterations",
            "hint": "More hybrid loops deepen search; 50 suits aggressive runs.",
        },
        "failure_retries": {
            "type": "int",
            "default": 2,
            "desc": "Retry attempts on failure",
            "hint": "Extra retries rebuild failing schedules; 4 offers more resilience.",
        },
        "fallback_on_failure": {
            "type": "bool",
            "default": True,
            "desc": "Fallback to CPU on GPU failure",
            "hint": "Keep true for reliability; disable only while debugging GPU issues.",
        },
        "target_chromatic": {
            "type": "int",
            "default": 83,
            "desc": "Target for quantum phase",
            "hint": "Quantum target; set 84 to aim above the classical goal.",
        },
    },
    "Memetic": {
        "population_size": {
            "type": "int",
            "default": 256,
            "desc": "Population size",
            "hint": "Larger populations widen coverage; 512 doubles diversity.",
        },
        "elite_size": {
            "type": "int",
            "default": 8,
            "desc": "Elite individuals preserved",
            "hint": "Elites carried forward; 16 preserves more top candidates.",
        },
        "generations": {
            "type": "int",
            "default": 900,
            "desc": "Number of generations",
            "hint": "More generations extend evolution; 2000 for marathon sweeps.",
        },
        "mutation_rate": {
            "type": "float",
            "default": 0.05,
            "desc": "Mutation probability",
            "hint": "Higher mutation injects diversity; 0.1 shakes stagnation loose.",
        },
        "tournament_size": {
            "type": "int",
            "default": 3,
            "desc": "Tournament selection size",
            "hint": "Larger tournaments increase pressure; 5 strongly favours elites.",
        },
        "local_search_depth": {
            "type": "int",
            "default": 10000,
            "desc": "DSATUR depth per individual",
            "hint": "Deepens per-individual DSATUR search; 20000 digs harder before handoff.",
        },
        "use_tsp_guidance": {
            "type": "bool",
            "default": False,
            "desc": "Use TSP heuristic",
            "hint": "Enable to bias by TSP paths; helpful on geometric instances.",
        },
        "tsp_weight": {
            "type": "float",
            "default": 0.0,
            "desc": "TSP weight (if enabled)",
            "hint": "Heuristic weight; 0.3 mixes in TSP guidance when enabled.",
        },
    },
    "Transfer Entropy": {
        "geodesic_weight": {
            "type": "float",
            "default": 0.2,
            "desc": "Geodesic feature weight",
            "hint": "Higher weight emphasises graph distance; 0.3 balances signals.",
        },
        "te_vs_kuramoto_weight": {
            "type": "float",
            "default": 0.7,
            "desc": "TE vs Kuramoto blend (0.7=70% TE)",
            "hint": "Closer to 1 leans on TE; 0.95 suits plateau-breaking recipes.",
        },
    },
    "Orchestrator": {
        "adp_dsatur_depth": {
            "type": "int",
            "default": 50000,
            "desc": "DSATUR search depth",
            "hint": "Higher depth extends DSATUR lookahead; 100000 for aggressive scans.",
        },
        "dsatur_target_offset": {
            "type": "int",
            "default": 3,
            "desc": "Colors above target before phase switch",
            "hint": "Lower offset triggers phase switches sooner; 2 flips earlier.",
        },
        "adp_min_history_for_thermo": {
            "type": "int",
            "default": 2,
            "desc": "Min history for thermo trigger",
            "hint": "Smaller history fires thermo faster; 1 starts almost immediately.",
        },
        "adp_min_history_for_quantum": {
            "type": "int",
            "default": 5,
            "desc": "Min history for quantum trigger",
            "hint": "Lower value engages quantum sooner; 2 is quite aggressive.",
        },
        "adp_min_history_for_loopback": {
            "type": "int",
            "default": 3,
            "desc": "Min history for loopback",
            "hint": "Controls full reset cadence; 4 recycles phases sooner.",
        },
        "restarts": {
            "type": "int",
            "default": 10,
            "desc": "Memetic restarts",
            "hint": "More restarts diversify search; 20 for wide exploration.",
        },
    },
    "Neuromorphic": {
        "phase_threshold": {
            "type": "float",
            "default": 0.5,
            "desc": "Difficulty zone threshold (radians)",
            "hint": "Lower threshold engages neuromorphic helpers more often; 0.4 catches spikes.",
        },
    },
    "Geodesic": {
        "num_landmarks": {
            "type": "int",
            "default": 16,
            "desc": "Number of landmark vertices",
            "hint": "More landmarks sharpen embeddings; 32 for huge graphs.",
        },
        "metric": {
            "type": "choice",
            "choices": ["hop", "shortest"],
            "default": "hop",
            "desc": "Distance metric",
            "hint": "Switch to 'shortest' for exact distances; 'hop' is faster on large instances.",
        },
        "centrality_weight": {
            "type": "float",
            "default": 0.5,
            "desc": "Centrality importance",
            "hint": "Higher weight favours central nodes; 0.7 spotlights hubs.",
        },
        "eccentricity_weight": {
            "type": "float",
            "default": 0.5,
            "desc": "Eccentricity importance",
            "hint": "Higher weight favours fringe nodes; 0.7 probes the periphery.",
        },
    },
}

# TOML section mapping
SECTION_MAP = {
    "Top-Level": "",
    "CPU": "cpu",
    "GPU": "gpu",
    "ADP": "adp",
    "Thermodynamic": "thermo",
    "Quantum": "quantum",
    "Memetic": "memetic",
    "Transfer Entropy": "transfer_entropy",
    "Orchestrator": "orchestrator",
    "Neuromorphic": "neuromorphic",
    "Geodesic": "geodesic",
}


SECTION_PARAM_ORDER = {}
PARAM_LOOKUP = {}
for category, params in TUNABLE_PARAMS.items():
    section = SECTION_MAP[category]
    order = SECTION_PARAM_ORDER.setdefault(section, [])
    for param_name, info in params.items():
        if param_name not in order:
            order.append(param_name)
        PARAM_LOOKUP[(section, param_name)] = info


def _load_toml(path: Path) -> dict:
    """Load TOML data from path with available parser."""
    if not path.exists():
        return {}

    if tomllib is not None:
        with open(path, "rb") as handle:
            return tomllib.load(handle)

    if toml_module is not None:
        with open(path, "r", encoding="utf-8") as handle:
            return toml_module.load(handle)

    raise RuntimeError("No TOML parser available. Install the 'toml' package.")


def _deep_merge(base: dict, override: dict) -> None:
    """Recursively merge override into base."""
    for key, value in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value


def load_active_config() -> dict:
    """Return the merged configuration (base + global overrides)."""
    base_data = _load_toml(BASE_CONFIG)
    global_data = _load_toml(GLOBAL_HYPER)

    merged = copy.deepcopy(base_data)
    _deep_merge(merged, global_data)
    return merged


def load_global_config() -> dict:
    """Load the global overrides file."""
    return copy.deepcopy(_load_toml(GLOBAL_HYPER))


def _format_toml_value(value):
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return f"{value}"
    return json.dumps(value)


def _iter_section_items(section: str, data: dict):
    order = SECTION_PARAM_ORDER.get(section, [])
    seen = set()
    for key in order:
        if key in data:
            seen.add(key)
            yield key, data[key]
    for key in sorted(data.keys()):
        if key not in seen:
            yield key, data[key]


def write_global_config(data: dict) -> None:
    """Persist the global override configuration."""
    GLOBAL_HYPER.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        "# PRISM CLI Managed Overrides",
        f"# Last updated: {datetime.now().isoformat()}",
        "",
    ]

    # Top-level entries
    top_level = {k: v for k, v in data.items() if not isinstance(v, dict)}
    seen_top = set()
    for key in SECTION_PARAM_ORDER.get("", []):
        if key in top_level:
            lines.append(f"{key} = {_format_toml_value(top_level[key])}")
            seen_top.add(key)
    for key in sorted(top_level.keys()):
        if key not in seen_top:
            lines.append(f"{key} = {_format_toml_value(top_level[key])}")
    if top_level:
        lines.append("")

    section_order = [sec for sec in SECTION_PARAM_ORDER.keys() if sec]
    extra_sections = [sec for sec in data.keys() if isinstance(data[sec], dict) and sec not in section_order]
    for sec in sorted(extra_sections):
        section_order.append(sec)

    for section in section_order:
        section_data = data.get(section, {})
        if not section_data:
            continue
        lines.append(f"[{section}]")
        for key, value in _iter_section_items(section, section_data):
            lines.append(f"{key} = {_format_toml_value(value)}")
        lines.append("")

    contents = "\n".join(lines).rstrip() + "\n"
    with open(GLOBAL_HYPER, "w", encoding="utf-8") as handle:
        handle.write(contents)


def apply_config_changes(entries):
    """Apply a sequence of section parameter updates to the global config."""
    config = load_global_config()

    for entry in entries:
        section = entry["section"]
        params = entry["params"]

        if section:
            section_dict = config.setdefault(section, {})
            section_dict.update(params)
        else:
            config.update(params)

    write_global_config(config)


def get_current_value(active_config: dict, section: str, key: str, default):
    if section:
        return active_config.get(section, {}).get(key, default)
    return active_config.get(key, default)


BACK_SENTINEL = object()


def _prompt_bool(label: str, current_value, default):
    default_bool = current_value if isinstance(current_value, bool) else bool(default)
    default_choice = "yes" if default_bool else "no"
    response = Prompt.ask(
        f"{label} (yes/no/back)",
        choices=["yes", "no", "back"],
        default=default_choice,
    )
    if response == "back":
        return BACK_SENTINEL
    return response == "yes"


def _prompt_int(label: str, current_value, default):
    default_val = current_value if isinstance(current_value, int) else int(default)
    while True:
        response = Prompt.ask(
            f"{label} (type 'back' to return)",
            default=str(default_val),
        )
        if response.strip().lower() == "back":
            return BACK_SENTINEL
        try:
            return int(response)
        except ValueError:
            console.print("[red]Please enter an integer or 'back'.[/red]")


def _prompt_float(label: str, current_value, default):
    if isinstance(current_value, (int, float)):
        default_val = float(current_value)
    else:
        default_val = float(default)
    while True:
        response = Prompt.ask(
            f"{label} (type 'back' to return)",
            default=str(default_val),
        )
        if response.strip().lower() == "back":
            return BACK_SENTINEL
        try:
            return float(response)
        except ValueError:
            console.print("[red]Please enter a number or 'back'.[/red]")


def _prompt_choice(label: str, choices, current_value, default):
    default_choice = str(current_value) if str(current_value) in choices else str(default)
    response = Prompt.ask(
        f"{label} (type 'back' to return)",
        choices=list(choices) + ["back"],
        default=default_choice,
    )
    if response == "back":
        return BACK_SENTINEL
    return response


def prompt_parameter_value(label: str, param_info: dict, current_value):
    param_type = param_info["type"]
    default = param_info["default"]

    if param_type == "bool":
        return _prompt_bool(label, current_value, default)
    if param_type == "int":
        return _prompt_int(label, current_value, default)
    if param_type == "float":
        return _prompt_float(label, current_value, default)
    if param_type == "choice":
        return _prompt_choice(label, param_info["choices"], current_value, default)

    return current_value


def clear_screen():
    """Clear terminal screen"""
    os.system('clear' if os.name != 'nt' else 'cls')


def show_header():
    """Display CLI header"""
    console.print(Panel.fit(
        "[bold cyan]PRISM CLI Dashboard[/bold cyan]\n"
        "[dim]Interactive Configuration & Job Management[/dim]",
        border_style="cyan"
    ))


def main_menu():
    """Display main menu and get user choice"""
    clear_screen()
    show_header()

    table = Table(show_header=False, box=box.SIMPLE)
    table.add_column("Option", style="cyan", width=4)
    table.add_column("Description", style="white")

    table.add_row("1", "Edit Active Config")
    table.add_row("2", "Create New Experiment")
    table.add_row("3", "Run Experiment")
    table.add_row("4", "View Running Jobs")
    table.add_row("5", "View Logs & Reports")
    table.add_row("6", "Quick Parameter Adjust")
    table.add_row("7", "Load Experiment Template")
    table.add_row("q", "Quit")

    console.print(table)
    console.print()

    choice = Prompt.ask("Select option", choices=["1", "2", "3", "4", "5", "6", "7", "q"])
    return choice


def configure_parameters(for_experiment: bool = False):
    """Interactive parameter configuration."""
    while True:
        clear_screen()
        show_header()

        console.print("[bold]Select parameter category:[/bold]\n")
        console.print("[dim]Type 'back' inside a category to return here without saving.[/dim]\n")

        categories = list(TUNABLE_PARAMS.keys())
        for i, cat in enumerate(categories, 1):
            console.print(f"{i}. {cat}")
        console.print("0. Back to main menu")

        choice = Prompt.ask("\nCategory", choices=[str(i) for i in range(len(categories) + 1)])

        if choice == "0":
            return None

        category = categories[int(choice) - 1]
        active_config = load_active_config()
        result = edit_category(category, active_config)

        if result is None:
            if for_experiment:
                return None
            continue

        if for_experiment:
            return result

        apply_config_changes([result])
        console.print("\n[green]✓ Updated configs/global_hyper.toml[/green]\n")

        if not Confirm.ask("Edit another category", default=False):
            break

    if not for_experiment:
        Prompt.ask("\nPress Enter to continue")


def edit_category(category, active_config):
    """Edit all parameters in a category."""
    params = TUNABLE_PARAMS[category]
    section = SECTION_MAP[category]

    edited = {}

    clear_screen()
    show_header()
    console.print(f"[bold cyan]Editing: {category}[/bold cyan]\n")
    console.print("[dim]Type 'back' at any prompt to return without saving changes.[/dim]\n")

    for param_name, param_info in params.items():
        desc = param_info["desc"]
        current_value = get_current_value(active_config, section, param_name, param_info["default"])
        label = param_info.get("label", param_name.replace("_", " "))

        console.print(f"[yellow]{label}[/yellow]: {desc}")
        console.print(f"[dim]Current: {current_value}[/dim]")
        hint = param_info.get("hint")
        if hint:
            console.print(f"[dim]Hint: {hint}[/dim]")

        value = prompt_parameter_value(label, param_info, current_value)
        if value is BACK_SENTINEL:
            console.print("\n[yellow]Back pressed. No changes saved for this category.[/yellow]")
            return None

        edited[param_name] = value
        console.print()

    return {"section": section, "params": edited}


def save_to_toml(config_dict, output_file):
    """Save configuration to TOML file"""
    lines = ["# PRISM Experiment Configuration", f"# Created: {datetime.now().isoformat()}", ""]

    # Group by section
    by_section = {}
    for entry in config_dict:
        section = entry["section"]
        if section not in by_section:
            by_section[section] = []
        by_section[section].extend(entry["params"].items())

    # Write top-level (no section)
    if "" in by_section:
        for key, value in by_section[""]:
            if isinstance(value, bool):
                lines.append(f"{key} = {str(value).lower()}")
            elif isinstance(value, str):
                lines.append(f'{key} = "{value}"')
            else:
                lines.append(f"{key} = {value}")
        lines.append("")
        del by_section[""]

    # Write sections
    for section, params in by_section.items():
        lines.append(f"[{section}]")
        for key, value in params:
            if isinstance(value, bool):
                lines.append(f"{key} = {str(value).lower()}")
            elif isinstance(value, str):
                lines.append(f'{key} = "{value}"')
            else:
                lines.append(f"{key} = {value}")
        lines.append("")

    with open(output_file, 'w') as f:
        f.write('\n'.join(lines))

    console.print(f"[green]✓ Saved to {output_file}[/green]")

    # Validate TOML syntax
    validator = REPO_ROOT / "tools" / "validate_toml.sh"
    if validator.exists():
        result = subprocess.run([str(validator), str(output_file)], capture_output=True, text=True)
        if result.returncode != 0:
            console.print(f"[yellow]⚠ TOML validation warning:[/yellow]\n{result.stderr}")
        else:
            console.print("[dim]✓ TOML syntax validated[/dim]")


def create_experiment():
    """Create a new experiment configuration"""
    clear_screen()
    show_header()

    console.print("[bold]Create New Experiment[/bold]\n")

    exp_name = Prompt.ask("Experiment name (no spaces)")
    exp_name = exp_name.replace(" ", "_")

    console.print("\n[dim]Configure parameters for this experiment...[/dim]\n")

    config_data = []

    while True:
        result = configure_parameters(for_experiment=True)
        if result is None:
            break
        config_data.append(result)

        if not Confirm.ask("\nConfigure another category", default=False):
            break

    if config_data:
        output_file = OVERRIDES_DIR / f"{exp_name}.toml"
        save_to_toml(config_data, output_file)
        console.print(f"\n[bold green]Experiment '{exp_name}' created![/bold green]")
    else:
        console.print("\n[yellow]No parameters configured. Experiment not saved.[/yellow]")

    Prompt.ask("\nPress Enter to continue")


def list_experiments():
    """List available experiment files"""
    experiments = sorted(OVERRIDES_DIR.glob("*.toml"))
    exp_names = [exp.stem for exp in experiments if exp.stem not in ["experiment_template", "README"]]
    return exp_names, experiments


def run_experiment():
    """Launch an experiment in a new terminal window"""
    clear_screen()
    show_header()

    console.print("[bold]Run Experiment[/bold]\n")

    exp_names, exp_files = list_experiments()

    if not exp_names:
        console.print("[yellow]No experiments found. Create one first![/yellow]")
        Prompt.ask("\nPress Enter to continue")
        return

    console.print("Available experiments:")
    for i, name in enumerate(exp_names, 1):
        console.print(f"{i}. {name}")
    console.print("0. Cancel")

    choice = Prompt.ask("\nSelect experiment", choices=[str(i) for i in range(len(exp_names) + 1)])

    if choice == "0":
        return

    exp_file = exp_files[int(choice) - 1]

    # Ask for timeout
    timeout = Prompt.ask("Timeout (e.g., 90m, 24h, 48h)", default="90m")

    # Build command
    cmd = f"cd {REPO_ROOT} && TIMEOUT={timeout} ./tools/run_wr_toml.sh {exp_file}"

    # Detect terminal and launch in new window
    launch_in_new_window(cmd, f"PRISM: {exp_file.stem}")

    console.print(f"\n[green]✓ Launched {exp_file.stem} in new window![/green]")
    Prompt.ask("\nPress Enter to continue")


def launch_in_new_window(command, title="PRISM Job"):
    """Launch command in a new terminal window"""
    # Try different terminals
    terminals = [
        ["gnome-terminal", "--title", title, "--", "bash", "-c", f"{command}; read -p 'Press Enter to close...'"],
        ["xterm", "-title", title, "-e", f"bash -c \"{command}; read -p 'Press Enter to close...'\""],
        ["konsole", "--title", title, "-e", f"bash -c \"{command}; read -p 'Press Enter to close...'\""],
    ]

    for term_cmd in terminals:
        try:
            subprocess.Popen(term_cmd, start_new_session=True)
            return True
        except FileNotFoundError:
            continue

    # Fallback: background process with tmux if available
    try:
        tmux_cmd = f"tmux new-window -n '{title}' '{command}'"
        subprocess.run(tmux_cmd, shell=True, check=True)
        console.print("[dim]Launched in tmux window[/dim]")
        return True
    except:
        pass

    # Last resort: background process
    console.print("[yellow]Warning: Could not open new terminal. Running in background...[/yellow]")
    subprocess.Popen(f"bash -c \"{command}\" > /tmp/prism_last_run.log 2>&1", shell=True, start_new_session=True)
    console.print("[dim]Output redirected to /tmp/prism_last_run.log[/dim]")
    return False


def view_running_jobs():
    """Show running PRISM jobs"""
    clear_screen()
    show_header()

    console.print("[bold]Running Jobs[/bold]\n")

    # Check for running world_record_dsjc1000 processes
    try:
        result = subprocess.run(
            ["pgrep", "-f", "world_record_dsjc1000"],
            capture_output=True, text=True
        )
        pids = result.stdout.strip().split('\n') if result.stdout else []
        pids = [p for p in pids if p]

        if pids:
            table = Table()
            table.add_column("PID", style="cyan")
            table.add_column("Command", style="white")

            for pid in pids:
                try:
                    cmd_result = subprocess.run(
                        ["ps", "-p", pid, "-o", "cmd="],
                        capture_output=True, text=True
                    )
                    cmd = cmd_result.stdout.strip()
                    table.add_row(pid, cmd[:80] + "..." if len(cmd) > 80 else cmd)
                except:
                    pass

            console.print(table)
            console.print(f"\n[green]Found {len(pids)} running job(s)[/green]")
        else:
            console.print("[yellow]No running jobs found[/yellow]")
    except Exception as e:
        console.print(f"[red]Error checking jobs: {e}[/red]")

    Prompt.ask("\nPress Enter to continue")


def view_logs_and_reports():
    """View logs and generate reports"""
    clear_screen()
    show_header()

    console.print("[bold]Logs & Reports[/bold]\n")

    # List recent logs
    logs = sorted(LOGS_DIR.glob("*.log"), key=os.path.getmtime, reverse=True)[:10]

    if not logs:
        console.print("[yellow]No logs found[/yellow]")
        Prompt.ask("\nPress Enter to continue")
        return

    console.print("Recent logs:")
    for i, log in enumerate(logs, 1):
        mtime = datetime.fromtimestamp(log.stat().st_mtime)
        size_mb = log.stat().st_size / (1024 * 1024)
        console.print(f"{i}. {log.name} ({size_mb:.1f}MB, {mtime.strftime('%Y-%m-%d %H:%M')})")
    console.print("0. Back")

    choice = Prompt.ask("\nSelect log to view/summarize", choices=[str(i) for i in range(len(logs) + 1)])

    if choice == "0":
        return

    log_file = logs[int(choice) - 1]

    # Summarize the log
    console.print(f"\n[cyan]Summarizing {log_file.name}...[/cyan]\n")

    try:
        result = subprocess.run(
            ["python3", "tools/summarize_wr_log.py", str(log_file)],
            capture_output=True, text=True, cwd=REPO_ROOT
        )
        console.print(result.stdout)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")

    Prompt.ask("\nPress Enter to continue")


def quick_adjust():
    """Quick single-parameter adjustment"""
    clear_screen()
    show_header()

    console.print("[bold]Quick Parameter Adjust[/bold]\n")
    console.print("[dim]Common adjustments for quick experiments[/dim]\n")

    active_config = load_active_config()
    adjustments = [
        ("Target chromatic number", "", "target_chromatic"),
        ("Runtime (hours)", "", "max_runtime_hours"),
        ("Thermodynamic steps per temp", "thermo", "steps_per_temp"),
        ("TE vs Kuramoto weight", "transfer_entropy", "te_vs_kuramoto_weight"),
        ("ADP epsilon decay", "adp", "epsilon_decay"),
        ("GPU batch size", "gpu", "batch_size"),
    ]

    for i, (desc, section, param) in enumerate(adjustments, 1):
        param_info = PARAM_LOOKUP.get((section, param), {})
        default = param_info.get("default")
        current_value = get_current_value(active_config, section, param, default)
        console.print(f"{i}. {desc} (current: {current_value})")
        hint = param_info.get("hint")
        if hint:
            console.print(f"   [dim]Hint: {hint}[/dim]")
    console.print("0. Cancel")

    choice = Prompt.ask("\nSelect parameter", choices=[str(i) for i in range(len(adjustments) + 1)])

    if choice == "0":
        return

    desc, section, param = adjustments[int(choice) - 1]
    param_info = PARAM_LOOKUP.get((section, param))
    if not param_info:
        console.print("[red]Unable to locate parameter metadata.[/red]")
        Prompt.ask("\nPress Enter to continue")
        return

    current_value = get_current_value(active_config, section, param, param_info.get("default"))
    label = param_info.get("label", param.replace("_", " "))

    console.print(f"\n[bold]{desc}[/bold]")
    console.print(f"Current value: [cyan]{current_value}[/cyan]")
    hint = param_info.get("hint")
    if hint:
        console.print(f"[dim]Hint: {hint}[/dim]")

    value = prompt_parameter_value(label, param_info, current_value)
    if value is BACK_SENTINEL:
        console.print("\n[yellow]Back pressed. No quick adjust applied.[/yellow]")
        return

    apply_config_changes([{"section": section, "params": {param: value}}])

    console.print(f"\n[green]✓ Updated configs/global_hyper.toml ({param} = {value})[/green]")

    if Confirm.ask("\nRun experiment with these settings", default=True):
        timeout = Prompt.ask("Timeout", default="90m")
        cmd = f"cd {REPO_ROOT} && TIMEOUT={timeout} ./tools/run_wr_toml.sh"
        launch_in_new_window(cmd, f"PRISM: Quick Adjust ({param}={value})")
        console.print("[green]✓ Launched in new window![/green]")

    Prompt.ask("\nPress Enter to continue")


def main():
    """Main CLI loop"""
    while True:
        choice = main_menu()

        if choice == "1":
            configure_parameters()
        elif choice == "2":
            create_experiment()
        elif choice == "3":
            run_experiment()
        elif choice == "4":
            view_running_jobs()
        elif choice == "5":
            view_logs_and_reports()
        elif choice == "6":
            quick_adjust()
        elif choice == "7":
            console.print("[yellow]Load template feature coming soon![/yellow]")
            Prompt.ask("\nPress Enter to continue")
        elif choice == "q":
            console.print("\n[cyan]Goodbye![/cyan]\n")
            break


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n\n[cyan]Interrupted. Goodbye![/cyan]\n")
        sys.exit(0)
