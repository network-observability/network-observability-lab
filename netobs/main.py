"""Netobs CLI."""

# ruff: noqa: B008, B006
import os
import shlex
import subprocess  # nosec
import time
from enum import Enum
from pathlib import Path
from subprocess import CompletedProcess  # nosec
from typing import Any, Optional
from urllib.parse import urlparse

import netmiko
import requests
import typer
import yaml
from dotenv import dotenv_values, load_dotenv
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry  # type: ignore
from rich.console import Console
from rich.theme import Theme
from typing_extensions import Annotated

load_dotenv(verbose=True, override=True, dotenv_path=Path("./.env"))
ENVVARS = {**dotenv_values(".env"), **dotenv_values(".setup.env"), **os.environ}

custom_theme = Theme({"info": "cyan", "warning": "bold magenta", "error": "bold red", "good": "bold green"})

console = Console(color_system="truecolor", log_path=False, record=True, theme=custom_theme, force_terminal=True)

app = typer.Typer(help="Run commands for setup and testing", rich_markup_mode="rich", add_completion=False)
containerlab_app = typer.Typer(help="Containerlab related commands.", rich_markup_mode="rich")
app.add_typer(containerlab_app, name="containerlab")

docker_app = typer.Typer(help="Docker and Stacks management related commands.", rich_markup_mode="rich")
app.add_typer(docker_app, name="docker")

lab_app = typer.Typer(help="Overall Lab management related commands.", rich_markup_mode="rich")
app.add_typer(lab_app, name="lab")

setup_app = typer.Typer(help="Lab hosting machine setup related commands.", rich_markup_mode="rich")
app.add_typer(setup_app, name="setup")

utils_app = typer.Typer(help="Utilities and scripts related commands.", rich_markup_mode="rich")
app.add_typer(utils_app, name="utils")


class NetObsScenarios(Enum):
    """NetObs scenarios."""

    BATTERIES_INCLUDED = "batteries-included"
    CH3_COMPLETED = "ch3-completed"
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
    CH12 = "ch12"
    CH12_COMPLETED = "ch12-completed"
    CH13 = "ch13"
    CH13_COMPLETED = "ch13-completed"
    WEBINAR = "webinar"
    WEBINAR_COMPLETED = "webinar-completed"


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

    # Clean environment variables
    clean_envvars = {k: str(v) for k, v in envvars.items() if v is not None and isinstance(v, (str, int, float, bool))}

    result = subprocess.run(
        shlex.split(exec_cmd),
        env=clean_envvars,
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
            raise typer.Exit(1) from exc
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


@docker_app.command(rich_help_panel="Docker Stack Management", name="build")
def docker_build(
    scenario: Annotated[
        NetObsScenarios, typer.Option("--scenario", "-s", help="Scenario to execute command", envvar="LAB_SCENARIO")
    ],
    services: Annotated[Optional[list[str]], typer.Argument(help="Service(s) to show")] = None,
    verbose: Annotated[bool, typer.Option(help="Verbose mode")] = False,
):
    """Build necessary containers.

    [u]Example:[/u]

    To build all services:
        [i]netobs docker build --scenario batteries-included[/i]

    To build a specific services:
        [i]netobs docker build telegraf-01 telegraf-02 --scenario batteries-included[/i]
    """
    console.log(f"Building service(s): [orange1 i]{services}", style="info")
    run_docker_compose_cmd(
        action="build",
        filename=Path(f"./chapters/{scenario.value}/docker-compose.yml"),
        services=services if services else [],
        verbose=verbose,
        task_name="build stack",
    )


@docker_app.command(rich_help_panel="Docker Stack Management", name="exec")
def docker_exec(
    service: Annotated[str, typer.Argument(help="Service to execute command")],
    scenario: Annotated[
        NetObsScenarios, typer.Option("--scenario", "-s", help="Scenario to execute command", envvar="LAB_SCENARIO")
    ],
    command: Annotated[str, typer.Argument(help="Command to execute")] = "bash",
    verbose: Annotated[bool, typer.Option(help="Verbose mode")] = False,
):
    """Execute a command in a container.

    [u]Example:[/u]

    To execute a command in a service:
        [i]netobs docker exec telegraf-01 --scenario batteries-included --command bash[/i]

        To execute a command in a service and verbose mode:
        [i]netobs docker exec telegraf-01 --scenario batteries-included --command bash --verbose[/i]
    """
    console.log(f"Executing command in service: [orange1 i]{service}", style="info")
    run_docker_compose_cmd(
        action="exec",
        filename=Path(f"./chapters/{scenario.value}/docker-compose.yml"),
        services=[service],
        command=command,
        verbose=verbose,
        task_name="exec command",
    )


@docker_app.command(rich_help_panel="Docker Stack Management", name="debug")
def docker_debug(
    scenario: Annotated[
        NetObsScenarios, typer.Option("--scenario", "-s", help="Scenario to execute command", envvar="LAB_SCENARIO")
    ],
    services: Annotated[Optional[list[str]], typer.Argument(help="Service(s) to show")] = None,
    verbose: Annotated[bool, typer.Option(help="Verbose mode")] = False,
):
    """Start docker compose in debug mode.

    [u]Example:[/u]

    To start all services in debug mode:
        [i]netobs docker debug --scenario batteries-included[/i]

    To start a specific service in debug mode:
        [i]netobs docker debug telegraf-01 --scenario batteries-included[/i]
    """
    console.log(f"Starting in debug mode service(s): [orange1 i]{services}", style="info")
    run_docker_compose_cmd(
        action="up",
        filename=Path(f"./chapters/{scenario.value}/docker-compose.yml"),
        services=services if services else [],
        verbose=verbose,
        extra_options="--remove-orphans",
        task_name="debug stack",
    )


@docker_app.command(rich_help_panel="Docker Stack Management", name="start")
def docker_start(
    scenario: Annotated[
        NetObsScenarios, typer.Option("--scenario", "-s", help="Scenario to execute command", envvar="LAB_SCENARIO")
    ],
    services: Annotated[Optional[list[str]], typer.Argument(help="Service(s) to show")] = None,
    verbose: Annotated[bool, typer.Option(help="Verbose mode")] = False,
):
    """Start all containers.

    [u]Example:[/u]

    To start all services:
        [i]netobs docker start --scenario batteries-included[/i]

    To start a specific service:
        [i]netobs docker start telegraf-01 --scenario batteries-included[/i]
    """
    console.log(f"Starting service(s): [orange1 i]{services}", style="info")
    run_docker_compose_cmd(
        action="up",
        filename=Path(f"./chapters/{scenario.value}/docker-compose.yml"),
        services=services if services else [],
        verbose=verbose,
        extra_options="-d --remove-orphans",
        task_name="start stack",
    )


@docker_app.command(rich_help_panel="Docker Stack Management", name="stop")
def docker_stop(
    scenario: Annotated[
        NetObsScenarios, typer.Option("--scenario", "-s", help="Scenario to execute command", envvar="LAB_SCENARIO")
    ],
    services: Annotated[Optional[list[str]], typer.Argument(help="Service(s) to show")] = None,
    verbose: Annotated[bool, typer.Option(help="Verbose mode")] = False,
):
    """Stop all containers.

    [u]Example:[/u]

    To stop all services:
        [i]netobs docker stop --scenario batteries-included[/i]

    To stop a specific service:
        [i]netobs docker stop telegraf-01 telegraf-02 --scenario batteries-included[/i]
    """
    console.log(f"Stopping service(s): [orange1 i]{services}", style="info")
    run_docker_compose_cmd(
        action="stop",
        filename=Path(f"./chapters/{scenario.value}/docker-compose.yml"),
        services=services if services else [],
        verbose=verbose,
        task_name="stop stack",
    )


@docker_app.command(rich_help_panel="Docker Stack Management", name="restart")
def docker_restart(
    scenario: Annotated[
        NetObsScenarios, typer.Option("--scenario", "-s", help="Scenario to execute command", envvar="LAB_SCENARIO")
    ],
    services: Annotated[Optional[list[str]], typer.Argument(help="Service(s) to show")] = None,
    verbose: Annotated[bool, typer.Option(help="Verbose mode")] = False,
):
    """Restart all containers.

    [u]Example:[/u]

    To restart all services:
        [i]netobs docker restart --scenario batteries-included[/i]

    To restart a specific service:
        [i]netobs docker restart telegraf-01 logstash --scenario batteries-included[/i]
    """
    console.log(f"Restarting service(s): [orange1 i]{services}", style="info")
    run_docker_compose_cmd(
        action="restart",
        filename=Path(f"./chapters/{scenario.value}/docker-compose.yml"),
        services=services if services else [],
        verbose=verbose,
        task_name="restart stack",
    )


@docker_app.command(rich_help_panel="Docker Stack Management", name="logs")
def docker_logs(
    scenario: Annotated[
        NetObsScenarios, typer.Option("--scenario", "-s", help="Scenario to execute command", envvar="LAB_SCENARIO")
    ],
    services: Annotated[Optional[list[str]], typer.Argument(help="Service(s) to show")] = None,
    follow: Annotated[bool, typer.Option("-f", "--follow", help="Follow logs")] = False,
    tail: Optional[int] = typer.Option(None, "-t", "--tail", help="Number of lines to show"),
    verbose: Annotated[bool, typer.Option(help="Verbose mode")] = False,
):
    """Show logs for containers.

    [u]Example:[/u]

    To show logs for all services:
        [i]netobs docker logs --scenario batteries-included[/i]

    To show logs for a specific service:
        [i]netobs docker logs telegraf-01 --scenario batteries-included[/i]

    To show logs for a specific service and follow the logs and tail 10 lines:
        [i]netobs docker logs telegraf-01 --scenario batteries-included --follow --tail 10[/i]
    """
    console.log(f"Showing logs for service(s): [orange1 i]{services}", style="info")
    options = ""
    if follow:
        options += "-f "
    if tail:
        options += f"--tail={tail}"
    run_docker_compose_cmd(
        action="logs",
        filename=Path(f"./chapters/{scenario.value}/docker-compose.yml"),
        services=services if services else [],
        extra_options=options,
        verbose=verbose,
        task_name="show logs",
    )


@docker_app.command(rich_help_panel="Docker Stack Management", name="ps")
def docker_ps(
    scenario: Annotated[
        NetObsScenarios, typer.Option("--scenario", "-s", help="Scenario to execute command", envvar="LAB_SCENARIO")
    ],
    services: Annotated[Optional[list[str]], typer.Argument(help="Service(s) to show")] = None,
    verbose: Annotated[bool, typer.Option(help="Verbose mode")] = False,
):
    """Show containers.

    [u]Example:[/u]

    To show all services:
        [i]netobs docker ps --scenario batteries-included[/i]

    To show a specific service:
        [i]netobs docker ps telegraf-01 --scenario batteries-included[/i]
    """
    console.log(f"Showing containers for service(s): [orange1 i]{services}", style="info")
    run_docker_compose_cmd(
        action="ps",
        filename=Path(f"./chapters/{scenario.value}/docker-compose.yml"),
        services=services if services else [],
        verbose=verbose,
        task_name="show containers",
    )


@docker_app.command(rich_help_panel="Docker Stack Management", name="destroy")
def docker_destroy(
    scenario: Annotated[
        NetObsScenarios, typer.Option("--scenario", "-s", help="Scenario to execute command", envvar="LAB_SCENARIO")
    ],
    services: Annotated[Optional[list[str]], typer.Argument(help="Service(s) to show")] = None,
    volumes: Annotated[bool, typer.Option(help="Remove volumes")] = False,
    verbose: Annotated[bool, typer.Option(help="Verbose mode")] = False,
):
    """Destroy containers and resources.

    [u]Example:[/u]

    To destroy all services:
        [i]netobs docker destroy --scenario batteries-included[/i]

    To destroy a specific service:
        [i]netobs docker destroy --scenario batteries-included[/i]

    To destroy a specific service and remove volumes:
        [i]netobs docker destroy telegraf-01 --volumes --scenario batteries-included[/i]

    To destroy all services and remove volumes:
        [i]netobs docker destroy --volumes --scenario batteries-included[/i]
    """
    console.log(f"Destroying service(s): [orange1 i]{services}", style="info")
    run_docker_compose_cmd(
        action="down",
        filename=Path(f"./chapters/{scenario.value}/docker-compose.yml"),
        services=services if services else [],
        verbose=verbose,
        extra_options="--volumes --remove-orphans" if volumes else "--remove-orphans",
        task_name="destroy stack",
    )


@docker_app.command(rich_help_panel="Docker Stack Management", name="rm")
def docker_rm(
    scenario: Annotated[
        NetObsScenarios, typer.Option("--scenario", "-s", help="Scenario to execute command", envvar="LAB_SCENARIO")
    ],
    services: Annotated[Optional[list[str]], typer.Argument(help="Service(s) to show")] = None,
    volumes: Annotated[bool, typer.Option(help="Remove volumes")] = False,
    force: Annotated[bool, typer.Option(help="Force removal of containers")] = False,
    verbose: Annotated[bool, typer.Option(help="Verbose mode")] = False,
):
    """Remove containers.

    [u]Example:[/u]

    To remove all services:
        [i]netobs docker rm --scenario batteries-included[/i]

    To remove a specific service:
        [i]netobs docker rm telegraf-01 --scenario batteries-included[/i]

    To remove a specific service and remove volumes:
        [i]netobs docker rm telegraf-01 --volumes --scenario batteries-included[/i]

    To remove all services and remove volumes:
        [i]netobs docker rm --volumes --scenario batteries-included[/i]

    To remove all services and force removal of containers:
        [i]netobs docker rm --force --scenario batteries-included[/i]

    To force removal of a specific service and remove volumes:
        [i]netobs docker rm telegraf-01 --volumes --force --scenario batteries-included[/i]
    """
    extra_options = "--stop "
    if force:
        extra_options += "--force "
    if volumes:
        extra_options += "--volumes "
    console.log(f"Removing service(s): [orange1 i]{services}", style="info")
    run_docker_compose_cmd(
        action="rm",
        filename=Path(f"./chapters/{scenario.value}/docker-compose.yml"),
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
    scenario: Annotated[
        NetObsScenarios, typer.Option("--scenario", "-s", help="Scenario to execute command", envvar="LAB_SCENARIO")
    ],
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
    scenario: Annotated[
        NetObsScenarios, typer.Option("--scenario", "-s", help="Scenario to execute command", envvar="LAB_SCENARIO")
    ],
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
def lab_purge(
    sudo: Annotated[bool, typer.Option(help="Use sudo to run containerlab", envvar="LAB_SUDO")] = False,
):
    """Purge all lab environments."""
    console.rule("[b i]PURGING ALL LAB ENVIRONMENTS", style="error")
    console.log("Purging lab environments", style="info")

    # Iterate over all scenarios and destroy them
    for scenario in NetObsScenarios:
        try:
            lab_destroy(scenario=scenario, sudo=sudo)
        except typer.Exit:
            pass

    console.rule("[b i]LAB ENVIRONMENTS PURGED", style="error")


@lab_app.command("show")
def lab_show(
    scenario: Annotated[
        NetObsScenarios, typer.Option("--scenario", "-s", help="Scenario to execute command", envvar="LAB_SCENARIO")
    ],
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
    scenario: Annotated[
        NetObsScenarios, typer.Option("--scenario", "-s", help="Scenario to execute command", envvar="LAB_SCENARIO")
    ],
    topology: Annotated[Path, typer.Option(help="Path to the topology file", exists=True)] = Path(
        "./containerlab/lab.yml"
    ),
    sudo: Annotated[bool, typer.Option(help="Use sudo to run containerlab", envvar="LAB_SUDO")] = False,
):
    """Prepare the lab for the scenario."""
    console.log(f"Preparing lab environment for scenario: [orange1 i]{scenario.value}", style="info")

    # Destroy all other lab environments and network topologies
    lab_purge(sudo=sudo)

    # Deploy containerlab topology
    containerlab_deploy(topology=topology, sudo=sudo)

    # Start docker compose
    docker_start(scenario=scenario, services=[], verbose=True)

    console.log(f"Lab environment prepared for scenario: [orange1 i]{scenario.value}", style="info")


@lab_app.command("update")
def lab_update(
    services: Annotated[list[str], typer.Argument(help="Service(s) to update")],
    scenario: Annotated[
        NetObsScenarios, typer.Option("--scenario", "-s", help="Scenario to execute command", envvar="LAB_SCENARIO")
    ],
):
    """Update the service(s) of a lab scenario.

    [u]Example:[/u]]

    To update all services:
        [i]netobs lab update --scenario batteries-included[/i]

    To update a specific service:
        [i]netobs lab update telegraf-01 telegraf-02 --scenario batteries-included[/i]
    """
    console.log(f"Updating lab environment for scenario: [orange1 i]{scenario.value}", style="info")

    # Delete the containers
    docker_rm(scenario=scenario, services=services, volumes=True, force=True, verbose=True)

    # Start them back
    docker_start(scenario=scenario, services=services, verbose=True)

    console.log(f"Lab environment updated for scenario: [orange1 i]{scenario.value}", style="info")


@lab_app.command("rebuild")
def lab_rebuild(
    services: Annotated[list[str], typer.Argument(help="Service(s) to rebuild")],
    scenario: Annotated[
        NetObsScenarios, typer.Option("--scenario", "-s", help="Scenario to execute command", envvar="LAB_SCENARIO")
    ],
):
    """Rebuild the service(s) of a lab scenario.

    [u]Example:[/u]

    To rebuild all services:
        [i]netobs lab rebuild --scenario batteries-included[/i]

    To rebuild a specific service:
        [i]netobs lab rebuild webhook --scenario batteries-included[/i]
    """
    console.log(f"Rebuilding lab environment for scenario: [orange1 i]{scenario.value}", style="info")

    # Stop the containers
    docker_stop(scenario=scenario, services=services, verbose=True)

    # Rebuild the containers
    docker_build(scenario=scenario, services=services, verbose=True)

    # Start them back
    docker_start(scenario=scenario, services=services, verbose=True)

    console.log(f"Lab environment rebuilt for scenario: [orange1 i]{scenario.value}", style="info")


# --------------------------------------#
#           Digital Ocean VM            #
# --------------------------------------#


def ansible_command(
    playbook: str,
    inventories: list[str] | None = None,
    limit: str | None = None,
    extra_vars: str | None = None,
    verbose: int = 0,
    scenario: str | None = None,
    topology: Path | None = None,
    vars_topology: Path | None = None,
) -> str:
    """Run an ansible playbook with the given inventories and limit.

    Args:
        playbook (str): The name of the playbook to run.
        inventories (List[str]): The list of inventories to use.
        limit (Optional[str], optional): The limit to use. Defaults to None.
        verbose (int, optional): The verbosity level. Defaults to 0.

    Returns:
        str: The ansible command to run.
    """
    exec_cmd = f"ansible-playbook setup/{playbook}"
    if inventories:
        for inventory in inventories:
            exec_cmd += f" -i setup/inventory/{inventory}"

    if limit:
        exec_cmd += f" -l {limit}"

    if extra_vars:
        exec_cmd += f' -e "{extra_vars}"'

    if scenario:
        exec_cmd += f' -e "lab_scenario={scenario}"'

    if topology:
        exec_cmd += f' -e "lab_topology_file={topology}"'

    if vars_topology:
        exec_cmd += f' -e "lab_vars_file={vars_topology}"'

    if verbose:
        exec_cmd += f" -{'v' * verbose}"

    return exec_cmd


@setup_app.command(rich_help_panel="DigitalOcean", name="deploy")
def deploy_droplet(
    verbose: Annotated[int, typer.Option("--verbose", "-v", count=True)] = 0,
    extra_vars: Annotated[
        Optional[str], typer.Option("--extra-vars", "-e", help="Extra vars to pass to the playbook")
    ] = None,
    scenario: Annotated[
        NetObsScenarios, typer.Option("--scenario", "-s", help="Scenario to execute command", envvar="LAB_SCENARIO")
    ] = NetObsScenarios.BATTERIES_INCLUDED,
    topology: Annotated[Path, typer.Option(help="Path to the topology file", exists=True)] = Path(
        "./containerlab/lab.yml"
    ),
    vars_topology: Annotated[Path, typer.Option(help="Path to the vars topology file", exists=True)] = Path(
        "./containerlab/lab_vars.yml"
    ),
):
    """Create DigitalOcean Droplets.

    [u]Example:[/u]
        [i]> netobs setup deploy[/i]
    """
    # First create the keep_api_key file in the root directory from the environment variable using Path
    keep_api_key = Path("./keep_api_key")
    keep_api_key.write_text(ENVVARS.get("KEEP_API_KEY", ""))

    # Then create the droplets
    exec_cmd = ansible_command(
        playbook="create_droplet.yml",
        inventories=["localhost.yaml"],
        verbose=verbose,
        extra_vars=extra_vars,
    )
    result = run_cmd(exec_cmd=exec_cmd, envvars=ENVVARS, task_name="create droplets")
    if result.returncode == 0:
        console.log("Droplets created successfully", style="good")
    else:
        console.log("Issues encountered creating droplets", style="warning")
        raise typer.Abort()
    console.log("Proceeding to setup the droplets", style="info")
    exec_cmd = ansible_command(
        playbook="setup_droplet.yml",
        inventories=["do_hosts.yaml", "localhost.yaml"],
        verbose=verbose,
        extra_vars=extra_vars,
        scenario=scenario.value,
        topology=topology,
        vars_topology=vars_topology,
    )
    result = run_cmd(exec_cmd=exec_cmd, envvars=ENVVARS, task_name="setup droplets")
    if result.returncode == 0:
        console.log("Droplets setup successfully", style="good")
    else:
        console.log("Issues encountered setting up droplets", style="warning")
        raise typer.Abort()

    # Delete the keep_api_key file
    keep_api_key.unlink()


@setup_app.command(rich_help_panel="DigitalOcean", name="destroy")
def destroy_droplet(
    verbose: Annotated[int, typer.Option("--verbose", "-v", count=True)] = 0,
    extra_vars: Annotated[
        Optional[str], typer.Option("--extra-vars", "-e", help="Extra vars to pass to the playbook")
    ] = None,
):
    """Destroy DigitalOcean Droplets.

    [u]Example:[/u]
        [i]> netobs setup destroy[/i]
    """
    exec_cmd = ansible_command(
        playbook="destroy_droplet.yml",
        inventories=["do_hosts.yaml"],
        verbose=verbose,
        extra_vars=extra_vars,
    )
    result = run_cmd(exec_cmd=exec_cmd, envvars=ENVVARS, task_name="destroy droplets")
    if result.returncode == 0:
        console.log("Droplets destroyed successfully", style="good")
    else:
        console.log("Issues encountered destroying droplets", style="warning")
        raise typer.Abort()


@setup_app.command(rich_help_panel="DigitalOcean", name="show")
def show_droplet():
    """Show the DigitalOcean Droplet SSH command.

    [u]Example:[/u]
        [i]> netobs setup list[/i]
    """
    exec_cmd = ansible_command(
        playbook="list_droplet.yml",
        inventories=["do_hosts.yaml"],
    )
    return run_cmd(exec_cmd=exec_cmd, envvars=ENVVARS, task_name="test")


# --------------------------------------#
#                Utils                  #
# --------------------------------------#


@utils_app.command("load-nautobot", rich_help_panel="Nautobot")
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

    for manufacturer in ["Arista", "Nokia"]:
        manufacturers = nautobot_client.http_call(
            url="/api/dcim/manufacturers/",
            method="post",
            json_data={"name": manufacturer},
        )
        console.log(f"Created Manufacturer: [orange1 i]{manufacturers['display']}", style="info")

        # Create Device Types in Nautobot
        device_types = nautobot_client.http_call(
            url="/api/dcim/device-types/",
            method="post",
            json_data={"manufacturer": manufacturer, "model": "cEOS" if manufacturer == "Arista" else "SRLinux"},
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
            "color": "aaf0d1",
        },
    )
    console.log(f"Created Status: [orange1 i]{statuses['display']}", style="info")
    alerted_statuses = nautobot_client.http_call(
        url="/api/extras/statuses/",
        method="post",
        json_data={
            "name": "Alerted",
            "content_types": ["dcim.device", "dcim.interface", "dcim.location", "ipam.ipaddress", "ipam.prefix"],
            "color": "ff5a36",
        },
    )
    console.log(f"Created Status: [orange1 i]{alerted_statuses['display']}", style="info")

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


@utils_app.command("delete-nautobot", rich_help_panel="Nautobot")
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


@utils_app.command("device-interface-flap", rich_help_panel="Network Device")
def utils_device_interface_flap(
    device: Annotated[str, typer.Option(help="Device to flap interface", envvar="LAB_DEVICE")],
    interface: Annotated[str, typer.Option(help="Interface to flap", envvar="LAB_INTERFACE")],
    count: Annotated[int, typer.Option(help="Number of flaps", envvar="LAB_FLAP_COUNT")] = 1,
    delay: Annotated[int, typer.Option(help="Delay between flaps", envvar="LAB_FLAP_DELAY")] = 5,
):
    """Flap a network device interface."""
    console.log(f"Flapping interface: [orange1 i]{interface} on device: {device}", style="info")
    device_conn = netmiko.ConnectHandler(
        device_type="arista_eos",
        host=device,
        username="netobs",
        password="netobs123",
    )
    # Enable the config mode
    device_conn.enable()
    device_conn.config_mode()
    for _ in range(count):
        console.log("Bringing interface down...", style="info")
        device_conn.send_config_set([f"interface {interface}", "shutdown"])
        time.sleep(delay)
        console.log("Bringing interface up...", style="info")
        device_conn.send_config_set([f"interface {interface}", "no shutdown"])
        time.sleep(delay)
    console.log(f"Flapped interface: [orange1 i]{interface} on device: {device}", style="info")


@utils_app.command("load-prefect-secrets", rich_help_panel="Prefect")
def utils_load_prefect_secrets(
    prefect_api_url: Annotated[
        str, typer.Option(help="Prefect API URL", envvar="PREFECT_API_URL")
    ] = "http://localhost:4200/api",
    nautobot_token: Annotated[str, typer.Option(help="Nautobot Token", envvar="NAUTOBOT_SUPERUSER_API_TOKEN")] = "",
    openai_token: Annotated[str, typer.Option(help="OpenAI API Key", envvar="OPENAI_API_KEY")] = "",
    network_user: Annotated[str, typer.Option(help="Network Agent User", envvar="NETWORK_AGENT_USER")] = "netobs",
    network_password: Annotated[
        str, typer.Option(help="Network Agent Password", envvar="NETWORK_AGENT_PASSWORD")
    ] = "netobs123",
    network_device_type: Annotated[str, typer.Option(help="Network Device Type")] = "arista_eos",
    slack_bot_token: Annotated[str, typer.Option(help="Slack Bot Token", envvar="SLACK_BOT_TOKEN")] = "",
):
    """Load secrets to Prefect server from environment variables.

    [u]Example:[/u]
        [i]netobs utils load-prefect-secrets[/i]

        To load with custom values:
        [i]netobs utils load-prefect-secrets --openai-token sk-xxx --slack-bot-token xoxb-xxx[/i]
    """
    console.log("Loading secrets to Prefect server", style="info")

    # Define secrets to upload
    secrets = {
        "nautobot-token": nautobot_token,
        "openai-token": openai_token,
        "net-user": network_user,
        "net-pass": network_password,
        "net-device-type": network_device_type,
        "slack-bot-token": slack_bot_token,
    }

    # Filter out empty secrets
    secrets_to_upload = {name: value for name, value in secrets.items() if value}

    if not secrets_to_upload:
        console.log("No secrets to upload. Please provide secret values.", style="warning")
        return

    console.log(f"Prefect API URL: [orange1 i]{prefect_api_url}", style="info")
    console.log(f"Uploading {len(secrets_to_upload)} secret(s)", style="info")

    # Get the secret block type and schema IDs
    try:
        block_type_response = requests.post(
            f"{prefect_api_url}/block_types/filter",
            json={"block_types": {"slug": {"any_": ["secret"]}}},
            timeout=10,
        )
        block_type_response.raise_for_status()
        block_types = block_type_response.json()

        if not block_types:
            console.log("Secret block type not found in Prefect server", style="error")
            return

        block_type_id = block_types[0]["id"]

        # Get the schema ID for the secret block type
        schema_response = requests.post(
            f"{prefect_api_url}/block_schemas/filter",
            json={"block_schemas": {"block_type_id": {"any_": [block_type_id]}}},
            timeout=10,
        )
        schema_response.raise_for_status()
        schemas = schema_response.json()

        if not schemas:
            console.log("Secret block schema not found in Prefect server", style="error")
            return

        block_schema_id = schemas[0]["id"]

    except requests.exceptions.RequestException as err:
        console.log(f"Failed to get secret block type/schema: {err}", style="error")
        return

    for secret_name, secret_value in secrets_to_upload.items():
        try:
            # Create secret block document via Prefect API
            response = requests.post(
                f"{prefect_api_url}/block_documents/",
                json={
                    "name": secret_name,
                    "block_type_id": block_type_id,
                    "block_schema_id": block_schema_id,
                    "data": {"value": secret_value},
                },
                timeout=10,
            )

            if response.status_code == 201:
                console.log(f"Created secret: [orange1 i]{secret_name}", style="good")
            elif response.status_code == 409 or "already exists" in response.text.lower():
                # Secret already exists, update it
                console.log(f"Secret already exists, updating: [orange1 i]{secret_name}", style="info")

                # Get existing block ID
                blocks_response = requests.post(
                    f"{prefect_api_url}/block_documents/filter",
                    json={"block_documents": {"name": {"any_": [secret_name]}}},
                    timeout=10,
                )
                blocks_response.raise_for_status()
                blocks = blocks_response.json()

                if blocks:
                    block_id = blocks[0]["id"]
                    # Update the block
                    update_response = requests.patch(
                        f"{prefect_api_url}/block_documents/{block_id}",
                        json={"data": {"value": secret_value}},
                        timeout=10,
                    )
                    update_response.raise_for_status()
                    console.log(f"Updated secret: [orange1 i]{secret_name}", style="good")
            else:
                response.raise_for_status()

        except requests.exceptions.RequestException as err:
            console.log(f"Failed to create secret [orange1 i]{secret_name}: {err}", style="error")
            continue

    console.log("Prefect secrets loaded successfully", style="good")


@utils_app.command("delete-prefect-secrets", rich_help_panel="Prefect")
def utils_delete_prefect_secrets(
    prefect_api_url: Annotated[
        str, typer.Option(help="Prefect API URL", envvar="PREFECT_API_URL")
    ] = "http://localhost:4200/api",
):
    """Delete all secrets from Prefect server.

    [u]Example:[/u]
        [i]netobs utils delete-prefect-secrets[/i]
    """
    console.log("Deleting secrets from Prefect server", style="info")
    console.log(f"Prefect API URL: [orange1 i]{prefect_api_url}", style="info")

    try:
        # Get the secret block type ID first
        block_type_response = requests.post(
            f"{prefect_api_url}/block_types/filter",
            json={"block_types": {"slug": {"any_": ["secret"]}}},
            timeout=10,
        )
        block_type_response.raise_for_status()
        block_types = block_type_response.json()

        if not block_types:
            console.log("Secret block type not found", style="warning")
            return

        block_type_id = block_types[0]["id"]

        # Get all secret block documents
        response = requests.post(
            f"{prefect_api_url}/block_documents/filter",
            json={"block_documents": {"block_type_id": {"any_": [block_type_id]}}},
            timeout=10,
        )
        response.raise_for_status()
        secrets = response.json()

        if not secrets:
            console.log("No secrets found to delete", style="info")
            return

        console.log(f"Found {len(secrets)} secret(s) to delete", style="info")

        # Delete each secret
        for secret in secrets:
            secret_name = secret["name"]
            secret_id = secret["id"]

            try:
                delete_response = requests.delete(
                    f"{prefect_api_url}/block_documents/{secret_id}",
                    timeout=10,
                )
                delete_response.raise_for_status()
                console.log(f"Deleted secret: [orange1 i]{secret_name}", style="good")
            except requests.exceptions.RequestException as err:
                console.log(f"Failed to delete secret [orange1 i]{secret_name}: {err}", style="error")
                continue

        console.log("Prefect secrets deleted successfully", style="good")

    except requests.exceptions.RequestException as err:
        console.log(f"Failed to retrieve secrets: {err}", style="error")
        raise typer.Exit(1) from err
