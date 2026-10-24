# Review of the documentation archive

**Date:** 2026-10-24
**Scope:** `doc/ARCHITECTURE.md`, `doc/CONTROL_PROTOCOL.md`, `doc/investigation/*`
**Method:** every document was read in full and cross-checked against three
things — the code in `packages/`, the machine's live state, and the
`scripts/check_no_pii.py` guard.

This is a review, not a change. Nothing here has been applied.

## Verdict

The archive is genuinely good, and the thing that makes it good is the part
most projects throw away: the **negative results**. §12 "the TV's DNS did not
change", §12.2 "the router cannot be chained to the Mac filter", §6 "what is
not available on this firmware", and `ubus_client.py` documented as "does not
work on this firmware — kept so nobody repeats the attempt". Those cost real
time to establish and cost nothing to keep.

One factual error and one stale section need fixing. The rest is polish.

---

## Findings, in priority order

### 1. Factual error — port 53 does not require sudo

`telemetry-strategy.md:87`, in the §2 options table:

> **Requires sudo** — macOS `mDNSResponder` already owns `0.0.0.0:53`, and
> binding port 53 unprivileged returns `Permission denied`

This is contradicted by the live deployment on the same machine. The filter
process runs as an ordinary user, holds `UDP *:53`, and `mDNSResponder` is
running at the same time:

```
USER      PID COMMAND
<user>   6683 .../dnsfilter.py --listen 0.0.0.0:53 ...
mDNSResponder  481
python3.1 6683 <user>  4u  IPv4  *:53   (UDP)
```

The same table's verdict for option C is obsolete for the same reason:

> use for measurement only… the Mac sleeps… directly violates the "don't break
> the device" constraint

§9.2 and §10.4 later turned the Mac-hosted filter into the *permanent*
solution, on the strength of the port-53 binding that §2 says is impossible.
§2 was written before that finding and never revisited.

**Proposed fix.** Replace the §2 option C row with what was actually observed,
and mark the verdict as superseded:

```diff
-| Port 53 | **Requires sudo** — macOS `mDNSResponder` already owns `0.0.0.0:53`, and binding port 53 unprivileged returns `Permission denied` |
+| Port 53 | Works unprivileged — the filter binds `0.0.0.0:53` as a normal user while `mDNSResponder` runs alongside it. It may fail with `Address already in use` if something else already holds the port. |
```

and in the same table, note that option C was later adopted as the standing
architecture (§9.2) rather than dismissed.

### 2. §3 contradicts §9.2 and does not forward-reference the reversal

`## 3. Recommended architecture` (line 145) recommends **DNS filtering on the
OpenWrt router**, with a `TV → OpenWrt dnsmasq` diagram. §9.2 (line 439)
states that design "is not reachable on this firmware" and gives the opposite:

```
TV ──DNS──> <mac>  (Mac filter, launchd + caffeinate)
```

§9.2 is labelled "Final architecture (corrected)", but §3 — the section
literally titled *Recommended* — carries no pointer forward. A reader who stops
at §3, or who arrives from the table of contents, gets the wrong answer.

**Proposed fix.** Add immediately under the §3 heading:

```markdown
> **Superseded by §9.2.** The router-as-resolver design sketched below is not
> reachable on this firmware: the router's dnsmasq will not forward to a
> LAN-hosted resolver (§12.2). What is actually deployed is in §9.2.
```

### 3. Three different rule counts are in circulation

| Where | Claim | Status |
|---|---|---|
| `telemetry-strategy.md:151,211` | 59 block / 29 KEEP | stale by 11 |
| `telemetry-strategy.md:451,616`, `device-privacy-checklist.md:170` | 67 rules / 33 KEEP | stale by 3 |
| `artifacts.md:100`, `profiles/README.md:28` | 70 block / 33 KEEP | **correct** |

The shipped profile `profiles/samsung-tv-telemetry.blocklist` contains 70 block
rules and 33 KEEP rules — 103 lines. It is byte-identical to the live
`blocklists/samsung-tv-privacy.blocklist` used by the prototype.

Line 211 additionally mixes a total with a sub-count in one cell — "59 block
rules, 3 regex, 29 KEEP exceptions" — so the arithmetic is ambiguous even in
place.

**Proposed fix.** Standardise on 70 / 33 and mark the earlier figures as
historical. For the §3 and §5 occurrences, a parenthetical is enough:
"59 block rules *(as of the first measurement pass; the profile now has 70)*".
For §11 and §12, correct the number and add the total.

### 4. `tv-recon.md` gives the target device two different MACs

| Line | Value |
|---|---|
| 7 | `00:11:22:33:44:55` — the target, with the vendor attribution |
| 19 | `00:11:22:33:44:5` **6** — the topology table |
| 27, 50 | `00:11:22:33:44:55` — the AirPlay `deviceid` and `wifiMac` |

This mirrors an inconsistency in the source notes, where the header and the
topology table carried slightly different values for the same interface. The
sanitiser mapped them to adjacent values rather than collapsing them, so a
reader cannot tell which one is the device's real MAC.

**Proposed fix.** Pick one value — the one already used on lines 7, 27 and 50 —
and use it on line 19 as well.

### 5. The CI guard skips whole lines, which is a real hole

The commit message for the archive claims:

> the CI no-personal-data check covers the archive, so it cannot leak again

Coverage is real, but note that `scripts/check_no_pii.py` **was not modified** —
`os.walk(ROOT)` already covered whatever directory the docs lived in. The claim
describes a property of the script, not a change to it.

The problem is `looks_like_placeholder()`. When a line contains any of
`example`, `placeholder`, `yourname`, `username`, `xxxx` or `192.0.2`, **the
entire line is skipped** before any pattern is applied. Verified:

```
For example the TV at <private-address> talks to <mac>
-> problems found: []
```

A future line that pairs a real address with the word "example" therefore ships
silently. The archive's own prose uses "for example" heavily, so this is a live
hazard rather than a theoretical one.

**Proposed fix.** Make the placeholder check apply per-match rather than
per-line — skip a pattern hit only if the *matched value itself* looks like a
placeholder, not the whole line.

### 6. `ALLOWED_MACS` is narrower than the documents it polices

`check_no_pii.py` allows exactly two MACs:

```python
ALLOWED_MACS = ("00:11:22:33:44:55", "02:00:00:00:00:01")
```

But `doc/` uses the whole `00:11:22:33:44:5x` series — `:55` through `:5b`.
The `:56` to `:5b` values are **not** in the allow list. They pass today only
because each happens to sit on a line that also contains `192.0.2`, which trips
the line-level placeholder skip.

Verified — move one to a line without that token and CI fails:

```
mactest.txt:1 hardware address <the :56 variant>
```

So reformatting the topology table, or splitting the MAC onto its own line,
would break CI spuriously.

**Proposed fix.** Extend the allow list to the full range the archive uses, and
fix finding 4 at the same time so only one MAC is in play:

```python
ALLOWED_MACS = tuple(
    "00:11:22:33:44:%02x" % octet for octet in range(0x55, 0x5C)
) + ("02:00:00:00:00:01",)
```

### 7. One identifier survives the scrub

`Telmex` is gone, `PRV33AC22` is gone, and the MACs, serials, DUID and
addresses are all replaced with documentation-range values. But the router
vendor name **"Arcadyan"** remains in three files, alongside `OpenWrt`, `LuCI`
and `GPON`.

This is a judgement call rather than an error — a vendor name is not personal
data and does not pinpoint a household. But it is the last string that narrows
the router to one model family, so if the intent was "the provider is not
identifiable from the repository", it is not quite there yet.

**Decision needed:** either scrub it, or state the intent explicitly in
`doc/investigation/README.md` so a future reader does not have to guess.

### 8. A cited script does not exist

`telemetry-strategy.md:637`:

```
`python3 tv_dns_report.py` / `node tv_conns.js`.
```

There is no `tv_dns_report.py` — not in the repository and not in the working
directory that holds the prototype scripts. The real scripts are `dnsfilter.py`,
`leak_check.py`, `telmex_login.py`, `tv_netinfo.py`, `tvctl.py`,
`ubus_client.py`, `watch_sdb.py` and `watch_tv.py`.

The reporting capability the line is pointing at does exist, as a flag on
`dnsfilter.py`:

```
python3 dnsfilter.py --report dnslog.jsonl
```

which is also how `device-privacy-checklist.md` correctly invokes it.

**Proposed fix.** Point the line at the two commands that exist:

```
`python3 dnsfilter.py --report tv-dns.log` / `python3 leak_check.py`.
```

### 9. Stale paths and an implicit file inventory

Lines 342 and 507 refer to `~/Projects/samsung-tv/`. The working directory has
moved to `~/.minimax/workspace/samsung-tv/`.

Separately, `telemetry-strategy.md` cites scripts and
`blocklists/samsung-tv-privacy.blocklist` as bare filenames. Only
`device-privacy-checklist.md` exists in the repository; the scripts live in the
working directory. `artifacts.md` states this explicitly — "the scripts
themselves were kept in the working directory that still runs the filter" — but
that disclaimer does not carry into the strategy document, so the §5 table
reads like an inventory of the repository.

**Proposed fix.** Correct the two paths, and add one line near the top of
`telemetry-strategy.md` pointing at `artifacts.md` for the script locations.

### 10. Control-protocol drift

Not introduced by the archive commit, but now more visible because the archive
is presented as the reference. All four are in `CONTROL_PROTOCOL.md`:

| Doc says | Code does |
|---|---|
| `config.set` "Returns the new effective configuration" | returns `{"changed": [...], "config": {...}}` |
| `status.rules` has `count`, `loaded_at`, `sources` | also emits `block` and `allow` |
| `config.get` masks "any secret-bearing fields" with `***` | the config holds no secrets, so nothing is ever masked |
| — | `status.rules.loaded_at` is the **service start time**, not the rule load time |

The last one is a genuine bug, not just documentation: `service.py:168` uses
`_iso(self.started_at)`, so `loaded_at` is wrong for the whole life of the
process and never changes after a `rules.reload`. `reload_rules()` already
computes the value correctly, so the fix is to keep that timestamp on the rule
set and report it.

**Proposed fix.** Correct the three doc entries, and fix the `loaded_at`
source in `service.py`.

---

## What is working well

Worth stating explicitly, because it is easy to lose when the tone of a review
turns critical:

- **The negative results are preserved.** §12, §12.2, §6 and the `ubus_client.py`
  note all record what was tried and failed. This is the highest-value part of
  the archive.
- **The leak check is treated as a first-class method.** §11's "LEAKED: NONE"
  result — resolving blocked names and intersecting them with the device's live
  NAT endpoints — is a much stronger claim than "the blocklist is applied".
- **§10.3 corrects earlier conclusions explicitly** rather than quietly
  rewriting them, including the app-inventory mistake.
- **§13 explains a negative outcome** (why Brave's method cannot be reproduced
  at the DNS layer) instead of leaving it as an unexplained gap.
- **The profiles carry explicit KEEP rules**, and `ALLOW` is evaluated before
  `BLOCK`, so a KEEP always wins. That is the "don't break the device" rule
  encoded into the data rather than into a comment.

## Open question: the prototype and the product overlap

Not a documentation defect, but it belongs in the handoff.

The live filtering is done by the prototype — `dnsfilter.py`, launched by a
launchd agent, serving `:53` with the 70 / 33 profile. `dnsguard` reimplements
the same job with a query log, a control socket, rule hot-reload and the TUI,
but is not what is filtering traffic right now.

If Toney is meant to replace the prototype, the remaining work is the
migration, and no document mentions it:

1. Point the launchd agent at `dnsguard` instead of `dnsfilter.py`.
2. Move the filter's `listen` to whatever port `dnsguard` will own, and decide
   whether it takes `:53` directly or sits behind dnsmasq.
3. Confirm the rule set that `dnsguard` loads is the same 70 / 33 profile, and
   that `rules.set` writes somewhere the service actually reads.
4. Keep the query-log format compatible with `leak_check.py` and the other
   measurement scripts, or update those scripts.
5. Decide what happens to the `caffeinate` wrapper and the keep-awake duty.

That is a small list, but it is the gap between "the tool exists" and "the tool
is running", and it is currently unwritten.
