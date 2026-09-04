import argparse
from proxmoxer import ProxmoxAPI

from proxmox_utils import _vmid_exists, _stop_vi

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
    
def _delete_vi(proxmox: ProxmoxAPI, args: argparse.Namespace) -> int:
    """Delete a VM or LXC container with the given VMID."""
    vmid = int(args.vmid)
    confirmed = bool(args.yes)
    vm = _vmid_exists(proxmox, vmid)
    type = vm["type"]
    node = vm["node"]
    name = vm["name"]
    if not vm:
        print(f"❌ VMID {vmid} does not exist in the cluster.")
        return 1
    try:
        if not confirmed and not ask_yes_no(f"Are you sure you want to delete VMID {vmid} (type={type}) on node {node} as '{name}'? [N/y]: ", default=False):
            print(f"❌ Deletion aborted for VMID {vmid}.")
            return 1
        payload = {"purge": 1}  # purge the VM or LXC container
        if _stop_vi(proxmox, vmid) != 0:
            return 1

        if vm["type"] == "qemu":
            proxmox.nodes(vm["node"]).qemu(vmid).delete(**payload)
        elif vm["type"] == "lxc":
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
