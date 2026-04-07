# Prompits Example Configs

## Translations

- [English](README.md)
- [繁體中文](README.zh-Hant.md)
- [简体中文](README.zh-Hans.md)
- [Español](README.es.md)
- [Français](README.fr.md)
- [Italiano](README.it.md)
- [Deutsch](README.de.md)
- [日本語](README.ja.md)
- [한국어](README.ko.md)

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
