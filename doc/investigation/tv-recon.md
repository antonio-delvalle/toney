# Investigation — Samsung Tizen TV, device control surface

> Part of the [Toney](../README.md) investigation archive. Every address,
> serial, MAC and identifier in this document has been replaced with a
> documentation-range value; the technical findings are unchanged.

**Target:** `192.0.2.64` (wired Ethernet, MAC `00:11:22:33:44:55` → Samsung Electronics Co.,Ltd)
**Analyst host:** `192.0.2.69` (Wi-Fi) — LAN `192.0.2.0/24`, gateway `192.0.2.254`
**Date:** 2026-10-24

---

## 0. LAN topology (`192.0.2.0/24`)

Full neighbour table, stable across a 50-minute poll — **6 devices, no other candidates**:

| IP | MAC | Identity |
|---|---|---|
| `192.0.2.64` | `00:11:22:33:44:56` | **Samsung Smart TV** (this target) |
| `192.0.2.66` | `00:11:22:33:44:57` | unidentified — locally-administered MAC; opens `49152`, `62997`; no banner, no TLS, no HTTP |
| `192.0.2.68` | `00:11:22:33:44:58` | an Android handset — ADB wireless debugging on `46888`/`47888` |
| `192.0.2.69` | `00:11:22:33:44:59` | this Mac (AirPlay receiver `:7000`, a dev tool on `:3000`) |
| `192.0.2.71` | `00:11:22:33:44:5a` | Apple device |
| `192.0.2.254` | `00:11:22:33:44:5b` | ISP GPON IAD (Arcadyan <router-model>), OpenWrt + LuCI, MiniUPnPd |

The TV's real Samsung MAC is what identifies it — its AirPlay `deviceid` from the
mDNS TXT record is `00:11:22:33:44:55`, which `macvendors.com` resolves to
Samsung Electronics Co.,Ltd. Because the set is wired, that MAC is stable (no Wi-Fi
MAC randomisation), which is what made `watch_tv.py` reliable.

---

## 1. Device identity

Source: `GET http://192.0.2.64:8001/api/v2/` (Tizen REST API, unauthenticated)

| Field | Value |
|---|---|
| `modelName` | `<model>` — 43" Crystal UHD (CU7000, 2020/21) |
| `model` | `23_KSUE_UB_T09` (Tizen 9.0 platform string) |
| `name` | `43" Crystal UHD` |
| `OS` / `type` | `Tizen` / `Samsung SmartTV` |
| API version | `2.0.25` |
| `firmwareVersion` | `Unknown` (masked by firmware) |
| `duid` / `udn` | `<device-id>` |
| `serialNumber` | `<serial-redacted>` (UPnP DMR, :9197) |
| `resolution` | `3840x2160` (4K) |
| `countryCode` / `Language` | `<country>` / `<locale>` |
| `networkType` | **`wired`** |
| `wifiMac` | `00:11:22:33:44:55` |
| `PowerState` | `on` |
| `developerMode` / `developerIP` | `0` / `0.0.0.0` → **Developer Mode OFF** |
| `TokenAuthSupport` | `true` |
| `remote_available` | `true` (fourDirections, touchPad, voiceControl) |
| `EDEN_available` | `true` (but see §5 — EDEN methods are dead on this build) |

---

## 2. Attack surface (open TCP ports)

| Port | Proto | Service | Status |
|---|---|---|---|
| 8001 | HTTP | Tizen REST v2 (`/api/v2/`), DIAL mount, plaintext WS fallback | open |
| 8002 | HTTPS/WSS | Remote-control channel (`ms.remote.control`) | open, self-signed TLS |
| 8080 | HTTP | Secondary DIAL / TV web server (403 at `/`) | open |
| 9197 | HTTP | UPnP DMR (RenderingControl / AVTransport / ConnectionManager) | open |
| 7678 | HTTP | UPnP `nservice` endpoint | open |
| 26101 | TCP | **SDB developer bridge** | **closed** (needs Developer Mode) |
| 55000 / 1985 / 2345 / 60103 / 60104 / 7676 / 9080 / 15000 | — | legacy / dev | closed |

---

## 3. Control channel — verified working

**Pairing:** first WSS connection raises an on-screen *"Smart Device attempting to connect"*
prompt. Once accepted, the TV emits `ms.channel.connect` carrying a persistent token.

```
token = <token>        # reuse as ?token=<token> on every later connection
```

**Key injection** (`ms.remote.control` over WSS :8002, JSON):

```json
{"method":"ms.remote.control",
 "params":{"Cmd":"Click","DataOfCmd":"KEY_MUTE","Option":"false","TypeOfRemote":"SendRemoteKey"}}
```

### Proof of a closed control→state loop

| | before | after `KEY_MUTE` |
|---|---|---|
| `RenderingControl.GetMute` | `CurrentMute = 0` | **`CurrentMute = 1`** |

State was read back independently over UPnP :9197 — the write really landed on the TV.
(Mute was restored to `0` afterwards.)

**Important protocol quirk:** sending `Sec-WebSocket-Protocol: samsungTv.remote.control`
makes this firmware **close the TCP connection without a 101**. The header must be omitted
entirely. With it removed → `HTTP/1.1 101 Switching Protocols`.

Also: the API listener tolerates **one connection at a time**. Concurrent 8001 + 8002
connections caused `Connection reset by peer` / `Connection refused` until requests were
serialised.

---

## 4. App inventory

No list-all endpoint exists on this build (`/api/v2/applications` → 404). Apps were
enumerated by probing IDs against `GET /api/v2/applications/<id>` (200 = installed,
404 = absent). **Both numeric and alphanumeric IDs work.**

| ID | Name | Version | Running |
|---|---|---|---|
| `3201910019365` | Prime Video | 5.3.22 | ✅ yes (visible) |
| `111299001912` / `9Ur5IzDKqV.TizenYouTube` | YouTube | 2.1.527 | ✅ yes |
| `3201901017640` / `MCmYXNxgcu.DisneyPlus` | Disney+ | 26.4.0 | no |
| `3201807016597` | Apple TV | 16.2.0 | no |
| `3201606009684` / `rJeHak5zRg.Spotify` | Spotify | 2.1.71 | no |

Netflix (`RN1MCdNq8t.Netflix`, `11101200001`) → 404, not installed on this set.

**Launch confirmed:** `POST /api/v2/applications/3201910019365` → `200 true`.

---

## 5. Power state machine (measured)

`KEY_POWER` on this firmware behaves like this — it is **not** a simple on/off toggle:

| From | `KEY_POWER` result | Network stack |
|---|---|---|
| `on` | → **`standby`** | stays up: `:8001`, `:8002` alive, `:9197` closes |
| `standby` | → **`on`** | fully up |
| `on` → `standby` → `standby` (2nd press too fast) | → **full reboot** | all ports drop ~60 s, returns in `standby` |

Verified end-to-end: `on` → `KEY_POWER` → `standby` → `KEY_POWER` → **reboot** (60 s
downtime) → `standby` → `KEY_POWER` → **`on`**. The TV was left running.

Practical consequence: the remote channel is reachable in standby, so the TV can be
woken and re-parked programmatically — but leave ~8 s between presses or you trigger a
reboot instead of a clean wake.

---

## 6. What is *not* available on this firmware

| Endpoint / method | Result |
|---|---|
| `GET /api/v2/applications` (list) | 404 |
| `GET /api/v2/channels`, `/device`, `/settings`, `/networks`, `/notify`, `/editor` | 404 |
| WS `ed.installedApp.get`, `ed.edanApp.get`, `ed.editMode.get`, `ed.channel.get`, `ed.apps.launch` | `ms.error: unrecognized method value` — **EDEN API removed** |
| `POST /ws/apps/<name>` | 401 (name unresolvable) / 500 (name resolves, launch fails) — header/query token auth rejected |
| `POST /ws/app/<id>` | 401 |
| `:8080/apps`, `:8080/dmr`, `:8080/` | 404 / 403 (generic web server) |
| `:7678` ContentDirectory `Browse` | UPnP fault (no browseable tree) |
| `DELETE /api/v2/applications/<id>` | not exercised against a real app — would remove software |

Tizen 9.0 has locked down the legacy EDEN/app-management API. The surviving levers are
REST v2 (read + launch), the WSS key channel, and UPnP (read + set).

---

## 7. Operative capability (non-root — the sanctioned path for this task)

Everything below was **executed and verified against the live TV**:

| Capability | Mechanism | Verified |
|---|---|---|
| Device inventory & metadata | `GET :8001/api/v2/` | ✅ |
| Remote key injection (any key) | `ms.remote.control` over WSS `:8002` | ✅ |
| App launch | `POST :8001/api/v2/applications/<id>` | ✅ `200 true` |
| App enumeration (by ID probe) | `GET :8001/api/v2/applications/<id>` | ✅ 5 apps |
| Volume read / write | UPnP `RenderingControl` `:9197` | ✅ |
| Mute read / write | UPnP `RenderingControl` `:9197` | ✅ |
| Transport state | UPnP `AVTransport` `:9197` | ✅ |
| Shutdown / wake | `KEY_POWER` | ✅ `on → standby → on` |

By injecting keys you can drive the TV's own Settings menus (e.g. toggle ad tracking,
autorun Smart Hub, picture/sound profiles) — the script navigates blind, since Tizen
exposes no screenshot API.

### Root-level modification (requires Developer Mode — *not enabled*)

`developerMode: 0`, `developerIP: 0.0.0.0`, port **26101 closed**. Enabling it requires
physical remote access on the TV:

1. Open the **Apps** panel
2. Press **1 2 3 4 5** on the remote (or gear icon top-right of the Apps panel → 12345)
3. Toggle **Developer Mode** → **ON**
4. Host PC IP → `192.0.2.69`
5. Accept the prompt, let the TV restart

Then `sdb connect 192.0.2.64` (default port 26101) yields a **root shell**:

```bash
sdb connect 192.0.2.64
sdb devices
sdb shell "ls /opt/usr/apps/"       # privileged native apps
sdb shell "ls /apps/"               # user apps
sdb shell "cat /etc/version"        # platform info
sdb push local.tpk /tmp/local.tpk
sdb shell "pkgcmd -i -t tpk -p /tmp/local.tpk"   # install (unsigned OK in dev mode)
sdb shell "app_launcher -s <pkgid>"              # launch
```

That is the route to reading/replacing native binaries, patching bundled web apps, and
adding or removing features at the package level.

**Toolchain:** `sdb` ships only inside Tizen Studio (Samsung-licensed, not
redistributable). `web-cli_Tizen_Studio_6.0_macos-64.bin` (277,146,828 bytes,
SHA-256 `3205597d127c4b93d924f591153b0b2f83f4ab90c4abc8786b3e902397e5488e`) is already
downloaded in this directory. `sdb` is an **x86_64** binary — **Rosetta 2 is already
installed** on this Mac ✅. Signing custom packages with Samsung *Partner* certificates
(required for `avplay` hardware video decode) additionally needs the device **DUID**
(`<device-id>`).

---

## 8. Toolkit

- `tvctl.py` — stdlib-only discovery + REST/UPnP/WebSocket control
- `watch_tv.py` — waits for the TV to appear, identifies it by Samsung OUI
- `watch_sdb.py` — waits for the SDB developer port to open
- `tv_token.txt` — the pairing token (`<token>`)
- `apps_installed.json` — app inventory snapshot
- `web-cli_Tizen_Studio_6.0_macos-64.bin` — Tizen Studio CLI installer (not installed)

Usage:

```bash
python3 tvctl.py discover                 # find + identify Samsung TVs on the LAN
python3 tvctl.py state    192.0.2.64    # device info + volume/mute/transport
python3 tvctl.py apps     192.0.2.64    # installed app inventory
python3 tvctl.py launch   192.0.2.64 3201910019365
python3 tvctl.py key      192.0.2.64 KEY_POWER
python3 tvctl.py power    192.0.2.64    # power toggle with state verification
python3 tvctl.py vol      192.0.2.64 20
python3 tvctl.py mute     192.0.2.64 0
```

### Two protocol quirks worth remembering

1. **Never send `Sec-WebSocket-Protocol: samsungTv.remote.control`** — this firmware
   closes the TCP connection *without* a 101. Omit the header entirely.
2. **One connection at a time.** Concurrent `:8001` + `:8002` connections caused
   `Connection reset by peer` / `Connection refused` until requests were serialised.

---
