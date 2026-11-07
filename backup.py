import argparse
from proxmoxer import ProxmoxAPI

from proxmox_utils import _vmid_exists

def _backup_vi(proxmox: ProxmoxAPI, args: argparse.Namespace) -> int:
    """Backup a VM or LXC container with the given VMID."""
    vmid = int(args.vmid)
    storage_id = args.storage_id
    if not (vm := _vmid_exists(proxmox, vmid)):
        print(f"❌ VMID {vmid} does not exist in the cluster.")
        return 1
    
    node = vm["node"]
    name = vm["name"]
    backup_payload = {
        "vmid": vmid,
        "node": node,
        "storage": storage_id,
        "compress": "zstd",
        "mode": "snapshot",
        "notes-template": f"Backup of VMID {vmid} ({name})",
        "prune-backups": "keep-daily=7,keep-weekly=4,keep-monthly=1",
        "remove": 1,
    }
    try:
        # Trigger backup for the VM or LXC container
        proxmox.nodes(node).vzdump.post(**backup_payload)
    except Exception as exc:
        print(f"❌ Backup failed for VMID {vmid}: {exc}")
        return 1
    else:
        print(f"✅ Backup initiated for VMID {vmid}")
        return 0
