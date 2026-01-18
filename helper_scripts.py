#!/usr/bin/env python3
"""
OCI Instance Hunter - Helper Scripts

Utilities to help gather information from OCI and validate configuration.
"""

import argparse
import sys
from pathlib import Path
from typing import Optional

try:
    import oci
    from dotenv import load_dotenv
    import os
except ImportError:
    print("ERROR: Required packages not installed.")
    print("Run: uv sync")
    sys.exit(1)

try:
    from colorama import init, Fore, Style
    init(autoreset=True)
    HAS_COLOR = True
except ImportError:
    HAS_COLOR = False
    class Fore:
        GREEN = RED = YELLOW = CYAN = BLUE = MAGENTA = ""
    class Style:
        BRIGHT = RESET_ALL = ""


def load_config():
    """Load configuration from .env file."""
    env_path = Path(__file__).parent / ".env"
    if not env_path.exists():
        print(f"{Fore.RED}ERROR: .env file not found!")
        print(f"{Fore.YELLOW}Copy .env.example to .env and fill in your details.")
        sys.exit(1)
    
    load_dotenv(env_path)
    return {
        'user': os.getenv('OCI_USER_OCID'),
        'tenancy': os.getenv('OCI_TENANCY_OCID'),
        'region': os.getenv('OCI_REGION'),
        'fingerprint': os.getenv('OCI_FINGERPRINT'),
        'key_file': os.getenv('OCI_KEY_FILE'),
        'compartment': os.getenv('OCI_COMPARTMENT_OCID'),
    }


def create_oci_config(config: dict) -> dict:
    """Create OCI SDK config from environment variables."""
    key_file_path = Path(config['key_file'])
    if not key_file_path.is_absolute():
        key_file_path = Path(__file__).parent / key_file_path
    
    return {
        'user': config['user'],
        'tenancy': config['tenancy'],
        'region': config['region'],
        'fingerprint': config['fingerprint'],
        'key_file': str(key_file_path),
    }


def test_authentication(config: dict) -> bool:
    """Test OCI authentication."""
    print(f"\n{Fore.CYAN}{'='*60}")
    print(f"{Fore.CYAN}Testing OCI Authentication...")
    print(f"{Fore.CYAN}{'='*60}\n")
    
    try:
        oci_config = create_oci_config(config)
        identity_client = oci.identity.IdentityClient(oci_config)
        
        # Test by getting user details
        user = identity_client.get_user(config['user']).data
        print(f"{Fore.GREEN}✓ Authentication successful!")
        print(f"  User: {user.name}")
        print(f"  Email: {user.email or 'N/A'}")
        print(f"  Region: {config['region']}")
        
        return True
    except oci.exceptions.ConfigFileNotFound as e:
        print(f"{Fore.RED}✗ Config file not found: {e}")
        return False
    except oci.exceptions.InvalidPrivateKey as e:
        print(f"{Fore.RED}✗ Invalid private key: {e}")
        print(f"{Fore.YELLOW}  Check that OCI_KEY_FILE path is correct")
        return False
    except oci.exceptions.ServiceError as e:
        print(f"{Fore.RED}✗ Service error: {e.message}")
        print(f"{Fore.YELLOW}  Status: {e.status}")
        return False
    except Exception as e:
        print(f"{Fore.RED}✗ Authentication failed: {e}")
        return False


def list_availability_domains(config: dict):
    """List all availability domains in the tenancy."""
    print(f"\n{Fore.CYAN}{'='*60}")
    print(f"{Fore.CYAN}Availability Domains in {config['region']}")
    print(f"{Fore.CYAN}{'='*60}\n")
    
    try:
        oci_config = create_oci_config(config)
        identity_client = oci.identity.IdentityClient(oci_config)
        
        ads = identity_client.list_availability_domains(
            compartment_id=config['compartment']
        ).data
        
        if not ads:
            print(f"{Fore.YELLOW}No availability domains found.")
            return
        
        print(f"Found {len(ads)} availability domain(s):\n")
        for i, ad in enumerate(ads, 1):
            print(f"{Fore.GREEN}{i}. {ad.name}")
        
        print(f"\n{Fore.CYAN}Copy one of these to AVAILABILITY_DOMAIN in your .env file")
        
    except Exception as e:
        print(f"{Fore.RED}✗ Failed to list availability domains: {e}")


def list_images(config: dict, shape: Optional[str] = None, os_name: Optional[str] = None):
    """List available images for a given shape."""
    print(f"\n{Fore.CYAN}{'='*60}")
    print(f"{Fore.CYAN}Available Images")
    print(f"{Fore.CYAN}{'='*60}\n")
    
    shape = shape or os.getenv('INSTANCE_SHAPE', 'VM.Standard.A1.Flex')
    print(f"Shape: {Fore.YELLOW}{shape}")
    if os_name:
        print(f"OS Filter: {Fore.YELLOW}{os_name}")
    print()
    
    try:
        oci_config = create_oci_config(config)
        compute_client = oci.core.ComputeClient(oci_config)
        
        # List images
        list_images_kwargs = {
            'compartment_id': config['compartment'],
            'sort_by': 'TIMECREATED',
            'sort_order': 'DESC',
            'lifecycle_state': 'AVAILABLE',
        }
        
        if os_name:
            list_images_kwargs['operating_system'] = os_name
        
        images = compute_client.list_images(**list_images_kwargs).data
        
        if not images:
            print(f"{Fore.YELLOW}No images found.")
            return
        
        # Filter by shape compatibility
        compatible_images = []
        for img in images:
            # Check if shape is compatible (simplified - may need more checks)
            if 'A1' in shape and 'aarch64' in img.display_name.lower():
                compatible_images.append(img)
            elif 'E2' in shape and 'aarch64' not in img.display_name.lower():
                compatible_images.append(img)
            elif not shape or 'A1' not in shape and 'E2' not in shape:
                compatible_images.append(img)
        
        if not compatible_images:
            print(f"{Fore.YELLOW}No compatible images found for shape {shape}")
            print(f"{Fore.YELLOW}Try a different OS filter or check shape name")
            return
        
        # Group by OS
        os_groups = {}
        for img in compatible_images[:50]:  # Limit to 50 most recent
            os_key = img.operating_system
            if os_key not in os_groups:
                os_groups[os_key] = []
            os_groups[os_key].append(img)
        
        for os_name, imgs in os_groups.items():
            print(f"\n{Fore.MAGENTA}{Style.BRIGHT}{os_name}:")
            for img in imgs[:5]:  # Show top 5 per OS
                print(f"  {Fore.GREEN}• {img.display_name}")
                print(f"    {Fore.CYAN}OCID: {Fore.YELLOW}{img.id}")
                print(f"    {Fore.CYAN}Size: {img.size_in_mbs} MB")
                print()
        
        print(f"{Fore.CYAN}Copy the OCID of your preferred image to IMAGE_OCID in .env")
        
    except Exception as e:
        print(f"{Fore.RED}✗ Failed to list images: {e}")


def list_shapes(config: dict):
    """List available compute shapes."""
    print(f"\n{Fore.CYAN}{'='*60}")
    print(f"{Fore.CYAN}Available Compute Shapes")
    print(f"{Fore.CYAN}{'='*60}\n")
    
    try:
        oci_config = create_oci_config(config)
        compute_client = oci.core.ComputeClient(oci_config)
        
        shapes = compute_client.list_shapes(
            compartment_id=config['compartment']
        ).data
        
        # Filter for Always Free eligible shapes
        free_shapes = [s for s in shapes if 'A1' in s.shape or 'E2.1.Micro' in s.shape]
        
        print(f"{Fore.GREEN}Always Free Eligible Shapes:\n")
        for shape in free_shapes:
            print(f"  {Fore.YELLOW}{shape.shape}")
            if hasattr(shape, 'ocpus'):
                print(f"    OCPUs: {shape.ocpus}, Memory: {shape.memory_in_gbs} GB")
            print()
        
        print(f"{Fore.CYAN}Note: VM.Standard.A1.Flex allows up to 4 OCPUs and 24GB RAM total (free)")
        print(f"{Fore.CYAN}      VM.Standard.E2.1.Micro: 1 OCPU, 1GB RAM (2 instances free)")
        
    except Exception as e:
        print(f"{Fore.RED}✗ Failed to list shapes: {e}")


def validate_config(config: dict):
    """Validate the configuration."""
    print(f"\n{Fore.CYAN}{'='*60}")
    print(f"{Fore.CYAN}Validating Configuration")
    print(f"{Fore.CYAN}{'='*60}\n")
    
    errors = []
    warnings = []
    
    # Check required fields
    required_fields = ['user', 'tenancy', 'region', 'fingerprint', 'key_file', 'compartment']
    for field in required_fields:
        if not config.get(field):
            errors.append(f"Missing {field.upper().replace('_', ' ')}")
    
    # Check key file exists
    key_file = Path(config.get('key_file', ''))
    if not key_file.is_absolute():
        key_file = Path(__file__).parent / key_file
    
    if not key_file.exists():
        errors.append(f"Private key file not found: {key_file}")
    
    # Check SSH key file
    ssh_key = os.getenv('SSH_PUBLIC_KEY_FILE')
    if ssh_key:
        ssh_key_path = Path(ssh_key)
        if not ssh_key_path.is_absolute():
            ssh_key_path = Path(__file__).parent / ssh_key_path
        if not ssh_key_path.exists():
            errors.append(f"SSH public key file not found: {ssh_key_path}")
    else:
        warnings.append("SSH_PUBLIC_KEY_FILE not set")
    
    # Check other important env vars
    required_env_vars = [
        'INSTANCE_DISPLAY_NAME',
        'AVAILABILITY_DOMAIN',
        'INSTANCE_SHAPE',
        'SUBNET_OCID',
        'IMAGE_OCID',
    ]
    
    for var in required_env_vars:
        if not os.getenv(var):
            errors.append(f"Missing {var} in .env")
    
    # Print results
    if errors:
        print(f"{Fore.RED}✗ Configuration Errors:\n")
        for error in errors:
            print(f"  {Fore.RED}• {error}")
        print()
    
    if warnings:
        print(f"{Fore.YELLOW}⚠ Warnings:\n")
        for warning in warnings:
            print(f"  {Fore.YELLOW}• {warning}")
        print()
    
    if not errors and not warnings:
        print(f"{Fore.GREEN}✓ Configuration looks good!\n")
        return True
    elif not errors:
        print(f"{Fore.GREEN}✓ No critical errors (warnings only)\n")
        return True
    else:
        print(f"{Fore.RED}✗ Please fix the errors above before proceeding.\n")
        return False


def main():
    parser = argparse.ArgumentParser(
        description='OCI Instance Hunter - Helper Scripts',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    
    parser.add_argument('--test-auth', action='store_true',
                       help='Test OCI authentication')
    parser.add_argument('--list-ads', action='store_true',
                       help='List availability domains')
    parser.add_argument('--list-images', action='store_true',
                       help='List available images')
    parser.add_argument('--list-shapes', action='store_true',
                       help='List available compute shapes')
    parser.add_argument('--validate', action='store_true',
                       help='Validate configuration')
    parser.add_argument('--shape', type=str,
                       help='Filter images by shape (e.g., VM.Standard.A1.Flex)')
    parser.add_argument('--os', type=str,
                       help='Filter images by OS (e.g., "Canonical Ubuntu", "Oracle Linux")')
    
    args = parser.parse_args()
    
    # If no arguments, show help and run validate
    if len(sys.argv) == 1:
        parser.print_help()
        print(f"\n{Fore.YELLOW}Running validation by default...\n")
        args.validate = True
    
    # Load config
    config = load_config()
    
    # Run requested operations
    success = True
    
    if args.test_auth:
        success = test_authentication(config) and success
    
    if args.list_ads:
        list_availability_domains(config)
    
    if args.list_images:
        list_images(config, shape=args.shape, os_name=args.os)
    
    if args.list_shapes:
        list_shapes(config)
    
    if args.validate:
        success = validate_config(config) and success
        if success:
            success = test_authentication(config) and success
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
