# Proxmox VE commandline
Out of the box, proxmox provides commandline tools to manage virtual machines (qm) and LXC containers (pct).  These tools will only run on a proxmox node.  Remote administration is possible via bash scripts which ssh to the node, and run the command line tools remotely.  This works, but seem klunky.  This repo attempts to provide a single commandline tool (pvi) that replicates much of the frequently used functionality from qm and pct and can be run from anyhost, and that connects to the proxmox cluster via the proxmox API. **note:** I use the 'vi' nomenclature to indicate a 'virtual instance' which may be either a QEMU-style Virtual Machine, or an LXC-style container.

| Filename | (type) Purpose| Status|
|----------|---------------|-------|
| pvi | (bash) calls uv run pvi.py | Functional |
| pvi.py | (python) parses the command line, connects to the proxmox API, and calls the selected command | Functional |
| command_line.py | (python) instantiates argparse | Functional |
| proxmox_utils.py | (python) provides _connect_proxmox (env vars), _start_vi, _stop_vi, and _reboot_vi | Functional |
| check.py | (python) _check_vi - checks for the existence of a vi at the specified VMID | Functional |
| backup.py | (python) _backup_vi - initiates a backup of the vi with the specified VMID | Functional |
| delete.py | (python) _delete_vi - destroys/purges the vi with the specified VMID | Functional |
| create.py | (python) _create_vi - creates a new vi from the commandline arguments | Functional |
| modify.py | (python) _modify_vi - modifies an existing vi from the commandline arguments | Partially Functional |
---

### Python Dependencies:
- proxmoxer
- python-dotenv
- requests

## Usage Example
```
./pvi create qemu -i base.img -v 102 -c 2 -m 4096 -S
```