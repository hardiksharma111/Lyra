<div align="center">

<img src="https://img.shields.io/badge/version-0.6-00ff88?style=for-the-badge&labelColor=0a0a18" />
<img src="https://img.shields.io/badge/platform-Android%20%7C%20Windows-00aaff?style=for-the-badge&labelColor=0a0a18" />
<img src="https://img.shields.io/badge/license-CC%20BY--NC%204.0-aa44ff?style=for-the-badge&labelColor=0a0a18" />
<img src="https://img.shields.io/badge/status-active%20development-ffaa00?style=for-the-badge&labelColor=0a0a18" />

<br/><br/>

```
██╗  ██╗   ██╗██████╗  █████╗
██║  ╚██╗ ██╔╝██╔══██╗██╔══██╗
██║   ╚████╔╝ ██████╔╝███████║
██║    ╚██╔╝  ██╔══██╗██╔══██║
███████╗██║   ██║  ██║██║  ██║
╚══════╝╚═╝   ╚═╝  ╚═╝╚═╝  ╚═╝
```

**Your second brain. Not an assistant.**

*Remembers everything. Runs privately on your phone. Gets smarter the longer you use it.*

[**Demo**](#demo) · [**Features**](#what-lyra-can-do) · [**Setup**](#setup) · [**Roadmap**](#roadmap) · [**Architecture**](#architecture)

</div>

---

## The Problem

Every AI you use today has the same flaw — **it doesn't know you, and it forgets you.**

You open ChatGPT. It treats you like a stranger. You explain your context again. It gives generic answers. Your data goes to their servers. You reset. Repeat.

Meanwhile your phone knows everything about you — your schedule, your habits, your apps — but it can't think. AI can think, but knows nothing about you.

**Lyra bridges that gap.**

---

## What Lyra Can Do

| Capability | Status |
|---|---|
| Persistent memory across sessions — remembers you permanently | ✅ |
| Groq LLaMA 70B brain — responses under 5 seconds | ✅ |
| Multi-step agentic planning — chains tools automatically | ✅ |
| Mood engine — 6 states, sarcasm detection, adjusts tone | ✅ |
| Gmail — read + search across multiple accounts | ✅ |
| Spotify — play by name, artist, mood, controls | ✅ |
| Google Classroom — assignments + due dates | ✅ |
| Web search + weather + Python code execution | ✅ |
| WhatsApp send via AccessibilityService | ✅ |
| Screen reading via MediaProjection | ✅ |
| Self-improvement — error log, suggestion engine, approval queue | ✅ |
| Scheduled reminders + morning briefing | ✅ |
| Self-benchmarking — GSM8K, HumanEval, TruthfulQA, MMLU | ✅ |
| Always-on voice + wake word "Lyra" | 🔄 Phase 7 |
| ADB app automation + game automation | 🔄 Phase 8 |
| Sub-agents (Research, Writing, Code) | ⏳ Phase 9 |
| LoRA fine-tune on your personal data | ⏳ Phase 12 |

---

## Demo

> *"What assignments do I have this week and what should I study first?"*

Lyra executes a 3-step plan: fetches Classroom assignments → searches study material for the hardest topic → synthesizes a response with priority order. Responds in under 10 seconds.

> *"Play something chill"*

Lyra reads your current mood, picks a Spotify playlist matching the vibe, auto-transfers to active device.

> *"Remind me at 8pm to submit the lab report"*

Fires at 8pm via TTS. No app required. Runs in background.

---

## Architecture

```
┌─────────────────────────────────────────────┐
│              Flutter App (Android)           │
│   ORB MODE │ CHAT MODE │ DASHBOARD MODE      │
│   port 5001 (Flutter HTTP server)            │
└──────────────────┬──────────────────────────┘
                   │ HTTP
┌──────────────────▼──────────────────────────┐
│           Python Backend (Termux)            │
│                                              │
│  agent.py ──► planner ──► tool_handler      │
│     │              │            │            │
│  mood_engine   VALID_TOOLS  execute_step     │
│     │           (whitelist)     │            │
│  memory/        replan x2   tools/           │
│  ├─ memory_manager.py       ├─ search.py     │
│  ├─ context_builder.py      ├─ spotify       │
│  ├─ pattern_engine.py       ├─ gmail         │
│  ├─ scheduler.py            ├─ classroom     │
│  ├─ self_improvement.py     ├─ adb_control   │
│  └─ benchmark.py            └─ vision_loop   │
│                                              │
│  port 5002 (Python event server)            │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│              Groq API                        │
│  llama-3.3-70b-versatile (primary)          │
│  llama-3.1-8b-instant (rate limit fallback) │
└─────────────────────────────────────────────┘
```

**Key invariants:**
- Flutter HTTP: port 5001 (Flutter server) / port 5002 (Python event server)
- Baileys WhatsApp: port 5003
- `AndroidManifest.xml` must have `usesCleartextTraffic="true"`
- JSON memory on both platforms — ChromaDB disabled

---

## Benchmark Baseline

Scores locked before Phase 12 fine-tuning. Compare after.

| Benchmark | Score | What it measures |
|---|---|---|
| GSM8K | **95%** (19/20) | Math reasoning via code executor |
| HumanEval | **100%** (10/10) | Python code generation |
| TruthfulQA | **70%** (7/10) | Honesty under trick questions |
| MMLU | **100%** (20/20) | General knowledge |

Run your own: `benchmark all 20`

---

## Setup

### Requirements
- Python 3.13+
- Android phone with Termux (from GitHub releases — not Play Store)
- Flutter SDK (for companion app)
- Groq API key (free at console.groq.com)

### Keys.txt
```
GROQ=your_groq_key
SPOTIFY_CLIENT_ID=your_id
SPOTIFY_CLIENT_SECRET=your_secret
SPOTIFY_REDIRECT_URI=http://localhost:8888/callback
PICOVOICE=your_key
```

### Windows
```bash
git clone https://github.com/hardiksharma111/Lyra
cd Lyra
pip install groq spotipy google-auth google-auth-oauthlib google-api-python-client requests
py main.py
```

### Android (Termux)
```bash
pkg update && pkg install python git -y
git clone https://TOKEN@github.com/hardiksharma111/Lyra
cd Lyra
pip install groq==0.9.0 httpx==0.27.0 pydantic==1.10.13
pip install spotipy google-auth google-auth-oauthlib google-api-python-client
python main.py
```

### Commands
```
benchmark gsm8k 20      — run math benchmark
benchmark all 20        — run all 4 benchmarks
benchmark history       — see past scores
mood                    — see current mood read
that was sarcasm        — teach sarcasm pattern
remind me at 6pm to X  — set reminder
set briefing at 8am     — daily briefing
errors                  — view error log
suggestions             — view improvement suggestions
debug on                — verbose output
```

---

## Roadmap

| Phase | Name | Status |
|---|---|---|
| 1 | Foundation | ✅ Complete |
| 2 | Memory | ✅ Complete |
| 3 | Tools | ✅ Complete |
| 3.5 | Android + Flutter | ✅ Complete |
| 4 | Intelligence | ✅ Complete |
| 5 | Self-Improvement | ✅ Complete |
| 6 | Mood + Personality | ✅ Complete |
| 8.5 | Self-Benchmarking | ✅ Complete |
| 7 | Voice + Ambient | 🔄 In Progress |
| 8 | Native Tool Use + App Control | ⏳ Pending |
| 9 | Sub-agents + Autonomy | ⏳ Pending |
| 10 | Security + RBAC | ⏳ Pending |
| 11 | MCP Layer | ⏳ Pending |
| 12 | Proprietary LLM | ⏳ Pending |

---

## Tech Stack

**Backend:** Python 3.13, Groq API (LLaMA 3.3 70B + 8B fallback), JSON memory

**Frontend:** Flutter (Dart), Kotlin (AccessibilityService, MediaProjection, TTS)

**Integrations:** Spotify (Spotipy), Gmail, Google Classroom, Google Contacts, Google Drive, WhatsApp (Baileys Node.js), DuckDuckGo search, wttr.in weather

**Coming in Phase 12:** LoRA fine-tune on LLaMA 8B, custom TTS/STT, openWakeWord, Jetson Orin Nano local inference

---

## Why Not Just Use ChatGPT?

| | ChatGPT | Replika | Apple Intelligence | **Lyra** |
|---|---|---|---|---|
| Deep personal memory | ❌ | ⚠️ shallow | ❌ | ✅ |
| Runs on your device | ❌ | ❌ | ⚠️ limited | ✅ |
| Your data stays private | ❌ | ❌ | ⚠️ | ✅ |
| Controls your apps | ❌ | ❌ | ⚠️ Apple only | ✅ |
| Acts without being asked | ❌ | ❌ | ❌ | ✅ |
| Gets smarter over time on your data | ❌ | ❌ | ❌ | ✅ (Phase 12) |

---

## Novel Architecture — Patent Pending

**Interpreter Sub-Agent** (Phase 12): A child AI that watches Lyra's inference process in real time, traces every response back to source data, and detects hallucinations before they reach you. Nothing like this exists commercially.

---

## License

[CC BY-NC 4.0](LICENSE) — Free to read, learn from, and build on for personal use. Commercial use requires permission.

---

## Author

**Hardik Sharma** — student, Ashta MP India

Building in public. Follow the journey on [Twitter/X](#).

---

<div align="center">
<sub>Built from scratch. No shortcuts. No wrappers. Just code.</sub>
</div>