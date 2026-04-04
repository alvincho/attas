# File Storage Pulser Demo

`file-storage` is the easiest pulser demo in the repo. It starts a local Plaza and a local `FileStoragePulser`, then exercises bucket and object operations through the pulser editor UI or `curl`.

## Files In This Folder

- `plaza.agent`: local Plaza for this pulser demo
- `file-storage.pulser`: local filesystem-backed storage pulser
- `start-plaza.sh`: launch the Plaza
- `start-pulser.sh`: launch the pulser

## Quickstart

Open two terminals from the repository root.

### Terminal 1: start Plaza

```bash
./demos/pulsers/file-storage/start-plaza.sh
```

Expected result:

- Plaza starts on `http://127.0.0.1:8256`

### Terminal 2: start the pulser

```bash
./demos/pulsers/file-storage/start-pulser.sh
```

Expected result:

- the pulser starts on `http://127.0.0.1:8257`
- it registers itself with the Plaza on `http://127.0.0.1:8256`

## Try It In The Browser

Open:

- `http://127.0.0.1:8257/`

Then test these pulses in order:

1. `bucket_create`
2. `object_save`
3. `object_load`
4. `list_bucket`

Suggested params for `bucket_create`:

```json
{
  "bucket_name": "demo-assets",
  "visibility": "public"
}
```

Suggested params for `object_save`:

```json
{
  "bucket_name": "demo-assets",
  "object_key": "notes/hello.txt",
  "text": "hello from the file storage pulser demo"
}
```

Suggested params for `object_load`:

```json
{
  "bucket_name": "demo-assets",
  "object_key": "notes/hello.txt"
}
```

## Try It With Curl

Create a bucket:

```bash
curl -sS http://127.0.0.1:8257/api/test-pulse \
  -H 'Content-Type: application/json' \
  -d '{"pulse_name":"bucket_create","params":{"bucket_name":"demo-assets","visibility":"public"}}'
```

Save an object:

```bash
curl -sS http://127.0.0.1:8257/api/test-pulse \
  -H 'Content-Type: application/json' \
  -d '{"pulse_name":"object_save","params":{"bucket_name":"demo-assets","object_key":"notes/hello.txt","text":"hello from curl"}}'
```

Load it back:

```bash
curl -sS http://127.0.0.1:8257/api/test-pulse \
  -H 'Content-Type: application/json' \
  -d '{"pulse_name":"object_load","params":{"bucket_name":"demo-assets","object_key":"notes/hello.txt"}}'
```

## What To Point Out

- this pulser is fully local and does not need cloud credentials
- the payloads are simple enough to understand without extra tooling
- the storage backend can later be swapped from filesystem to another provider while keeping the pulse interface stable

## Build Your Own

If you want to customize it:

1. copy `file-storage.pulser`
2. change the ports and storage `root_path`
3. keep the same pulse surface if you want compatibility with the workbench and existing examples
