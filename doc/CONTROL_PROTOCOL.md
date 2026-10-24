# Control protocol

`dnsguard` (the service) and `toney` (the TUI) are two separate applications
that talk over a Unix domain socket. The socket is the *only* interface
between them: the TUI never touches the service's files, processes or ports
directly, it asks the service over the socket.

## Transport

- Unix domain socket, path given by `--control` (default
  `~/.local/state/toney/dnsguard.sock`).
- One JSON object per line, UTF-8, `\n`-terminated, in both directions.
- A client may send multiple requests on the same connection; responses come
  back in order. The connection may stay open indefinitely.
- Maximum request line length: 1 MiB.

## Request

```json
{"id": 7, "cmd": "status", "params": {}}
```

- `id` — any JSON scalar chosen by the client. Echoed back verbatim.
- `cmd` — the command name (see below).
- `params` — optional object with command-specific arguments.

## Response

```json
{"id": 7, "ok": true, "data": {"…": "…"}}
```

or

```json
{"id": 7, "ok": false, "error": "unknown command: frobnicate"}
```

A command that fails does not close the connection.

## Commands

### `status`

Full service state. No params.

```json
{
  "name": "dnsguard",
  "version": "0.1.0",
  "pid": 4242,
  "started_at": "2026-01-02T03:04:05Z",
  "uptime_s": 3600,
  "listen": "0.0.0.0:5353",
  "upstream": ["198.51.100.53", "198.51.100.54"],
  "config_path": "/etc/toney/dnsguard.json",
  "rules": {"count": 67, "loaded_at": "2026-01-02T03:04:05Z", "sources": ["profiles/privacy-tv.blocklist"]},
  "counters": {"total": 1285, "allowed": 903, "blocked": 179, "cached": 203, "errors": 0},
  "clients": {"192.0.2.10": {"total": 900, "blocked": 120, "allowed": 780}},
  "log": {"dir": "/var/log/toney/dnsguard", "retention_days": 5,
          "total_bytes": 1048576, "files": [{"path": "2026-01-02.jsonl", "bytes": 4096, "mtime": "2026-01-02T04:00:00Z"}]}
}
```

`counters.cached` counts answers served from the in-memory cache; it is also
included in `total`.

### `stats`

Params: `{"window_s": 300}` (default 300). Time-bucketed counters plus the
most frequent names.

```json
{
  "window_s": 300,
  "buckets": [{"t": "2026-01-02T03:05:00Z", "total": 12, "blocked": 3, "allowed": 9}],
  "top_blocked": [{"name": "ads.example.net", "count": 12}],
  "top_allowed": [{"name": "cdn.example.net", "count": 30}]
}
```

### `rules.list`

```json
{
  "count": 67,
  "rules": [{"pattern": "||ads.example.net^", "action": "block", "source": "profiles/privacy-tv.blocklist", "line": 12}]
}
```

`action` is `block` or `allow`.

### `rules.reload`

Re-reads every source file listed in the config. Returns the same shape as
`rules.list` plus `{"loaded_at": "…", "duration_ms": 3}`.

### `rules.set`

Params: `{"path": "/tmp/toney-rules-1234.blocklist"}`.

Replaces the active rule set with the contents of `path` (the TUI writes the
file first). The file is copied into the service's own rule directory, so it
survives a restart. Returns the same shape as `rules.reload`.

### `logs.tail`

Params: `{"limit": 200, "filter": "substring", "client": "192.0.2.10"}`
(all optional; `limit` default 100, max 5000).

Returns the most recent matching log records, newest first:

```json
{"lines": [{"ts": "2026-01-02T03:05:00Z", "client": "192.0.2.10",
            "name": "ads.example.net.", "type": "A",
            "decision": "block", "rule": "||ads.example.net^"}]}
```

### `config.get`

Returns the effective configuration with any secret-bearing fields replaced by
`"***"`.

### `config.set`

Params: a partial configuration object. Only the listed keys are changed; the
rest keep their current value. Returns the new effective configuration.

Known keys: `listen`, `upstream`, `cache_size`, `cache_ttl_s`,
`log_dir`, `retention_days`, `log_max_bytes`, `rules` (list of paths),
`control` (socket path — changing it requires a restart and is rejected
otherwise).

### `upstream.set`

Params: `{"servers": ["198.51.100.53"]}` or `{"servers": [], "doh": "https://dns.example/dns-query"}`.

Swaps the upstream resolver at runtime without dropping the listening socket.

### `shutdown`

Graceful stop: flush the log, close the socket, exit `0`. The TUI uses this
for "stop".

### `router.status`

Report whether the generated dnsmasq include file is installed on the
configured router and whether it matches the rule set that is loaded now.

```json
{"configured": true, "installed": true, "remote_path": "/etc/dnsmasq.d/toney.conf",
 "bytes": 2048, "matches": true, "local_hash": "…", "remote_hash": "…"}
```

When no router is configured: `{"configured": false, "installed": false, "matches": false}`.

### `router.deploy`

Writes the rule set to the router as a dnsmasq include file and restarts
dnsmasq. The previous file is backed up locally first, so `router.rollback`
can restore it.

```json
{"deployed": true, "remote_path": "/etc/dnsmasq.d/toney.conf",
 "rules": 67, "skipped": 3, "bytes": 2048}
```

`skipped` counts the rules dnsmasq cannot express: KEEP rules and regular
expressions. The router is therefore always coarser than the service.

### `router.rollback`

Restores the last backed-up file on the router and restarts dnsmasq. When no
backup exists the generated file is removed instead.

```json
{"rolled_back": true, "restored": "~/.local/state/toney/router-backups/router-20260102-030405.conf", "removed": false}
```

## Errors

| Situation | `error` |
|---|---|
| Unknown command | `unknown command: <cmd>` |
| Missing/invalid params | `invalid params: <detail>` |
| Rule file unreadable | `rules: <exception message>` |
| Socket not writable | `socket: <exception message>` |
