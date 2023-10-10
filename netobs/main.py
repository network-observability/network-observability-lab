"""Netobs CLI."""
import os
import subprocess
import shlex
import json
from enum import Enum
from typing import Optional, Any
from pathlib import Path
from subprocess import CompletedProcess

import typer
from dotenv import dotenv_values, load_dotenv
from rich.console import Console
from rich.theme import Theme


load_dotenv(verbose=True, override=True, dotenv_path=Path("./.env"))
ENVVARS = {**dotenv_values(".env"), **os.environ}

custom_theme = Theme({"info": "cyan", "warning": "bold magenta", "error": "bold red", "good": "bold green"})

console = Console(color_system="truecolor", log_path=False, record=True, theme=custom_theme, force_terminal=True)

app = typer.Typer(help="Run commands for setup and testing", rich_markup_mode="rich")
containerlab_app = typer.Typer(help="Containerlab related commands.", rich_markup_mode="rich")
app.add_typer(containerlab_app, name="containerlab")

docker_app = typer.Typer(help="Docker and Stacks management related commands.", rich_markup_mode="rich")
app.add_typer(docker_app, name="docker")

lab_app = typer.Typer(help="Overall Lab management related commands.", rich_markup_mode="rich")
app.add_typer(lab_app, name="lab")

vm_app = typer.Typer(help="Digital Ocean VM management related commands.", rich_markup_mode="rich")
app.add_typer(vm_app, name="vm")


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
) -> CompletedProcess:
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


@containerlab_app.command(rich_help_panel="Containerlab Management", name="deploy")
def containerlab_deploy(
    topology: Path = typer.Argument(Path("./containerlab/lab.yml"), help="Path to the topology file", exists=True),
    sudo: bool = typer.Option(True, help="Use sudo to run containerlab", envvar="LAB_SUDO"),
):
    """Deploy a containerlab topology.

    [u]Example:[/u]
        [i]netobs containerlab deploy --topology ./containerlab/lab.yml[/i]
    """
    console.log("Deploying containerlab topology", style="info")
    console.log(f"Topology file: [orange1 i]{topology}", style="info")
    exec_cmd = f"containerlab deploy -t {topology}"
    if sudo:
        exec_cmd = f"sudo {exec_cmd}"
    run_cmd(exec_cmd, task_name="Deploying containerlab topology")


@containerlab_app.command(rich_help_panel="Containerlab Management", name="destroy")
def containerlab_destroy(
    topology: Path = typer.Argument(Path("./containerlab/lab.yml"), help="Path to the topology file", exists=True),
    sudo: bool = typer.Option(True, help="Use sudo to run containerlab", envvar="LAB_SUDO"),
):
    """Destroy a containerlab topology.

    [u]Example:[/u]
        [i]netobs containerlab destroy --topology ./containerlab/lab.yml[/i]
    """
    console.log("Deploying containerlab topology", style="info")
    console.log(f"Topology file: [orange1 i]{topology}", style="info")
    exec_cmd = f"containerlab destroy -t {topology} --cleanup"
    if sudo:
        exec_cmd = f"sudo {exec_cmd}"
    run_cmd(exec_cmd, task_name="Destroying containerlab topology")


@containerlab_app.command(rich_help_panel="Containerlab Management", name="inspect")
def containerlab_inspect(
    topology: Path = typer.Argument(Path("./containerlab/lab.yml"), help="Path to the topology file", exists=True),
    sudo: bool = typer.Option(True, help="Use sudo to run containerlab", envvar="LAB_SUDO"),
):
    """Inspect a containerlab topology.

    [u]Example:[/u]
        [i]netobs containerlab show --topology ./containerlab/lab.yml[/i]
    """
    console.log("Showing containerlab topology", style="info")
    console.log(f"Topology file: [orange1 i]{topology}", style="info")
    exec_cmd = f"containerlab inspect -t {topology}"
    if sudo:
        exec_cmd = f"sudo {exec_cmd}"
    run_cmd(exec_cmd, task_name="Inspect containerlab topology")


# --------------------------------------#
#                Docker                 #
# --------------------------------------#


@docker_app.command(rich_help_panel="Docker Stack Management", name="exec")
def docker_exec(
    service: str = typer.Argument(..., help="Service to execute command"),
    command: str = typer.Argument("bash", help="Command to execute"),
    scenario: str = typer.Option(..., "-S", "--scenario", help="Scenario to execute command", envvar="LAB_SCENARIO"),
    verbose: bool = typer.Option(False, help="Verbose mode"),
):
    """Execute a command in a container.

    [u]Example:[/u]

    To execute a command in a service:
        [i]netobs docker exec --scenario skeleton --service telegraf-01 --command bash[/i]

        To execute a command in a service and verbose mode:
        [i]netobs docker exec --scenario skeleton --service telegraf-01 --command bash --verbose[/i]
    """
    console.log(f"Executing command in service: [orange1 i]{service}", style="info")
    run_docker_compose_cmd(
        action="exec",
        filename=Path(f"./obs_stack/{scenario}/docker-compose.yml"),
        services=[service],
        command=command,
        verbose=verbose,
        task_name="exec command",
    )


@docker_app.command(rich_help_panel="Docker Stack Management", name="debug")
def docker_debug(
    scenario: str = typer.Option(..., help="Scenario to execute command", envvar="LAB_SCENARIO"),
    services: Optional[list[str]] = typer.Argument(None, help="Service(s) to run in debug mode"),
    verbose: bool = typer.Option(False, help="Verbose mode"),
):
    """Start docker compose in debug mode.

    [u]Example:[/u]

    To start all services in debug mode:
        [i]netobs docker --scenario skeleton debug[/i]

    To start a specific service in debug mode:
        [i]netobs docker --scenario skeleton debug telegraf-01[/i]
    """
    console.log(f"Starting in debug mode service(s): [orange1 i]{services}", style="info")
    run_docker_compose_cmd(
        action="up",
        filename=Path(f"./obs_stack/{scenario}/docker-compose.yml"),
        services=services if services else [],
        verbose=verbose,
        extra_options="--remove-orphans",
        task_name="debug stack",
    )


@docker_app.command(rich_help_panel="Docker Stack Management", name="start")
def docker_start(
    scenario: str = typer.Option(..., help="Scenario to execute command", envvar="LAB_SCENARIO"),
    services: Optional[list[str]] = typer.Argument(None, help="Service(s) to start"),
    verbose: bool = typer.Option(False, help="Verbose mode"),
):
    """Start all containers.

    [u]Example:[/u]

    To start all services:
        [i]netobs docker start --scenario skeleton[/i]

    To start a specific service:
        [i]netobs docker start telegraf-01 --scenario skeleton[/i]
    """
    console.log(f"Starting service(s): [orange1 i]{services}", style="info")
    run_docker_compose_cmd(
        action="up",
        filename=Path(f"./obs_stack/{scenario}/docker-compose.yml"),
        services=services if services else [],
        verbose=verbose,
        extra_options="-d --remove-orphans",
        task_name="start stack",
    )


@docker_app.command(rich_help_panel="Docker Stack Management", name="stop")
def docker_stop(
    scenario: str = typer.Option(..., help="Scenario to execute command", envvar="LAB_SCENARIO"),
    services: Optional[list[str]] = typer.Argument(None, help="Service(s) to stop"),
    verbose: bool = typer.Option(False, help="Verbose mode"),
):
    """Stop all containers.

    [u]Example:[/u]

    To stop all services:
        [i]netobs docker stop --scenario skeleton[/i]

    To stop a specific service:
        [i]netobs docker stop telegraf-01 --scenario skeleton[/i]
    """
    console.log(f"Stopping service(s): [orange1 i]{services}", style="info")
    run_docker_compose_cmd(
        action="stop",
        filename=Path(f"./obs_stack/{scenario}/docker-compose.yml"),
        services=services if services else [],
        verbose=verbose,
        task_name="stop stack",
    )


@docker_app.command(rich_help_panel="Docker Stack Management", name="restart")
def docker_restart(
    scenario: str = typer.Option(..., help="Scenario to execute command", envvar="LAB_SCENARIO"),
    services: Optional[list[str]] = typer.Argument(None, help="Service(s) to restart"),
    verbose: bool = typer.Option(False, help="Verbose mode"),
):
    """Restart all containers.

    [u]Example:[/u]

    To restart all services:
        [i]netobs docker restart --scenario skeleton[/i]

    To restart a specific service:
        [i]netobs docker restart telegraf-01 --scenario skeleton[/i]
    """
    console.log(f"Restarting service(s): [orange1 i]{services}", style="info")
    run_docker_compose_cmd(
        action="restart",
        filename=Path(f"./obs_stack/{scenario}/docker-compose.yml"),
        services=services if services else [],
        verbose=verbose,
        task_name="restart stack",
    )


@docker_app.command(rich_help_panel="Docker Stack Management", name="logs")
def docker_logs(
    scenario: str = typer.Option(..., help="Scenario to execute command", envvar="LAB_SCENARIO"),
    services: Optional[list[str]] = typer.Argument(None, help="Service(s) to show logs"),
    follow: bool = typer.Option(False, "-f", "--follow", help="Follow logs"),
    tail: Optional[int] = typer.Option(None, "-t", "--tail", help="Number of lines to show"),
    verbose: bool = typer.Option(False, help="Verbose mode"),
):
    """Show logs for containers.

    [u]Example:[/u]

    To show logs for all services:
        [i]netobs docker logs --scenario skeleton[/i]

    To show logs for a specific service:
        [i]netobs docker logs telegraf-01 --scenario skeleton[/i]

    To show logs for a specific service and follow the logs and tail 10 lines:
        [i]netobs docker logs telegraf-01 --scenario skeleton --follow --tail 10[/i]
    """
    console.log(f"Showing logs for service(s): [orange1 i]{services}", style="info")
    options = ""
    if follow:
        options += "-f "
    if tail:
        options += f"--tail={tail}"
    run_docker_compose_cmd(
        action="logs",
        filename=Path(f"./obs_stack/{scenario}/docker-compose.yml"),
        services=services if services else [],
        extra_options=options,
        verbose=verbose,
        task_name="show logs",
    )


@docker_app.command(rich_help_panel="Docker Stack Management", name="ps")
def docker_ps(
    scenario: str = typer.Option(..., help="Scenario to execute command", envvar="LAB_SCENARIO"),
    services: Optional[list[str]] = typer.Argument(None, help="Service(s) to show"),
    verbose: bool = typer.Option(False, help="Verbose mode"),
):
    """Show containers.

    [u]Example:[/u]

    To show all services:
        [i]netobs docker ps --scenario skeleton[/i]

    To show a specific service:
        [i]netobs docker ps telegraf-01 --scenario skeleton[/i]
    """
    console.log(f"Showing containers for service(s): [orange1 i]{services}", style="info")
    run_docker_compose_cmd(
        action="ps",
        filename=Path(f"./obs_stack/{scenario}/docker-compose.yml"),
        services=services if services else [],
        verbose=verbose,
        task_name="show containers",
    )


@docker_app.command(rich_help_panel="Docker Stack Management", name="destroy")
def docker_destroy(
    scenario: str = typer.Option(..., help="Scenario to execute command", envvar="LAB_SCENARIO"),
    services: Optional[list[str]] = typer.Argument(None, help="Service(s) to destroy"),
    volumes: bool = typer.Option(False, help="Remove volumes"),
    verbose: bool = typer.Option(False, help="Verbose mode"),
):
    """Destroy containers and resources.

    [u]Example:[/u]

    To destroy all services:
        [i]netobs docker destroy --scenario skeleton[/i]

    To destroy a specific service:
        [i]netobs docker destroy --scenario skeleton[/i]

    To destroy a specific service and remove volumes:
        [i]netobs docker destroy telegraf-01 --volumes --scenario skeleton[/i]

    To destroy all services and remove volumes:
        [i]netobs docker destroy --volumes --scenario skeleton[/i]
    """
    console.log(f"Destroying service(s): [orange1 i]{services}", style="info")
    run_docker_compose_cmd(
        action="down",
        filename=Path(f"./obs_stack/{scenario}/docker-compose.yml"),
        services=services if services else [],
        verbose=verbose,
        extra_options="--volumes --remove-orphans" if volumes else "--remove-orphans",
        task_name="destroy stack",
    )


@docker_app.command(rich_help_panel="Docker Stack Management", name="rm")
def docker_rm(
    scenario: str = typer.Option(..., help="Scenario to execute command", envvar="LAB_SCENARIO"),
    services: Optional[list[str]] = typer.Argument(None, help="Service(s) to remove"),
    volumes: bool = typer.Option(False, help="Remove volumes"),
    force: bool = typer.Option(False, help="Force removal of containers"),
    verbose: bool = typer.Option(False, help="Verbose mode"),
):
    """Remove containers.

    [u]Example:[/u]

    To remove all services:
        [i]netobs docker rm --scenario skeleton[/i]

    To remove a specific service:
        [i]netobs docker rm telegraf-01 --scenario skeleton[/i]

    To remove a specific service and remove volumes:
        [i]netobs docker rm telegraf-01 --volumes --scenario skeleton[/i]

    To remove all services and remove volumes:
        [i]netobs docker rm --volumes --scenario skeleton[/i]

    To remove all services and force removal of containers:
        [i]netobs docker rm --force --scenario skeleton[/i]

    To force removal of a specific service and remove volumes:
        [i]netobs docker rm telegraf-01 --volumes --force --scenario skeleton[/i]
    """
    extra_options = "--stop "
    if force:
        extra_options += "--force "
    if volumes:
        extra_options += "--volumes "
    console.log(f"Removing service(s): [orange1 i]{services}", style="info")
    run_docker_compose_cmd(
        action="rm",
        filename=Path(f"./obs_stack/{scenario}/docker-compose.yml"),
        services=services if services else [],
        verbose=verbose,
        extra_options=extra_options,
        task_name="remove containers",
    )


@docker_app.command("network")
def docker_network(
    action: DockerNetworkAction = typer.Argument(..., help="Action to perform", case_sensitive=False),
    name: Optional[str] = typer.Option("network-observability", "-n", "--name", help="Network name"),
    driver: Optional[str] = typer.Option("bridge", help="Network driver"),
    subnet: Optional[str] = typer.Option("198.51.100.0/24", help="Network subnet"),
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
    scenario: str = typer.Argument(..., help="Scenario to execute command", envvar="LAB_SCENARIO"),
    topology: Path = typer.Option(Path("./containerlab/lab.yml"), help="Path to the topology file", exists=True),
    network_name: Optional[str] = typer.Option("network-observability", "-n", "--network-name", help="Network name"),
    subnet: Optional[str] = typer.Option("198.51.100.0/24", help="Network subnet"),
    sudo: bool = typer.Option(False, help="Use sudo to run containerlab", envvar="LAB_SUDO"),
):
    """Deploy a lab topology."""
    console.log(f"Deploying lab environment for scenario: [orange1 i]{scenario}", style="info")

    # First create docker network if not exists
    docker_network(
        DockerNetworkAction.CREATE,
        name=network_name,
        driver="bridge",
        subnet=subnet,
        verbose=True,
    )

    # Deploy containerlab topology
    containerlab_deploy(topology=topology, sudo=sudo)

    # Start docker compose
    docker_start(scenario=scenario, services=None, verbose=True)

    console.log(f"Lab environment deployed for scenario: [orange1 i]{scenario}", style="info")


@lab_app.command("destroy")
def lab_destroy(
    scenario: str = typer.Argument(..., help="Scenario to execute command", envvar="LAB_SCENARIO"),
    topology: Path = typer.Option(Path("./containerlab/lab.yml"), help="Path to the topology file", exists=True),
    sudo: bool = typer.Option(False, help="Use sudo to run containerlab", envvar="LAB_SUDO"),
):
    """Destroy a lab topology."""
    console.log(f"Destroying lab environment for scenario: [orange1 i]{scenario}", style="info")

    # Stop docker compose
    docker_destroy(scenario=scenario, services=None, volumes=True, verbose=True)

    # Destroy containerlab topology
    containerlab_destroy(topology=topology, sudo=sudo)

    console.log(f"Lab environment destroyed for scenario: [orange1 i]{scenario}", style="info")


@lab_app.command("show")
def lab_show(
    scenario: str = typer.Argument(..., help="Scenario to execute command", envvar="LAB_SCENARIO"),
    topology: Path = typer.Option(Path("./containerlab/lab.yml"), help="Path to the topology file", exists=True),
    sudo: bool = typer.Option(False, help="Use sudo to run containerlab", envvar="LAB_SUDO"),
):
    """Show lab environment."""
    console.log(f"Showing lab environment for scenario: [orange1 i]{scenario}", style="info")

    # Show docker compose
    docker_ps(scenario=scenario, services=None, verbose=True)

    # Show containerlab topology
    containerlab_inspect(topology=topology, sudo=sudo)

    console.log(f"Lab environment shown for scenario: [orange1 i]{scenario}", style="info")


# --------------------------------------#
#           Digital Ocean VM            #
# --------------------------------------#


@vm_app.command("deploy")
def vm_deploy():
    """Deploy a lab VM."""
    console.log("Deploying lab VM", style="info")

    # Terraform init
    exec_cmd = "terraform -chdir=./terraform/ init"
    run_cmd(exec_cmd, task_name="terraform init")

    # Terraform validate
    exec_cmd = "terraform -chdir=./terraform/ validate"
    run_cmd(exec_cmd, task_name="terraform validate")

    # Terraform apply
    exec_cmd = "terraform -chdir=./terraform/ apply -auto-approve"
    run_cmd(exec_cmd, task_name="terraform apply")
    console.log("Lab VM deployed", style="info")

    # Get VM IP and SSH command
    exec_cmd = "terraform -chdir=./terraform/ output -json"
    result = run_cmd(exec_cmd, task_name="terraform output", capture_output=True)

    # Parse JSON output
    result_json = json.loads(result.stdout)
    vm_endpoints = result_json["vm_endpoints"]["value"]
    vm_ssh_cmd = result_json["ssh_command"]["value"]
    console.log("VM Endpoints:", style="info")
    console.print(vm_endpoints)
    console.log(f"VM SSH command: [orange1 i]{vm_ssh_cmd}", style="info")
    console.log("You can now connect to the VM using the above SSH command", style="info")


@vm_app.command("destroy")
def vm_destroy():
    """Destroy a lab VM."""
    console.log("Destroying lab VM", style="info")

    # Terraform destroy
    exec_cmd = "terraform -chdir=./terraform/ destroy -auto-approve"
    run_cmd(exec_cmd, task_name="terraform destroy")

    console.log("Lab VM destroyed", style="info")
