#!/usr/bin/env python3
# PROXMOX_CLUSTER_NAME is required from environment, and used to read the cluster config file
"""Create Proxmox virtual instances (VMs or LXCs) using Proxmox API (via proxmoxer)

Connects to Proxmox API
using environment variables: 
PROXMOX_HOST, PROXMOX_USER, and either: 
PROXMOX_TOKEN_ID and PROXMOX_TOKEN_SECRET (preferred) or 
PROXMOX_PASSWORD (deprecated). 
Disable SSL verify with PROXMOX_VERIFY_SSL=0.
"""
from __future__ import annotations

import argparse
import json # not currently used
import os
from time import sleep
from typing import Any
from urllib import parse

import dotenv
from proxmoxer import ProxmoxAPI
from pydantic import BaseModel, Field # TODO: Use Pydantic models for validation of VM/LXC configurations

clusterdir = os.getenv("PROXMOX_CLUSTER_DIR", "/home/ubuntu/.proxmox")
clustername= os.getenv("PROXMOX_CLUSTER_NAME", "example")
dotenv.load_dotenv(f"{clusterdir}/{clustername}.env")

DEFAULTS = {
    "pve_node": os.environ.get("PVENODE", "local"),
    "gateway": os.environ.get("GATEWAY", "192.168.1.1"),
    "storage_pool": os.environ.get("STORAGE_POOL", "local-lvm"),
    ### Unlike build_vm.sh, we read SSH keys from an environment variable or **local** file path (not remote)
    "sshkeys": os.environ.get("SSHKEYS", "/home/ubuntu/.ssh/authorized_keys"),
    "logical_import_path": os.environ.get("LOGICAL_IMPORT_PATH", "local:import"),
    "logical_template_path": os.environ.get("LOGICAL_TEMPLATE_PATH", "local:vztmpl"),
}

def _get_command_line_args(argv) -> list[str]:
    """Return the command line arguments as a list of strings."""
    parser = argparse.ArgumentParser(description="Proxmox Virtual Instance (VM or LXC) management via proxmoxer")
    main_subparser = parser.add_subparsers(dest="command", required=True)
    # Subcommands: check, create, modify, backup, delete
    ## check parser
    check_parser = main_subparser.add_parser("check", help="Check the existence of a VM or LXC")
    check_parser.add_argument("-v", "--vmid", required=True, type=int, help="VM/CT ID to check")
    ## create parser
    create_parser = main_subparser.add_parser("create", help="Create a new VM or LXC")
    create_subparsers = create_parser.add_subparsers(dest="type", required=True)
    common_create_parser = argparse.ArgumentParser(add_help=False)
    common_create_parser.add_argument("-i", "--image", help="VM Image name (required), run with -L to list available images")
    common_create_parser.add_argument("-v", "--vmid", help="VM ID (optional, auto-assigned if not provided)", type=int)
    common_create_parser.add_argument("-o", "--hostname", help="VM Hostname (optional, defaults to vm-VMID)")
    common_create_parser.add_argument("-c", "--cores", default=2, help="VM Number of CPU cores (default 2)")
    common_create_parser.add_argument("-m", "--memory", default=2048, help="VM Memory size in MB (default 2048)")
    common_create_parser.add_argument("-b", "--boot_disk", default=10, type=int, help="VM boot disk size in GB (default 10)")
    common_create_parser.add_argument("-a", "--ipaddress", default="", help="VM IP address (optional), defaults to DHCP if not provided")
    common_create_parser.add_argument("-p", "--resource_pool", default="", help="VM Resource pool (optional)")
    common_create_parser.add_argument("-r", "--remarks", default="", help="VM Remarks (optional)")
    common_create_parser.add_argument("-g", "--tags", default="", help="VM Tags (optional)")
    common_create_parser.add_argument("-k", "--sshkeys", default=DEFAULTS["sshkeys"], help="VM (user)/CT (root) SSH public keys (literal or path to LOCAL file)")
    common_create_parser.add_argument("-n", "--node", default=DEFAULTS["pve_node"], help="VM Node (default is the value from DEFAULTS)")
    common_create_parser.add_argument("-w", "--gateway", default=DEFAULTS["gateway"], help="VM Gateway (default is the value from DEFAULTS)")
    common_create_parser.add_argument("-s", "--storage_pool", default=DEFAULTS["storage_pool"], help="VM Storage pool (default is the value from DEFAULTS)")
    common_create_parser.add_argument("-L", "--list", action="store_true", help="List available VM images to import")
    common_create_parser.add_argument("-R", "--dry-run", action="store_true", help="Perform a dry run without creating the VM")
    common_create_parser.add_argument("-S", "--no-start", action="store_true", help="Do not start the VM after creation (default is to start)")
    common_create_parser.add_argument("-F", "--fallback", action="store_true", help="If vmid specified and in use, fallback to next available (default to no fallback)")

    ### create QEMU parser
    create_qemu_parser = create_subparsers.add_parser("qemu", parents=[common_create_parser], help="Create a new QEMU VM")
    create_qemu_parser.add_argument("-u", "--user", help="VM Username for cloud-init (optional, auto-detected from image if not provided)")
    create_qemu_parser.add_argument("--passwd", default="", help="VM Password for cloud-init (deprecated, optional, default empty)")
    create_qemu_parser.add_argument("-t", "--cputype", default="host", choices=["host", "kvm64", "qemu64"], help="VM CPU type (default host)")
    create_qemu_parser.add_argument("-e", "--extra_disk", default=0, type=int, help="VM Extra disk size in GB (default 0)")
    create_qemu_parser.add_argument("-T", "--machine_type", default="pc", choices=["pc", "q35"], help="VM Machine type (default pc)")
    create_qemu_parser.add_argument("-d", "--display", default="none", choices=["std", "qxl", "virtio", "vmware", "cirrus", "none"], help="VM Display type (optional)")
    create_qemu_parser.add_argument("-P", "--hostpci0", default="", help="VM Host PCI device (optional)")
    create_qemu_parser.add_argument("-l", "--logical_import_path", default=DEFAULTS["logical_import_path"])
    create_qemu_parser.add_argument("-N", "--no-upgrade", action="store_true", help="Do not upgrade the VM via cloud-init (default is to upgrade)")
    #### create LXC parser
    create_lxc_parser = create_subparsers.add_parser("lxc", parents=[common_create_parser], help="Create a new LXC container")
    create_lxc_parser.add_argument("-l", "--logical_template_path", default=DEFAULTS["logical_template_path"])
    create_lxc_parser.add_argument("-O", "--only-root", action="store_true", help="for standard LXC templates, only user 'root' is supported")
    
    ## modify parser # todo
    modify_parser = main_subparser.add_parser("modify", help="Modify an existing VM or LXC")
    modify_subparsers = modify_parser.add_subparsers(dest="type", required=True)
    common_modify_parser = argparse.ArgumentParser(add_help=False)
    common_modify_parser.add_argument("-v", "--vmid", required=True, type=int, help="VM/CT ID to modify")
    common_modify_parser.add_argument("-o", "--hostname", default="", help="new VM/CT Hostname") # restart required for hostname change
    common_modify_parser.add_argument("-c", "--cores", default=2, help="new VM/CT Number of CPU cores") # restart required for qemu, not for lxc
    common_modify_parser.add_argument("-m", "--memory", default=2048, help="new VM/CT Memory size in MB") # restart required for qemu, not for lxc
    common_modify_parser.add_argument("-b", "--boot_disk", default=0, type=int, help="new VM/CT boot disk size in GB") # restart required
    common_modify_parser.add_argument("-a", "--ipaddress", default="", help="new VM/CT IP address (optional), pass 'dhcp' to use DHCP") # restart required
    common_modify_parser.add_argument("-p", "--resource_pool", default="", help="new VM/CT Resource pool (optional)") # restart not required
    common_modify_parser.add_argument("-r", "--remarks", default="", help="new VM/CT Remarks (optional)") # restart not required
    common_modify_parser.add_argument("-g", "--tags", default="", help="new VM/CT Tags (optional)") # restart not required
    common_modify_parser.add_argument("-k", "--sshkeys", default="", help="VM (user)/CT (root) new SSH public keys (literal or path to LOCAL file)") # restart required
    common_modify_parser.add_argument("-y", "--yes", action="store_true", help="Confirm modification without prompting")
    modify_qemu_parser = modify_subparsers.add_parser("qemu", help="Modify an existing QEMU VM", parents=[common_modify_parser])
    modify_qemu_parser.add_argument("--passwd", default="", help="VM Password for cloud-init (deprecated, optional, default empty)") # restart maybe required
    modify_qemu_parser.add_argument("-t", "--cputype", default="host", choices=["host", "kvm64", "qemu64"], help="new VM CPU type (default host)") # restart required
    modify_qemu_parser.add_argument("-e", "--extra_disk", default=0, type=int, help="new VM Extra disk size in GB (default 0), or new additional disk size in GB") # restart required
    modify_qemu_parser.add_argument("-T", "--machine_type", default="q35", choices=["pc", "q35"], help="new VM Machine type (default q35)") # restart required
    modify_qemu_parser.add_argument("-d", "--display", default="none", choices=["std", "qxl", "virtio", "vmware", "cirrus", "none"], help="new VM Display type (optional)") # restart required
    modify_qemu_parser.add_argument("-P", "--hostpci0", default="", help="new VM Host PCI device (optional)") # restart required
    modify_lxc_parser = modify_subparsers.add_parser("lxc", help="Modify an existing LXC container", parents=[common_modify_parser])

    ## backup parser
    backup_parser = main_subparser.add_parser("backup", help="Backup a VM or LXC")
    backup_parser.add_argument("-v", "--vmid", required=True, type=int, help="VM/CT ID to backup")
    backup_parser.add_argument("-s", "--storage_id", required=True, help="Storage ID to store the backup")

    ## delete parser
    delete_parser = main_subparser.add_parser("delete", help="Delete a VM or LXC")
    delete_parser.add_argument("-v", "--vmid", required=True, type=int, help="VM/CT ID to delete")
    delete_parser.add_argument("-y", "--yes", action="store_true", help="Confirm deletion without prompting")

    return parser.parse_args(argv)

def _connect_proxmox() -> ProxmoxAPI:
    """Connect to the Proxmox API using environment variables from the cluster environment for credentials."""
    host = os.environ.get("PROXMOX_HOST", "127.0.0.1")
    user = os.environ.get("PROXMOX_USER", "root@pam")
    token_id = os.environ.get("PROXMOX_TOKEN_ID", "default")
    token_secret = os.environ.get("PROXMOX_TOKEN_SECRET")
    password = os.environ.get("PROXMOX_PASSWORD")
    verify_ssl = os.environ.get("PROXMOX_VERIFY_SSL", "0") not in ("0", "false", "False")

    if token_id and token_secret and user:
        return ProxmoxAPI(host, user=user, token_name=token_id, token_value=token_secret, verify_ssl=verify_ssl)
    if user and password:
        return ProxmoxAPI(host, user=user, password=password, verify_ssl=verify_ssl)

    # fallback: try local socket (when running on the Proxmox node)
    try:
        return ProxmoxAPI(host, user="root@pam", password="", verify_ssl=verify_ssl)
    except Exception:
        # allow credentials-less connection attempt (useful when running against local socket)
        return ProxmoxAPI(host)

def _vmid_exists(proxmox: ProxmoxAPI, vmid: int) -> bool:
    """Check if a VMID already exists in the Proxmox cluster.

    Returns the vm structure if the VMID exists, None otherwise.
    """
    vms = proxmox.cluster.resources.get(type="vm")
    if vmid in [vm["vmid"] for vm in vms]:
        vm = next(vm for vm in vms if vm["vmid"] == vmid)
        return vm
    return None

def _validate_vmid(proxmox: ProxmoxAPI, args: argparse.Namespace) -> None:
    try:
        if args.vmid:
            found_vm = _vmid_exists(proxmox, int(args.vmid))
            if found_vm:
                print(f"VMID {args.vmid} (type={found_vm['type']}) in {found_vm['status']} on node {found_vm['node']} as '{found_vm['name']}'.")
                if args.fallback:
                    args.vmid = int(proxmox.cluster.nextid.get())
                    print(f"VMID {found_vm['vmid']} is in use, falling back to next available VMID: {args.vmid}")
                else:
                    return 1
        else:
            args.vmid = int(proxmox.cluster.nextid.get())
            print(f"No VMID specified, using next available VMID: {args.vmid}")
    except Exception as exc:
        print(f"Error validating VMID: {exc}")
        raise
    else:
        return args.vmid

def _get_vi_config(proxmox: ProxmoxAPI, vmid: int) -> dict[str, Any]:
    """Retrieve the current configuration of a VM or container."""
    vm  = _vmid_exists(proxmox, vmid)
    # print(vm)
    if not vm:
        raise ValueError(f"VMID {vmid} does not exist")
    else:
        node = vm["node"]
        vmid = vm["vmid"]
        vitype = vm["type"]
    # Determine if the VM is a QEMU VM or an LXC container
    if vitype == "lxc":
        return vitype, proxmox.nodes(node).lxc(vmid).config.get()
    else:
        return vitype, proxmox.nodes(node).qemu(vmid).config.get()
    
def _detect_user_from_image(image: str) -> str:
    """Detect the default user for cloud-init based on the image name. 
    QEMU images often have different default users depending on the distribution. 
    This function checks the image name for known patterns and returns the appropriate default user.
    """
    image = image.lower()
    if any(x in image for x in ("ubuntu", "jammy", "noble", "resolute")):
        return "ubuntu"
    if any(x in image for x in ("debian", "bookworm", "trixie", "forky")):
        return "debian"
    if any(x in image for x in ("rocky", "almalinux", "centos", "rhel")):
        return "cloud-user"
    if any(x in image for x in ("al2023", "amzn2", "amazonlinux")):
        return "ecs-user"
    if "fedora" in image:
        return "fedora"
    if "arch" in image:
        return "arch"
    return "ubuntu"

def _read_sshkeys(sshkeys) -> str:
    """Return the SSH public keys as a single string.

    Behavior:
    - If `args.sshkeys` is a path that exists locally, read it.
    - Otherwise treat `args.sshkeys` as the literal key data and return it.

    # encode the SSH keys for URL safety and add to payload
    """
    # If it looks like a file path and exists locally, read it
    if os.path.isabs(sshkeys) and os.path.exists(sshkeys):
        with open(sshkeys, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read().strip()
            return content

    # otherwise assume sshkeys is already the key content
    return sshkeys.strip()

def _build_qemu_create_payload(args: argparse.Namespace) -> dict[str, Any]:
    """Build the payload for creating a QEMU VM."""
    ip_string = f"ip={args.ipaddress}/24,gw={args.gateway}" if args.ipaddress else "ip=dhcp"
    payload = {
        "vmid": int(args.vmid),
        "name": args.hostname or f"vm-{args.vmid}",
        "cores": int(args.cores),
        "memory": int(args.memory),
        "balloon": int(args.memory),
        "net0": "virtio,bridge=vmbr0",
        "scsihw": "virtio-scsi-single",
        "boot": "order=scsi0",
        "scsi0": f"{args.storage_pool}:0,import-from={args.logical_import_path}/{args.image}",
        "ostype": "l26",
        "ide2": f"{args.storage_pool}:cloudinit",
        "citype": "nocloud",
        "ciupgrade": 0 if args.no_upgrade else 1,
        "ciuser": args.user or _detect_user_from_image(args.image),
        "agent": 1,
        "onboot": 1,
        "serial0": "socket",
        "ipconfig0": ip_string,
        **({"sshkeys": parse.quote(_read_sshkeys(args.sshkeys), safe='')} if args.sshkeys else {}),
        **({"pool": args.resource_pool} if args.resource_pool else {}),
        **({"cpu": f"cputype={args.cputype},phys-bits=host"} if args.cputype == "host" else {"cpu": f"cputype={args.cputype}"} if args.cputype else {}),
        **({"scsi1": f"file={args.storage_pool}:{args.extra_disk}"} if args.extra_disk and args.extra_disk != 0 else {}),
        **({"description": args.remarks} if args.remarks else {}),
        **({"tags": args.tags} if args.tags else {}),
        **({"vga": args.display} if args.display else {}),
        **({"cipassword": args.passwd} if args.passwd else {}),
        **({"hostpci0": args.hostpci0} if args.hostpci0 else {}),
        **({"machine": "type=q35,viommu=virtio", "bios": "ovmf", "efidisk0": f"{args.storage_pool}:1,efitype=4m,ms-cert=2023k,pre-enrolled-keys=1"} if args.machine_type == "q35" or args.hostpci0 else {}),
        "disk_size": args.boot_disk,          # not consumed by Proxmox API, but used later to resize the boot disk after creation, and before starting the VM
        "start": 0 if args.no_start else 1,   # not consumed by Proxmox API, but used later to optionally start the VM after creation and resizing the boot disk
    }
    return payload

def _build_lxc_create_payload(args: argparse.Namespace) -> dict[str, Any]:
    """Build the payload for creating an LXC container."""
    ip_string = f"ip={args.ipaddress}/24,gw={args.gateway}" if args.ipaddress else "ip=dhcp"
    payload = {
        "vmid": int(args.vmid),
        "hostname": args.hostname or f"ct-{args.vmid}",
        "cores": int(args.cores),
        "memory": int(args.memory),
        "swap": 0,
        "ostemplate": f"{args.logical_template_path}/{args.image}",
        "rootfs": f"{args.storage_pool}:{args.boot_disk}",
        **({ "sshkeys": _read_sshkeys(args.sshkeys)} if args.sshkeys and args.only_root else {}),
        "unprivileged": 1,
        "features": "nesting=1",
        "onboot": 1,
        "net0": f"name=eth0,bridge=vmbr0,{ip_string}",
        **({"pool": args.resource_pool} if args.resource_pool else {}),
        **({"description": args.remarks} if args.remarks else {}),
        **({"tags": args.tags} if args.tags else {}),
        "start": 0 if args.no_start else 1,
    }
    return payload

def _build_qemu_modify_payload(current_config: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    """Build the payload for creating a QEMU VM."""

    if args.ipaddress == "dhcp":
        ip_string = "ip=dhcp"
    elif args.ipaddress:
        ip_string = f"ip={args.ipaddress}/24,gw={args.gateway}"
    payload = {
        "vmid": int(args.vmid),
        **({"name": args.hostname, "restart": True} if args.hostname and args.hostname != current_config.get("name") else {}),
        **({"cores": int(args.cores), "restart": True} if args.cores and int(args.cores) != current_config.get("cores") else {}),
        **({"memory": int(args.memory), "balloon": int(args.memory), "restart": True} if args.memory and int(args.memory) != current_config.get("memory") else {}),
        "scsi0": f"{args.storage_pool}:0,import-from={args.logical_import_path}/{args.image}",
        # "ciuser": args.user or _detect_user_from_image(args.image),
        **({"ipconfig0": ip_string, "restart": True} if ip_string and ip_string != current_config.get("ipconfig0") else {}),
        # **({"sshkeys": parse.quote(_read_sshkeys(args.sshkeys), safe='')} if args.sshkeys else {}),
        **({"pool": args.resource_pool} if args.resource_pool else {}),
        **({"cpu": f"cputype={args.cputype},phys-bits=host"} if args.cputype == "host" else {"cpu": f"cputype={args.cputype}"} if args.cputype else {}),
        **({"scsi1": f"file={args.storage_pool}:{args.extra_disk}"} if args.extra_disk and args.extra_disk != 0 else {}),
        **({"description": args.remarks} if args.remarks else {}),
        **({"tags": args.tags} if args.tags else {}),
        **({"vga": args.display, "restart": True} if args.display else {}),
        **({"cipassword": args.passwd} if args.passwd else {}),
        **({"hostpci0": args.hostpci0, "restart": True} if args.hostpci0 else {}),
        **({"machine": "type=q35,viommu=virtio", "bios": "ovmf", "efidisk0": f"{args.storage_pool}:1,efitype=4m,ms-cert=2023k,pre-enrolled-keys=1"} if args.machine_type == "q35" or args.hostpci0 else {}),
        "disk_size": args.boot_disk,          # not consumed by Proxmox API, but used later to resize the boot disk after creation, and before starting the VM
    }
    return payload

def _build_lxc_modify_payload(current_config: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    """Build the payload for modifying an LXC container."""

    if args.ipaddress == "dhcp":
        ip_string = "ip=dhcp"
    elif args.ipaddress:
        ip_string = f"ip={args.ipaddress}/24,gw={args.gateway}"
    payload = {
        "vmid": int(args.vmid),
        **({"hostname": args.hostname, "restart": True} if args.hostname and args.hostname != current_config.get("hostname") else {}),
        **({"cores": int(args.cores), "restart": True} if args.cores and int(args.cores) != current_config.get("cores") else {}),
        **({"memory": int(args.memory), "restart": True} if args.memory and int(args.memory) != current_config.get("memory") else {}),
        **({"ipconfig0": ip_string, "restart": True} if ip_string and ip_string != current_config.get("ipconfig0") else {}),
        **({"description": args.remarks} if args.remarks else {}),
        **({"tags": args.tags} if args.tags else {}),
        **({"vga": args.display, "restart": True} if args.display else {}),
        **({"cipassword": args.passwd} if args.passwd else {}),
    }
    return payload

def _dump_payload(payload: dict[str, Any], type: str, node: str) -> None:
    """Dump the payload to stdout in a readable format."""
    hostname = payload.get("hostname") if type == "lxc" else payload.get("name")
    print(f"Dry run for {type.upper()} {payload['vmid']} ({hostname}) on node {node} — create payload:")
    for k, v in payload.items():
        print(f"  {k}: {v}")
    print(f"Would call: POST /nodes/{node}/{type} with vmid={payload['vmid']}")

def _list_available_images(proxmox: ProxmoxAPI, node: str, storage_id: str, vitype: str) -> None:
    """List available VM images or LXC templates in the specified storage."""
    files = proxmox.nodes(node).storage(storage_id).content.get()
    if vitype == "qemu":
        print(f"Available images in storage {storage_id}:")
        for f in files:
            if f["format"] == "qcow2":
                print(f"  {f['volid'].split(':')[1].split('/')[-1]}  ({f['size'] // (1024*1024)} MB)")
    else:
        print(f"Available templates in storage {storage_id}:")
        for f in files:
            if f["format"] == "txz":
                print(f"  {f['volid'].split(':')[1].split('/')[-1]}  ({f['size'] // (1024*1024)} MB)")

def _build_qemu_from_payload(payload: dict[str, Any], proxmox: ProxmoxAPI, node: str) -> int:
    """Create a VM from the given payload."""
    print(f"🛡️ Building QEMU {payload['vmid']} ({payload['name']}) on node {node}")
    startup = payload.pop("start", 0)  # save desired startup behavior and remove from payload
    disk_size = payload.pop("disk_size", 10)  # save desired boot disk size for resizing after creation and remove from payload
    try:
        proxmox.nodes(node).qemu.post(**payload)
        # wait for creation to complete before resizing the boot disk (Proxmox locks the VM during creation)
        print(f"Waiting for VMID {payload['vmid']} to unlock (this may take several seconds)...")
        while proxmox.nodes(node).qemu(payload["vmid"]).status.current.get().get("lock", "") != "":
            sleep(1)
        # resize boot disk after creation lock is released
        proxmox.nodes(node).qemu(payload["vmid"]).resize.put(disk="scsi0", size=f"{disk_size}G")
        # optionally start the VM after creation
        if startup == 1:
            proxmox.nodes(node).qemu(int(payload["vmid"])).status.start.post()
    except Exception as exc:
        print(f"❌ Creation failed for QEMU {payload['vmid']} ({payload['name']}) on node {node}: {exc}")
        return 1
    else:
        print(f"✅ Created  QEMU {payload['vmid']} ({payload['name']}) on node {node}")
        return 0

def _build_lxc_from_payload(payload: dict[str, Any], proxmox: ProxmoxAPI, node: str) -> int:
    """Create an LXC container from the given payload."""
    print(f"🛡️ Building LXC {payload['vmid']} ({payload['hostname']}) on node {node}")
    try:
        proxmox.nodes(node).lxc.post(**payload)
    except Exception as exc:
        print(f"❌ Creation failed for LXC {payload['vmid']} ({payload['hostname']}) on node {node}: {exc}")
        return 1
    else:
        print(f"✅ Created  LXC {payload['vmid']} ({payload['hostname']}) on node {node}")
        return 0

def ask_yes_no(prompt="Do you want to continue? [N/y]: ", default=False) -> bool:
    """Ask the user a yes/no question and return True for yes and False for no."""
    while True:
        # Get input and remove leading/trailing whitespace
        user_input = input(prompt).strip().lower()
        
        # If the user presses Enter without typing, return False (Default: No)
        if user_input == '':
            return default
        # If they type 'y' or 'yes', return True
        elif user_input in ['y', 'yes']:
            return True
        # If they type 'n' or 'no', return False
        elif user_input in ['n', 'no']:
            return False
        
        # If they type anything else, loop again
        print("Invalid input. Please enter 'y' for yes or 'n' for no.")    

def _backup_vi(proxmox: ProxmoxAPI, vmid: int, storage_id: str) -> int:
    """Backup a VM or LXC container with the given VMID."""
    vm = _vmid_exists(proxmox, vmid)
    if not vm:
        print(f"❌ VMID {vmid} does not exist in the cluster.")
        return 1
    backup_payload = {
        "vmid": vmid,
        "node": vm["node"],
        "storage": storage_id,
        "compress": "zstd",
        "mode": "snapshot",
        "notes-template": f"Backup of VMID {vmid} ({vm['name']})",
        "prune-backups": "keep-daily=7,keep-weekly=4,keep-monthly=1",
        "remove": 1,
    }
    try:
        # Trigger backup for the VM or LXC container
        proxmox.nodes(vm["node"]).vzdump.post(**backup_payload)
    except Exception as exc:
        print(f"❌ Backup failed for VMID {vmid}: {exc}")
        return 1
    else:
        print(f"✅ Backup initiated for VMID {vmid}")
        return 0

def _delete_vi(proxmox: ProxmoxAPI, vmid: int, confirmed: bool = False) -> int:
    """Delete a VM or LXC container with the given VMID."""
    vm = _vmid_exists(proxmox, vmid)
    if not vm:
        print(f"❌ VMID {vmid} does not exist in the cluster.")
        return 1
    try:
        if not confirmed and not ask_yes_no(f"Are you sure you want to delete VMID {vmid} (type={vm['type']}) on node {vm['node']} as '{vm['name']}'? [N/y]: ", default=False):
                print(f"❌ Deletion aborted for VMID {vmid}.")
                return 1
        payload = {"purge": 1}  # purge the VM or LXC container
        if vm["type"] == "qemu":
            if vm["status"] == "running":
                proxmox.nodes(vm["node"]).qemu(vmid).status.stop.post()
                while proxmox.nodes(vm["node"]).qemu(vmid).status.current.get()["status"] == "running":
                    sleep(1)
            proxmox.nodes(vm["node"]).qemu(vmid).delete(**payload)
        elif vm["type"] == "lxc":
            if vm["status"] == "running":
                proxmox.nodes(vm["node"]).lxc(vmid).status.stop.post()
                while proxmox.nodes(vm["node"]).lxc(vmid).status.current.get()["status"] == "running":
                    sleep(1)
            proxmox.nodes(vm["node"]).lxc(vmid).delete(**payload)
        else:
            print(f"❌ Unknown VM type for VMID {vmid}: {vm['type']}")
            return 1
    except Exception as exc:
        print(f"❌ Deletion failed for VMID {vmid}: {exc}")
        return 1
    else:
        print(f"✅ Deleted VMID {vmid}")
        return 0

def _modify_vi(proxmox: ProxmoxAPI, vmid: int, args) -> int:
    """Modify a VM or LXC container with the given VMID based on the provided arguments."""
    vitype, vm_config = _get_vi_config(proxmox, vmid)
    if not vm_config:
        print(f"❌ VMID {vmid} does not exist in the cluster.")
        return 1
    try:
        # print(f"Modifying VMID {vmid} with args: {args}")
        print(f"Current configuration for VMID {vmid}: {vm_config}")
        if vitype == "qemu":
            payload = _build_qemu_modify_payload(vm_config, args)
            if args.dry_run:
                _dump_payload(payload, args.type, args.node)
            else:
                pass
                # _modify_qemu_from_payload(payload, proxmox, args.node)
        elif vitype == "lxc":
            payload = _build_lxc_modify_payload(vm_config, args)
            if args.dry_run:
                _dump_payload(payload, args.type, args.node)
            else:
                pass
                # _modify_lxc_from_payload(payload, proxmox, args.node)
        else:
            print(f"❌ Unknown VM type for VMID {vmid}: {vitype}")
            return 1
    except Exception as exc:
        print(f"❌ Modification failed for VMID {vmid}: {exc}")
        return 1
    else:
        print(f"✅ Modified VMID {vmid}")
        return 0

def main(argv: list[str] | None = None) -> int:
    """Main function to manage a Proxmox VM or LXC container based on command line arguments."""

    # get command line arguments
    if argv is None:
        argv = os.sys.argv[1:]
    args = _get_command_line_args(argv)

    # connect to Proxmox API
    proxmox = _connect_proxmox()
    
    match args.command:
        case "check":
            found_vm = _vmid_exists(proxmox, args.vmid)
            if found_vm:
                print(f"VMID {args.vmid} (type={found_vm['type']}) in {found_vm['status']} on node {found_vm['node']} as '{found_vm['name']}'.")
                return 1
            else:
                print(f"VMID {args.vmid} is available in the cluster.")
                return 0
        case "create":
            if args.list:
                args.storage_id = args.logical_import_path.split(":")[0] if args.type == "qemu" else args.logical_template_path.split(":")[0]
                _list_available_images(proxmox, args.node, args.storage_id, args.type)
                return 0
            elif not args.image and not args.list:
                print("❌ Error: --image is required for create command unless --list is specified.")
                return 2
            else:
                args.vmid = _validate_vmid(proxmox, args)
                if args.vmid == 1:
                    return 3  # error validating VMID
                match args.type:
                    case "qemu":
                        payload = _build_qemu_create_payload(args)
                        if args.dry_run: 
                            _dump_payload(payload, args.type, args.node)
                        else:
                            _build_qemu_from_payload(payload, proxmox, args.node)
                    case "lxc":
                        payload = _build_lxc_create_payload(args)
                        if args.dry_run: 
                            _dump_payload(payload, args.type, args.node)
                        else:
                            _build_lxc_from_payload(payload, proxmox, args.node)
        case "modify":
            # for keys, values in vars(args).items():
            #     print(f"{keys}: {values}")
            _modify_vi(proxmox, args.vmid, args)
            # TODO: implement modify functionality
        case "backup":
            return _backup_vi(proxmox, args.vmid, args.storage_id)
        case "delete":
            return _delete_vi(proxmox, args.vmid, confirmed=args.yes)

if __name__ == "__main__":
    raise SystemExit(main())
