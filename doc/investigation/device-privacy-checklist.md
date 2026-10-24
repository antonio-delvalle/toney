# Investigation — device-side privacy switches for a Tizen TV

> Part of the [Toney](../README.md) investigation archive. Every address,
> serial, MAC and identifier in this document has been replaced with a
> documentation-range value; the technical findings are unchanged.

These are the switches Samsung itself exposes. They cost nothing, break nothing,
and they remove the *consent* for several telemetry pipelines at the source.
Do these **first**; the DNS filter in `telemetry-strategy.md` is the enforcement layer
that catches whatever the switches miss.

---

## 0. The single biggest win — sign out of the Samsung account

`Settings → General → Samsung Account → Sign Out`

This is worth doing before anything else. A signed-in Samsung account is what
ties your **watch history, viewing recommendations, interest profile and
cross-device personalization** to a persistent identity. Signing out removes the
identity that all of it hangs off.

Consequences to expect:
- No personalised "Top Picks" / recommendation tiles in Smart Hub
- No cross-device continuity (phone-to-TV handover, SmartThings linking)
- The Tizen Store still works for installing apps; you can sign back in
  temporarily when you need to buy something

> If you prefer to stay signed in, at minimum disable **Sync** and
> **Smart Login** under the same menu.

---

## 1. Privacy Choices — the master consent page

`Settings → General → Terms & Policies → Privacy Choices`

Turn **OFF** every switch in this list. Names vary slightly by region/firmware,
so match on meaning:

| Switch (label may vary) | What it governs | Turn |
|---|---|---|
| **Help improve Samsung products and services** | Diagnostic / usage telemetry upload | **OFF** |
| **Personalised Advertising** / *Interest-based Advertising* | Ad targeting based on your profile | **OFF** |
| **Viewing Information Services** | **ACR** — content fingerprinting of what's on screen | **OFF** |
| **Voice Recognition Services** | Voice data / recordings leaving the set | **OFF** |
| Any "Personalised content" / "Recommendations" entry | Behavioural recommendations | **OFF** |

**Viewing Information Services is the important one.** ACR is Samsung's
Automatic Content Recognition: it fingerprints what is on screen (including
audio) and reports a viewing history. Samsung runs this through
`samsungacr.com`, `acr-<region>-prd.samsungcloud.tv` and
`musicid.samsungcloudsolution.com` — all of which the DNS filter blocks
regardless, but switching it off stops the *consents* from being re-synced
upstream via `auth.samsungosp.com`.

---

## 2. Voice — stop uploading recordings

`Settings → General → Voice Recognition`

| Control | Turn |
|---|---|
| **Voice Assistant** / *Voice Recognition* master switch | **OFF** if you don't use voice |
| **Send voice data to Samsung** / *Voice data upload* | **OFF** (leave on only if you actively use voice control) |

If you keep voice on, the data still leaves the set: the set records the audio,
sends it for server-side speech recognition, and stores the transcript on
Samsung's side. This is the one category that the DNS filter can only
partially blunt — the voice service endpoints are shared with the "wake word"
and account features, so blocking them wholesale risks breaking voice entirely.

**Recommendation:** if you do not use voice control, switch it off entirely.
That is the only way to guarantee no audio leaves the house, because a blocked
DNS name just causes a retry loop, it does not stop the on-device microphone
from capturing.

---

## 3. Diagnostic logs

`Settings → Support → Contact Samsung → Logs`

Uncheck **Enable** (the log-upload consent box). This stops the set from
shipping its log journals on request.

The corresponding endpoints are `devicelog.samsungcloudsolution.net`,
`prderrordumpssm.samsungcloudsolution.net` and
`prderrordumphsm.samsungcloudsolution.com` — all blocked by the DNS filter.

---

## 4. Personalisation / ad surface

| Path | Control | Turn |
|---|---|---|
| `Settings → General → Samsung Account` | **Personalise Recommendations** / *Sync* | **OFF** |
| `Settings → Support → e-Manual / Support` | *Contact Samsung* → auto-upload | **OFF** |
| Smart Hub | Right-click a recommendation tile → **Remove** | remove what you don't want |

**TV Plus** (Samsung's free ad-supported channels) is not a toggle you can
remove — it is built into the firmware. Two options:

- **Keep it** and let the DNS filter strip its *log beacons* only
  (`tvpnlog*.samsungcloud.tv`, `qoe.samsungcloud.tv`) while the streaming
  itself keeps working.
- **Kill it** by blocking `osb-*.samsungqbe.com` and `*.samsungcloud.tv`
  — the channels disappear from the guide, and with them the ad-impression
  and session telemetry. **This is a visible change**: TV Plus channels will
  no longer appear. It does not affect the tuner, HDMI sources, or the app
  store.

---

## 5. What you cannot switch off, and needs the network layer

| Behaviour | Why the UI can't stop it | Covered by DNS filter |
|---|---|---|
| ACR content fingerprinting | Ships from a system service, not a settings page | Yes — `samsungacr.com`, `acr-<cc>-prd.samsungcloud.tv`, `musicid.*` |
| Error dumps / log journals | Background uploader | Yes — `devicelog.*`, `prderrordump*.*` |
| TV Plus session + QoE beacons | Part of the streaming session | Yes — `tvpnlog*`, `qoe.*` |
| Samsung Ads / AdGear RTB | Ad decisioning in the Smart Hub web app | Yes — `samsungads.com`, `adgrx.com`, `samsungrs.com` |
| In-app analytics (`ureca.samsungapps.com`) | Bundled analytics SDK | Yes |
| Prime Video / Netflix device logging | Third-party SDKs inside the apps | Yes |
| Behavioural profile build-up | Requires an account | Partly — signing out is the real fix |

---

## 6. Verification

After making the changes, the DNS filter's query log is your proof. With the
filter running (see `telemetry-strategy.md`), watch what the set asks for:

```bash
python3 dnsfilter.py --report dnslog.jsonl
```

Expect to see **no** entries for:

```
samsungacr.com
acr-mx-prd.samsungcloud.tv
musicid.samsungcloudsolution.com
devicelog.samsungcloudsolution.net
tvpnlogosus.samsungcloud.tv
```

and expect to **still** see normal traffic for time sync, the app store,
TV Plus streaming and streaming apps.

---

## 7. Order of operations

1. Sign out of the Samsung account (or disable Sync + Smart Login)
2. Privacy Choices → all switches off
3. Voice Recognition → off (or "send voice data" off)
4. Contact Samsung → Logs → uncheck Enable
5. Enable the DNS filter (see `telemetry-strategy.md`)
6. Verify with the query log

Steps 1–4 are safe and reversible. Step 5 is the enforcement backstop.

### Network settings on the TV

- **Leave `DNS Server` on the value the DHCP lease provides** (the Mac filter
  at `192.0.2.69`). Setting it to the router instead was tried on
  2026-10-24 and it did not take effect; even if it did, it would cut
  coverage from 67 rules + a full query log to 10 rules + no log, because this
  router's dnsmasq will not forward to a LAN-hosted resolver
  (`telemetry-strategy.md` §12).
- **Confirm encrypted DNS (DoH / DoT) is off.** This is the one network
  setting still unverified, and it is the one that would defeat the filter
  entirely.