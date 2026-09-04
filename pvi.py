#!/usr/bin/env python3
"""
Manage Proxmox virtual instances (VMs or LXCs) using Proxmox API (via proxmoxer)

Examples:
    Check if a VM exists:
        pvi.py check --vmid 101

    Create a new VM:
        pvi.py create --vmid 101 --name myvm --type qemu --image myimage.qcow2

    Modify an existing VM:
        pvi.py modify --vmid 101 --name newname

    Backup a VM:
        pvi.py backup --vmid 101

    Delete a VM:
        pvi.py delete --vmid 101

"""
import os

from command_line import _get_command_line_args
from  check import _check_vi
from create import _create_vi
from modify import _modify_vi
from backup import _backup_vi
from delete import _delete_vi
from proxmox_utils import _connect_proxmox

DEFAULTS = {
    "pve_node": os.environ.get("PVENODE", "local"),
    "gateway": os.environ.get("GATEWAY", "192.168.1.1"),
    "storage_pool": os.environ.get("STORAGE_POOL", "local-lvm"),
    ### Unlike build_vm.sh, we read SSH keys from an environment variable or **local** file path (not remote)
    "sshkeys": os.environ.get("SSHKEYS", "/home/ubuntu/.ssh/authorized_keys"),
    "logical_import_path": os.environ.get("LOGICAL_IMPORT_PATH", "local:import"),
    "logical_template_path": os.environ.get("LOGICAL_TEMPLATE_PATH", "local:vztmpl"),
}

def main(argv: list[str] | None = None) -> int:
    """Main function to manage a Proxmox VM or LXC container based on command line arguments."""
    # get command line arguments
    if argv is None:
        argv = os.sys.argv[1:]
    args = _get_command_line_args(argv, DEFAULTS)

    # connect to Proxmox API
    proxmox = _connect_proxmox()

    # execute the appropriate action based on the command
    match args.command:
        case  "check":
            return  _check_vi(proxmox, args)
        case "create":
            return _create_vi(proxmox, args)
        case "modify":
            return _modify_vi(proxmox, args)
        case "backup":
            return _backup_vi(proxmox, args)
        case "delete":
            return _delete_vi(proxmox, args)

if __name__ == "__main__":
    raise SystemExit(main())
