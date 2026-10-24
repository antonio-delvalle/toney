# dnsguard

The filtering service behind Toney. It answers DNS queries, blocks the names
you list, forwards the rest, and writes a query log that expires on its own.

Standard library only. Python 3.10 or newer.

## Install

```bash
python3 -m pip install -e .
```

## Run

```bash
dnsguard serve \
  --listen 0.0.0.0:5353 \
  --upstream 192.0.2.53 \
  --rules ../../profiles/samsung-tv-telemetry.blocklist
```

`--config` points at a JSON configuration file; every command accepts it
before or after the subcommand.

```bash
dnsguard serve --config ~/.config/toney/dnsguard.json
```

### Configuration

```json
{
  "listen": "0.0.0.0:5353",
  "upstream": ["192.0.2.53"],
  "doh": null,
  "timeout_s": 4.0,
  "cache_size": 4096,
  "cache_ttl_s": 300,
  "log_dir": "~/.local/state/toney/dnsguard",
  "retention_days": 5,
  "log_max_bytes": 67108864,
  "rules": ["profiles/samsung-tv-telemetry.blocklist"],
  "control": "~/.local/state/toney/dnsguard.sock"
}
```

| Setting | Meaning |
|---|---|
| `listen` | address and port to answer on |
| `upstream` | resolvers to forward to, in order |
| `doh` | DNS-over-HTTPS endpoint (RFC 8484), used instead of `upstream` when set |
| `log_dir` | where the query log is written |
| `retention_days` | how many days of log files to keep |
| `log_max_bytes` | size at which a daily file is compressed and rolled over |
| `rules` | rule files to load |
| `control` | path of the control socket |

## Other commands

```bash
dnsguard config                  # print the effective configuration
dnsguard rules                   # print the loaded rules
dnsguard logs --limit 50         # print recent query log records
dnsguard sweep                   # delete log files outside the retention window
dnsguard version
```

## Control socket

The service listens on a Unix socket and speaks newline-delimited JSON, one
object per line. That is how `toney` manages it. The commands are documented
in [`../../docs/CONTROL_PROTOCOL.md`](../../docs/CONTROL_PROTOCOL.md).

```bash
python3 - <<'EOF'
import json, socket
s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
s.connect("~/.local/state/toney/dnsguard.sock")
s.sendall(b'{"id":1,"cmd":"status","params":{}}\n')
print(s.recv(65536).decode())
EOF
```

## Ports

Port 53 needs privileges on most systems. Options:

- Run on port 5353 and have the router forward to it.
- On Linux, grant the capability: `setcap 'cap_net_bind_service=+ep' $(which dnsguard)`.
- On macOS, binding `0.0.0.0:53` is allowed for the default resolver port;
  run it as a user with the right entitlements.

## Router deployment (optional)

`dnsguard` can push the rule set to a router that runs dnsmasq, so the
filter keeps working when the machine running the service is off. It is a
second enforcement point, not a replacement: dnsmasq cannot express a KEEP
exception or a regular expression, so the rule set on the router is always
coarser.

Configure the router in the JSON configuration:

```json
{
  "router": {
    "host": "192.0.2.1",
    "port": 22,
    "user": "root",
    "remote_dir": "/etc/dnsmasq.d",
    "remote_file": "toney.conf",
    "service": "dnsmasq",
    "sudo": false,
    "ssh_key": "~/.ssh/id_ed25519"
  }
}
```

Then:

```bash
dnsguard router status     # is the file installed, does it match
dnsguard router deploy     # write the rules and restart dnsmasq
dnsguard router rollback   # restore the previous file and restart
```

The driver uses the SSH key or agent the machine already has, so no
credential is stored anywhere. The file it writes is a plain dnsmasq
include:

```
address=/ads.example.net/0.0.0.0
```

The previous file is backed up locally before every deployment, which is what
makes `rollback` possible.

## Tests

```bash
python3 -m unittest discover -s tests
```
