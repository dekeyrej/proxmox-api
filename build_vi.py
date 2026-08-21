#!/usr/bin/env python3
# PROXMOX_CLUSTER_NAME is required from environment, and used to read the cluster config file
"""Create Proxmox VMs using Proxmox API (via proxmoxer) — replacement for build_vm.sh

Usage: mirror most options from build_vm.sh. Connects to Proxmox API
using environment variables: PROXMOX_HOST, PROXMOX_USER, PROXMOX_PASSWORD
or PROXMOX_TOKEN_ID and PROXMOX_TOKEN_SECRET. Disable SSL verify with
PROXMOX_VERIFY_SSL=0.
"""
from __future__ import annotations

import argparse
import json
import os
from time import sleep
from typing import Dict, Any
from urllib import parse

import dotenv
from proxmoxer import ProxmoxAPI
# from pydantic import BaseModel, Field

# class VIConfigModel(BaseModel):
#     vmid: int = Field(..., description="VMID of the VM or LXC container")
#     name: str = Field(..., description="Hostname of the VM or LXC container")
#     cores: int = Field(..., description="Number of CPU cores")
#     memory: int = Field(..., description="Memory size in MB")
#     balloon: int = Field(..., description="Balloon memory size in MB (VM Only)")
#     net0: str = Field(..., description="Network configuration string")
#     scsihw: str = Field(..., description="SCSI hardware type")
#     boot: str = Field(..., description="Boot order configuration")
#     scsi0: str = Field(..., description="SCSI disk configuration string")
#     ostype: str = Field(..., description="Operating system type")
#     ide2: str = Field(..., description="IDE disk configuration string")
#     citype: str = Field(..., description="Cloud-init type")
#     ciupgrade: int =  Field(..., description="Cloud-init upgrade flag (0 or 1)")
#     ciuser: str = Field(..., description="Cloud-init username")
#     sshkeys: str = Field(..., description="SSH public keys (URL-encoded)")
#     agent: int = Field(..., description="QEMU guest agent flag (0 or 1)")
#     onboot: int = Field(..., description="Start on boot flag (0 or 1)")
#     serial0: str = Field(..., description="Serial port configuration string")
#     ipconfig0: str = Field(..., description="IP configuration string for cloud-init")
#     pool: str = Field(..., description="Resource pool name")
#     cpu: str = Field(..., description="CPU type")
#     hostpci0: str = Field(..., description="Host PCI device configuration string")
#     machine: str = Field(..., description="Machine type")
#     bios: str = Field(..., description="BIOS type")
#     efidisk0: str = Field(..., description="EFI disk configuration string")

clusterdir = os.getenv("PROXMOX_CLUSTER_DIR", "")
clustername= os.getenv("PROXMOX_CLUSTER_NAME", "example")
dotenv.load_dotenv(f"{clusterdir}/{clustername}.env")

DEFAULTS = {
    "pve_node": os.environ.get("PVENODE", "local"),
    "gateway": os.environ.get("GATEWAY", "192.168.86.1"),
    "storage_pool": os.environ.get("STORAGE_POOL", "nvme_pool"),
    ### Unlike build_vm.sh, we read SSH keys from an environment variable or **local** file path (not remote)
    "sshkeys": os.environ.get("SSHKEYS", "/user/ubuntu/repos/proxmox-api/authorized_keys"),
    "logical_import_path": os.environ.get("LOGICAL_IMPORT_PATH", "ssd_backup:import"),
    "logical_template_path": os.environ.get("LOGICAL_TEMPLATE_PATH", "ssd_backup:vztmpl"),
}

def _get_command_line_args(argv) -> list[str]:
    """Return the command line arguments as a list of strings."""
    parser = argparse.ArgumentParser(description="Create Proxmox VM or LXC via proxmoxer")
    parser.add_argument("command", choices=["qemu", "lxc"], help="Command (required) to execute: vm or lxc")
    parser.add_argument("-i", "--image", help="VM/CT Image name (required), run with -L to list available images")
    parser.add_argument("-v", "--vmid", help="VM/CT ID (optional, auto-assigned if not provided)", type=int)
    parser.add_argument("-o", "--hostname", help="VM/CT Hostname (optional, defaults to vm-VMID or ct-VMID)")
    parser.add_argument("-u", "--user", help="VM Username for cloud-init (optional, auto-detected from image if not provided)")
    parser.add_argument("--passwd", default="", help="VM Password for cloud-init (deprecated, optional, default empty)")
    parser.add_argument("-k", "--sshkeys", default=DEFAULTS["sshkeys"], help="VM SSH public keys (literal or path to LOCAL file)")
    parser.add_argument("-c", "--cores", default=2, help="VM/CT Number of CPU cores (default 2)")
    parser.add_argument("-m", "--memory", default=2048, help="VM/CT Memory size in MB (default 2048)")
    parser.add_argument("-d", "--disk_size", default=10, type=int, help="VM/CT Disk size in GB (default 10)")
    parser.add_argument("-a", "--ipaddress", default="", help="VM/CT IP address (optional), defaults to DHCP if not provided")
    parser.add_argument("-p", "--resource_pool", default="", help="VM/CT Resource pool (optional)")
    parser.add_argument("-t", "--cputype", default="host", choices=["host", "kvm64", "qemu64"], help="VM CPU type (default host)")
    parser.add_argument("-e", "--extra_disk", default=0, type=int, help="VM Extra disk size in GB (default 0)")
    parser.add_argument("-r", "--remarks", default="", help="VM/CT Remarks (optional)")
    parser.add_argument("-g", "--tags", default="", help="VM/CT Tags (optional)")
    parser.add_argument("-T", "--machine_type", default="pc", choices=["pc", "q35"], help="VM Machine type (default pc)")
    parser.add_argument("-D", "--display", default="", choices=["std", "qxl", "virtio", "vmware", "cirrus", "none"], help="VM Display type (optional)")
    parser.add_argument("-P", "--hostpci0", default="", help="VM Host PCI device (optional)")
    parser.add_argument("-N", "--no-upgrade", action="store_true", help="Do not upgrade the VM via cloud-init (default is to upgrade)")
    parser.add_argument("-L", "--list", action="store_true", help="List available VM images or LXC templates")
    parser.add_argument("-O", "--only-root", action="store_true", help="for standard LXC templates, only user 'root' is supported")
    parser.add_argument("-R", "--dry-run", action="store_true", help="Perform a dry run without creating the VM/CT")
    parser.add_argument("-S", "--no-start", action="store_true", help="Do not start the VM/CT after creation (default is to start)")
    parser.add_argument("-n", "--node", default=DEFAULTS["pve_node"], help="VM/CT Node (default is the value from DEFAULTS)")
    parser.add_argument("-w", "--gateway", default=DEFAULTS["gateway"], help="VM/CT Gateway (default is the value from DEFAULTS)")
    parser.add_argument("-s", "--storage_pool", default=DEFAULTS["storage_pool"], help="VM/CT Storage pool (default is the value from DEFAULTS)")
    parser.add_argument("--logical_template_path", default=DEFAULTS["logical_template_path"])
    parser.add_argument("--logical_import_path", default=DEFAULTS["logical_import_path"])

    local_args = parser.parse_args(argv)

    if not local_args.image and not local_args.list:
        parser.print_help()
        print("\n❌ Error: --image is required unless --list is specified")
        return 2
    
    return parser.parse_args(argv)

def _detect_user_from_image(image: str) -> str:
    """Detect the default user for cloud-init based on the image name."""
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

def _build_qemu_payload(args: argparse.Namespace) -> Dict[str, Any]:
    """Build the payload for creating a QEMU VM."""
    payload = {
        "vmid": int(args.vmid),
        "name": args.hostname,
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
        "ciupgrade": int(args.upgrade),
        "ciuser": args.user or _detect_user_from_image(args.image),
        "agent": 1,
        "onboot": 1,
        "serial0": "socket",
        "ipconfig0": args.ipstring,
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
        "disk_size": args.disk_size,          # not consumed by Proxmox API, but used later to resize the boot disk after creation, and before starting the VM
        "start": args.start_after_creation,   # not consumed by Proxmox API, but used later to optionally start the VM after creation and resizing the boot disk
    }
    return payload

def _build_lxc_payload(args: argparse.Namespace) -> Dict[str, Any]:
    """Build the payload for creating an LXC container."""
    payload = {
        "vmid": int(args.vmid),
        "hostname": args.hostname,
        "cores": int(args.cores),
        "memory": int(args.memory),
        "swap": 0,
        "ostemplate": f"{args.logical_template_path}/{args.image}",
        "rootfs": f"{args.storage_pool}:{args.disk_size}",
        **({ "sshkeys": _read_sshkeys(args.sshkeys)} if args.sshkeys and args.only_root else {}),
        "unprivileged": 1,
        "features": "nesting=1",
        "onboot": 1,
        "net0": f"name=eth0,bridge=vmbr0,{args.ipstring}",
        **({"pool": args.resource_pool} if args.resource_pool else {}),
        **({"description": args.remarks} if args.remarks else {}),
        **({"tags": args.tags} if args.tags else {}),
        "start": args.start_after_creation
    }
    return payload

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
        # print(json.dumps(vm, indent=2))
        # print(f"VMID {vmid} already exists in the cluster on node {vm['node']}.")
        return vm
    return None

def _list_available(proxmox: ProxmoxAPI, node: str, storage_id: str, vitype: str) -> None:
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

def _get_next_vmid(proxmox: ProxmoxAPI) -> int:
    """Get the next available VMID from the Proxmox cluster"""
    try:
        next_vmid = proxmox.cluster.nextid.get()
        return int(next_vmid)
    except Exception as exc:
        print(f"Error getting next VMID: {exc}")
        raise

def _lock(proxmox: ProxmoxAPI, node: str, vmid: int) -> bool:
    """Check if a VM is locked (returns True if locked, False if unlocked)"""
    try:
        status = proxmox.nodes(node).qemu(vmid).status.current.get()
        return status.get("lock", "") != ""
    except Exception:
        return False

def _build_vi_from_payload(payload: Dict[str, Any], proxmox: ProxmoxAPI, node: str, vitype: str) -> None:
    """Create a VM or LXC container from the given payload."""
    if vitype == "qemu":
        startup = payload.pop("start", 0)  # ensure VM is not started immediately
        disk_size = payload.pop("disk_size", 10)  # default to 10G if not specified
        proxmox.nodes(node).qemu.post(**payload)
        # wait for creation to complete before resizing the boot disk (Proxmox locks the VM during creation)
        while _lock(proxmox, node, payload["vmid"]):
            print(f"Waiting for VMID {payload['vmid']} to unlock...")
            sleep(5)
        # resize boot disk after creation lock is released
        proxmox.nodes(node).qemu(payload["vmid"]).resize.put(disk="scsi0", size=f"{disk_size}G")
        # optionally start the VM after creation
        if startup == 1:
            proxmox.nodes(node).qemu(int(payload["vmid"])).status.start.post()
    elif vitype == "lxc":
        proxmox.nodes(node).lxc.post(**payload)
    
def main(argv: list[str] | None = None) -> int:
    """Main function to create a Proxmox VM or LXC container based on command line arguments."""
    if argv is None:
        argv = os.sys.argv[1:]
    args = _get_command_line_args(argv)
    if isinstance(args, int):
        return args  # return the error code if _get_command_line_args returned an int

    args.start_after_creation = 0 if args.no_start   else 1
    args.upgrade              = 0 if args.no_upgrade else 1 # VM only
    args.ipstring = f"ip={args.ipaddress}/24,gw={args.gateway}" if args.ipaddress else "ip=dhcp"
    
    # connect
    proxmox = _connect_proxmox()

    if args.list:
        storage_id = args.logical_template_path.split(":")[0] if args.command == "lxc" else args.logical_import_path.split(":")[0]
        _list_available(proxmox, args.node, storage_id, args.command)
        return 0

    if args.vmid:
        found_vm = _vmid_exists(proxmox, int(args.vmid))
        if found_vm:
            print(f"VMID {args.vmid} in {found_vm['status']} on node {found_vm['node']} as '{found_vm['name']}' (type={found_vm['type']}).")
            return 1
    else:
        args.vmid = _get_next_vmid(proxmox)
        print(f"No VMID specified, using next available VMID: {args.vmid}")
        
    args.hostname = args.hostname or (f"vm-{args.vmid}" if args.command == "qemu" else f"ct-{args.vmid}")

    try:
        if args.command == "lxc":
            payload = _build_lxc_payload(args)
        else: # args.command == "qemu"
            payload = _build_qemu_payload(args)

        if args.dry_run:
            print(f"Dry run for {args.command.upper()} {args.vmid} ({args.hostname}) on node {args.node} — create payload:")
            for k, v in payload.items():
                print(f"  {k}: {v}")
            print(f"Would call: POST /nodes/{args.node}/{args.command} with vmid={args.vmid}")
        else:
            print(f"🛡️ Building {args.command.upper()} {args.vmid} ({args.hostname}) on node {args.node}")
            _build_vi_from_payload(payload, proxmox, args.node, args.command)
            print(f"✅ Created  {args.command.upper()} {args.vmid} ({args.hostname}) on node {args.node}")

    except Exception as exc:  # pragma: no cover - runtime error handling
        print(f"❌ Creation failed for {args.command.upper()} {args.vmid} ({args.hostname}) on node {args.node}: {exc}")
        return 1
    else:
        return 0

if __name__ == "__main__":
    raise SystemExit(main())
