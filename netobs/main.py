"""Netobs CLI."""

import os
import subprocess  # nosec
import shlex
import json
from enum import Enum
from typing import Optional, Any
from typing_extensions import Annotated
from pathlib import Path
from subprocess import CompletedProcess  # nosec
from urllib.parse import urlparse

import typer
import yaml
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry  # type: ignore
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

utils_app = typer.Typer(help="Utilities and scripts related commands.", rich_markup_mode="rich")
app.add_typer(utils_app, name="utils")


class NetObsScenarios(Enum):
    """NetObs scenarios."""

    SKELETON = "skeleton"
    BATTERIES_INCLUDED = "batteries-included"
    CH5 = "ch5"
    CH5_COMPLETED = "ch5-completed"
    CH6 = "ch6"
    CH6_COMPLETED = "ch6-completed"
    CH7 = "ch7"
    CH7_COMPLETED = "ch7-completed"
    CH8 = "ch8"
    CH8_COMPLETED = "ch8-completed"
    CH9 = "ch9"
    CH9_COMPLETED = "ch9-completed"
    CH13 = "ch13"
    CH13_COMPLETED = "ch13-completed"


class DockerNetworkAction(Enum):
    """Docker network action."""

    CONNECT = "connect"
    CREATE = "create"
    DISCONNECT = "disconnect"
    INSPECT = "inspect"
    LIST = "ls"
    PRUNE = "prune"
    REMOVE = "rm"


class NautobotClient:
    def __init__(
        self,
        url: str,
        token: str | None = None,
        **kwargs,
    ):
        self.base_url = self._parse_url(url)
        self._token = token
        self.verify_ssl = kwargs.get("verify_ssl", False)
        self.retries = kwargs.get("retries", 3)
        self.timeout = kwargs.get("timeout", 10)
        self.proxies = kwargs.get("proxies", None)
        self._create_session()

    def _parse_url(self, url: str) -> str:
        """Checks if the provided URL has http or https and updates it if needed.

        Args:
            url (str): URL of the grafana instance. ex: "grafana.mylab.com:3000"

        Returns:
            str: a string of the URL. ex: "http://grafana.mylab.com:3000"
        """
        parsed_url = urlparse(url)
        if not parsed_url.scheme:
            return f"http://{url}"
        return f"{parsed_url.geturl()}"

    def _create_session(self):
        """
        Creates the requests.Session object and applies the necessary parameters
        """
        self.session = requests.Session()
        self.session.headers["Content-Type"] = "application/json"
        self.session.headers["Accept"] = "application/json"
        self.session.headers["Authorization"] = f"Token {self._token}"
        if self.proxies:
            self.session.proxies.update(self.proxies)

        retry_method = Retry(
            total=self.retries,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_method)

        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    def http_call(
        self,
        method: str,
        url: str,
        data: dict | str | None = None,
        json_data: dict | None = None,
        headers: dict | None = None,
        verify: bool = False,
        params: dict | list[tuple] | None = None,
    ) -> dict:
        """
        Performs the HTTP operation actioned

        **Required Attributes:**

        - `method` (enum): HTTP method to perform: get, post, put, delete, head,
        patch (**required**)
        - `url` (str): URL target (**required**)
        - `data`: Dictionary or byte of request body data to attach to the Request
        - `json_data`: Dictionary or List of dicts to be passed as JSON object/array
        - `headers`: Dictionary of HTTP Headers to attach to the Request
        - `verify`: SSL Verification
        - `params`: Dictionary or bytes to be sent in the query string for the Request
        """
        _request = requests.Request(
            method=method.upper(),
            url=self.base_url + url,
            data=data,
            json=json_data,
            headers=headers,
            params=params,
        )

        # Prepare the request
        _request = self.session.prepare_request(_request)

        # Send the request
        try:
            _response = self.session.send(request=_request, verify=verify, timeout=self.timeout)
            # print(_response.text)
        except Exception as err:
            raise err

        # Raise Error if object already exists
        if "already exists" in _response.text:
            raise ValueError(_response.text)

        # Raise any HTTP errors
        try:
            _response.raise_for_status()
        except Exception as err:
            raise err

        if _response.status_code == 204:
            return {}
        return _response.json()


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
    envvars: dict[str, Any] = ENVVARS,
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
        shell=shell,  # nosec
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
    envvars: dict[str, Any] = ENVVARS,
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


def load_yaml(topology: Path) -> dict:
    """Read a containerlab topology file.

    Args:
        topology (Path): Path to the topology file

    Returns:
        dict: Topology file as a dict
    """
    with open(topology, "r") as stream:
        try:
            topology_dict = yaml.safe_load(stream)
        except yaml.YAMLError as exc:
            console.log(exc, style="error")
            raise typer.Exit(1)
    return topology_dict


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
    service: Annotated[str, typer.Argument(help="Service to execute command")],
    scenario: Annotated[NetObsScenarios, typer.Option(help="Scenario to execute command", envvar="LAB_SCENARIO")],
    command: Annotated[str, typer.Argument(help="Command to execute")] = "bash",
    verbose: Annotated[bool, typer.Option(help="Verbose mode")] = False,
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
        filename=Path(f"./obs_stack/{scenario.value}/docker-compose.yml"),
        services=[service],
        command=command,
        verbose=verbose,
        task_name="exec command",
    )


@docker_app.command(rich_help_panel="Docker Stack Management", name="debug")
def docker_debug(
    scenario: Annotated[NetObsScenarios, typer.Option(help="Scenario to execute command", envvar="LAB_SCENARIO")],
    services: Annotated[list[str], typer.Option(help="Service(s) to run in debug mode")] = [],
    verbose: Annotated[bool, typer.Option(help="Verbose mode")] = False,
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
        filename=Path(f"./obs_stack/{scenario.value}/docker-compose.yml"),
        services=services if services else [],
        verbose=verbose,
        extra_options="--remove-orphans",
        task_name="debug stack",
    )


@docker_app.command(rich_help_panel="Docker Stack Management", name="start")
def docker_start(
    scenario: Annotated[NetObsScenarios, typer.Option(help="Scenario to execute command", envvar="LAB_SCENARIO")],
    services: Annotated[list[str], typer.Option(help="Service(s) to start")] = [],
    verbose: Annotated[bool, typer.Option(help="Verbose mode")] = False,
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
        filename=Path(f"./obs_stack/{scenario.value}/docker-compose.yml"),
        services=services if services else [],
        verbose=verbose,
        extra_options="-d --remove-orphans",
        task_name="start stack",
    )


@docker_app.command(rich_help_panel="Docker Stack Management", name="stop")
def docker_stop(
    scenario: Annotated[NetObsScenarios, typer.Option(help="Scenario to execute command", envvar="LAB_SCENARIO")],
    services: Annotated[list[str], typer.Option(help="Service(s) to stop")] = [],
    verbose: Annotated[bool, typer.Option(help="Verbose mode")] = False,
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
        filename=Path(f"./obs_stack/{scenario.value}/docker-compose.yml"),
        services=services if services else [],
        verbose=verbose,
        task_name="stop stack",
    )


@docker_app.command(rich_help_panel="Docker Stack Management", name="restart")
def docker_restart(
    scenario: Annotated[NetObsScenarios, typer.Option(help="Scenario to execute command", envvar="LAB_SCENARIO")],
    services: Annotated[list[str], typer.Option(help="Service(s) to restart")] = [],
    verbose: Annotated[bool, typer.Option(help="Verbose mode")] = False,
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
        filename=Path(f"./obs_stack/{scenario.value}/docker-compose.yml"),
        services=services if services else [],
        verbose=verbose,
        task_name="restart stack",
    )


@docker_app.command(rich_help_panel="Docker Stack Management", name="logs")
def docker_logs(
    scenario: Annotated[NetObsScenarios, typer.Option(help="Scenario to execute command", envvar="LAB_SCENARIO")],
    services: Annotated[list[str], typer.Option(help="Service(s) to show logs")] = [],
    follow: Annotated[bool, typer.Option("-f", "--follow", help="Follow logs")] = False,
    tail: Optional[int] = typer.Option(None, "-t", "--tail", help="Number of lines to show"),
    verbose: Annotated[bool, typer.Option(help="Verbose mode")] = False,
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
        filename=Path(f"./obs_stack/{scenario.value}/docker-compose.yml"),
        services=services if services else [],
        extra_options=options,
        verbose=verbose,
        task_name="show logs",
    )


@docker_app.command(rich_help_panel="Docker Stack Management", name="ps")
def docker_ps(
    scenario: Annotated[NetObsScenarios, typer.Option(help="Scenario to execute command", envvar="LAB_SCENARIO")],
    services: Annotated[list[str], typer.Option(help="Service(s) to show")] = [],
    verbose: Annotated[bool, typer.Option(help="Verbose mode")] = False,
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
        filename=Path(f"./obs_stack/{scenario.value}/docker-compose.yml"),
        services=services if services else [],
        verbose=verbose,
        task_name="show containers",
    )


@docker_app.command(rich_help_panel="Docker Stack Management", name="destroy")
def docker_destroy(
    scenario: Annotated[NetObsScenarios, typer.Option(help="Scenario to execute command", envvar="LAB_SCENARIO")],
    services: Annotated[list[str], typer.Option(help="Service(s) to destroy")] = [],
    volumes: Annotated[bool, typer.Option(help="Remove volumes")] = False,
    verbose: Annotated[bool, typer.Option(help="Verbose mode")] = False,
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
        filename=Path(f"./obs_stack/{scenario.value}/docker-compose.yml"),
        services=services if services else [],
        verbose=verbose,
        extra_options="--volumes --remove-orphans" if volumes else "--remove-orphans",
        task_name="destroy stack",
    )


@docker_app.command(rich_help_panel="Docker Stack Management", name="rm")
def docker_rm(
    scenario: Annotated[NetObsScenarios, typer.Option(help="Scenario to execute command", envvar="LAB_SCENARIO")],
    services: Annotated[list[str], typer.Option(help="Service(s) to remove")] = [],
    volumes: Annotated[bool, typer.Option(help="Remove volumes")] = False,
    force: Annotated[bool, typer.Option(help="Force removal of containers")] = False,
    verbose: Annotated[bool, typer.Option(help="Verbose mode")] = False,
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
        filename=Path(f"./obs_stack/{scenario.value}/docker-compose.yml"),
        services=services if services else [],
        verbose=verbose,
        extra_options=extra_options,
        task_name="remove containers",
    )


@docker_app.command("network")
def docker_network(
    action: Annotated[DockerNetworkAction, typer.Argument(..., help="Action to perform", case_sensitive=False)],
    name: Annotated[str, typer.Option("-n", "--name", help="Network name")] = "network-observability",
    driver: Annotated[str, typer.Option(help="Network driver")] = "bridge",
    subnet: Annotated[str, typer.Option(help="Network subnet")] = "198.51.100.0/24",
    verbose: Annotated[bool, typer.Option(help="Verbose mode")] = False,
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
    scenario: Annotated[NetObsScenarios, typer.Option(help="Scenario to execute command", envvar="LAB_SCENARIO")],
    topology: Annotated[Path, typer.Option(help="Path to the topology file", exists=True)] = Path(
        "./containerlab/lab.yml"
    ),
    network_name: Annotated[
        str, typer.Option(help="Network name", envvar="LAB_NETWORK_NAME")
    ] = "network-observability",
    subnet: Annotated[str, typer.Option(help="Network subnet", envvar="LAB_SUBNET")] = "198.51.100.0/24",
    sudo: Annotated[bool, typer.Option(help="Use sudo to run containerlab", envvar="LAB_SUDO")] = False,
):
    """Deploy a lab topology."""
    console.log(f"Deploying lab environment for scenario: [orange1 i]{scenario.value}", style="info")

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
    docker_start(scenario=scenario, services=[], verbose=True)

    console.log(f"Lab environment deployed for scenario: [orange1 i]{scenario.value}", style="info")


@lab_app.command("destroy")
def lab_destroy(
    scenario: Annotated[NetObsScenarios, typer.Option(help="Scenario to execute command", envvar="LAB_SCENARIO")],
    topology: Annotated[Path, typer.Option(help="Path to the topology file", exists=True)] = Path(
        "./containerlab/lab.yml"
    ),
    sudo: Annotated[bool, typer.Option(help="Use sudo to run containerlab", envvar="LAB_SUDO")] = False,
):
    """Destroy a lab topology."""
    console.log(f"Destroying lab environment for scenario: [orange1 i]{scenario.value}", style="info")

    # Stop docker compose
    docker_destroy(scenario=scenario, services=[], volumes=True, verbose=True)

    # Destroy containerlab topology
    containerlab_destroy(topology=topology, sudo=sudo)

    console.log(f"Lab environment destroyed for scenario: [orange1 i]{scenario.value}", style="info")


@lab_app.command("purge")
def lab_purge():
    """Purge all lab environments."""
    console.rule("[b i]PURGING ALL LAB ENVIRONMENTS", style="error")
    console.log("Purging lab environments", style="info")

    # Iterate over all scenarios and destroy them
    for scenario in NetObsScenarios:
        try:
            lab_destroy(scenario=scenario)
        except typer.Exit:
            pass

    console.rule("[b i]LAB ENVIRONMENTS PURGED", style="error")


@lab_app.command("show")
def lab_show(
    scenario: Annotated[NetObsScenarios, typer.Option(help="Scenario to execute command", envvar="LAB_SCENARIO")],
    topology: Annotated[Path, typer.Option(help="Path to the topology file", exists=True)] = Path(
        "./containerlab/lab.yml"
    ),
    sudo: Annotated[bool, typer.Option(help="Use sudo to run containerlab", envvar="LAB_SUDO")] = False,
):
    """Show lab environment."""
    console.log(f"Showing lab environment for scenario: [orange1 i]{scenario.value}", style="info")

    # Show docker compose
    docker_ps(scenario=scenario, services=[], verbose=True)

    # Show containerlab topology
    containerlab_inspect(topology=topology, sudo=sudo)

    console.log(f"Lab environment shown for scenario: [orange1 i]{scenario.value}", style="info")


@lab_app.command("prepare")
def lab_prepare(
    scenario: Annotated[NetObsScenarios, typer.Option(help="Scenario to execute command", envvar="LAB_SCENARIO")],
    topology: Annotated[Path, typer.Option(help="Path to the topology file", exists=True)] = Path(
        "./containerlab/lab.yml"
    ),
    sudo: Annotated[bool, typer.Option(help="Use sudo to run containerlab", envvar="LAB_SUDO")] = False,
):
    """Prepare the lab for the scenario."""
    console.log(f"Preparing lab environment for scenario: [orange1 i]{scenario.value}", style="info")

    # Destroy all other lab environments and network topologies
    lab_purge()

    # Deploy containerlab topology
    containerlab_deploy(topology=topology, sudo=sudo)

    # Start docker compose
    docker_start(scenario=scenario, services=[], verbose=True)

    console.log(f"Lab environment prepared for scenario: [orange1 i]{scenario.value}", style="info")


@lab_app.command("update")
def lab_update(
    scenario: Annotated[NetObsScenarios, typer.Option(help="Scenario to execute command", envvar="LAB_SCENARIO")],
    # services: Optional[list[str]] = typer.Option(None, help="Service(s) to update"),
    services: Annotated[list[str], typer.Option(help="Service(s) to update")] = [],
):
    """Update the service(s) of a lab scenario.

    [u]Example:[/u]]

    To update all services:
        [i]netobs lab update --scenario skeleton[/i]

    To update a specific service:
        [i]netobs lab update telegraf-01 --scenario skeleton[/i]
    """
    console.log(f"Updating lab environment for scenario: [orange1 i]{scenario.value}", style="info")

    # Delete the containers
    docker_rm(scenario=scenario, services=services, volumes=True, force=True, verbose=True)

    # Start them back
    docker_start(scenario=scenario, services=services, verbose=True)

    console.log(f"Lab environment updated for scenario: [orange1 i]{scenario.value}", style="info")


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


# --------------------------------------#
#                Utils                  #
# --------------------------------------#


@utils_app.command("load-nautobot", help="Load Nautobot data from containerlab topology file")
def utils_load_nautobot_data(
    nautobot_token: Annotated[str, typer.Option(help="Nautobot Token", envvar="NAUTOBOT_SUPERUSER_API_TOKEN")],
    topology: Annotated[Path, typer.Option(help="Path to the topology file", exists=True)] = Path(
        "./containerlab/lab.yml"
    ),
    extra_topology_vars: Annotated[Path, typer.Option(help="Path to the extra topology vars file", exists=True)] = Path(
        "./containerlab/lab_vars.yml"
    ),
    nautobot_url: Annotated[str, typer.Option(help="Nautobot URL", envvar="NAUTOBOT_URL")] = "http://localhost:8080",
):
    """Load Nautobot data from containerlab topology file."""
    console.log(
        f"Loading Nautobot data from topology file: [orange1 i]{topology} && {extra_topology_vars}", style="info"
    )

    console.log("Reading containerlab topology file", style="info")
    topology_dict = load_yaml(topology)

    # Add extra vars to topology dict
    extra_topology_vars_dict = load_yaml(extra_topology_vars)
    for key, value in extra_topology_vars_dict["nodes"].items():
        topology_dict["topology"]["nodes"][key].update(value)

    # Instantiate Nautobot Client
    console.log("Instantiating Nautobot Client", style="info")
    nautobot_client = NautobotClient(url=nautobot_url, token=nautobot_token)

    # Create Roles in Nautobot
    roles = nautobot_client.http_call(
        url="/api/extras/roles/",
        method="post",
        json_data={"name": "network_device", "content_types": ["dcim.device"]},
    )
    console.log(f"Created Role: [orange1 i]{roles['display']}", style="info")

    # Create Manufacturers in Nautobot
    manufacturers = nautobot_client.http_call(
        url="/api/dcim/manufacturers/",
        method="post",
        json_data={"name": "Arista"},
    )
    console.log(f"Created Manufacturer: [orange1 i]{manufacturers['display']}", style="info")

    # Create Device Types in Nautobot
    device_types = nautobot_client.http_call(
        url="/api/dcim/device-types/",
        method="post",
        json_data={"manufacturer": "Arista", "model": "cEOS"},
    )
    console.log(f"Created Device Types: [orange1 i]{device_types['display']}", style="info")

    # Create Location Types
    location_type = nautobot_client.http_call(
        url="/api/dcim/location-types/",
        method="post",
        json_data={"name": "site", "content_types": ["dcim.device"]},
    )
    console.log(f"Created Location Type: [orange1 i]{location_type['display']}", style="info")

    # Create Statuses
    statuses = nautobot_client.http_call(
        url="/api/extras/statuses/",
        method="post",
        json_data={
            "name": "lab-active",
            "content_types": ["dcim.device", "dcim.interface", "dcim.location", "ipam.ipaddress", "ipam.prefix"],
        },
    )
    console.log(f"Created Status: [orange1 i]{statuses['display']}", style="info")

    # Create Locations
    locations = nautobot_client.http_call(
        url="/api/dcim/locations/",
        method="post",
        json_data={
            "name": "lab",
            "location_type": {"id": location_type["id"]},
            "status": {"id": statuses["id"]},
        },
    )
    console.log(f"Created Location: [orange1 i]{locations['display']}", style="info")

    # Create IPAM Namespace
    ipam_namespace = nautobot_client.http_call(
        url="/api/ipam/namespaces/",
        method="post",
        json_data={"name": "lab-default"},
    )
    console.log(f"Created IPAM Namespace: [orange1 i]{ipam_namespace['display']}", style="info")

    # Create Prefixes for the Namespace
    for prefix_data in extra_topology_vars_dict["prefixes"]:
        prefix = nautobot_client.http_call(
            url="/api/ipam/prefixes/",
            method="post",
            json_data={
                "prefix": prefix_data["prefix"],
                "namespace": {"id": ipam_namespace["id"]},
                "type": "network",
                "status": {"id": statuses["id"]},
                "description": prefix_data["name"],
            },
        )
        console.log(f"Created Prefix: [orange1 i]{prefix['display']}", style="info")

    # Create Management Prefix
    mgmt_prefix = nautobot_client.http_call(
        url="/api/ipam/prefixes/",
        method="post",
        json_data={
            "prefix": topology_dict["mgmt"]["ipv4-subnet"],
            "namespace": {"id": ipam_namespace["id"]},
            "type": "network",
            "status": {"id": statuses["id"]},
            "description": "lab-mgmt-prefix",
        },
    )
    console.log(f"Created Prefix: [orange1 i]{mgmt_prefix['display']}", style="info")

    # Create Devices
    for node, node_data in topology_dict["topology"]["nodes"].items():
        device = nautobot_client.http_call(
            url="/api/dcim/devices/",
            method="post",
            json_data={
                "name": node,
                "role": {"id": roles["id"]},
                "device_type": {"id": device_types["id"]},
                # "platform": "other",
                "location": {"id": locations["id"]},
                "status": {"id": statuses["id"]},
                # "primary_ip4": {"id": ip_address["id"]},
                "customn_fields": {
                    "containerlab": {
                        "node_kind": node_data["kind"],
                        "node_address": node_data["mgmt-ipv4"],
                    }
                },
            },
        )
        console.log(f"Created Device: [orange1 i]{device['display']}", style="info")

        # Create IP Addresses and Interfaces
        for intf_data in node_data["interfaces"]:
            ip_address = nautobot_client.http_call(
                url="/api/ipam/ip-addresses/",
                method="post",
                json_data={
                    "address": intf_data["ipv4"],
                    "status": {"id": statuses["id"]},
                    "namespace": {"id": ipam_namespace["id"]},
                    "type": "host",
                },
            )
            console.log(f"Created IP Address: [orange1 i]{ip_address['display']}", style="info")

            interface = nautobot_client.http_call(
                url="/api/dcim/interfaces/",
                method="post",
                json_data={
                    "device": {"id": device["id"]},
                    "name": intf_data["name"],
                    "type": "virtual",
                    "enabled": True,
                    "description": f"Interface {intf_data['name']}",
                    "status": {"id": statuses["id"]},
                    "label": intf_data["role"],
                },
            )
            console.log(f"Created Interface: [orange1 i]{device['display']}:{interface['display']}", style="info")

            # Create IP address to interface mapping
            mapping = nautobot_client.http_call(
                url="/api/ipam/ip-address-to-interface/",
                method="post",
                json_data={
                    "ip_address": {"id": ip_address["id"]},
                    "interface": {"id": interface["id"]},
                },
            )
            console.log(f"Created IP Address to Interface Mapping: [orange1 i]{mapping['display']}", style="info")

        # Create Mgmt IP Address
        mgmt_ip_address = nautobot_client.http_call(
            url="/api/ipam/ip-addresses/",
            method="post",
            json_data={
                "address": node_data["mgmt-ipv4"],
                "status": {"id": statuses["id"]},
                "namespace": {"id": ipam_namespace["id"]},
                "type": "host",
            },
        )
        console.log(f"Created Mgmt IP Address: [orange1 i]{mgmt_ip_address['display']}", style="info")

        # Create Mgmt Interface
        mgmt_interface = nautobot_client.http_call(
            url="/api/dcim/interfaces/",
            method="post",
            json_data={
                "device": {"id": device["id"]},
                "name": "Management0",
                "type": "virtual",
                "enabled": True,
                "description": "Management Interface",
                "status": {"id": statuses["id"]},
                "label": "mgmt",
            },
        )
        console.log(f"Created Mgmt Interface: [orange1 i]{device['display']}:{mgmt_interface['display']}", style="info")

        # Create Mgmt IP address to interface mapping
        mgmt_mapping = nautobot_client.http_call(
            url="/api/ipam/ip-address-to-interface/",
            method="post",
            json_data={
                "ip_address": {"id": mgmt_ip_address["id"]},
                "interface": {"id": mgmt_interface["id"]},
            },
        )
        console.log(f"Created Mgmt IP Address to Interface Mapping: [orange1 i]{mgmt_mapping['display']}", style="info")

        # Update Device with Primary IP Address
        device = nautobot_client.http_call(
            url=f"/api/dcim/devices/{device['id']}/",
            method="patch",
            json_data={
                "primary_ip4": {"id": mgmt_ip_address["id"]},
            },
        )
        console.log(f"Updated Device: [orange1 i]{device['display']}", style="info")


@utils_app.command("delete-nautobot", help="Delete Nautobot data from containerlab topology file")
def utils_delete_nautobot_data(
    nautobot_token: Annotated[str, typer.Option(help="Nautobot Token", envvar="NAUTOBOT_SUPERUSER_API_TOKEN")],
    nautobot_url: Annotated[str, typer.Option(help="Nautobot URL", envvar="NAUTOBOT_URL")] = "http://localhost:8080",
):
    """Delete Nautobot data from containerlab topology file."""
    console.log("Deleting Nautobot data", style="info")

    # Instantiate Nautobot Client
    console.log("Instantiating Nautobot Client", style="info")
    nautobot_client = NautobotClient(url=nautobot_url, token=nautobot_token)

    # Delete Devices
    console.log("Delete Devices in Nautobot", style="info")
    all_devices = nautobot_client.http_call(url="/api/dcim/devices/", method="get")
    if all_devices["count"] > 0:
        nautobot_client.http_call(url="/api/dcim/devices/", method="delete", json_data=all_devices["results"])

    # Delete Locations
    console.log("Delete Locations in Nautobot", style="info")
    all_locations = nautobot_client.http_call(url="/api/dcim/locations/", method="get")
    if all_locations["count"] > 0:
        nautobot_client.http_call(url="/api/dcim/locations/", method="delete", json_data=all_locations["results"])

    # Delete Location Types
    console.log("Delete Location Types in Nautobot", style="info")
    all_location_types = nautobot_client.http_call(url="/api/dcim/location-types/", method="get")
    if all_location_types["count"] > 0:
        nautobot_client.http_call(
            url="/api/dcim/location-types/", method="delete", json_data=all_location_types["results"]
        )

    # Delete Device Types
    console.log("Delete Device Types in Nautobot", style="info")
    all_device_types = nautobot_client.http_call(url="/api/dcim/device-types/", method="get")
    if all_device_types["count"] > 0:
        nautobot_client.http_call(url="/api/dcim/device-types/", method="delete", json_data=all_device_types["results"])

    # Delete Manufacturers
    console.log("Delete Manufacturers in Nautobot", style="info")
    all_manufacturers = nautobot_client.http_call(url="/api/dcim/manufacturers/", method="get")
    if all_manufacturers["count"] > 0:
        nautobot_client.http_call(
            url="/api/dcim/manufacturers/", method="delete", json_data=all_manufacturers["results"]
        )

    # Delete Roles
    console.log("Delete Roles in Nautobot", style="info")
    all_roles = nautobot_client.http_call(url="/api/extras/roles/", method="get")
    if all_roles["count"] > 0:
        nautobot_client.http_call(url="/api/extras/roles/", method="delete", json_data=all_roles["results"])

    # Delete IP Address
    console.log("Delete IP Address in Nautobot", style="info")
    all_ip_address = nautobot_client.http_call(url="/api/ipam/ip-addresses/", method="get")
    if all_ip_address["count"] > 0:
        nautobot_client.http_call(url="/api/ipam/ip-addresses/", method="delete", json_data=all_ip_address["results"])

    # Delete Prefix
    console.log("Delete Prefix in Nautobot", style="info")
    all_prefix = nautobot_client.http_call(url="/api/ipam/prefixes/", method="get")
    if all_prefix["count"] > 0:
        nautobot_client.http_call(url="/api/ipam/prefixes/", method="delete", json_data=all_prefix["results"])

    # Delete Namespace
    console.log("Delete Namespace in Nautobot", style="info")
    all_namespaces = nautobot_client.http_call(url="/api/ipam/namespaces/", method="get")
    if all_namespaces["count"] > 0:
        nautobot_client.http_call(url="/api/ipam/namespaces/", method="delete", json_data=all_namespaces["results"])

    # Delete Statuses
    console.log("Delete Statuses in Nautobot", style="info")
    all_statuses = nautobot_client.http_call(url="/api/extras/statuses/", method="get")
    if all_statuses["count"] > 0:
        nautobot_client.http_call(url="/api/extras/statuses/", method="delete", json_data=all_statuses["results"])

    console.log("Nautobot data deleted", style="info")
