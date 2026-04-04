# Prompits Example Configs

These files are minimal local examples for the current Prompits runtime. They are meant for open source documentation, demos, and first-run onboarding.

## Files

- `plaza.agent`: Plaza with a local `FileSystemPool`
- `worker.agent`: a basic `StandbyAgent` that auto-registers with Plaza
- `user.agent`: a `UserAgent` that exposes the Plaza browser UI

## Run Order

From the repository root:

```bash
python3 prompits/create_agent.py --config prompits/examples/plaza.agent
python3 prompits/create_agent.py --config prompits/examples/worker.agent
python3 prompits/create_agent.py --config prompits/examples/user.agent
```

Then visit `http://127.0.0.1:8214/`.

## Storage

The example configs write local state under:

```text
prompits/examples/storage/
```

That directory is created automatically by `FileSystemPool`.
