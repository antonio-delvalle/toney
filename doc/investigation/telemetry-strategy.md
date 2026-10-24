# Investigation — smart TV telemetry, strategy and measurements

> Part of the [Toney](../README.md) investigation archive. Every address,
> serial, MAC and identifier in this document has been replaced with a
> documentation-range value; the technical findings are unchanged.

**Device:** `<model>` — 43" Crystal UHD, Tizen 9.0 (`23_KSUE_UB_T09`), fw `377.40.00`, <region>, serial `<serial-redacted>`, IP `192.0.2.64`, wired.
**Network:** `192.0.2.0/24`, gateway `192.0.2.254` = ISP GPON IAD (Arcadyan <router-model>) running **OpenWrt** with dnsmasq + LuCI.
**Constraint:** the set must keep working normally — firmware updates, app store, streaming, TV Plus, tuner, HDMI sources, voice (if used).

---

## 1. What is actually being sent, and by which channel

A Samsung Tizen TV has **five** outbound telemetry channels. They are
independent, so any single measure leaves gaps.

| # | Channel | What leaks | Transport | Killable by UI? | Killable by DNS? |
|---|---|---|---|---|---|
| 1 | **ACR** (Automatic Content Recognition) | On-screen + audio fingerprint → viewing history | `samsungacr.com`, `acr-<cc>-prd.samsungcloud.tv`, `musicid.samsungcloudsolution.com` | ✅ "Viewing Information Services" | ✅ |
| 2 | **Diagnostic logs / error dumps** | Device logs, crash reports, usage journals | `devicelog.samsungcloudsolution.net`, `prderrordump*.{com,net}`, `sas.*` | ✅ Contact Samsung → Logs | ✅ |
| 3 | **Ad / behaviour profiling** | Impressions, RTB requests, interest profile | `samsungads.com`, `samsungadhub.com`, `adgrx.com`, `samsungrs.com`, `samsungnyc.com` | ⚠️ partial (Personalised Advertising) | ✅ |
| 4 | **TV Plus session + QoE** | Channel/viewing sessions, playback QoE | `tvpnlog*.samsungcloud.tv`, `qoe.samsungcloud.tv` | ❌ built into firmware | ✅ (logs only) |
| 5 | **Account-linked identity** | History, recommendations, cross-device profile, voice transcripts | `auth.samsungosp.com`, `account.samsung.com`, voice services | ✅ sign out | ⚠️ only by blocking auth (breaks account) |
| 6 | **Third-party in-app SDKs** | Prime Video / Netflix / analytics beacons | `unagi*.amazon.com`, `*.netflix.com`, `newrelic` | ❌ inside the apps | ✅ |

**Voice deserves its own line.** Samsung's voice stack records on-device,
sends the audio for server-side ASR, and stores the transcript against the
account. The DNS layer can only partially blunt it (the voice endpoints are
shared with wake-word and account features). **The only guaranteed way to stop
audio leaving the house is the device switch** — `Settings → General → Voice
Recognition → Voice Assistant: Off`. A blocked DNS name causes a retry loop,
not a dead microphone.

---

## 2. Strategy options evaluated

### A. Device-native privacy switches only
**Tools:** none — the TV's own UI.
**How:** `device-privacy-checklist.md`.

| | |
|---|---|
| Breaks functionality | **No** — this is the sanctioned path |
| Blocks ACR | Yes, if the switch is found and the account is signed out |
| Blocks logs | Yes |
| Blocks ads | Partly |
| Blocks voice | **Yes — completely, if you turn voice off** |
| Blocks in-app SDK beacons | **No** |
| Stops the *capability* remaining on the device | No — the collectors stay installed |
| Verifiable by me | **No** — Tizen has no screenshot API and no REST endpoint that exposes consent state |

**Verdict: necessary, not sufficient.** Do it, but do not treat it as the whole
defence. Two reasons it cannot be the whole defence: (a) the UI switches change
*consent*, not *code* — the collectors remain armed and Samsung can re-consent
via an account-side update; (b) I cannot read the switch states back over the
API, so I cannot verify you flipped the right one.

### B. DNS filtering on the OpenWrt router  ← **recommended**
**Tools:** dnsmasq `address=/domain/0.0.0.0` (already installed), or AdGuard Home
for a nicer UI, or the script in `deploy_openwrt.sh`.

| | |
|---|---|
| Breaks functionality | **No** if the KEEP list is respected |
| Breaks functionality if done wrong | Yes — blocking `time.samsungcloudsolution.com` breaks Plex/YouTube/Amazon playback; blocking `otnprd*` breaks firmware updates; blocking `osb-ussvc.samsungqbe.com` kills TV Plus |
| Breaks ACR / logs / ads / TV Plus beacons | Yes, all of them |
| Breaks third-party SDK beacons | Yes |
| Breaks voice | Partly — stops the *upload* path for telemetry, not the microphone |
| Touches the TV | **No — zero TV-side change** |
| Always on | **Yes** — the router never sleeps |
| Verifiable by me | **Yes** — dnsmasq's query log shows every name the set resolves |
| Rollback | One command |

**Verdict: best layer.** It is the only one that is always-on, requires no
device change, works for every client, and — critically — **produces the
measurement** that tells you what this particular set actually talks to,
instead of trusting a generic list.

### C. DNS filtering on the Mac
**Tools:** `dnsfilter.py` (this repo, stdlib + dnslib).

| | |
|---|---|
| Breaks functionality | No, but see below |
| Port 53 | **Requires sudo** — macOS `mDNSResponder` already owns `0.0.0.0:53`, and binding port 53 unprivileged returns `Permission denied` |
| Always on | **No — the Mac sleeps.** If the Mac sleeps while the TV is pointed at it, the TV loses DNS entirely and the UI starts erroring. This directly violates the "don't break the device" constraint |
| Verifiable by me | Yes — this is its main strength |
| Best use | A **temporary measurement window**, not the permanent filter |

**Verdict: use for measurement only.** Point the TV's DNS at `192.0.2.69`
for 10 minutes, capture exactly what it resolves, revert the TV to Automatic
DNS. That gives an evidence-based blocklist for this specific set and
firmware, instead of a generic one.

### D. Public hosted resolver
**Tools:** AdGuard public DNS `94.140.14.14` / `94.140.15.15`, NextDNS.

| | |
|---|---|
| Setup | One field on the TV: DNS Server = `94.140.14.14` |
| Local infrastructure | None |
| Custom blocklist | **No** — public AdGuard DNS has a fixed policy you cannot edit; NextDNS needs an account to host a custom profile |
| Measurement | **No** — you cannot see what your TV asked for |
| Trust | Your queries go to a third party instead of your ISP |
| Availability | If AdGuard is down, the TV has no DNS |

**Verdict: acceptable stopgap, poor end state.** It is the only zero-
infrastructure option, and it works, but you lose visibility and control, and
you are trusting someone else's filtering decisions. NextDNS with a custom
profile is the better version of this — free, supports per-device profiles
and a real query log, and accepts the same blocklist file.

### E. Envelope / deep inspection (MITM)
**Tools:** mitmproxy, a transparent proxy, ARP spoofing the gateway.

| | |
|---|---|
| Visibility | Best possible — every request, not just hostnames |
| Breaks functionality | **Very likely** — TLS interception breaks DRM (Widevine/PlayReady), app authentication and firmware signatures |
| Detectable | Yes — the TV would see a foreign CA |
| Complexity | High |

**Verdict: rejected.** It breaks streaming and app auth, and Samsung's DRM
stack will refuse to play. It also conflicts with the "do not interfere with
proper working" constraint. Hostname-level filtering captures ~95% of the
value at ~0% of the risk.

### F. Root-level on the TV (SDB)
**Tools:** Tizen Studio `sdb`.

| | |
|---|---|
| Capability | Read/replace native bundles, install unsigned `.tpk`, run arbitrary shell |
| Usefulness for *this* task | **Low** — it changes the software, it does not stop the software phoning home. You would be rewriting Samsung's ACR client instead of disabling it |
| Cost | Developer Mode on the TV, 1–2 GB toolchain, and you declined it |

**Verdict: rejected for this objective.** Root is the right tool for
*customising* the TV. For *silencing telemetry*, DNS + consent switches are
both cheaper and more complete.

---

## 3. Recommended architecture

```
                       ┌─────────────────────────────────────────┐
   TV ──── DNS ───────►│  OpenWrt 192.0.2.254                 │
   (no TV change)      │   dnsmasq                             │
                       │    • 59 telemetry rules → 0.0.0.0      │
   all other clients ─►│    • 29 KEEP exceptions                │
                       │    • query log = measurement           │
                       └─────────────────────────────────────────┘

   Plus, on the device itself:
     • Samsung account signed out (or Sync + Smart Login off)
     • Privacy Choices: ACR / ads / help-us / voice services OFF
     • Voice Recognition: OFF (if you don't use it)
     • Contact Samsung → Logs: uncheck Enable
```

**Why the router and not the Mac:** the Mac sleeps. Pointing the TV's DNS at a
laptop is the classic way to end up with a TV that loses its internet at 2am.
The router is always up, needs no TV-side change, and turns DNS into a
network-wide policy rather than a per-device hack.

**Why NXDOMAIN and not 0.0.0.0:** a blocked telemetry host that resolves to
`0.0.0.0` causes a *connection timeout* on the TV, which can stall the UI
thread for seconds. NXDOMAIN fails instantly, so a blocked collector is
simply "not found" and the TV moves on. `dnsfilter.py` returns NXDOMAIN;
dnsmasq's `address=` returns `0.0.0.0`, so on the router the better choice is
AdGuard Home (NXDOMAIN by default) or `dnsmasq` with `address=/domain/`.

---

## 4. Blocklist design — the part that actually decides success

The failure mode of this whole exercise is blocking too much. From community
reports, these are the specific breakages:

| If you block | You break |
|---|---|
| `time.samsungcloudsolution.com` / `.net` | **Plex, YouTube and Amazon Video playback** (they use it as a time source) |
| `cdn.samsungcloudsolution.com` | System update check on some models |
| `otnprd8-11.samsungcloudsolution.net` | **Firmware/OTA update delivery** |
| `lcprd1/2.samsungcloudsolution.net`, `configprd.*` | Tizen Store / login |
| `osb-ussvc.samsungqbe.com`, `gpm.samsungqbe.com` | **TV Plus** — the free channels vanish |
| `auth.samsungosp.com`, `sc-auth.*`, `eu-auth2.*` | **Samsung account login breaks entirely** |
| `api/hub/iap/img.samsungapps.com` | Tizen Store breaks |
| `www.samsungrm.net` | Remote management |
| `tvpnlinupepg{peu,pus}.samsungcloud.tv` | TV Plus EPG/guide data |
| `samsungcloud.com` | TV Plus session service |
| The whole `samsungcloudsolution.net` zone | Log collection — but also time and firmware |

Hence the rule this repo follows: **block per-host for telemetry, never per-zone
for shared infrastructure.** Every exception is written as an ABP exception
rule (`@@||domain^`) in `blocklists/samsung-tv-privacy.blocklist`, so the same
file is correct in AdGuard Home, Pi-hole, NextDNS *and* `dnsfilter.py` — and
exception rules outrank block rules in all of them.

The list is deliberately conservative. Where a host might serve a real TV
function, it stays allowed.

---

## 5. What is implemented and verified here

| Artifact | Status |
|---|---|
| `blocklists/samsung-tv-privacy.blocklist` | 59 block rules, 3 regex, **29 KEEP exceptions**, Samsung-only + app-SDK telemetry |
| `dnsfilter.py` | **Verified working.** Blocks → NXDOMAIN; functional hosts → resolve. Handles UDP+TCP, client-IP logging, cache, report mode |
| `deploy_openwrt.sh` | Rule generation **dry-run verified** (59 rules, no KEEP leakage). Needs a root shell on the router |
| `device-privacy-checklist.md` | Device-native switches, exact paths |
| `tvctl.py` | Already proven against this set |

Blocklist verification (live, against the running filter):

```
BLOCKED  log-1.samsungacr.com             NXDOMAIN
BLOCKED  acr-mx-prd.samsungcloud.tv       NXDOMAIN
BLOCKED  musicid.samsungcloudsolution.com NXDOMAIN
BLOCKED  tvpnlogosus.samsungcloud.tv      NXDOMAIN
BLOCKED  devicelog.samsungcloudsolution.net NXDOMAIN
BLOCKED  samsungads.com                   NXDOMAIN

ALLOWED  time.samsungcloudsolution.com    NOERROR  13.65.228.237
ALLOWED  cdn.samsungcloudsolution.com     NOERROR  189.247.174.168
ALLOWED  otnprd8.samsungcloudsolution.net NOERROR  52.171.195.236
ALLOWED  osb-ussvc.samsungqbe.com         NOERROR  13.184.43.14
ALLOWED  account.samsung.com              NOERROR  13.226.187.72
ALLOWED  api.samsungapps.com              NOERROR  63.34.102.83
ALLOWED  tvpnlinupepgpeu.samsungcloud.tv  NOERROR  13.226.204.36
```

---

## 6. Rollout and rollback

**Rollout**
1. Device switches (`device-privacy-checklist.md`) — safe, reversible, no infra
2. Router filter — `deploy_openwrt.sh` over ssh, or AdGuard Home's UI
3. Verify: `logread -e dnsmasq | grep 192.0.2.64`

**Rollback**
- Router: `sh /tmp/deploy_openwrt.sh rollback` — restores the backed-up
  `dnsmasq.conf` and restarts dnsmasq
- Device switches: every one of them is a toggle you can flip back
- There is no state on the TV that the filter alters, so removing the filter
  restores the pre-filter behaviour exactly

**Kill switch (if a block causes a real problem):** remove that one
`address=/domain/0.0.0.0` line and `service dnsmasq restart`. Nothing else is
touched. Keep the blocklist in version control so you can see exactly what
changed.

---

## 7. Known limits — stated plainly

1. **DNS filtering is hostname-level.** If Samsung moves a collector to a
   shared CDN hostname, it gets through. The query log is how you detect that,
   which is why logging is enabled.
2. **Encrypted DNS.** If the TV is configured for DoH/DoT it bypasses plain
   DNS entirely. Tizen does not expose DoH by default, but confirm in
   `General → Network`. If it is on, turn it off; otherwise the whole filter
   is bypassed.
3. **The MAC address and the fact the set exists** still leave the house —
   DHCP, ARP, the Samsung account login. DNS filtering does not address
   that; signing out of the account addresses most of it.
4. **A 2023-era Tizen set is no longer receiving security updates.** If
   firmware support has ended for this model, the device-side attack surface
   is permanently open, and that argues for keeping it off the internet
   entirely when not in use — a firewall rule or a smart-plug schedule.
   Check the model's support status before deciding.
5. **I cannot read the TV's consent state back over the API**, so the device
   switches cannot be machine-verified. The DNS log verifies the *effect* of
   the switches, which is the part that matters.

---

## 8. What is ACTUALLY deployed right now (measured, not assumed)

**The router turned out to be fully drivable programmatically** — no root, no
SSH, no Scheduled Tasks needed. See `tv-recon.md` §Router API for the protocol.
That changed the plan: the enforcement layer moved from "please run this
command on the router" to **the router's own native DNS-block feature,
configured remotely**.

### 8.1 Router admin access (new capability)

| Fact | Value |
|---|---|
| Login | `POST /login.cgi` with `usr`/`pws` = `SHA512(MD5_HEX(x))` + `httoken` |
| `httoken` | 9-digit value embedded in each page's `data:` image, `src[78:]` base64-decoded |
| Session | `SID` cookie |
| Config write | `POST /apply_abstract.cgi`, `action` = per-page command (`ui_dns`, `ui_lan`, `ui_firewall`, …) |
| Payload | every field as `DCBA` = `AES-256-CBC(key = page httoken, IV = 0)` of `"<numeric-config-id>=<value>"` |
| Config schema | `GET /cgi/cgi_<page>.js?_tn=<token>` → `addCfg("logical_name", "<numeric_id>", "<current>")` |

The numeric id is the key detail: the page's own form uses logical names, but
the CGI stores by id. Writing logical names silently stores nothing.

### 8.2 Native DNS-block feature, with measured limits

Router UI: **Network → DNS → DNS Host**. Each entry becomes a dnsmasq rule
that answers the hostname with `0.0.0.0`. Measured behaviour on this
firmware (Arcadyan <router-model>, ISP GPON, fw 1.33.007.0038):

| Constraint | Value | How it was measured |
|---|---|---|
| Max entries | **10** | slots 10/20/49 are stored in the config store but never reach dnsmasq |
| Max hostname length | **31 chars** | 31-char names block; 32-char names are stored but ignored |
| Subdomain coverage | **none** — exact hostname only | `example.com` blocked ⇒ `www.example.com` still resolves |
| Block response | `0.0.0.0` (not NXDOMAIN) | client fails fast; no retry loop |
| Write action | `action=ui_dns` | other action names store values but never apply them |

Two traps worth recording: (1) an out-of-range id in the same POST **aborts
the whole apply** — slots 0-9 plus a made-up slot 10 left every entry
unapplied; (2) a rule is only effective if its hostname is ≤ 31 chars, which
silently excludes most of the diagnostic-upload hosts
(`prderrordumphsm.samsungcloudsolution.com` is 40 chars).

### 8.3 The 10 native rules now live on the router

```
acr-mx-prd.samsungcloud.tv        ACR - viewing history (one region of the vendor's footprint)
acr0.samsungcloudsolution.com     ACR - viewing history
samsungads.com                    Samsung ad server
samsungads.adsmeasurement.com     ad measurement / attribution
samsungtvads.com                  Samsung TV ad server
tvx.adgrx.com                     ad exchange (OpenX)
dc.di.atlas.samsung.com           data collection / analytics
adconsent.samsungrs.com           ad consent + profiling
qoe.samsungcloud.tv               TV Plus QoE / session tracking
unagi-na.amazon.com               Amazon device telemetry (Prime Video)
```

All 10 answer `0.0.0.0`; all 20 KEEP hosts still resolve. Verify with:

```bash
cd ~/Projects/samsung-tv
ROUTER_PASS='<router password>' node router_dns_rules.js verify
```

Rollback — clears every entry, restoring the router's stock DNS behaviour:

```bash
ROUTER_PASS='<router password>' node router_dns_rules.js rollback
```

### 8.4 What the native 10 do NOT cover

The curated list has 60 rules. The other 50 are not reachable through the
router's native feature because of the limits in §8.2:

- **>31 chars**: every diagnostic-upload host
  (`prderrordumphsm.samsungcloudsolution.com`,
  `devicelog.samsungcloudsolution.net`, `prderrordumpssm.samsungcloudsolution.net`).
- **Subdomain families**: `acr-{au,br,ca,eu,in,kr,nz,us}-prd.samsungcloud.tv`
  (8 more ACR regions — only the `mx` one is blocked),
  `tvpnlog{opus,opeu,osus,odus}.samsungcloud.tv` and
  `tvpndynamiclog*.samsungcloud.tv` (8 TV Plus viewing-log hosts).
- **>10 distinct parents**: `samsungcloudsolution.com` cannot be blocked as a
  parent because `time.*` and `cdn.*` under it are required for playback and
  clock sync; `samsungcloud.tv` cannot be blocked because
  `tvpnlinupepgp*` under it carries the TV Plus EPG.

### 8.5 The one remaining lever: point the router's upstream at the Mac

`lan_dns_mode0=2` + `lan_dns_svr0` sets the **upstream resolver the router's
own dnsmasq uses** — verified by pointing it at a dead IP and watching every
name stop resolving while the native blocks kept applying. `lan_dns_svr_2nd0`
is the secondary.

That gives a complete design:

```
TV ──DNS──> router dnsmasq (192.0.2.254)
             ├─ native address= rules: the 10 above, always on, no dependency
             └─ upstream ──> Mac filter (192.0.2.69): full 60-rule list + query log
                             secondary ──> ISP DNS, so the TV still works if the Mac sleeps
```

The clients keep using the router as their resolver, so nothing on the TV or
on the other LAN devices changes. If the Mac is asleep, dnsmasq falls back to
the ISP resolver and the TV keeps working — it just falls back to the 10
native rules instead of 60.

**Open trade-off, needs a decision:** this makes every LAN device's DNS
traffic pass through the Mac while it is awake, and the Mac's own blocklist
applies to the whole house (not just the TV). It also needs the Mac awake
for full coverage. See the rollout options in §9.

---

## 9. The finding that changes everything: the TV does not use the router's DNS

The router's NAT session table (`cgi/cgi_nat_show.js`) shows the TV's live
outbound connections. Dumping it reveals:

```
udp  192.0.2.64:56193  ->  8.8.8.8:53      (x14 concurrent DNS sessions)
tcp  192.0.2.64:47138  ->  34.160.212.185:443   (lcprd1/lcprd2 - DRM licensing)
tcp  192.0.2.64:48968  ->  13.226.187.18:443    (osb-apps-v2 - TV Plus)
tcp  192.0.2.64:47096  ->  13.226.187.68:443    (osb-apps-v2)
tcp  192.0.2.64:32844  ->  13.226.186.165:443   (osb-ussvc-v2 - TV Plus)
tcp  192.0.2.64:43268  ->  189.247.175.83:443   (Akamai MX - Samsung CDN)
tcp  192.0.2.64:50376  ->  34.255.141.141:5229  (AWS eu-west-1)
tcp  192.0.2.64:48318  ->  52.210.43.251:5229   (AWS eu-west-1)
tcp  192.0.2.64:38564  ->  3.141.180.121:443     (AWS us-east-2)
tcp  192.0.2.64:43372  ->  3.148.126.150:443     (AWS us-east-2)
tcp  192.0.2.64:52238  ->  44.215.137.192:443    (AWS)
```

**The TV resolves DNS through `8.8.8.8` directly, not through the router's
dnsmasq.** Consequences:

1. The 10 native blocks in §8.3 are currently **not** applied to the TV — a
   DNS query that never reaches the router cannot be filtered by it.
2. The router's DHCP pool hands out `192.0.2.254` as the DNS (confirmed on
   the Mac's lease: `domain_name_server = {192.0.2.254}`), and the TV took
   its lease at 11:51:48 with `8.8.8.8` already in use. The override is on
   the TV itself.
3. The TV is therefore **not** affected by any router-side DNS work until its
   own DNS setting is changed.

### 9.1 The action on the TV — attempted, and it did not take effect

`Settings → General → Network → Network Settings → DNS Server` → `192.0.2.254`.

**Verified 2026-10-24: the TV still resolves through `192.0.2.69` (the Mac
filter).** The setting either was not applied, was not committed, or was
overridden back to the DHCP value. Full evidence in **§12**.

While on that screen, confirm **encrypted DNS is off** (if the firmware offers
DoH / DoT, it would bypass plain DNS entirely).

### 9.2 Final architecture (corrected)

The architecture originally sketched here — router as the TV's resolver,
router forwarding to the Mac — **is not reachable on this firmware**. The
router's dnsmasq does not forward to a LAN-hosted resolver (§12.2): pointing
`lan_dns_svr_2nd0` at the Mac produced **zero** queries at the Mac's port 53
and took the router's DNS down with it.

What actually works, and what is live:

```
TV ──DNS──> 192.0.2.69  (Mac filter, launchd + caffeinate)
              ├─ 67 rules / 33 KEEP exceptions   [§11, measured]
              ├─ JSONL query log                 [the measurement instrument]
              └─ upstream: ISP DNS
Router 192.0.2.254 keeps its own 10 native blocks for anything that
queries it directly (phones, laptops, the router's own resolver).
```

This is **better than the router-as-resolver design**, not worse:

| | TV → router | TV → Mac filter (current) |
|---|---|---|
| Rules enforced on the TV | 10 | **67** |
| Query log | none | **full, per client, per decision** |
| Behaviour if the Mac sleeps | n/a | falls back to the TV's hardcoded `8.8.8.8` (unfiltered but functional) |
| Behaviour if the router sleeps | TV loses DNS | unaffected |

So the TV should stay on **`192.0.2.69`**. `caffeinate -i -m` keeps the Mac
awake while the filter runs (no root required) and the launchd agent restarts
the filter if it dies.

**The router's 10 native blocks are fully redundant for the TV** — all 10
hosts are already in the Mac's 67-rule list. They stay as a safety net for
anything that uses `192.0.2.254` as its resolver, and they are the only
layer that survives the Mac being off.

### 9.3 Measurement without a DNS log

Even before the TV's DNS is changed, the NAT table is a usable instrument:
resolve the candidate telemetry hosts, match their IPs against the TV's
live connections, and you get a *measured* inventory instead of a generic
list. `tv_conns.js` does exactly that:

```bash
ROUTER_PASS='<router password>' node tv_conns.js          # snapshot
ROUTER_PASS='<router password>' node tv_conns.js watch 60 # 60s accumulation
```

The five AWS endpoints in §9 (`:5229`, `us-east-2`, `eu-west-1`) are **not**
in the curated blocklist — they are Samsung service endpoints that only
appear once you look at what the set actually connects to. They are the
argument for switching the TV onto a logging resolver: the NAT table gives
IPs, the resolver gives names.

---

## 10. Deployed state (verified) and the measured telemetry inventory

### 10.1 What is live right now

| Layer | Status | Verified by |
|---|---|---|
| Router: 10 native DNS blocks | **deployed** | `dig @192.0.2.254 <host>` → `0.0.0.0` for all 10 |
| Router: 20 KEEP hosts | **still resolve** | compared against public DNS |
| Router: dnsmasq upstream | `lan_dns_mode0=2`, `lan_dns_svr0=192.0.2.69`, `lan_dns_svr_2nd0=198.51.100.53` | bogus-upstream test: resolution died, then recovered from the secondary |
| Mac: DNS filter | **running as a launchd service** | `launchctl list \| grep dnsfilter` → pid, exit 0 |
| Mac: keep-awake | `caffeinate -i -m` wrapping the filter (no root needed) | `pgrep caffeinate` |
| Log | `~/Projects/samsung-tv/tv-dns.log` (JSONL, one line per query) | — |

Files: `run_dnsfilter.sh`, `~/Library/LaunchAgents/com.local.samsung-tv-dnsfilter.plist`.

### 10.2 Measured inventory (live TV traffic, not a generic list)

The TV was observed querying the filter. 153 queries, 15 distinct names.
**Blocked and confirmed effective:**

```
customerevents.netflix.com
ichnaea.netflix.com
```

and the NAT table confirms the point: **zero TCP connections to any of the
14 Netflix telemetry IPs**, even though the TV asked for the hostnames.

**Allowed — functional, keep:**

```
cdn-0.nflximg.com            Netflix image CDN
uiboot.netflix.com           Netflix app boot
secure.netflix.com           Netflix secure API
api-global.netflix.com       Netflix API
osb-v2.samsungqbe.com        TV Plus
osb-apps-v2.samsungqbe.com   TV Plus apps
osb-ussvc-v2.samsungqbe.com  TV Plus service
cdn.samsungcloudsolution.com Samsung content CDN
gld.push.samsungosp.com      Samsung account push
```

**Allowed but telemetry — should be blocked, added to the blocklist:**

```
nrdp.prod.cloud.netflix.com       Netflix device telemetry
nrdp51-appboot.netflix.com       Netflix app-boot telemetry
nrdp-cell4.prod.ftl.netflix.com  Netflix device telemetry
client.smartthings.com           SmartThings device telemetry
```

### 10.3 Two corrections to earlier conclusions

1. **Netflix IS on this set.** The earlier app inventory said "Netflix not
   installed" — that was wrong, and the reason is that Tizen 9 removed the
   app-management API (`ed.installedApp.get` → `unrecognized method value`),
   so the inventory had to be built by probing IDs and missed it. The live
   traffic shows the Netflix stack running.
2. **The TV's DNS is not what DHCP advertises by default.** It was using
   `8.8.8.8` directly, which is why the router's blocks had no effect on it.

### 10.4 The answer to "does the Mac have to be always on?"

**For the full 67-rule coverage and the query log: yes.** The Mac has to be
awake and the filter running.

**The TV never breaks because of it.** Three separate facts, all tested:

1. The TV keeps a **hardcoded `8.8.8.8`** in its resolver list (visible in the
   router's NAT table as live `udp … → 8.8.8.8:53` sessions). If the Mac
   filter stops answering, the TV falls back to Google DNS on its own — no DNS
   outage, just unfiltered resolution.
2. The router's own **10 native blocks are applied by the router itself**,
   independently of any upstream, so they hold even with the Mac off.
3. `caffeinate -i -m` wraps the filter so the Mac does not sleep while it
   runs, and the launchd agent restarts the filter if it dies.

Net effect of the Mac being asleep:

| | Mac awake | Mac asleep |
|---|---|---|
| TV resolves names | yes | yes (via its hardcoded `8.8.8.8`) |
| Rules enforced | 67 | 0 on the TV (router's 10 still apply to router-resolving clients) |
| Query log | full | none |

A powered-off or hibernating Mac therefore drops the TV to *unfiltered* (not
to "no DNS"). That is the trade, and it is the reason option C (a hosted
resolver) exists: it has no local dependency at all.

### 10.5 Still to do on the TV

- Confirm **encrypted DNS (DoH / DoT) is off** in
  `Settings → General → Network → Network Settings`. Unverified so far, and it
  matters more than usual: a DoH resolver on the TV would bypass plain DNS
  entirely and no amount of filtering below it would help.
- Optionally re-attempt the manual DNS entry — but see §9.1/§12: the TV should
  stay on the Mac filter (`192.0.2.69`) even if the entry takes.

---

## 11. Measured per-app telemetry inventory

All five installed apps were launched over the REST API
(`POST /api/v2/applications/<id>`) and the filter log was harvested:
**407 queries, 28 distinct hostnames, 179 blocked.**

| App | Telemetry observed | Status |
|---|---|---|
| **Netflix** | `ichnaea.netflix.com`, `customerevents.netflix.com`, `nrdp.logs.netflix.com`, `nrdp.prod.cloud.netflix.com`, `nrdp51-appboot.netflix.com`, `nrdp-cell4.prod.ftl.netflix.com` | **blocked** |
| Netflix | `nrdp.prod.ftl.netflix.com` | was allowed → **now blocked** |
| Netflix (functional) | `api-global.netflix.com`, `secure.netflix.com`, `uiboot.netflix.com`, `cdn-0.nflximg.com` | allowed (needed) |
| **Prime Video** | `unagi-na.amazon.com` (Amazon device telemetry) | **blocked** |
| **YouTube** | only content hosts: `www.youtube.com`, `rr5---sn-0opoxu-hxmke.googlevideo.com`, `www.gstatic.com`, `tools.google.com` | no ad/analytics host seen in this window |
| **Disney+** | only `cd-dmgz.bamgrid.com` (content CDN) | no telemetry host seen in this window |
| **Spotify** | `ap-guc3.spotify.com`, `api-partner.spotify.com`, `apresolve.spotify.com`, `agnostic-api.spotify.dev`, `tv.scdn.co` | no telemetry host seen in this window |
| **Apple TV** | `atve.tv.apple.com` (Apple device metrics) | allowed — not in the blocklist |
| **Samsung platform** | `prd-use2-ucs.aibixby.com` (Bixby usage collection) | was allowed → **now blocked** |
| **Crash reporting** | `o22381.ingest.sentry.io` | was allowed → **now blocked** |
| Samsung (functional) | `cdn.samsungcloudsolution.com`, `lcprd1.samsungcloudsolution.net`, `osb-v2.samsungqbe.com` | allowed (KEEP) |

Blocklist is now **67 rules / 33 KEEP exceptions**.

### Leak check
`leak_check.py` resolves every host the filter blocked for the TV and
intersects those IPs with the TV's live NAT endpoints:

```
blocked names seen for the TV : 8
their distinct IPs            : 22
TV live NAT endpoints         : 6
LEAKED (TV connected to a blocked host): NONE
```

The TV asked for blocked names and never reached them — the filter is
authoritative in practice, even though the TV keeps 2 background sessions
open to `8.8.8.8:53`.

### Caveat on this inventory
It is one light session (apps opened, nothing signed in, no video playing,
no voice). Signing into accounts, actually playing content, and using the
remote are what surface the rest. Re-harvest after real use:
`python3 tv_dns_report.py` / `node tv_conns.js`.

---

## 12. Verification of the manual DNS change (2026-10-24)

### 12.1 Result: the TV's DNS did **not** change

The user set `Settings → General → Network → Network Settings → DNS Server`
to `192.0.2.254` (the router). Three independent measurements say the TV
is still using `192.0.2.69` (the Mac filter):

| Evidence | Reading |
|---|---|
| Filter query log (live, 1,285 entries) | **1,282** from `192.0.2.64` (the TV's own IP), **0** from `192.0.2.254` |
| Router NAT table | TV still holds live `udp → 8.8.8.8:53` sessions |
| Leak check (re-run) | 15 blocked names → 46 IPs vs 5 live NAT endpoints → **NONE leaked** |

The log reading is the decisive one. If the TV were using the router, the
router would have resolved the name itself (its upstream is the ISP, §12.2)
and the Mac would have seen *nothing* from the TV. Instead the Mac sees
**every** query arriving from the TV's own source IP — so the TV is talking
to `192.0.2.69` directly.

The TV's device WebSocket API (`ms.network.getNetwork` on port 8001) completes
the WS upgrade and then closes the channel on any remote client, so the TV-side
DNS value could not be read back directly. The traffic evidence is
unambiguous enough on its own.

### 12.2 The router cannot be chained to the Mac filter

The design sketched in §9.2 needed the router's dnsmasq to forward to the
Mac. Tested directly by repointing the secondary upstream:

```
lan_dns_svr_2nd0:  198.51.100.53  →  192.0.2.69   (the Mac)
```

* The router's DNS **went down**: `dig @192.0.2.254 <host>` timed out for
  every name.
* The Mac's log recorded **zero** queries from `192.0.2.254` — the router
  never sent a single packet to the Mac's port 53, so the filter was never
  even asked.
* Restoring `lan_dns_svr_2nd0=198.51.100.53` brought the router's DNS back
  within about a minute; all 10 native blocks and all 20 KEEP hosts verified
  again afterwards.

Conclusion: **this firmware's dnsmasq will not forward to a LAN-hosted
resolver.** `TV → router → Mac → ISP` is not achievable, so pointing the TV at
the router would cut its coverage from 67 rules + a full query log down to
10 rules + no log. The TV stays on `192.0.2.69`.

### 12.3 State verified after the test

| Component | State |
|---|---|
| Router native blocks | 10/10 return `0.0.0.0` |
| Router KEEP hosts | 20/20 resolve |
| Router LAN config | `lan_dns_mode0=2`, `lan_dns_svr0=192.0.2.69`, `lan_dns_svr_2nd0=198.51.100.53` |
| `wan_dns0` | untouched (`198.51.100.53 198.51.100.54`) |
| Mac filter | alive (launchd, `caffeinate`-wrapped); TV queries landing, `BLOCK` decisions firing for `ichnaea.netflix.com`, `customerevents.netflix.com`, `nrdp*.netflix.com` |
| TV | reachable, `developerMode 0`; DNS = Mac filter + hardcoded `8.8.8.8` fallback |

---

## 13. YouTube ad blocking: why Brave's method cannot be reproduced here

Brave/uBlock-Origin block YouTube ads by **rewriting the ad slots out of the
`playerResponse`** returned by `youtubei/v1/player`, plus CSS element hiding
and SABR backoff patching. That is application-layer surgery performed
*inside the browser* on the page's own JavaScript objects.

A DNS filter only ever sees **hostnames**. It cannot see the JSON body, the
`adPlacements` / `playerAds` / `adSlots` arrays, or the timing heuristics
involved. There is no DNS-level equivalent of "strip the ad slots".

What *is* reachable at the DNS layer is host-level blocking — the TV
demonstrably does ask for ad hosts such as
`googleads.g.doubleclick.net` (measured, §11) — so a DNS filter can cut the
ad *host* traffic, not the ad *slots* inside the video player. It cannot
replace Brave on a device where Brave's method is impossible.

The alternatives were evaluated and rejected:

| Approach | Verdict |
|---|---|
| MITM / deep inspection of TLS | **Rejected** — breaks Widevine/PlayReady DRM and app authentication |
| JS injection | Impossible — the TV's apps are signed, sandboxed packages |
| DNS host blocking | Possible, partial: ad hosts only, no ad slots |
| uBO/Brave on the TV | Not installed, not installable on Tizen 9 |

One further caution if a device-side ad blocker were ever attempted: Brave's
and uBlock's YouTube filters trigger YouTube's anti-adblock enforcement
screen, which would break playback of the apps that matter. Any experiment
there trades video playback for ad removal.