# Investigation — the Arcadyan GPON router admin API

> Part of the [Toney](../README.md) investigation archive. Every address,
> serial, MAC and identifier in this document has been replaced with a
> documentation-range value; the technical findings are unchanged.

No LuCI, no ubus, no SSH. The admin UI is the vendor's own, but it is fully
scriptable. Everything below was derived from the router's own JavaScript
and verified against the running device.

This is the reference that a future Toney router driver can be built on: the
DNS-filter driver in `dnsguard` today speaks SSH and dnsmasq, and this is the
other way to do it — straight through the admin UI, on routers that do not
give you a shell.

## Auth

- `GET /login.htm` → the session token is embedded in the page's spacer image:
  `ArcBase._t()` scans `<img>` tags for a `data:` URI and returns
  `ArcBase.decode(src.substring(78))` — a 9-digit integer.
- `POST /login.cgi` with `usr = SHA512(MD5_HEX("<isp-username>"))`,
  `pws = SHA512(MD5_HEX(<password>))`, `httoken = <token>` → sets `SID`.
  `err=3` means "session expired", not "wrong password".
- The router's httpd emits malformed responses (extra bytes after
  `Connection: close`); node's HTTP parser rejects them. Use curl.

The password hash is the MD5 hex digest of the password, hex encoded again
through SHA-512:

```js
function arcMd5(s) {
  const md5 = crypto.createHash('md5').update(s, 'utf8').digest('hex');
  return crypto.createHash('sha512').update(md5, 'ascii').digest('hex');
}
```

The token itself is extracted from a `data:` URI inside an `<img>` tag on the
page:

```js
function getHttoken(html) {
  const re = /<img[^>]*>/gi;
  let m;
  while ((m = re.exec(html))) {
    const s = /src="([^"]*)"/i.exec(m[0]);
    if (s && s[1].startsWith('data:') && s[1].length > 78) {
      return ArcBase.decode(s[1].substring(78));
    }
  }
  return '';
}
```

## Read config

`GET /cgi/cgi_<page>.js?_tn=<token>&_t=<ms>` → JS declaring every config slot
of that page:

```js
addCfg("logical_name", "<numeric_config_id>", "<current value>");
```

The `cgi/` files are served with the token from the **index.htm** render,
not from the page's own render.

## Write config

`POST /apply_abstract.cgi`, body fields:

- `httoken=<token>` — plaintext; it is also the AES key
- `DCBA=<urlencoded>` — one per field, each `AES-256-CBC(key = httoken,
  IV = 0)` of `"<numeric_config_id>=<value>"` (zero-padded plaintext,
  output as `%XX` bytes)
- the page's `action` name goes in as a DCBA entry too
  (`action=ui_dns`, `ui_lan`, `ui_firewall`, `ui_dhcp_static`, `ui_ddns`, …)

**The field name is the numeric config id, not the logical name.** Writing
logical names stores nothing. An id outside the page's declared set aborts
the whole apply.

The body builder, which reproduces the router's own `genForm()`:

```js
function dcbaBody(tok, fields, { cmd, cmdparam, next }) {
  const { ArcBase, do_encode } = loadArc();
  ArcBase._t = function () { return tok; };
  const items = [];
  items.push(['action', cmd]);
  items.push(['httoken', tok]);          // stays plaintext
  items.push(['submit_button', next]);
  if (cmdparam) items.push(['action_params', cmdparam]);
  for (const [k, v] of Object.entries(fields)) items.push([k, v]);

  const parts = [];
  for (const [k, v] of items) {
    if (k === 'httoken') { parts.push('httoken=' + encodeURIComponent(v)); continue; }
    const enc = do_encode(k + '=' + v);
    parts.push('DCBA=' + encodeURIComponent(enc));
  }
  return parts.join('&');
}
```

`do_encode` and `ArcBase` are the router's own functions, lifted verbatim
out of `/js/global.js` at runtime and evaluated in a sandbox. That is the
whole trick: the cipher is not re-implemented, it is borrowed.

## Things that exist but do not work

| Feature | Result |
|---|---|
| `firewall_url` (URL Blocking, 30 slots) | HTTP-layer filter, does not affect DNS |
| `dns_host` (DNS Host, 10 slots) | **works** — becomes dnsmasq `address=` with `0.0.0.0` |
| `lan_dns_svr0` + `lan_dns_mode0=2` | sets the router dnsmasq's **upstream** resolver |
| `lan_dhcp_static` | MAC/IP lease only, no per-client DNS |
| `system_backup` (upload.cgi) | config backup is OpenSSL-encrypted with an unknown key |
| `networktools.cgi` (ping/traceroute) | validates `dest` server-side; no injection |

## DNS Host limits (measured)

- 10 entries max
- hostname ≤ 31 characters (longer names are stored but ignored)
- exact hostname only — a parent does NOT cover its subdomains
- `0.0.0.0` is returned (not NXDOMAIN)

## Measurement surface

`cgi/cgi_nat_show.js` → live NAT session table, rows
`[proto, lan_ip, lan_port, nat_public_ip, nat_port, real_remote_ip, real_port]`.
This is how the TV's direct `8.8.8.8:53` DNS usage was found.

## Configuration field map

The numeric ids are what `apply_abstract.cgi` stores. The logical names are
only what the page's own form uses.

| Logical name | Numeric id | Meaning |
|---|---|---|
| `lan_dns_mode0` | `131094001000` | 1 = automatic, 2 = manual |
| `lan_dns_svr0` | `131095001000` | primary DNS (advertised to DHCP clients, and the router's upstream) |
| `lan_dns_svr_2nd0` | `131096001000` | secondary DNS |
| `wan_dns0` | `65562001000` | WAN-side resolvers |
| `dns_hostname0..9` | `983196001000` + n×1000 | DNS Host entry name |
| `dns_ip0..9` | `983197001000` + n×1000 | DNS Host entry address |
| `url_keyword0..29` | `655388001000` + n×1000 | URL Blocking keyword |

## What this API is worth, and what it is not

It is worth a lot: it is the only way to make the router itself enforce
blocks, and it is the only way to read the router's live NAT table, which is
what makes measurement possible at all.

It is not a way to make the router forward to another resolver. Pointing
`lan_dns_svr_2nd0` at a LAN-hosted resolver produced **zero** queries at that
resolver's port 53 and took the router's DNS down with it. The router's
dnsmasq does not forward to a LAN address it can see. So a chain of
`TV → router → local filter` is not achievable on this firmware, and the
local filter has to be the resolver the device talks to directly.
