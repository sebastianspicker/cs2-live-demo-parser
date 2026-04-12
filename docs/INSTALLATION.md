# Installation

## Requirements
- Python 3.8+
- pip
- Windows, macOS, or Linux

## Windows
```powershell
# From PowerShell
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```
This installs demoparser2 from PyPI (no local build needed).

## macOS
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```
This installs demoparser2 from PyPI (no local build needed).

## Linux
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```
This installs demoparser2 from PyPI (no local build needed).

## Run
```bash
python server/main.py
```

Optional configuration lives in `config.json` and `maps/`.

Common flags:
- `--demo-dir` to point to a custom demo folder.
- `--poll-interval` to change the live parsing cadence.
- `--no-msgpack` to force JSON messages.
- `--parser-executor` (`none`, `thread`, `process`) for parser isolation.
- `--metrics-port 8766` to enable a JSON metrics endpoint.
