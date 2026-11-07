# Avatar demo setup: Empfangs-Avatar

These instructions use Windows and an existing Foundry project. They do not
provision a subscription, project, or model deployment. All data is fictional
and built into the app ([campus.json](../hospital-avatar/campus.json)). The demo runs on port 8030 and is
independent of the other demos.

## 1. Prerequisites

- Python 3.11+, Azure CLI, Microsoft Edge or Google Chrome, a microphone
  (a headset or a directional microphone for a noisy room).
- A Foundry project in a region with **voice agents** and **real-time text to speech
  avatars**, for example Sweden Central or West Europe. The reference build used
  Sweden Central with the service-managed `gpt-realtime-2.1` and the standard video avatar `nia`.
- The **Foundry User** role on the project for the signed-in identity.
- No model deployment is needed. Voice sessions and avatar minutes are billed.
- The browser must reach the avatar's TURN relay (WebRTC, UDP/TCP 3478 and 443). Test on the
  event network beforehand.

## 2. Configure

From `hospital-avatar`:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

| Variable | Value |
|---|---|
| `FOUNDRY_PROJECT_ENDPOINT` | Endpoint copied from your Foundry project |
| `AZURE_TENANT_ID` | Directory that owns the project |
| `FOUNDRY_AVATAR_AGENT_NAME` | Defaults to `hospital-welcome-avatar` |
| `FOUNDRY_AVATAR_AGENT_MODEL` | Realtime model available to voice agents, e.g. `gpt-realtime-2.1` |
| `FOUNDRY_AVATAR_AGENT_VOICE` | Multilingual Azure voice, default `de-DE-Seraphina:DragonHDLatestNeural` |
| `FOUNDRY_AVATAR_CHARACTER` / `FOUNDRY_AVATAR_STYLE` | Standard video avatar, default `nia` (no style) |

```powershell
az login --tenant YOUR-DIRECTORY-ID
.\.venv\Scripts\python.exe create_agent.py
```

Each run saves a new agent version with instructions, audio settings, the avatar
configuration and four function tools. Check it in the Foundry portal's voice agent playground.

## 3. Start and check

```powershell
.\Start-AvatarDemo.ps1
```

| Page | Purpose |
|---|---|
| <http://127.0.0.1:8030/> | Kiosk: avatar, map, check-in, visitor information |
| <http://127.0.0.1:8030/team> | Information desk and clinic: arrivals, help requests, transcripts, reset |

```powershell
.\.venv\Scripts\python.exe -m pytest -q     # local, no Azure calls
.\.venv\Scripts\python.exe smoke_test.py   # live, app running: 8 typed cases in 5 languages
```

The smoke test runs without avatar video (voice-only mode) and checks check-in,
privacy, routes in several languages, step-free routes, visitor information, the
refusal of medical questions and the emergency rule. It waits 40 seconds between
sessions because avatar sessions started back to back are rate-limited. Then rehearse
in the browser with the [presenter script](AVATAR-SCRIPT-DE.md): avatar video, lip sync,
voice and microphone can only be judged live.

## Completion checklist

- Live smoke test passes.
- The avatar appears within a few seconds on the presentation laptop and network.
- Check-in for Novak / 14.03.1959 shows waiting number and route; `/team` shows the arrival.
- After rehearsing, wait at least a minute before the live start, then reset `/team`.

State lives in memory only and is cleared on restart or with **Demo zurücksetzen**.
See [operations](OPERATIONS.md) for troubleshooting.
