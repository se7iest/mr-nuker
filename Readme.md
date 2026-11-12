# Mr Nuker

[![Python](https://img.shields.io/badge/Python-3.9%2B-blue?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![PyQt6](https://img.shields.io/badge/PyQt6-GUI-green?style=for-the-badge&logo=qt&logoColor=white)](https://pypi.org/project/PyQt6/)
[![Discord](https://img.shields.io/badge/Discord-API-5865F2?style=for-the-badge&logo=discord&logoColor=white)](https://discord.gg/mrontop)

Discord guild management terminal built with PyQt6. Features a fully custom-painted "Neon Glass" interface, multi-threaded execution, rate-limit handling, and a full suite of destructive and administrative actions.

## Features

- **Authentication**: Supports User and Bot tokens with automatic prefix detection and validation via `/users/@me`.
- **Target Selection**: Fetch guilds via API or input a Guild ID manually.
- **Action Matrix**: 21 distinct actions including Ban/Kick All, Delete/Create/Rename Channels and Roles, Webhook Spam, Audit Log Lag, Guild Rename, and Full Nuke.
- **Rate Limiter**: Built-in bucket management tracking `X-RateLimit-*` headers. Handles HTTP 429 with automatic retries and global rate limit cooldowns.
- **Proxy Support**: Optional proxy pool. Reads from `proxies_cache.txt` in the root directory. Falls back to direct connection if `DIRECT_FALLBACK` is enabled.
- **Concurrency**: Utilizes `ThreadPoolExecutor` for parallel API requests (up to 64 workers for channel/role deletion).
- **Custom UI**: Frameless window, custom drag/resize edges, `QPainter`-rendered aurora backdrop, glass frame, particle bursts, and real-time stat sparklines.

## Prerequisites

- Python 3.9+
- Discord User or Bot Token
- Target Guild ID

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yuvi123se/mr-nuker.git
cd mr-nuker
