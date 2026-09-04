import argparse
from proxmoxer import ProxmoxAPI

from proxmox_utils import _vmid_exists

def _check_vi(proxmox: ProxmoxAPI, args: argparse.Namespace) -> int:
    """Check if the given VMID exists in the Proxmox cluster."""
    found_vm = _vmid_exists(proxmox, args.vmid)
    if found_vm:
        print(f"VMID {args.vmid} (type={found_vm['type']}) in {found_vm['status']} on node {found_vm['node']} as '{found_vm['name']}'.")
        return 1
    else:
        print(f"VMID {args.vmid} is available in the cluster.")
        return 0
