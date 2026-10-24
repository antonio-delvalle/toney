# Architecture

## Two applications, one repository

Toney is split into two applications that are installed, run and upgraded
separately.

| | `dnsguard` | `toney` |
|---|---|---|
| Role | the filtering service | the terminal interface |
| Runs | headless, in the background | in a terminal, in front of a human |
| Depends on | the Python standard library | the Python standard library |
| Talks to | DNS clients, upstream resolvers | `dnsguard`, over a Unix socket |
| Knows about | rules, resolvers, logs | nothing about DNS internals |

`dnsguard` does not know that `toney` exists. `toney` never reads the
service's files, never touches its ports and never opens its process
directly except to start or stop it. Everything else goes through the
socket.

That split is what makes the pair usable on a router or a small always-on
box: the service has no UI dependency at all, so it can run headless under a
supervisor, and the UI can be run from a laptop over SSH without the service
knowing about it.

## The service

```
        DNS client
             |
             | UDP or TCP, port 53
             v
   +---------------------------+
   |  dnsguard                |
   |                           |
   |  1. parse the question   |
   |  2. match the rules      |----> KEEP rule?  -> forward upstream
   |  3. forward or refuse    |----> no match?   -> forward upstream
   |  4. write a log record   |----> block rule? -> NXDOMAIN
   +---------------------------+
             |
             v
      upstream resolver(s)
```

The rule match happens before anything is forwarded, so a blocked name never
leaves the machine. The answer to a blocked name is NXDOMAIN: the client is
told the name does not exist, and it stops asking.

Answers that are allowed through are relayed upstream unchanged, except that
the transaction id is rewritten to match the client's. That keeps the
service out of the business of re-serialising DNS records it does not need to
interpret.

### Data that flows through

- The **question** of every query: the name and the record type.
- The **source address** of the client.
- The **decision**: block, allow or cache.

Nothing else. The service does not see the request bodies, the URLs or the
payloads, and it cannot: it is a DNS resolver, not a proxy.

### The query log

One JSON object per line:

```json
{"client":"192.0.2.10","decision":"block","name":"ads.example.net.","rule":"||ads.example.net^","ts":"2026-01-02T03:04:05Z","type":"A"}
```

The log is written to one file per day. Files older than the retention
window are deleted; a file that grows past the size cap is compressed and
rolled over. The log is the measurement instrument, so it is also the thing
that must not grow without bound.

### Upstream resolvers

Plain DNS over UDP, with a TCP fallback when the answer does not fit in a
datagram. A DNS-over-HTTPS upstream (RFC 8484) is supported as an
alternative. Upstreams are tried in order, and answers are cached in memory
for a short time.

## The interface

```
        toney
          |
          | Unix socket, newline-delimited JSON
          v
   +---------------------------+
   |  dnsguard control server  |
   +---------------------------+
```

The protocol is one JSON object per line in each direction. The full
command list is in [`CONTROL_PROTOCOL.md`](CONTROL_PROTOCOL.md).

The commands fall into three groups:

- **Observation** - `status`, `stats`, `logs.tail`, `rules.list`,
  `config.get`.
- **Change** - `rules.reload`, `rules.set`, `config.set`, `upstream.set`.
- **Lifecycle** - `shutdown`.

The TUI supervises the service process as well: it starts it, stops it,
restarts it and reattaches to it. The socket commands cover everything the
service can do to itself.

### Why a socket and not a file

A file of configuration is a one-way street: the TUI would write it and then
have to guess whether the service had noticed. A socket is a conversation:
the service answers with the state it actually holds, so the interface never
shows a stale value, and every failure has a message that can be put on
screen.

## Design rules

1. **Never break the device.** Blocking is a decision with a cost. Every
   profile ships KEEP rules, and the service answers "allow" whenever it is
   not certain.
2. **Measure before you block.** The log exists so that rule sets are built
   from observed traffic rather than from guesses.
3. **No dependencies.** Both applications run on a bare Python install. A
   filtering service that needs a package index at deploy time is one
   package index failure away from not filtering anything.
4. **Nothing leaves the machine.** No accounts, no update checks, no
   telemetry. The only network traffic is DNS, in both directions.
