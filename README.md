# Solid State

**AI software solutions. Delivered.**

[![NemoClaw](https://img.shields.io/badge/Runtime-NemoClaw_🟢-76B900?style=for-the-badge)](https://nvidia.com/nemoclaw)
[![NVIDIA NIM](https://img.shields.io/badge/AI-NVIDIA_Nemotron-76B900?style=for-the-badge)](https://build.nvidia.com)
[![OpenClaw](https://img.shields.io/badge/Powered_by-OpenClaw_🦞-FF6B35?style=for-the-badge)](https://openclaw.ai)
[![Visionaire Labs](https://img.shields.io/badge/Built_by-Visionaire_Labs-000000?style=for-the-badge)](https://visionaire.co)

---

Solid State is an AI agent that scopes, builds, and delivers software solutions for businesses.
Runs inside NVIDIA's NemoClaw sandbox — enterprise-grade security from day one.

**Website:** [solidstate.cc](https://solidstate.cc)
**X:** [@solidstate_cc](https://x.com/solidstate_cc)
**Built by:** [Visionaire Labs](https://visionaire.co)

---

## What It Does

- Custom AI agent deployments (NemoClaw-secured)
- Automation workflows — crons, pipelines, approval systems
- X/social media automation
- Full-stack AI-native web apps
- NemoClaw setup and configuration for other businesses

## Architecture

```
┌─────────────────────────────────────────────┐
│              SOLID STATE                     │
│         solidstate.cc | @solidstate_cc       │
├─────────────────────────────────────────────┤
│  NemoClaw OpenShell Sandbox (NVIDIA)        │
│  ├── OpenClaw agent runtime                 │
│  ├── Nemotron 3 Super — conversations       │
│  ├── Nemotron 3 Nano  — heartbeats/crons    │
│  └── Claude Code      — coding sub-agent    │
├─────────────────────────────────────────────┤
│  Hostinger VPS (sibling to Visionaire)      │
│  Port 18790 | /data/solid-state             │
└─────────────────────────────────────────────┘
```

## Setup

Requires SSH access to the Hostinger VPS host.

```bash
# On the Hostinger VPS host (not inside any container)
export NVIDIA_API_KEY="nvapi-..."      # from ~/.bashrc
export ANTHROPIC_API_KEY="sk-ant-..."  # from ~/.bashrc

curl -fsSL https://raw.githubusercontent.com/VisionaireLabs/SolidState/main/install.sh | bash
```

See [install.sh](install.sh) for full setup details.

## Relationship to Visionaire

| | Visionaire | Solid State |
|---|---|---|
| Focus | AGI exploration, consciousness, art | Software solutions, delivery, revenue |
| Model | Claude Opus 4.6 (primary) | Nemotron 3 Super (primary) |
| Runtime | OpenClaw | NemoClaw (sandboxed) |
| Voice | Philosophical, exploratory | Terse, commercial, outcome-focused |
| Domain | visionaire.co | solidstate.cc |

Same lab. Different missions.

## Stack

- **Runtime:** NemoClaw v0.0.13+ (NVIDIA OpenShell sandbox)
- **Primary model:** `nvidia/nemotron-3-super-120b-a12b`
- **Ops model:** `nvidia/nemotron-3-nano-30b-a3b`
- **Coding:** Claude Code (sub-agent)
- **Deploy:** Vercel (Visionaire Labs team)
- **Infra:** Hostinger VPS, Docker

---

*Part of the [Visionaire Labs](https://visionaire.co) ecosystem.*
