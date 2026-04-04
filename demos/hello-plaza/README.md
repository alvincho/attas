# Hello Plaza

`hello-plaza` is the smallest public demo in this workspace. It starts a local Plaza, registers one worker, and serves a browser-facing user agent so people can see the directory come to life.

## What This Demo Shows

- a Plaza registry running locally
- an agent auto-registering with Plaza
- a browser-facing user UI connected to that Plaza
- a minimal config set that builders can copy into their own project

## Files In This Folder

- `plaza.agent`: demo Plaza config
- `worker.agent`: demo worker config
- `user.agent`: demo user-agent config
- `start-plaza.sh`: launch Plaza
- `start-worker.sh`: launch the worker
- `start-user.sh`: launch the browser-facing user agent

All runtime state is written under `demos/hello-plaza/storage/`.

## Prerequisites

From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

## Quickstart

Open three terminals from the repository root.

### Terminal 1: start Plaza

```bash
./demos/hello-plaza/start-plaza.sh
```

Expected result:

- Plaza starts on `http://127.0.0.1:8211`
- `http://127.0.0.1:8211/health` returns a healthy status

### Terminal 2: start the worker

```bash
./demos/hello-plaza/start-worker.sh
```

Expected result:

- the worker starts on `127.0.0.1:8212`
- it auto-registers with the Plaza from Terminal 1

### Terminal 3: start the user UI

```bash
./demos/hello-plaza/start-user.sh
```

Expected result:

- the browser-facing user agent starts on `http://127.0.0.1:8214/`

## Verify The Stack

In a fourth terminal, or after the services are up:

```bash
curl http://127.0.0.1:8211/health
curl http://127.0.0.1:8214/api/plazas_status
```

What you should see:

- the first command returns a healthy Plaza response
- the second command shows the local Plaza and the registered `demo-worker`

Then open:

- `http://127.0.0.1:8214/`

This is the public-demo URL to share in a local walkthrough or screen recording.

## What To Point Out In A Demo Call

- Plaza is the discovery layer.
- The worker can be started independently and still appears in the shared directory.
- The user-facing UI does not need hardcoded knowledge of the worker. It discovers it through Plaza.

## Build Your Own Instance

The simplest way to turn this into your own instance is:

1. Copy `plaza.agent`, `worker.agent`, and `user.agent` to a new folder.
2. Rename the agents.
3. Change the ports if needed.
4. Point each `root_path` at your own storage location.
5. If you change Plaza's URL or port, update `plaza_url` in `worker.agent` and `user.agent`.

The three most important fields to customize are:

- `name`: what the agent advertises as its identity
- `port`: where the HTTP service listens
- `root_path`: where local state is stored

Once the files look right, run:

```bash
python3 prompits/create_agent.py --config path/to/your/plaza.agent
python3 prompits/create_agent.py --config path/to/your/worker.agent
python3 prompits/create_agent.py --config path/to/your/user.agent
```

## Troubleshooting

### Port already in use

Edit the relevant `.agent` file and pick a free port. If you move Plaza to a new port, update the `plaza_url` in both dependent configs.

### The user UI shows an empty Plaza directory

Check these three things:

- Plaza is running on `http://127.0.0.1:8211`
- the worker terminal is still running
- `worker.agent` still points to `http://127.0.0.1:8211`

### You want a fresh demo state

The safest reset is to point the `root_path` values at a new folder name rather than deleting data in place.

## Stop The Demo

Press `Ctrl-C` in each terminal window.
