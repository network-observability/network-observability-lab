# `netobs`

**Usage**:

```console
$ netobs [OPTIONS] COMMAND [ARGS]...
```

**Options**:

* `--install-completion`: Install completion for the current shell.
* `--show-completion`: Show completion for the current shell, to copy it or customize the installation.
* `--help`: Show this message and exit.

**Commands**:

* `containerlab`
* `docker`

## `netobs containerlab`

**Usage**:

```console
$ netobs containerlab [OPTIONS] COMMAND [ARGS]...
```

**Options**:

* `--help`: Show this message and exit.

**Commands**:

* `deploy`: Deploy a containerlab topology.
* `destroy`: Destroy a containerlab topology.

### `netobs containerlab deploy`

Deploy a containerlab topology.

**Raises:**
    typer.Exit: Exit with code 1 if the topology file is not found

**Usage**:

```console
$ netobs containerlab deploy [OPTIONS] [TOPOLOGY]
```

**Arguments**:

* `[TOPOLOGY]`: Path to the topology file  [default: containerlab/lab.yml]

**Options**:

* `--sudo / --no-sudo`: Use sudo to run containerlab  [default: sudo]
* `--help`: Show this message and exit.

### `netobs containerlab destroy`

Destroy a containerlab topology.

**Raises:**
    typer.Exit: Exit with code 1 if the topology file is not found

**Usage**:

```console
$ netobs containerlab destroy [OPTIONS] [TOPOLOGY]
```

**Arguments**:

* `[TOPOLOGY]`: Path to the topology file  [default: containerlab/lab.yml]

**Options**:

* `--sudo / --no-sudo`: Use sudo to run containerlab  [default: sudo]
* `--help`: Show this message and exit.

## `netobs docker`

**Usage**:

```console
$ netobs docker [OPTIONS] COMMAND [ARGS]...
```

**Options**:

* `--help`: Show this message and exit.

**Commands**:

* `build`: Build a docker image.
* `debug`: Start docker compose in debug mode.
* `destroy`: Destroy all containers and resources.
* `exec`: Execute a command in a container.
* `logs`: Show logs for all containers.
* `network`: Manage docker network.
* `ps`: Show containers.
* `push`: Push a docker image.
* `restart`: Restart all containers.
* `start`: Start all containers.
* `stop`: Stop all containers.

### `netobs docker build`

Build a docker image.

**Raises:**
    typer.Exit: Exit with code 1 if the Dockerfile is not found

**Usage**:

```console
$ netobs docker build [OPTIONS] PATH TAG
```

**Arguments**:

* `PATH`: Path to the Dockerfile  [required]
* `TAG`: Tag to use for the image  [required]

**Options**:

* `--sudo / --no-sudo`: Use sudo to run docker  [default: sudo]
* `--help`: Show this message and exit.

### `netobs docker debug`

Start docker compose in debug mode.

**Usage**:

```console
$ netobs docker debug [OPTIONS] [SERVICE]...
```

**Arguments**:

* `[SERVICE]...`: Service(s) to run in debug mode

**Options**:

* `--verbose / --no-verbose`: Verbose mode  [default: no-verbose]
* `--help`: Show this message and exit.

### `netobs docker destroy`

Destroy all containers and resources.

**Usage**:

```console
$ netobs docker destroy [OPTIONS] [SERVICE]...
```

**Arguments**:

* `[SERVICE]...`: Service(s) to destroy

**Options**:

* `--volumes / --no-volumes`: Remove volumes  [default: no-volumes]
* `--verbose / --no-verbose`: Verbose mode  [default: no-verbose]
* `--help`: Show this message and exit.

### `netobs docker exec`

Execute a command in a container.

**Usage**:

```console
$ netobs docker exec [OPTIONS] SERVICE [COMMAND]
```

**Arguments**:

* `SERVICE`: Service to execute command  [required]
* `[COMMAND]`: Command to execute  [default: bash]

**Options**:

* `--verbose / --no-verbose`: Verbose mode  [default: no-verbose]
* `--help`: Show this message and exit.

### `netobs docker logs`

Show logs for all containers.

**Usage**:

```console
$ netobs docker logs [OPTIONS] [SERVICE]...
```

**Arguments**:

* `[SERVICE]...`: Service(s) to show logs

**Options**:

* `-f, --follow`: Follow logs
* `-t, --tail INTEGER`: Number of lines to show
* `--verbose / --no-verbose`: Verbose mode  [default: no-verbose]
* `--help`: Show this message and exit.

### `netobs docker network`

Manage docker network.

**Usage**:

```console
$ netobs docker network [OPTIONS] ACTION:{connect|create|disconnect|inspect|ls|prune|rm}
```

**Arguments**:

* `ACTION:{connect|create|disconnect|inspect|ls|prune|rm}`: Action to perform  [required]

**Options**:

* `-n, --name TEXT`: Network name  [default: network-observability]
* `--driver TEXT`: Network driver  [default: bridge]
* `--subnet TEXT`: Network subnet  [default: 172.24.177.0/24]
* `--verbose / --no-verbose`: Verbose mode  [default: no-verbose]
* `--help`: Show this message and exit.

### `netobs docker ps`

Show containers.

**Usage**:

```console
$ netobs docker ps [OPTIONS] [SERVICE]...
```

**Arguments**:

* `[SERVICE]...`: Service(s) to show

**Options**:

* `--verbose / --no-verbose`: Verbose mode  [default: no-verbose]
* `--help`: Show this message and exit.

### `netobs docker push`

Push a docker image.

**Usage**:

```console
$ netobs docker push [OPTIONS] TAG
```

**Arguments**:

* `TAG`: Tag to use for the image  [required]

**Options**:

* `--sudo / --no-sudo`: Use sudo to run docker  [default: sudo]
* `--help`: Show this message and exit.

### `netobs docker restart`

Restart all containers.

**Usage**:

```console
$ netobs docker restart [OPTIONS] [SERVICE]...
```

**Arguments**:

* `[SERVICE]...`: Service(s) to restart

**Options**:

* `--verbose / --no-verbose`: Verbose mode  [default: no-verbose]
* `--help`: Show this message and exit.

### `netobs docker start`

Start all containers.

**Usage**:

```console
$ netobs docker start [OPTIONS] [SERVICE]...
```

**Arguments**:

* `[SERVICE]...`: Service(s) to start

**Options**:

* `--verbose / --no-verbose`: Verbose mode  [default: no-verbose]
* `--help`: Show this message and exit.

### `netobs docker stop`

Stop all containers.

**Usage**:

```console
$ netobs docker stop [OPTIONS] [SERVICE]...
```

**Arguments**:

* `[SERVICE]...`: Service(s) to stop

**Options**:

* `--verbose / --no-verbose`: Verbose mode  [default: no-verbose]
* `--help`: Show this message and exit.
