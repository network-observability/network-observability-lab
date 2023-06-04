"""Netobs CLI."""
import os
import subprocess
import shlex
from enum import Enum
from typing import Optional, Any
from pathlib import Path

import typer
from dotenv import dotenv_values
from rich.console import Console
from rich.theme import Theme


ENVVARS = {**dotenv_values(".env"), **os.environ}

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

app = typer.Typer(help="Run commands for setup and testing", rich_markup_mode="rich")
containerlab_app = typer.Typer(help="[b i blue]Containerlab[/b i blue] related commands.", rich_markup_mode="rich")
app.add_typer(containerlab_app, name="containerlab")

docker_app = typer.Typer(
    help="[b i blue]Docker and Stacks[/b i blue] management related commands.", rich_markup_mode="rich"
)
app.add_typer(docker_app, name="docker")

lab_app = typer.Typer(help="[b i blue]Overall Lab[/b i blue] management related commands.", rich_markup_mode="rich")
app.add_typer(lab_app, name="lab")


class DockerNetworkAction(Enum):
    """Docker network action."""

    CONNECT = "connect"
    CREATE = "create"
    DISCONNECT = "disconnect"
    INSPECT = "inspect"
    LIST = "ls"
    PRUNE = "prune"
    REMOVE = "rm"


def strtobool(val: str) -> bool:
    """Convert a string representation of truth to true (1) or false (0).

    Args:
        val (str): String representation of truth.

    Returns:
        bool: True or False
    """
    val = val.lower()
    if val in ("y", "yes", "t", "true", "on", "1"):
        return True
    elif val in ("n", "no", "f", "false", "off", "0"):
        return False
    else:
        raise ValueError("invalid truth value %r" % (val,))


def is_truthy(arg: Any) -> bool:
    """Convert "truthy" strings into Booleans.

    Examples:
    ```python
        >>> is_truthy('yes')
        True
    ```

    Args:
        arg (str): Truthy string (True values are y, yes, t, true, on and 1; false values are n, no,
        f, false, off and 0. Raises ValueError if val is anything else.
    """
    if isinstance(arg, bool):
        return arg
    if arg is None:
        return False
    return bool(strtobool(arg))


def docker_compose_cmd(
    compose_action: str,
    docker_compose_file: Path,
    services: list[str] = [],
    verbose: int = 0,
    extra_options: str = "",
    command: str = "",
    compose_name: str = "",
) -> str:
    """Create docker-compose command to execute.
    Args:
        compose_action (str): Docker Compose action to run.
        docker_compose_file (Path): Docker compose file.
        services (List[str], optional): List of specifics container to action. Defaults to [].
        verbose (int, optional): Verbosity. Defaults to 0.
        extra_options (str, optional): Extra docker compose flags to pass to the command line. Defaults to "".
        command (str, optional): Command to execute in docker compose. Defaults to "".
        compose_name (str, optional): Name to give to the docker compose project. Defaults to PROJECT_NAME.
    Returns:
        str: Docker compose command
    """
    if is_truthy(ENVVARS.get("DOCKER_COMPOSE_WITH_HASH", None)):
        exec_cmd = f"docker-compose --project-name {compose_name} -f {docker_compose_file}"
    else:
        exec_cmd = f"docker compose --project-name {compose_name} -f {docker_compose_file}"

    if verbose:
        exec_cmd += " --verbose"
    exec_cmd += f" {compose_action}"

    if extra_options:
        exec_cmd += f" {extra_options}"
    if services:
        exec_cmd += f" {' '.join(services)}"
    if command:
        exec_cmd += f" {command}"

    return exec_cmd


def run_cmd(
    exec_cmd: str,
    envvars: dict[str, str] = ENVVARS,
    cwd: Optional[str] = None,
    timeout: Optional[int] = None,
    shell: bool = False,
    capture_output: bool = False,
    task_name: str = "",
) -> subprocess.CompletedProcess:
    """Run a command and return the result.

    Args:
        exec_cmd (str): Command to execute
        envvars (dict, optional): Environment variables. Defaults to ENVVARS.
        cwd (str, optional): Working directory. Defaults to None.
        timeout (int, optional): Timeout in seconds. Defaults to None.
        shell (bool, optional): Run the command in a shell. Defaults to False.
        capture_output (bool, optional): Capture stdout and stderr. Defaults to True.
        task_name (str, optional): Name of the task. Defaults to "".

    Returns:
        subprocess.CompletedProcess: Result of the command
    """
    console.log(f"Running command: [orange1 i]{exec_cmd}", style="info")
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


def run_docker_compose_cmd(
    filename: Path,
    action: str,
    services: list[str] = [],
    verbose: int = 0,
    command: str = "",
    extra_options: str = "",
    envvars: dict[str, str] = ENVVARS,
    timeout: Optional[int] = None,
    shell: bool = False,
    capture_output: bool = False,
    task_name: str = "",
) -> subprocess.CompletedProcess:
    """Run a docker compose command.

    Args:
        filename (str): Docker compose file.
        action (str): Docker compose action. Example 'up'
        services (List[str], optional): List of services defined in the docker compose. Defaults to [].
        verbose (int, optional): Execute verbose command. Defaults to 0.
        command (str, optional): Docker compose command to send on action `exec`. Defaults to "".
        extra_options (str, optional): Extra options to pass over docker compose command. Defaults to "".
        envvars (dict, optional): Environment variables. Defaults to ENVVARS.
        timeout (int, optional): Timeout in seconds. Defaults to None.
        shell (bool, optional): Run the command in a shell. Defaults to False.
        capture_output (bool, optional): Capture stdout and stderr. Defaults to True.
        task_name (str, optional): Name of the task passed. Defaults to "".

    Returns:
        subprocess.CompletedProcess: Result of the command
    """
    if not filename.exists():
        console.log(f"File not found: [orange1 i]{filename}", style="error")
        raise typer.Exit(1)

    exec_cmd = docker_compose_cmd(
        action,
        docker_compose_file=filename,
        services=services,
        command=command,
        verbose=verbose,
        extra_options=extra_options,
        compose_name="netobs",
    )
    return run_cmd(
        exec_cmd=exec_cmd,
        envvars=envvars,
        timeout=timeout,
        shell=shell,
        capture_output=capture_output,
        task_name=f"{task_name}",
    )


# --------------------------------------#
#             Containerlab              #
# --------------------------------------#


@containerlab_app.command("deploy")
def containerlab_deploy(
    topology: Path = typer.Argument(Path("./containerlab/lab.yml"), help="Path to the topology file"),
    sudo: bool = typer.Option(True, help="Use sudo to run containerlab"),
):
    """Deploy a containerlab topology.

    [u]Example:[/u]
        [i]netobs containerlab deploy --topology ./containerlab/lab.yml[/i]
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
    topology: Path = typer.Argument(Path("./containerlab/lab.yml"), help="Path to the topology file"),
    sudo: bool = typer.Option(True, help="Use sudo to run containerlab"),
):
    """Destroy a containerlab topology.

    **Raises:**
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

    **Raises:**
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
    """Push a docker image."""
    console.log("Pushing docker image", style="info")
    console.log(f"Image tag: [orange1 i]{tag}", style="info")
    exec_cmd = f"docker push {tag}"
    if sudo:
        exec_cmd = f"sudo {exec_cmd}"
    run_cmd(exec_cmd, task_name="Pushing docker image")


@docker_app.command("debug")
def docker_debug(
    service: Optional[list[str]] = typer.Argument(None, help="Service(s) to run in debug mode"),
    verbose: bool = typer.Option(False, help="Verbose mode"),
):
    """Start docker compose in debug mode."""
    console.log(f"Starting in debug mode service(s): [orange1 i]{service}", style="info")
    docker_compose_file = Path("./obs_stack/docker-compose.yml")
    run_docker_compose_cmd(
        action="up",
        filename=docker_compose_file,
        services=service if service else [],
        verbose=verbose,
        extra_options="--remove-orphans",
        task_name="debug stack",
    )


@docker_app.command("destroy")
def docker_destroy(
    service: Optional[list[str]] = typer.Argument(None, help="Service(s) to destroy"),
    volumes: bool = typer.Option(False, help="Remove volumes"),
    verbose: bool = typer.Option(False, help="Verbose mode"),
):
    """Destroy all containers and resources."""
    console.log(f"Destroying service(s): [orange1 i]{service}", style="info")
    docker_compose_file = Path("./obs_stack/docker-compose.yml")
    run_docker_compose_cmd(
        action="down",
        filename=docker_compose_file,
        services=service if service else [],
        verbose=verbose,
        extra_options="--volumes" if volumes else "",
        timeout=None,
        task_name="destroy stack",
    )


@docker_app.command("start")
def docker_start(
    service: Optional[list[str]] = typer.Argument(None, help="Service(s) to start"),
    verbose: bool = typer.Option(False, help="Verbose mode"),
):
    """Start all containers."""
    console.log(f"Starting service(s): [orange1 i]{service}", style="info")
    docker_compose_file = Path("./obs_stack/docker-compose.yml")
    run_docker_compose_cmd(
        action="up",
        filename=docker_compose_file,
        services=service if service else [],
        verbose=verbose,
        extra_options="-d --remove-orphans",
        task_name="start stack",
    )


@docker_app.command("stop")
def docker_stop(
    service: Optional[list[str]] = typer.Argument(None, help="Service(s) to stop"),
    verbose: bool = typer.Option(False, help="Verbose mode"),
):
    """Stop all containers."""
    console.log(f"Stopping service(s): [orange1 i]{service}", style="info")
    docker_compose_file = Path("./obs_stack/docker-compose.yml")
    run_docker_compose_cmd(
        action="stop",
        filename=docker_compose_file,
        services=service if service else [],
        verbose=verbose,
        task_name="stop stack",
    )


@docker_app.command("restart")
def docker_restart(
    service: Optional[list[str]] = typer.Argument(None, help="Service(s) to restart"),
    verbose: bool = typer.Option(False, help="Verbose mode"),
):
    """Restart all containers."""
    console.log(f"Restarting service(s): [orange1 i]{service}", style="info")
    docker_compose_file = Path("./obs_stack/docker-compose.yml")
    run_docker_compose_cmd(
        action="restart",
        filename=docker_compose_file,
        services=service if service else [],
        verbose=verbose,
        task_name="restart stack",
    )


@docker_app.command("logs")
def docker_logs(
    service: Optional[list[str]] = typer.Argument(None, help="Service(s) to show logs"),
    follow: bool = typer.Option(False, "-f", "--follow", help="Follow logs"),
    tail: Optional[int] = typer.Option(None, "-t", "--tail", help="Number of lines to show"),
    verbose: bool = typer.Option(False, help="Verbose mode"),
):
    """Show logs for all containers."""
    console.log(f"Showing logs for service(s): [orange1 i]{service}", style="info")
    docker_compose_file = Path("./obs_stack/docker-compose.yml")
    options = ""
    if follow:
        options += "-f "
    if tail:
        options += f"--tail={tail}"
    run_docker_compose_cmd(
        action="logs",
        filename=docker_compose_file,
        services=service if service else [],
        extra_options=options,
        verbose=verbose,
        task_name="show logs",
    )


@docker_app.command("exec")
def docker_exec(
    service: str = typer.Argument(..., help="Service to execute command"),
    command: str = typer.Argument("bash", help="Command to execute"),
    verbose: bool = typer.Option(False, help="Verbose mode"),
):
    """Execute a command in a container."""
    console.log(f"Executing command in service: [orange1 i]{service}", style="info")
    docker_compose_file = Path("./obs_stack/docker-compose.yml")
    run_docker_compose_cmd(
        action="exec",
        filename=docker_compose_file,
        services=[service],
        command=command,
        verbose=verbose,
        task_name="exec command",
    )


@docker_app.command("ps")
def docker_ps(
    service: Optional[list[str]] = typer.Argument(None, help="Service(s) to show"),
    verbose: bool = typer.Option(False, help="Verbose mode"),
):
    """Show containers."""
    console.log(f"Showing containers for service(s): [orange1 i]{service}", style="info")
    docker_compose_file = Path("./obs_stack/docker-compose.yml")
    run_docker_compose_cmd(
        action="ps",
        filename=docker_compose_file,
        services=service if service else [],
        verbose=verbose,
        task_name="show containers",
    )


@docker_app.command("network")
def docker_network(
    action: DockerNetworkAction = typer.Argument(..., help="Action to perform", case_sensitive=False),
    name: Optional[str] = typer.Option("network-observability", "-n", "--name", help="Network name"),
    driver: Optional[str] = typer.Option("bridge", help="Network driver"),
    subnet: Optional[str] = typer.Option("172.24.177.0/24", help="Network subnet"),
    verbose: bool = typer.Option(False, help="Verbose mode"),
):
    """Manage docker network."""
    console.log(f"Network {action.value}: [orange1 i]{name}", style="info")
    exec_cmd = f"docker network {action.value}"
    if driver and action.value == "create":
        exec_cmd += f" --driver={driver} "
    if subnet and action.value == "create":
        exec_cmd += f" --subnet={subnet}"
    if action.value != "ls" and action.value != "prune":
        exec_cmd += f" {name}"
    run_cmd(
        exec_cmd=exec_cmd,
        task_name=f"network {action.value}",
    )


# --------------------------------------#
#                  Lab                  #
# --------------------------------------#


@lab_app.command("deploy")
def lab_deploy(
    topology: Path = typer.Argument(Path("./containerlab/lab.yml"), help="Path to the topology file"),
    sudo: bool = typer.Option(False, help="Use sudo to run containerlab"),
):
    """Deploy a lab topology.

    **Raises:**
        typer.Exit: Exit with code 1 if the topology file is not found
    """
    console.log("Deploying lab environment", style="info")

    # First create docker network if not exists
    docker_network(
        DockerNetworkAction.CREATE,
        name="network-observability",
        driver="bridge",
        subnet="172.24.177.0/24",
        verbose=True,
    )

    # Deploy containerlab topology
    containerlab_deploy(topology=topology, sudo=sudo)

    # Start docker compose
    docker_start(service=None, verbose=True)


@lab_app.command("destroy")
def lab_destroy(
    topology: Path = typer.Argument(Path("./containerlab/lab.yml"), help="Path to the topology file"),
    sudo: bool = typer.Option(False, help="Use sudo to run containerlab"),
):
    """Destroy a lab topology.

    **Raises:**
        typer.Exit: Exit with code 1 if the topology file is not found
    """
    console.log("Destroying lab environment", style="info")

    # Stop docker compose
    docker_destroy(service=None, volumes=True, verbose=True)

    # Destroy containerlab topology
    containerlab_destroy(topology=topology, sudo=sudo)
