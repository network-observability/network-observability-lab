import os
import subprocess
import shlex
from typing import Optional
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


def run_cmd(
    exec_cmd: str,
    envvars: Optional[dict] = None,
    cwd: Optional[str] = None,
    timeout: int = 60,
    shell: bool = False,
    capture_output: bool = True,
    text: bool = False,
    check: bool = False,
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
            text (bool, optional): Return stdout and stderr as text. Defaults to False.
            check (bool, optional): Raise an exception if the command fails. Defaults to False.
            task_name (str, optional): Name of the task. Defaults to "".

        Returns:
            subprocess.CompletedProcess: Result of the command
    """
    console.log(f"Running command: [orange1 i]{exec_cmd}", style="info")
    if envvars:
        envvars = {**os.environ, **envvars}
    else:
        envvars = os.environ  # type: ignore
    try:
        result = subprocess.run(
            shlex.split(exec_cmd),
            env=envvars,
            cwd=cwd,
            timeout=timeout,
            shell=shell,
            capture_output=capture_output,
            text=text,
            check=check,
        )
    except subprocess.CalledProcessError as e:
        console.log(f"Command failed: {e}", style="error")
        raise e
    except subprocess.TimeoutExpired as e:
        console.log(f"Command timed out: {e}", style="error")
        raise e
    except Exception as e:
        console.log(f"Unknown exception raised: {e}", style="error")
        raise e
    else:
        if result.returncode == 0:
            console.log(f"Command succeeded: {result}", style="good")
        else:
            console.log(f"Command had issues: {result}", style="warning")
        return result
