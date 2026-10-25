# Profiles

Rule files for `dnsguard`. A profile is a plain text file with one
Adblock-Plus style rule per line. Nothing else about it is special: you can
write your own, point `dnsguard` at it, and it works the same way.

## Rule syntax

| Rule | Meaning |
|---|---|
| `||ads.example.net^` | block `ads.example.net` and every subdomain |
| `\|exact.example.net\|` | block that one name only |
| `/^acr[0-9]+\.example$/` | block when the regular expression matches the name |
| `@@\|\|cdn.example.net^` | never block it - a KEEP rule |
| `! comment` or `# comment` | ignored |

A KEEP rule always wins over a block rule. That is the whole design of the
profiles in this directory: the block list is deliberately narrow, and the
KEEP list protects the hosts that make the device work.

Wildcards are **not** supported. `cdn-*.example.net` is treated as a literal
name and will never match. Use a regular expression instead.

## The profiles

| File | What it covers |
|---|---|
| `samsung-tv-telemetry.blocklist` | Samsung Tizen TVs: viewing-history fingerprinting, advertising, device logs. 70 block rules, 33 KEEP rules. |
| `samsung-tv-account-voice.blocklist` | Opt-in. Account sign-in and voice backend. Breaks sign-in and voice control by design. |
| `streaming-telemetry.blocklist` | Device-agnostic streaming and smart-TV telemetry: Netflix device events, Amazon device telemetry, crash reporting, smart-home cloud. |
| `youtube-ads.blocklist` | YouTube advertising and ad-measurement hosts. 17 block rules, 5 KEEP rules. Stops the ad host traffic, not the ad slots inside the player. |

## Using a profile

```json
{
  "rules": ["profiles/samsung-tv-telemetry.blocklist"]
}
```

Several files can be listed at once; the rules are merged.

## Writing your own

The useful loop is:

1. Run the service with an empty or minimal rule set.
2. Let the device do its thing for a while.
3. Read the query log (`toney` dashboard, or the `logs.tail` command).
4. Add the telemetry names you saw as block rules, and anything that broke as
   KEEP rules.

A profile that is too aggressive breaks the device, and a device that does not
work is not a private device. When in doubt, keep it allowed.
