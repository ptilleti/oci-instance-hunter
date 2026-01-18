# OCI Instance Hunter

Automatically create an Oracle Cloud Infrastructure (OCI) Always Free instance by retrying when capacity is unavailable.

## Problem Statement

OCI's Always Free tier is excellent, but ARM-based instances (and sometimes AMD) often show "Out of Capacity" errors. This tool automatically retries instance creation until it succeeds.

## How It Works

1. Checks if instance already exists (by display name)
2. If not, attempts to create it with your specifications
3. On success, creates a flag file and stops
4. On capacity error, logs and exits (to be retried by scheduler)
5. On other errors, logs details for troubleshooting

## Scheduling Options

### Windows Task Scheduler (Recommended for Windows)
Run the Python script every 5-15 minutes. The script exits quickly if instance exists.

Command: `uv run python C:\path\to\oci-instance-hunter\create_instance.py`

### Linux Cron
Add to crontab: `*/10 * * * * cd /path/to/project && uv run python create_instance.py`

## Project Structure

```
oci-instance-hunter/
├── .env                      # Your configuration (create from .env.example)
├── .env.example              # Template
├── pyproject.toml            # Project metadata and dependencies
├── create_instance.py        # Main script (to be created)
├── helper_scripts.py         # Helper to fetch OCIDs (to be created)
├── config/
│   ├── oci_api_key.pem      # Your OCI API private key (you provide)
│   └── ssh_key.pub          # Your SSH public key (you provide)
├── logs/
│   └── attempts.log         # Automatically created
├── .venv/                    # Virtual environment (created by uv sync)
└── .instance_created        # Flag file (created on success)
```

## Setup Instructions

See [SETUP_GUIDE.md](SETUP_GUIDE.md) for detailed setup instructions.

## Quick Start

1. Install uv: `curl -LsSf https://astral.sh/uv/install.sh | sh` (or see [uv docs](https://github.com/astral-sh/uv))
2. Sync dependencies: `uv sync`
3. Copy `.env.example` to `.env`
4. Follow [SETUP_GUIDE.md](SETUP_GUIDE.md) to gather required information
5. Fill in `.env` with your details
6. Run helper script to validate: `uv run python helper_scripts.py`
7. Test manual run: `uv run python create_instance.py`
8. Set up scheduled execution

## Usage

### Main Script - create_instance.py

```bash
# Default: Try all availability domains
uv run python create_instance.py

# Verbose output
uv run python create_instance.py -v

# Validate config without creating
uv run python create_instance.py --dry-run

# Use single AD only
uv run python create_instance.py --no-cycle

# Force creation (ignore flag file)
uv run python create_instance.py --force
```

### Helper Script - helper_scripts.py

```bash
# Validate configuration
uv run python helper_scripts.py --validate

# Test authentication
uv run python helper_scripts.py --test-auth

# List availability domains
uv run python helper_scripts.py --list-ads

# List available images
uv run python helper_scripts.py --list-images

# Find images for specific shape/OS
uv run python helper_scripts.py --list-images --shape VM.Standard.A1.Flex --os "Canonical Ubuntu"

# List compute shapes
uv run python helper_scripts.py --list-shapes
```

For detailed usage documentation, see [USAGE.md](USAGE.md).

## Free Tier Shapes

- **VM.Standard.A1.Flex** (ARM): Up to 4 OCPUs, 24GB RAM (recommended)
- **VM.Standard.E2.1.Micro** (AMD): 1 OCPU, 1GB RAM

## Notes

- The script is idempotent - safe to run multiple times
- Logs all attempts to `logs/attempts.log`
- Once instance is created, script exits immediately on future runs
- Delete `.instance_created` flag to allow script to run again

## Troubleshooting

Check `logs/attempts.log` for detailed error messages and timestamps.
