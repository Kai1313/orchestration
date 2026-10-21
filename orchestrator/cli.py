import asyncio
from pathlib import Path
import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from orchestrator.config import load_config
from orchestrator.core.engine import OrchestrationEngine
from orchestrator.core.state import TDDPhase
from orchestrator.core.checkpoint import CheckpointManager

app = typer.Typer(
    name="orchestrator",
    help="Autonomous AI Software Development Orchestration Engine",
    add_completion=False,
)
console = Console()


@app.command()
def solve(
    issue: str = typer.Option(..., "--issue", "-i", help="Issue description or path to a markdown issue file"),
    repo: str = typer.Option(".", "--repo", "-r", help="Path to repository"),
    image: str = typer.Option(None, "--image", "-img", help="Path to screenshot or visual issue attachment"),
    sandbox: str = typer.Option("local", "--sandbox", "-s", help="Execution environment: 'local' or 'docker'"),
    docker_image: str = typer.Option(None, "--docker-image", help="Docker base image (e.g. node:20-slim, python:3.11-slim)"),
    interactive: bool = typer.Option(False, "--interactive", "-it", help="Enable interactive breakpoints on failure and PR approval"),
    in_place: bool = typer.Option(False, "--in-place", help="Edit directly in active working tree on a new git branch"),
    skip_verify: bool = typer.Option(False, "--skip-verify", help="Skip automated test reproduction and verification stages"),
    web: bool = typer.Option(False, "--web", help="Web preset: enables in-place editing, skip-verify, and interactive preview"),
    resume: str = typer.Option(None, "--resume", help="Resume an existing run_id from checkpoint"),
    test_cmd: str = typer.Option(None, "--test-cmd", help="Override auto-detected test command"),
    config_file: str = typer.Option(None, "--config", "-c", help="Path to orchestrator.yaml configuration"),
):
    """
    Solves a software issue autonomously following the 5-Stage TDD State Machine.
    """
    if web:
        in_place = True
        skip_verify = True
        interactive = True

    cfg = load_config(config_file)
    repo_path = Path(repo).resolve()

    # Read issue text from file if path is given
    issue_file = Path(issue)
    detected_image = image
    if issue_file.exists() and issue_file.is_file():
        issue_content = issue_file.read_text(encoding="utf-8")
        base_dir = issue_file.parent
    else:
        issue_content = issue
        base_dir = Path.cwd()

    if not detected_image:
        import re
        m = re.search(r'!\[.*?\]\((.*?)\)', issue_content)
        if m:
            potential_img = (base_dir / m.group(1)).resolve()
            if potential_img.exists() and potential_img.is_file():
                detected_image = str(potential_img)

    console.print(Panel(
        f"[bold green]AI Software Development Orchestrator[/bold green]\n"
        f"Target Repo: {repo_path}\n"
        f"Sandbox: {sandbox}\n"
        f"Interactive Mode: {interactive}\n"
        f"In-Place Branching: {in_place}\n"
        f"Skip Verify: {skip_verify}\n"
        f"Attached Image: {detected_image or 'None'}\n"
        f"Issue: {issue_content[:120]}...",
        title="Session Started",
    ))

    engine = OrchestrationEngine(cfg, interactive=interactive)
    state = asyncio.run(engine.run(
        repo_path=repo_path,
        issue_text=issue_content,
        sandbox=sandbox,
        resume_run_id=resume,
        test_cmd_override=test_cmd,
        docker_image_override=docker_image,
        image_path=detected_image,
        in_place=in_place,
        skip_verify=skip_verify,
    ))

    if state.current_phase == TDDPhase.COMPLETED:
        console.print("\n" + "=" * 60)
        console.print(Panel(
            f"[bold green]Run Completed Successfully![/bold green]\n\n"
            f"Branch: {state.worktree_branch}\n"
            f"Commit: {state.commit_hash}\n"
            f"Tokens: {state.prompt_tokens + state.completion_tokens:,}\n"
            f"Cost: ${state.estimated_cost_usd:.4f}\n\n"
            f"[bold cyan]{state.pr_title}[/bold cyan]\n\n"
            f"{state.pr_body}",
            title="Pull Request Ready",
        ))
    else:
        console.print(Panel(
            f"[bold red]Run Ended: {state.current_phase}[/bold red]\n"
            f"Error: {state.last_error}\n"
            f"Run ID: {state.run_id}",
            title="Execution Failed",
        ))


@app.command()
def status(
    run_id: str = typer.Argument(..., help="Run ID to inspect"),
    repo: str = typer.Option(".", "--repo", "-r", help="Path to repository"),
):
    """
    Displays the checkpoint status and event metrics of a past run.
    """
    repo_path = Path(repo).resolve()
    checkpoint_dir = repo_path / ".orchestrator" / "runs"
    checkpoint_mgr = CheckpointManager(checkpoint_dir, run_id)
    data = checkpoint_mgr.load_state()

    if not data:
        console.print(f"[bold red]Run '{run_id}' not found in {checkpoint_dir}[/bold red]")
        raise typer.Exit(1)

    table = Table(title=f"Run Status: {run_id}")
    table.add_column("Field", style="cyan")
    table.add_column("Value", style="white")

    for k, v in data.items():
        if k in ("pr_body", "plan_summary") and v:
            table.add_row(k, str(v)[:80] + "...")
        else:
            table.add_row(k, str(v))

    console.print(table)


@app.command()
def config():
    """
    Inspects loaded provider credentials, models, and role mappings.
    """
    cfg = load_config()
    table = Table(title="Configured Roles & Model Routing")
    table.add_column("Role", style="cyan")
    table.add_column("Provider", style="magenta")
    table.add_column("Model", style="green")
    table.add_column("API Key Status", style="yellow")

    for role_name, role_cfg in cfg.roles.items():
        provider = cfg.providers.get(role_cfg.provider)
        if provider:
            key = provider.get_api_key()
            status_text = "[green]Found[/green]" if (key or provider.name == "ollama") else "[red]Missing (Env)[/red]"
        else:
            status_text = "[red]Unknown[/red]"
        table.add_row(role_name, role_cfg.provider, role_cfg.model, status_text)

    console.print(table)


if __name__ == "__main__":
    app()
