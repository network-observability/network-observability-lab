"""Netobs CLI."""
import os
import subprocess
import shlex
from typing import Optional
from pathlib import Path

import typer
from rich.console import Console
from rich.theme import Theme

custom_theme = Theme(
    {
        "info": "cyan",
        "warning": "bold magenta",
        "error": "bold red",
        "good": "bold green",
    }
)

console = Console(
    color_system="truecolor",
    log_path=False,
    record=True,
    theme=custom_theme,
    force_terminal=True,
)

app = typer.Typer()
containerlab_app = typer.Typer()
app.add_typer(containerlab_app, name="containerlab")

docker_app = typer.Typer()
app.add_typer(docker_app, name="docker")


def run_cmd(
    exec_cmd: str,
    envvars: Optional[dict] = None,
    cwd: Optional[str] = None,
    timeout: int = 60,
    shell: bool = False,
    capture_output: bool = False,
    task_name: str = "",
) -> subprocess.CompletedProcess:
    """Run a command and return the result.

    Args:
        exec_cmd (str): Command to execute
        envvars (dict, optional): Environment variables to pass to the command. Defaults to None.
        cwd (str, optional): Working directory. Defaults to None.
        timeout (int, optional): Timeout in seconds. Defaults to 60.
        shell (bool, optional): Run the command in a shell. Defaults to False.
        capture_output (bool, optional): Capture stdout and stderr. Defaults to True.
        task_name (str, optional): Name of the task. Defaults to "".

    Returns:
        subprocess.CompletedProcess: Result of the command
    """
    console.log(f"Running command: [orange1 i]{exec_cmd}", style="info")
    if envvars:
        envvars = {**os.environ, **envvars}
    else:
        envvars = os.environ  # type: ignore
    result = subprocess.run(
        shlex.split(exec_cmd),
        env=envvars,
        cwd=cwd,
        timeout=timeout,
        shell=shell,
        capture_output=capture_output,
        text=True,
        check=False,
    )
    task_name = task_name if task_name else exec_cmd
    if result.returncode == 0:
        console.log(f"Successfully ran: [i]{task_name}", style="good")
    else:
        console.log(f"Issues encountered running: [i]{task_name}", style="warning")
    console.rule(f"End of task: [b i]{task_name}", style="info")
    console.print()
    return result


# --------------------------------------#
#             Containerlab              #
# --------------------------------------#


@containerlab_app.command("deploy")
def containerlab_deploy(
    topology: Path = typer.Argument(..., help="Path to the topology file"),
    sudo: bool = typer.Option(True, help="Use sudo to run containerlab"),
):
    """Deploy a containerlab topology.

    Args:
        topology (Path): Path to the topology file
        sudo (bool, optional): Use sudo to run containerlab. Defaults to True.

    Raises:
        typer.Exit: Exit with code 1 if the topology file is not found
    """
    console.log("Deploying containerlab topology", style="info")
    console.log(f"Topology file: [orange1 i]{topology}", style="info")
    if not topology.exists():
        console.log(f"Topology file not found: [red i]{topology}", style="error")
        raise typer.Exit(code=1)
    exec_cmd = f"containerlab deploy -t {topology}"
    if sudo:
        exec_cmd = f"sudo {exec_cmd}"
    run_cmd(exec_cmd, task_name="Deploying containerlab topology")


@containerlab_app.command("destroy")
def containerlab_destroy(
    topology: Path = typer.Argument(..., help="Path to the topology file"),
    sudo: bool = typer.Option(True, help="Use sudo to run containerlab"),
):
    """Destroy a containerlab topology.

    Args:
        topology (Path): Path to the topology file
        sudo (bool, optional): Use sudo to run containerlab. Defaults to True.

    Raises:
        typer.Exit: Exit with code 1 if the topology file is not found
    """
    console.log("Deploying containerlab topology", style="info")
    console.log(f"Topology file: [orange1 i]{topology}", style="info")
    if not topology.exists():
        console.log(f"Topology file not found: [red i]{topology}", style="error")
        raise typer.Exit(code=1)
    exec_cmd = f"containerlab destroy -t {topology} --cleanup"
    if sudo:
        exec_cmd = f"sudo {exec_cmd}"
    run_cmd(exec_cmd, task_name="Destroying containerlab topology")


# --------------------------------------#
#                Docker                 #
# --------------------------------------#

@docker_app.command("build")
def docker_build(
    path: Path = typer.Argument(..., help="Path to the Dockerfile"),
    tag: str = typer.Argument(..., help="Tag to use for the image"),
    sudo: bool = typer.Option(True, help="Use sudo to run docker"),
):
    """Build a docker image.

    Args:
        path (Path): Path to the Dockerfile
        tag (str): Tag to use for the image
        sudo (bool, optional): Use sudo to run docker. Defaults to True.

    Raises:
        typer.Exit: Exit with code 1 if the Dockerfile is not found
    """
    console.log("Building docker image", style="info")
    console.log(f"Dockerfile: [orange1 i]{path}", style="info")
    if not path.exists():
        console.log(f"Dockerfile not found: [red i]{path}", style="error")
        raise typer.Exit(code=1)
    exec_cmd = f"docker build -t {tag} {path}"
    if sudo:
        exec_cmd = f"sudo {exec_cmd}"
    run_cmd(exec_cmd, task_name="Building docker image")


@docker_app.command("push")
def docker_push(
    tag: str = typer.Argument(..., help="Tag to use for the image"),
    sudo: bool = typer.Option(True, help="Use sudo to run docker"),
):
    """Push a docker image.

    Args:
        tag (str): Tag to use for the image
        sudo (bool, optional): Use sudo to run docker. Defaults to True.
    """
    console.log("Pushing docker image", style="info")
    console.log(f"Image tag: [orange1 i]{tag}", style="info")
    exec_cmd = f"docker push {tag}"
    if sudo:
        exec_cmd = f"sudo {exec_cmd}"
    run_cmd(exec_cmd, task_name="Pushing docker image")


@docker_app.command("debug")
def docker_debug(
    service: str = typer.Argument(..., help="Tag to use for the image"),
    sudo: bool = typer.Option(True, help="Use sudo to run docker"),
):
    """Run a docker image in debug mode.

    Args:
        tag (str): Tag to use for the image
        sudo (bool, optional): Use sudo to run docker. Defaults to True.
    """
    console.log("Running docker image in debug mode", style="info")
    console.log(f"Image tag: [orange1 i]{tag}", style="info")
    exec_cmd = f"docker run -it {tag}"
    if sudo:
        exec_cmd = f"sudo {exec_cmd}"
    run_cmd(exec_cmd, task_name="Running docker image in debug mode")
