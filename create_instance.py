#!/usr/bin/env python3
"""
OCI Instance Hunter - Main Script

Automatically attempts to create an OCI Always Free instance by cycling through
availability domains and fault domains until successful.
"""

import os
import sys
import time
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List

try:
    import oci
    from oci.core.models import (
        LaunchInstanceDetails,
        CreateVnicDetails,
        InstanceSourceViaImageDetails,
        LaunchInstanceShapeConfigDetails,
    )
    from dotenv import load_dotenv
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


# Configuration
PROJECT_ROOT = Path(__file__).parent
FLAG_FILE = PROJECT_ROOT / ".instance_created"
LOG_DIR = PROJECT_ROOT / "logs"
LOG_FILE = LOG_DIR / "attempts.log"

# Ensure logs directory exists
LOG_DIR.mkdir(exist_ok=True)


class StripColorFormatter(logging.Formatter):
    """Formatter that strips ANSI color codes from log messages."""
    
    def format(self, record):
        # Strip colorama codes from the message
        if hasattr(record, 'msg'):
            # Remove ANSI escape sequences
            import re
            ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
            record.msg = ansi_escape.sub('', str(record.msg))
        return super().format(record)


def setup_logging(verbose: bool = False) -> logging.Logger:
    """Set up logging configuration."""
    log_level = logging.DEBUG if verbose else logging.INFO
    
    # File handler - always detailed, strips colors
    file_handler = logging.FileHandler(LOG_FILE)
    file_handler.setLevel(logging.DEBUG)
    file_formatter = StripColorFormatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(file_formatter)
    
    # Console handler - respects verbosity, keeps colors
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_formatter = logging.Formatter('%(levelname)s - %(message)s')
    console_handler.setFormatter(console_formatter)
    
    # Configure logger
    logger = logging.getLogger('oci-instance-hunter')
    logger.setLevel(logging.DEBUG)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger


def load_config() -> Dict[str, str]:
    """Load configuration from .env file."""
    env_path = PROJECT_ROOT / ".env"
    if not env_path.exists():
        print(f"{Fore.RED}ERROR: .env file not found!")
        print(f"{Fore.YELLOW}Run: cp .env.example .env")
        print(f"{Fore.YELLOW}Then fill in your OCI details.")
        sys.exit(1)
    
    load_dotenv(env_path)
    
    # Load all configuration
    config = {
        'user': os.getenv('OCI_USER_OCID'),
        'tenancy': os.getenv('OCI_TENANCY_OCID'),
        'region': os.getenv('OCI_REGION'),
        'fingerprint': os.getenv('OCI_FINGERPRINT'),
        'key_file': os.getenv('OCI_KEY_FILE'),
        'compartment': os.getenv('OCI_COMPARTMENT_OCID'),
        'display_name': os.getenv('INSTANCE_DISPLAY_NAME', 'my-always-free-instance'),
        'availability_domain': os.getenv('AVAILABILITY_DOMAIN'),
        'shape': os.getenv('INSTANCE_SHAPE', 'VM.Standard.A1.Flex'),
        'ocpus': os.getenv('INSTANCE_OCPUS', '4'),
        'memory': os.getenv('INSTANCE_MEMORY_IN_GBS', '24'),
        'subnet': os.getenv('SUBNET_OCID'),
        'image': os.getenv('IMAGE_OCID'),
        'ssh_key_file': os.getenv('SSH_PUBLIC_KEY_FILE'),
        'boot_volume_size': os.getenv('BOOT_VOLUME_SIZE_IN_GBS', '50'),
    }
    
    return config


def create_oci_config(config: Dict[str, str]) -> dict:
    """Create OCI SDK config from environment variables."""
    key_file_path = Path(config['key_file'])
    if not key_file_path.is_absolute():
        key_file_path = PROJECT_ROOT / key_file_path
    
    return {
        'user': config['user'],
        'tenancy': config['tenancy'],
        'region': config['region'],
        'fingerprint': config['fingerprint'],
        'key_file': str(key_file_path),
    }


def load_ssh_public_key(config: Dict[str, str]) -> str:
    """Load SSH public key from file."""
    ssh_key_path = Path(config['ssh_key_file'])
    if not ssh_key_path.is_absolute():
        ssh_key_path = PROJECT_ROOT / ssh_key_path
    
    if not ssh_key_path.exists():
        raise FileNotFoundError(f"SSH public key not found: {ssh_key_path}")
    
    return ssh_key_path.read_text().strip()


def check_if_instance_exists(
    compute_client: oci.core.ComputeClient,
    compartment_id: str,
    display_name: str,
    logger: logging.Logger
) -> Optional[object]:
    """Check if an instance with the given display name already exists."""
    logger.debug(f"Checking for existing instance: {display_name}")
    
    try:
        instances = compute_client.list_instances(
            compartment_id=compartment_id,
            display_name=display_name
        ).data
        
        # Filter for non-terminated instances
        active_instances = [
            i for i in instances 
            if i.lifecycle_state not in ['TERMINATED', 'TERMINATING']
        ]
        
        if active_instances:
            return active_instances[0]
        
        return None
    except Exception as e:
        logger.error(f"Error checking for existing instance: {e}")
        return None


def get_all_availability_domains(
    identity_client: oci.identity.IdentityClient,
    compartment_id: str,
    logger: logging.Logger
) -> List[str]:
    """Get all availability domains in the region."""
    logger.debug("Fetching all availability domains")
    
    try:
        ads = identity_client.list_availability_domains(
            compartment_id=compartment_id
        ).data
        
        ad_names = [ad.name for ad in ads]
        logger.info(f"Found {len(ad_names)} availability domains: {', '.join(ad_names)}")
        return ad_names
    except Exception as e:
        logger.error(f"Error fetching availability domains: {e}")
        return []


def get_fault_domains(
    identity_client: oci.identity.IdentityClient,
    compartment_id: str,
    availability_domain: str,
    logger: logging.Logger
) -> List[str]:
    """Get all fault domains in an availability domain."""
    logger.debug(f"Fetching fault domains for {availability_domain}")
    
    try:
        fds = identity_client.list_fault_domains(
            compartment_id=compartment_id,
            availability_domain=availability_domain
        ).data
        
        fd_names = [fd.name for fd in fds]
        logger.debug(f"Found {len(fd_names)} fault domains: {', '.join(fd_names)}")
        return fd_names
    except Exception as e:
        logger.warning(f"Could not fetch fault domains: {e}")
        return []


def create_instance(
    compute_client: oci.core.ComputeClient,
    config: Dict[str, str],
    ssh_public_key: str,
    availability_domain: str,
    fault_domain: Optional[str],
    logger: logging.Logger
) -> tuple[bool, Optional[object], Optional[str]]:
    """
    Attempt to create an instance.
    
    Returns:
        (success, instance, error_type)
        error_type can be: 'capacity', 'quota', 'other', None
    """
    logger.info(f"Attempting to create instance in {availability_domain}" + 
                (f" / {fault_domain}" if fault_domain else ""))
    
    try:
        # Build instance details
        instance_details = LaunchInstanceDetails()
        instance_details.availability_domain = availability_domain
        instance_details.compartment_id = config['compartment']
        instance_details.display_name = config['display_name']
        instance_details.shape = config['shape']
        
        # Shape config for flex shapes
        if 'Flex' in config['shape']:
            shape_config = LaunchInstanceShapeConfigDetails()
            shape_config.ocpus = float(config['ocpus'])
            shape_config.memory_in_gbs = float(config['memory'])
            instance_details.shape_config = shape_config
        
        # Source image
        source_details = InstanceSourceViaImageDetails()
        source_details.image_id = config['image']
        source_details.boot_volume_size_in_gbs = int(config['boot_volume_size'])
        instance_details.source_details = source_details
        
        # Network details
        vnic_details = CreateVnicDetails()
        vnic_details.subnet_id = config['subnet']
        vnic_details.assign_public_ip = True
        instance_details.create_vnic_details = vnic_details
        
        # SSH key
        instance_details.metadata = {
            'ssh_authorized_keys': ssh_public_key
        }
        
        # Fault domain (if specified)
        if fault_domain:
            instance_details.fault_domain = fault_domain
        
        # Launch instance
        logger.debug("Sending launch instance request...")
        response = compute_client.launch_instance(instance_details)
        instance = response.data
        
        logger.info(f"{Fore.GREEN}✓ Instance creation initiated!")
        logger.info(f"  Instance ID: {instance.id}")
        logger.info(f"  State: {instance.lifecycle_state}")
        logger.info(f"  AD: {availability_domain}")
        if fault_domain:
            logger.info(f"  FD: {fault_domain}")
        
        return True, instance, None
        
    except oci.exceptions.ServiceError as e:
        error_msg = str(e.message).lower()
        error_code = e.code
        
        # Categorize error
        if 'capacity' in error_msg or 'out of host capacity' in error_msg:
            error_type = 'capacity'
            logger.warning(f"Capacity error in {availability_domain}" + 
                          (f" / {fault_domain}" if fault_domain else ""))
            logger.debug(f"Error details: {e.message}")
        elif 'quota' in error_msg or 'limit' in error_msg:
            error_type = 'quota'
            logger.error(f"Quota/limit error: {e.message}")
        else:
            error_type = 'other'
            logger.error(f"Service error [{error_code}]: {e.message}")
        
        return False, None, error_type
        
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return False, None, 'other'


def create_success_flag(instance_id: str, logger: logging.Logger):
    """Create a flag file indicating successful instance creation."""
    try:
        FLAG_FILE.write_text(f"{instance_id}\n{datetime.now().isoformat()}\n")
        logger.info(f"Created success flag: {FLAG_FILE}")
    except Exception as e:
        logger.warning(f"Could not create flag file: {e}")


def main():
    """Main execution flow."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='OCI Instance Hunter - Automatically create Always Free instances'
    )
    parser.add_argument('-v', '--verbose', action='store_true',
                       help='Enable verbose logging')
    parser.add_argument('--no-cycle', action='store_true',
                       help='Do not cycle through ADs, only use the one in .env')
    parser.add_argument('--dry-run', action='store_true',
                       help='Validate configuration without creating instance')
    parser.add_argument('--force', action='store_true',
                       help='Force creation even if flag file exists')
    
    args = parser.parse_args()
    
    # Setup
    logger = setup_logging(verbose=args.verbose)
    logger.info("="*60)
    logger.info("OCI Instance Hunter - Starting")
    logger.info("="*60)
    
    # Check flag file
    if FLAG_FILE.exists() and not args.force:
        instance_info = FLAG_FILE.read_text().strip().split('\n')
        logger.info(f"{Fore.GREEN}✓ Instance already created!")
        if instance_info:
            logger.info(f"  Instance ID: {instance_info[0]}")
            if len(instance_info) > 1:
                logger.info(f"  Created at: {instance_info[1]}")
        logger.info(f"  Flag file: {FLAG_FILE}")
        logger.info("\nTo create another instance, delete the flag file:")
        logger.info(f"  rm {FLAG_FILE}")
        return 0
    
    # Load configuration
    logger.info("Loading configuration...")
    config = load_config()
    oci_config = create_oci_config(config)
    
    logger.info(f"Region: {config['region']}")
    logger.info(f"Shape: {config['shape']}")
    logger.info(f"Display Name: {config['display_name']}")
    
    if args.dry_run:
        logger.info("")
        logger.info(Fore.YELLOW + "DRY RUN MODE - No instance will be created")
    
    # Load SSH key
    try:
        ssh_public_key = load_ssh_public_key(config)
        logger.debug("SSH public key loaded")
    except FileNotFoundError as e:
        logger.error(f"SSH key error: {e}")
        return 1
    
    # Initialize OCI clients
    logger.info("Initializing OCI clients...")
    try:
        compute_client = oci.core.ComputeClient(oci_config)
        identity_client = oci.identity.IdentityClient(oci_config)
    except Exception as e:
        logger.error(f"Failed to initialize OCI clients: {e}")
        logger.error("Check your .env configuration and API keys")
        return 1
    
    # Check if instance already exists
    logger.info("Checking for existing instance...")
    existing_instance = check_if_instance_exists(
        compute_client,
        config['compartment'],
        config['display_name'],
        logger
    )
    
    if existing_instance:
        logger.info(f"{Fore.GREEN}✓ Instance already exists!")
        logger.info(f"  Instance ID: {existing_instance.id}")
        logger.info(f"  State: {existing_instance.lifecycle_state}")
        logger.info(f"  AD: {existing_instance.availability_domain}")
        
        # Create flag file if it doesn't exist
        if not FLAG_FILE.exists():
            create_success_flag(existing_instance.id, logger)
        
        return 0
    
    if args.dry_run:
        logger.info(f"\n{Fore.GREEN}✓ Dry run successful - configuration looks good!")
        logger.info("Remove --dry-run flag to actually create the instance")
        return 0
    
    # Get availability domains to try
    if args.no_cycle or config['availability_domain']:
        # Use only the specified AD
        if config['availability_domain']:
            availability_domains = [config['availability_domain']]
            logger.info(f"Using specified availability domain: {config['availability_domain']}")
        else:
            logger.error("No availability domain specified in .env")
            return 1
    else:
        # Get all ADs
        availability_domains = get_all_availability_domains(
            identity_client,
            config['compartment'],
            logger
        )
        
        if not availability_domains:
            logger.error("Could not retrieve availability domains")
            return 1
    
    # Try to create instance across ADs and FDs
    logger.info("")
    logger.info("="*60)
    logger.info("Starting instance creation attempts...")
    logger.info("="*60)
    logger.info("")
    
    total_attempts = 0
    capacity_errors = 0
    
    for ad in availability_domains:
        # Get fault domains for this AD
        fault_domains = get_fault_domains(
            identity_client,
            config['compartment'],
            ad,
            logger
        )
        
        # Try without specifying fault domain first
        attempts = [None] + fault_domains
        
        for fd in attempts:
            total_attempts += 1
            
            success, instance, error_type = create_instance(
                compute_client,
                config,
                ssh_public_key,
                ad,
                fd,
                logger
            )
            
            if success:
                # Success!
                logger.info("")
                logger.info(Fore.GREEN + "="*60)
                logger.info(Fore.GREEN + "✓ INSTANCE CREATED SUCCESSFULLY!")
                logger.info(Fore.GREEN + "="*60)
                logger.info("")
                logger.info(f"Instance ID: {Fore.YELLOW}{instance.id}")
                logger.info(f"Availability Domain: {Fore.YELLOW}{ad}")
                if fd:
                    logger.info(f"Fault Domain: {Fore.YELLOW}{fd}")
                logger.info(f"\nTotal attempts: {total_attempts}")
                logger.info(f"Capacity errors encountered: {capacity_errors}")
                
                # Create flag file
                create_success_flag(instance.id, logger)
                
                logger.info("")
                logger.info(f"{Fore.CYAN}Next steps:")
                logger.info("1. Wait for instance to finish provisioning (check OCI console)")
                logger.info("2. Get the public IP from OCI console")
                logger.info(f"3. SSH into instance: ssh -i {config['ssh_key_file'].replace('.pub', '')} ubuntu@<public-ip>")
                
                return 0
            
            # Track capacity errors
            if error_type == 'capacity':
                capacity_errors += 1
            elif error_type in ['quota', 'other']:
                # Non-capacity errors are likely persistent, stop trying
                logger.error(f"\n{Fore.RED}Non-capacity error encountered. Stopping attempts.")
                logger.error("Check the error message above and your configuration.")
                return 1
            
            # Small delay between attempts
            if total_attempts < len(availability_domains) * (1 + len(fault_domains)):
                time.sleep(1)
    
    # All attempts failed
    logger.warning("")
    logger.warning(Fore.YELLOW + "="*60)
    logger.warning(Fore.YELLOW + "All creation attempts failed")
    logger.warning(Fore.YELLOW + "="*60)
    logger.warning("")
    logger.warning(f"Total attempts: {total_attempts}")
    logger.warning(f"Capacity errors: {capacity_errors}")
    
    if capacity_errors == total_attempts:
        logger.info("")
        logger.info(f"{Fore.CYAN}All failures were due to capacity.")
        logger.info("This is normal for Always Free instances.")
        logger.info("")
        logger.info("Recommendations:")
        logger.info("1. Set up a scheduled task to run this script every 5-15 minutes")
        logger.info("2. Try during off-peak hours (early morning UTC)")
        logger.info("3. Consider trying a different region")
    
    return 1


if __name__ == '__main__':
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\nFATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
