from pathlib import Path

import typer

from .common import console, run_cmd


app = typer.Typer()


@app.command()
def deploy(
    topology: Path = typer.Argument(..., help="Path to the topology file"),
    sudo: bool = typer.Option(True, help="Use sudo to run containerlab"),
):
    console.log("Deploying containerlab topology", style="info")
    console.log(f"Topology file: {topology}", style="info")
    if not topology.exists():
        console.log(f"Topology file not found: {topology}", style="error")
        raise typer.Exit(code=1)
    exec_cmd = f"containerlab deploy -t {topology}"
    if sudo:
        exec_cmd = f"sudo {exec_cmd}"
    console.log(f"Executing: {exec_cmd}", style="info")
    run_cmd(exec_cmd, task_name="Deploying containerlab topology")
