#!/usr/bin/env python3
"""
PRISM CLI Dashboard - Interactive Configuration and Job Management
"""
import os
import sys
import json
import subprocess
import glob
from pathlib import Path
from datetime import datetime

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.prompt import Prompt, Confirm, IntPrompt, FloatPrompt
    from rich.layout import Layout
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
        "target_chromatic": {"type": "int", "default": 83, "desc": "Target colors to achieve"},
        "max_runtime_hours": {"type": "float", "default": 48.0, "desc": "Maximum runtime in hours"},
        "deterministic": {"type": "bool", "default": False, "desc": "Reproducible run with fixed seed"},
        "seed": {"type": "int", "default": 9001, "desc": "Random seed"},
        "use_tda": {"type": "bool", "default": True, "desc": "Enable Topological Data Analysis"},
        "use_pimc": {"type": "bool", "default": False, "desc": "Enable Path Integral Monte Carlo (slow)"},
    },
    "CPU": {
        "threads": {"type": "int", "default": 24, "desc": "Number of CPU threads"},
    },
    "GPU": {
        "device_id": {"type": "int", "default": 0, "desc": "GPU device ID (0, 1, 2...)"},
        "streams": {"type": "int", "default": 1, "desc": "Concurrent CUDA streams"},
        "batch_size": {"type": "int", "default": 1024, "desc": "Batch size for GPU kernels"},
    },
    "ADP": {
        "epsilon": {"type": "float", "default": 1.0, "desc": "Initial exploration rate"},
        "epsilon_decay": {"type": "float", "default": 0.995, "desc": "Exploration decay per episode"},
        "epsilon_min": {"type": "float", "default": 0.03, "desc": "Minimum exploration rate"},
        "alpha": {"type": "float", "default": 0.1, "desc": "Learning rate"},
        "gamma": {"type": "float", "default": 0.95, "desc": "Discount factor"},
    },
    "Thermodynamic": {
        "replicas": {"type": "int", "default": 48, "desc": "Parallel replicas (max 56 for 8GB VRAM)"},
        "num_temps": {"type": "int", "default": 48, "desc": "Temperature levels (max 56 for 8GB VRAM)"},
        "steps_per_temp": {"type": "int", "default": 5000, "desc": "Steps per temperature"},
        "t_min": {"type": "float", "default": 0.001, "desc": "Minimum temperature"},
        "t_max": {"type": "float", "default": 10.0, "desc": "Maximum temperature"},
    },
    "Quantum": {
        "iterations": {"type": "int", "default": 30, "desc": "Quantum-classical iterations"},
        "failure_retries": {"type": "int", "default": 2, "desc": "Retry attempts on failure"},
        "fallback_on_failure": {"type": "bool", "default": True, "desc": "Fallback to CPU on GPU failure"},
        "target_chromatic": {"type": "int", "default": 83, "desc": "Target for quantum phase"},
    },
    "Memetic": {
        "population_size": {"type": "int", "default": 256, "desc": "Population size"},
        "elite_size": {"type": "int", "default": 8, "desc": "Elite individuals preserved"},
        "generations": {"type": "int", "default": 900, "desc": "Number of generations"},
        "mutation_rate": {"type": "float", "default": 0.05, "desc": "Mutation probability"},
        "tournament_size": {"type": "int", "default": 3, "desc": "Tournament selection size"},
        "local_search_depth": {"type": "int", "default": 10000, "desc": "DSATUR depth per individual"},
        "use_tsp_guidance": {"type": "bool", "default": False, "desc": "Use TSP heuristic"},
        "tsp_weight": {"type": "float", "default": 0.0, "desc": "TSP weight (if enabled)"},
    },
    "Transfer Entropy": {
        "geodesic_weight": {"type": "float", "default": 0.2, "desc": "Geodesic feature weight"},
        "te_vs_kuramoto_weight": {"type": "float", "default": 0.7, "desc": "TE vs Kuramoto blend (0.7=70% TE)"},
    },
    "Orchestrator": {
        "adp_dsatur_depth": {"type": "int", "default": 50000, "desc": "DSATUR search depth"},
        "dsatur_target_offset": {"type": "int", "default": 3, "desc": "Colors above target before phase switch"},
        "adp_min_history_for_thermo": {"type": "int", "default": 2, "desc": "Min history for thermo trigger"},
        "adp_min_history_for_quantum": {"type": "int", "default": 5, "desc": "Min history for quantum trigger"},
        "adp_min_history_for_loopback": {"type": "int", "default": 3, "desc": "Min history for loopback"},
        "restarts": {"type": "int", "default": 10, "desc": "Memetic restarts"},
    },
    "Neuromorphic": {
        "phase_threshold": {"type": "float", "default": 0.5, "desc": "Difficulty zone threshold (radians)"},
    },
    "Geodesic": {
        "num_landmarks": {"type": "int", "default": 16, "desc": "Number of landmark vertices"},
        "metric": {"type": "choice", "choices": ["hop", "shortest"], "default": "hop", "desc": "Distance metric"},
        "centrality_weight": {"type": "float", "default": 0.5, "desc": "Centrality importance"},
        "eccentricity_weight": {"type": "float", "default": 0.5, "desc": "Eccentricity importance"},
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

    table.add_row("1", "Configure Parameters")
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


def configure_parameters():
    """Interactive parameter configuration"""
    clear_screen()
    show_header()

    console.print("[bold]Select parameter category:[/bold]\n")

    categories = list(TUNABLE_PARAMS.keys())
    for i, cat in enumerate(categories, 1):
        console.print(f"{i}. {cat}")
    console.print("0. Back to main menu")

    choice = Prompt.ask("\nCategory", choices=[str(i) for i in range(len(categories) + 1)])

    if choice == "0":
        return None

    category = categories[int(choice) - 1]
    return edit_category(category)


def edit_category(category):
    """Edit all parameters in a category"""
    params = TUNABLE_PARAMS[category]
    section = SECTION_MAP[category]

    edited = {}

    clear_screen()
    show_header()
    console.print(f"[bold cyan]Editing: {category}[/bold cyan]\n")

    for param_name, param_info in params.items():
        param_type = param_info["type"]
        default = param_info["default"]
        desc = param_info["desc"]

        console.print(f"[yellow]{param_name}[/yellow]: {desc}")
        console.print(f"[dim]Default: {default}[/dim]")

        if param_type == "bool":
            value = Confirm.ask(f"Enable {param_name}", default=default)
        elif param_type == "int":
            value = IntPrompt.ask(f"Value", default=default)
        elif param_type == "float":
            value = FloatPrompt.ask(f"Value", default=default)
        elif param_type == "choice":
            choices = param_info["choices"]
            console.print(f"Choices: {', '.join(choices)}")
            value = Prompt.ask(f"Value", choices=choices, default=default)

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
        result = configure_parameters()
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

    adjustments = [
        ("Target chromatic number", "target_chromatic", "int", 83),
        ("Runtime (hours)", "max_runtime_hours", "float", 48.0),
        ("Thermodynamic steps per temp", "steps_per_temp", "int", 5000),
        ("TE vs Kuramoto weight", "te_vs_kuramoto_weight", "float", 0.7),
        ("ADP epsilon decay", "epsilon_decay", "float", 0.995),
        ("GPU batch size", "batch_size", "int", 1024),
    ]

    for i, (desc, _, _, default) in enumerate(adjustments, 1):
        console.print(f"{i}. {desc} (default: {default})")
    console.print("0. Cancel")

    choice = Prompt.ask("\nSelect parameter", choices=[str(i) for i in range(len(adjustments) + 1)])

    if choice == "0":
        return

    desc, param, ptype, default = adjustments[int(choice) - 1]

    if ptype == "int":
        value = IntPrompt.ask(f"New value for {param}", default=default)
    else:
        value = FloatPrompt.ask(f"New value for {param}", default=default)

    # Save to quick_adjust.toml
    output = OVERRIDES_DIR / "quick_adjust.toml"
    with open(output, 'w') as f:
        f.write(f"# Quick adjustment: {desc}\n")
        f.write(f"{param} = {value}\n")

    console.print(f"\n[green]✓ Saved to {output}[/green]")

    if Confirm.ask("\nRun experiment with this adjustment", default=True):
        timeout = Prompt.ask("Timeout", default="90m")
        cmd = f"cd {REPO_ROOT} && TIMEOUT={timeout} ./tools/run_wr_toml.sh {output}"
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