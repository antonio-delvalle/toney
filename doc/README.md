# Documentation

| Document | What it covers |
|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | how the two applications fit together, and why they are split this way |
| [CONTROL_PROTOCOL.md](CONTROL_PROTOCOL.md) | the socket protocol between `dnsguard` and `toney` |
| [RUNNING.md](RUNNING.md) | installing, configuring and running the two applications, and checking that the filtering works |
| [DOC_REVIEW.md](DOC_REVIEW.md) | a review of this documentation and the protocol, with the findings still open |
| [investigation/](investigation/) | the measurements and reverse engineering Toney was built on |

## The investigation archive

[`investigation/`](investigation/) holds the work that came before the code:
the smart TV's control surface, the GPON router's proprietary admin API, the
telemetry strategy with its measured inventory, the device-side privacy
switches, and the catalogue of every artefact that was built.

It is kept in the repository because a filtering tool that nobody can check
is a belief, and because the negative results are the expensive part of the
work. The short version is in
[investigation/README.md](investigation/README.md): how the work was done,
and the three findings that shaped the design.

Everything in the archive is sanitised — addresses, serials, MACs and tokens
are replaced with documentation-range values — and a CI check keeps it that
way.
