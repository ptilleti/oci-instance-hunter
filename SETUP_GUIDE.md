# OCI Instance Hunter - Setup Guide

Complete this checklist before running the instance creation script.

## Prerequisites

- [ ] OCI Account (Always Free tier)
- [ ] Python 3.7+ installed
- [ ] Basic familiarity with OCI Console

---

## Step 1: Install Python Dependencies

### First, install uv (if not already installed):

**Windows (PowerShell):**
```powershell
irm https://astral.sh/uv/install.ps1 | iex
```

**Linux/Mac:**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Then sync dependencies:

```bash
uv sync
```

This reads `pyproject.toml` and creates a virtual environment with all dependencies installed.

---

## Step 2: Generate OCI API Keys

These keys allow the Python SDK to authenticate with OCI.

### On Windows (PowerShell):
```powershell
mkdir config
ssh-keygen -t rsa -b 4096 -f config\oci_api_key.pem
```

### On Linux/Mac:
```bash
mkdir -p config
openssl genrsa -out config/oci_api_key.pem 4096
openssl rsa -pubout -in config/oci_api_key.pem -out config/oci_api_key_public.pem
```

**Result:** You should have `config/oci_api_key.pem` (private key)

---

## Step 3: Add API Key to OCI Console

1. Log into OCI Console: https://cloud.oracle.com/
2. Click your profile icon (top right) → **User Settings**
3. Under **Resources** (left sidebar) → **API Keys**
4. Click **Add API Key**
5. Choose **Paste Public Key**
6. Paste contents of `config/oci_api_key_public.pem`
7. Click **Add**

**IMPORTANT:** After adding, OCI shows a configuration file preview. **Copy the fingerprint value** - you'll need it for `.env`

---

## Step 4: Gather Required OCIDs

You need to collect several OCIDs from OCI Console. Here's where to find them:

### 4.1 User OCID
1. Profile icon → **User Settings**
2. Copy the OCID under your username (starts with `ocid1.user.oc1..`)

### 4.2 Tenancy OCID
1. Profile icon → **Tenancy: [your-tenancy-name]**
2. Copy the Tenancy OCID (starts with `ocid1.tenancy.oc1..`)

### 4.3 Region
1. Look at the top-left of the console (e.g., "US East (Ashburn)")
2. The region identifier is like: `us-ashburn-1`, `us-phoenix-1`, `eu-frankfurt-1`
3. Full list: https://docs.oracle.com/en-us/iaas/Content/General/Concepts/regions.htm

### 4.4 Compartment OCID
1. Navigation Menu (≡) → **Identity & Security** → **Compartments**
2. Find your compartment (or use root compartment)
3. Copy the OCID (starts with `ocid1.compartment.oc1..` or `ocid1.tenancy.oc1..` for root)

### 4.5 VCN and Subnet OCID
**If you don't have a VCN yet:**
1. Navigation Menu → **Networking** → **Virtual Cloud Networks**
2. Click **Start VCN Wizard** → **Create VCN with Internet Connectivity**
3. Give it a name, keep defaults, click **Next** → **Create**

**To get Subnet OCID:**
1. Go to your VCN
2. Click **Subnets** under Resources
3. Click on the public subnet
4. Copy the Subnet OCID (starts with `ocid1.subnet.oc1..`)

### 4.6 Availability Domain
1. Navigation Menu → **Compute** → **Instances**
2. Click **Create Instance** (don't worry, we won't create it manually)
3. Under **Placement**, note the Availability Domain format (e.g., `aBCD:US-ASHBURN-AD-1`)
4. Try different ADs - some have better capacity
5. Cancel the manual creation

**Tip:** You can also run our helper script (after setup) to list available ADs.

### 4.7 Image OCID
You need the OS image OCID. Common options:

**For ARM (A1.Flex):**
1. Navigation Menu → **Compute** → **Instances** → **Create Instance**
2. Under Image and Shape → **Change Image**
3. Select your OS (e.g., Ubuntu 22.04, Oracle Linux 8)
4. Make sure it's compatible with ARM (it will say "A1" or show ARM architecture)
5. Copy the Image OCID from the image details (starts with `ocid1.image.oc1..`)

**For AMD (E2.1.Micro):**
- Same process, but pick an AMD64-compatible image

**Tip:** Our helper script can also list available images for your region and shape.

---

## Step 5: Generate SSH Keys (for Instance Access)

These are different from API keys - these are for SSH access to your instance.

### If you already have SSH keys:
```bash
# Copy your public key
cp ~/.ssh/id_rsa.pub config/ssh_key.pub
```

### If you need to generate new ones:

**Windows (PowerShell):**
```powershell
ssh-keygen -t rsa -b 4096 -f config\ssh_key
```

**Linux/Mac:**
```bash
ssh-keygen -t rsa -b 4096 -f config/ssh_key
```

This creates:
- `config/ssh_key` (private - keep safe!)
- `config/ssh_key.pub` (public - will be added to instance)

---

## Step 6: Create and Configure .env File

1. Copy the template:
   ```bash
   cp .env.example .env
   ```

2. Open `.env` in a text editor

3. Fill in all the values you gathered:

   ```bash
   # Example filled in (use YOUR values!)
   OCI_USER_OCID=ocid1.user.oc1..aaaaaaaaexampleuserocid
   OCI_TENANCY_OCID=ocid1.tenancy.oc1..aaaaaaaaexampletenancyocid
   OCI_REGION=us-ashburn-1
   OCI_FINGERPRINT=aa:bb:cc:dd:ee:ff:00:11:22:33:44:55:66:77:88:99
   OCI_KEY_FILE=config/oci_api_key.pem
   OCI_COMPARTMENT_OCID=ocid1.compartment.oc1..aaaaaaaaexamplecompartmentocid
   
   INSTANCE_DISPLAY_NAME=my-free-instance
   AVAILABILITY_DOMAIN=aBCD:US-ASHBURN-AD-1
   INSTANCE_SHAPE=VM.Standard.A1.Flex
   INSTANCE_OCPUS=4
   INSTANCE_MEMORY_IN_GBS=24
   SUBNET_OCID=ocid1.subnet.oc1..aaaaaaaaexamplesubnetocid
   IMAGE_OCID=ocid1.image.oc1..aaaaaaaaexampleimageocid
   SSH_PUBLIC_KEY_FILE=config/ssh_key.pub
   BOOT_VOLUME_SIZE_IN_GBS=50
   
   CHECK_INTERVAL_SECONDS=300
   MAX_RETRIES=0
   ```

---

## Step 7: Verify Your Configuration

Once we create the helper script, you can run:

```bash
python helper_scripts.py --validate
```

This will check:
- ✓ API authentication works
- ✓ All OCIDs are valid
- ✓ Files exist (keys, etc.)
- ✓ Image is compatible with shape
- ✓ Subnet is in the right compartment

---

## Step 8: Choose Your Instance Type

### ARM - VM.Standard.A1.Flex (Recommended)
- **Always Free Limit:** 4 OCPUs, 24GB RAM total across all ARM instances
- **Best for:** General purpose, good performance
- **Caveat:** Often out of capacity - that's why we need this tool!

```bash
INSTANCE_SHAPE=VM.Standard.A1.Flex
INSTANCE_OCPUS=4
INSTANCE_MEMORY_IN_GBS=24
```

### AMD - VM.Standard.E2.1.Micro
- **Always Free Limit:** 2 instances, 1 OCPU, 1GB RAM each
- **Best for:** Lightweight tasks, better availability
- **Caveat:** Less powerful

```bash
INSTANCE_SHAPE=VM.Standard.E2.1.Micro
# OCPUS and MEMORY not needed for micro shape
```

---

## Checklist Before Running

- [ ] `uv` installed
- [ ] Dependencies installed with `uv sync`
- [ ] `config/oci_api_key.pem` exists (API private key)
- [ ] API public key added to OCI Console
- [ ] `config/ssh_key.pub` exists (SSH public key)
- [ ] `.env` file created and filled with all OCIDs
- [ ] Fingerprint in `.env` matches OCI Console
- [ ] VCN and Subnet created in OCI
- [ ] Image OCID is compatible with chosen shape
- [ ] Availability Domain noted

---

## What's Next?

Once you've completed this setup:

1. Run validation: `uv run python helper_scripts.py --validate`
2. Test creation: `uv run python create_instance.py --dry-run` (if we implement dry-run)
3. First real attempt: `uv run python create_instance.py`
4. Set up scheduling (see README.md)

**Note:** `uv run` automatically uses the virtual environment created by `uv sync`.

---

## Common Issues

### "Invalid key file"
- Make sure path in `OCI_KEY_FILE` is correct
- Make sure the private key file has proper permissions

### "Authorization failed"
- Double-check fingerprint matches OCI Console
- Verify User OCID is correct
- Make sure API key is added to your user (not someone else's)

### "Subnet is in a different compartment"
- Subnet must be in the same compartment as specified in `OCI_COMPARTMENT_OCID`
- Or use the compartment where your subnet exists

### "Image not compatible with shape"
- ARM shapes need ARM images
- AMD shapes need AMD64 images
- Use helper script to find compatible images

---

## Helpful OCI CLI Commands (Optional)

If you want to explore using OCI CLI alongside the Python SDK:

```bash
# List availability domains
oci iam availability-domain list --compartment-id <compartment-ocid>

# List images for a shape
oci compute image list --compartment-id <compartment-ocid> --shape <shape-name>

# List shapes
oci compute shape list --compartment-id <compartment-ocid>
```

---

## Security Notes

- **Never commit** `.env`, `*.pem`, or `*.key` files to git
- `.gitignore` is already configured to prevent this
- Keep your API keys secure
- If compromised, delete the API key from OCI Console and generate new ones

---

## Questions or Issues?

Refer to:
- [OCI Documentation](https://docs.oracle.com/en-us/iaas/Content/home.htm)
- [OCI Python SDK Docs](https://oracle-cloud-infrastructure-python-sdk.readthedocs.io/)

Ready to gather this information? Let me know when you're done and we'll proceed with implementation!
