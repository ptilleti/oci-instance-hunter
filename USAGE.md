# Usage Guide

Complete guide to using OCI Instance Hunter scripts and their command-line options.

---

## Table of Contents

- [create_instance.py - Main Script](#create_instancepy---main-script)
- [helper_scripts.py - Configuration Helper](#helper_scriptspy---configuration-helper)
- [Common Workflows](#common-workflows)
- [Troubleshooting](#troubleshooting)

---

## create_instance.py - Main Script

The main script that attempts to create an OCI instance.

### Basic Usage

```bash
# Default: Try to create instance across all ADs
uv run python create_instance.py

# Verbose output (see detailed logs)
uv run python create_instance.py -v
```

### Command-Line Options

#### `-v, --verbose`
Enable verbose logging (DEBUG level) to see detailed information.

**Example:**
```bash
uv run python create_instance.py --verbose
```

**Use when:**
- Troubleshooting issues
- Understanding what the script is doing
- Debugging API calls

---

#### `--dry-run`
Validate configuration without actually creating an instance.

**Example:**
```bash
uv run python create_instance.py --dry-run
```

**What it does:**
- ✓ Loads and validates configuration
- ✓ Tests OCI authentication
- ✓ Checks for existing instance
- ✗ Does NOT create instance
- ✗ Does NOT make any changes

**Use when:**
- First time setup to verify everything is configured correctly
- Testing after changing configuration
- Validating credentials before scheduling

---

#### `--no-cycle`
Use only one availability domain instead of cycling through all.

**Example:**
```bash
# Uses AVAILABILITY_DOMAIN from .env
uv run python create_instance.py --no-cycle

# If AVAILABILITY_DOMAIN not set, uses first AD found
uv run python create_instance.py --no-cycle
```

**Behavior:**
- **With this flag:** Tries only the specified AD (or first one)
- **Without this flag (default):** Cycles through ALL availability domains

**Use when:**
- You know which AD has better capacity
- You want to limit attempts to a specific AD
- Testing a particular availability domain

---

#### `--force`
Force creation even if flag file exists (allows creating another instance).

**Example:**
```bash
uv run python create_instance.py --force
```

**What it does:**
- Ignores the `.instance_created` flag file
- Attempts to create instance even if one was already created
- Uses the same display name (may cause conflict)

**Use when:**
- You want to create multiple instances with different names (change `INSTANCE_DISPLAY_NAME` in `.env` first)
- The flag file exists but instance was manually deleted
- Testing the script repeatedly

**Warning:** Make sure to change `INSTANCE_DISPLAY_NAME` in `.env` to avoid naming conflicts!

---

### Exit Codes

- `0` - Success (instance created or already exists)
- `1` - Failure (capacity errors, configuration issues, etc.)
- `130` - Interrupted by user (Ctrl+C)

---

## helper_scripts.py - Configuration Helper

Utility script to help gather OCI information and validate configuration.

### Basic Usage

```bash
# Run without arguments to validate configuration
uv run python helper_scripts.py

# Or explicitly validate
uv run python helper_scripts.py --validate
```

### Command-Line Options

#### `--validate`
Validate complete configuration and test authentication.

**Example:**
```bash
uv run python helper_scripts.py --validate
```

**Checks:**
- ✓ All required fields in `.env` are present
- ✓ OCI API key file exists
- ✓ SSH public key file exists
- ✓ OCI authentication works
- ✓ Can connect to OCI API

**Output:** Detailed report of any errors or warnings

---

#### `--test-auth`
Test OCI authentication only.

**Example:**
```bash
uv run python helper_scripts.py --test-auth
```

**Output:**
- User name and email
- Region configured
- Confirms API keys are working

**Use when:**
- Verifying API key setup
- Troubleshooting authentication issues
- Testing after updating fingerprint

---

#### `--list-ads`
List all availability domains in your region.

**Example:**
```bash
uv run python helper_scripts.py --list-ads
```

**Output:**
```
Availability Domains in us-ashburn-1
============================================================

Found 3 availability domain(s):

1. aBCD:US-ASHBURN-AD-1
2. aBCD:US-ASHBURN-AD-2
3. aBCD:US-ASHBURN-AD-3

Copy one of these to AVAILABILITY_DOMAIN in your .env file
```

**Use when:**
- Setting up `.env` for the first time
- You need to know the exact AD name format
- Testing with `--no-cycle` flag

---

#### `--list-images`
List available OS images compatible with your shape.

**Example:**
```bash
# List all images for default shape (from .env)
uv run python helper_scripts.py --list-images

# List images for specific shape
uv run python helper_scripts.py --list-images --shape VM.Standard.A1.Flex

# Filter by OS
uv run python helper_scripts.py --list-images --os "Canonical Ubuntu"
uv run python helper_scripts.py --list-images --os "Oracle Linux"
```

**Output:**
- Grouped by operating system
- Shows display name, OCID, and size
- Sorted by most recent first
- Shows top 5 per OS

**Use when:**
- Finding the IMAGE_OCID for `.env`
- Choosing which OS to use
- Checking what's available for ARM vs AMD

---

#### `--list-shapes`
List available compute shapes (especially Always Free eligible ones).

**Example:**
```bash
uv run python helper_scripts.py --list-shapes
```

**Output:**
- Shows Always Free eligible shapes
- Lists OCPU and memory specs
- Highlights free tier limits

**Use when:**
- Deciding between ARM (A1.Flex) vs AMD (E2.1.Micro)
- Checking what shapes are available in your region
- Verifying shape specifications

---

#### `--shape SHAPE_NAME`
Filter images by shape (used with `--list-images`).

**Example:**
```bash
uv run python helper_scripts.py --list-images --shape VM.Standard.A1.Flex
```

**Common shapes:**
- `VM.Standard.A1.Flex` - ARM, up to 4 OCPU / 24GB RAM free
- `VM.Standard.E2.1.Micro` - AMD, 1 OCPU / 1GB RAM free

---

#### `--os OS_NAME`
Filter images by operating system (used with `--list-images`).

**Example:**
```bash
uv run python helper_scripts.py --list-images --os "Canonical Ubuntu"
uv run python helper_scripts.py --list-images --os "Oracle Linux"
```

**Common OS names:**
- `"Canonical Ubuntu"` - Ubuntu images
- `"Oracle Linux"` - Oracle Linux images
- `"CentOS"` - CentOS images (if available)

---

## Common Workflows

### First Time Setup

```bash
# 1. Install dependencies
uv sync

# 2. Create .env from template
cp .env.example .env

# 3. Test authentication (after filling basic .env fields)
uv run python helper_scripts.py --test-auth

# 4. Get availability domains
uv run python helper_scripts.py --list-ads

# 5. Find an image OCID
uv run python helper_scripts.py --list-images --shape VM.Standard.A1.Flex

# 6. Complete your .env file, then validate
uv run python helper_scripts.py --validate

# 7. Dry run to test
uv run python create_instance.py --dry-run

# 8. First real attempt
uv run python create_instance.py -v
```

---

### Regular Usage (Scheduled)

```bash
# Run on schedule (Windows Task Scheduler or cron)
uv run python create_instance.py

# Script will:
# - Check flag file (exit if exists)
# - Check for existing instance
# - Try all ADs and FDs until success
# - Create flag on success
```

---

### Testing Specific Configuration

```bash
# Test only one availability domain
uv run python create_instance.py --no-cycle -v

# Force re-attempt (ignore flag file)
uv run python create_instance.py --force -v

# Validate without creating
uv run python create_instance.py --dry-run
```

---

### Troubleshooting

```bash
# Check authentication
uv run python helper_scripts.py --test-auth

# Full validation
uv run python helper_scripts.py --validate

# Verbose creation attempt
uv run python create_instance.py -v

# Check logs
cat logs/attempts.log
```

---

## Troubleshooting

### "Out of capacity" errors

**Normal!** This is why the tool exists. Solutions:

1. **Schedule regularly** - Run every 10-15 minutes via Task Scheduler/cron
2. **Try off-peak hours** - Early morning UTC often has better capacity
3. **Try different region** - Update `OCI_REGION` in `.env`
4. **Consider E2.1.Micro** - AMD instances have better availability (but less powerful)

### "Authentication failed"

```bash
# Verify API key setup
uv run python helper_scripts.py --test-auth

# Common issues:
# - Wrong fingerprint in .env
# - API key file path incorrect
# - API key not added to OCI Console
# - Wrong user OCID
```

### "Image not compatible with shape"

```bash
# Find compatible images
uv run python helper_scripts.py --list-images --shape VM.Standard.A1.Flex

# Note:
# - ARM shapes (A1) need ARM images (aarch64)
# - AMD shapes (E2) need AMD64 images
```

### Script runs but nothing happens

```bash
# Check if flag file exists
ls -la .instance_created

# If exists, either:
# 1. Instance was already created (check OCI Console)
# 2. Use --force to override

# Remove flag to allow new attempts
rm .instance_created
```

### "Quota exceeded" or "Limit reached"

Not a capacity issue - you've hit Always Free limits:
- **A1.Flex:** Maximum 4 OCPU and 24GB RAM total
- **E2.1.Micro:** Maximum 2 instances

Check OCI Console for existing instances.

---

## Tips

### Maximize Success Rate

1. **Run on schedule** - Constant attempts increase success probability
2. **Use default (cycle all ADs)** - More attempts = better odds
3. **Try multiple regions** - Some regions have better capacity
4. **Be patient** - May take hours or days during high demand

### Monitoring Progress

```bash
# Watch logs in real-time (Linux/Mac)
tail -f logs/attempts.log

# Check recent attempts (Windows PowerShell)
Get-Content logs\attempts.log -Tail 50
```

### Multiple Instances

To create multiple instances:

1. Wait for first instance to succeed
2. Update `INSTANCE_DISPLAY_NAME` in `.env`
3. Run with `--force` flag:
   ```bash
   uv run python create_instance.py --force
   ```

### Cleanup

Delete instance that's no longer needed:

```bash
# 1. Terminate instance in OCI Console
# 2. Remove flag file to allow new creation
rm .instance_created
```

---

## Environment Variables Reference

Quick reference of `.env` variables (see `SETUP_GUIDE.md` for details):

### Required
- `OCI_USER_OCID` - Your user OCID
- `OCI_TENANCY_OCID` - Your tenancy OCID
- `OCI_REGION` - Region (e.g., `us-ashburn-1`)
- `OCI_FINGERPRINT` - API key fingerprint
- `OCI_KEY_FILE` - Path to API private key
- `OCI_COMPARTMENT_OCID` - Compartment OCID
- `INSTANCE_DISPLAY_NAME` - Instance name
- `INSTANCE_SHAPE` - Shape (e.g., `VM.Standard.A1.Flex`)
- `SUBNET_OCID` - Subnet OCID
- `IMAGE_OCID` - Image OCID
- `SSH_PUBLIC_KEY_FILE` - Path to SSH public key

### Shape-Specific (Flex shapes only)
- `INSTANCE_OCPUS` - Number of OCPUs (default: 4)
- `INSTANCE_MEMORY_IN_GBS` - Memory in GB (default: 24)

### Optional
- `AVAILABILITY_DOMAIN` - Specific AD (only used with `--no-cycle`)
- `BOOT_VOLUME_SIZE_IN_GBS` - Boot volume size (default: 50)

---

## Quick Command Reference

| Command | Description |
|---------|-------------|
| `uv run python create_instance.py` | Create instance (default behavior) |
| `uv run python create_instance.py -v` | Verbose creation attempt |
| `uv run python create_instance.py --dry-run` | Validate config without creating |
| `uv run python create_instance.py --no-cycle` | Use single AD only |
| `uv run python create_instance.py --force` | Override flag file |
| `uv run python helper_scripts.py` | Validate configuration |
| `uv run python helper_scripts.py --test-auth` | Test OCI authentication |
| `uv run python helper_scripts.py --list-ads` | List availability domains |
| `uv run python helper_scripts.py --list-images` | List available images |
| `uv run python helper_scripts.py --list-shapes` | List compute shapes |

---

For setup instructions, see [SETUP_GUIDE.md](SETUP_GUIDE.md).

For general information, see [README.md](README.md).
