import argparse
from typing import Any

from proxmoxer import ProxmoxAPI

from proxmox_utils import _vmid_exists, _stop_vi, _start_vi, _reboot_vi

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
        retval = proxmox.nodes(node).lxc(vmid).config.get()
        retval["node"] = node
        retval["type"] = vitype
        return retval
    else:
        retval = proxmox.nodes(node).qemu(vmid).config.get()
        retval["node"] = node
        retval["type"] = vitype
        return retval
    
def _build_qemu_modify_payload(current_config: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    """Build the payload for creating a QEMU VM."""

    if args.ipaddress == "dhcp":
        ip_string = "ip=dhcp"
    elif args.ipaddress:
        ip_string = f"ip={args.ipaddress}/24,gw={args.gateway}"
    else:
        ip_string = ""
    payload = {
        "vmid": int(args.vmid),
        **({"name": args.hostname, "restart": True} if args.hostname and args.hostname != current_config.get("name") else {}),
        **({"cores": int(args.cores), "restart": True} if args.cores and int(args.cores) != current_config.get("cores") else {}),
        **({"memory": int(args.memory), "balloon": int(args.memory), "restart": True} if args.memory and int(args.memory) != int(current_config.get("memory")) else {}),
        # "scsi0": f"{args.storage_pool}:0,import-from={args.logical_import_path}/{args.image}",
        # "ciuser": args.user or _detect_user_from_image(args.image),
        **({"ipconfig0": ip_string, "restart": True} if ip_string and ip_string != current_config.get("ipconfig0") else {}),
        # **({"sshkeys": parse.quote(_read_sshkeys(args.sshkeys), safe='')} if args.sshkeys else {}),
        **({"pool": args.resource_pool} if args.resource_pool else {}),
        # **({"cpu": f"cputype={args.cputype},phys-bits=host"} if args.cputype == "host" and args.cputype != current_config.get("cpu").split(",")[0] else {"cpu": f"cputype={args.cputype}"} if args.cputype else {}),
        **({"scsi1": f"file={args.storage_pool}:{args.extra_disk}"} if args.extra_disk and args.extra_disk != 0 else {}),
        **({"description": args.remarks} if args.remarks else {}),
        **({"tags": args.tags} if args.tags else {}),
        **({"vga": args.display, "restart": True} if args.display and args.display != current_config.get("vga") else {}),
        **({"cipassword": args.passwd} if args.passwd else {}),
        # **({"hostpci0": args.hostpci0, "restart": True} if args.hostpci0 and args.hostpci0 != current_config.get("hostpci0") else {}),
        # **({"machine": "type=q35,viommu=virtio", "bios": "ovmf", "efidisk0": f"{args.storage_pool}:1,efitype=4m,ms-cert=2023k,pre-enrolled-keys=1"} if (args.machine_type and args.machine_type != current_config.get("machine")) or (args.hostpci0 and args.hostpci0 != current_config.get("hostpci0")) else {}),
        **({"disk_size": args.boot_disk} if args.boot_disk else {}),          # not consumed by Proxmox API, but used later to resize the boot disk after creation, and before starting the VM
        # "node": current_config.get("node"),
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
    print(f"Dry run for {type.upper()} {payload['vmid']} ({hostname}) on node {node} — modify payload:")
    for k, v in payload.items():
        print(f"  {k}: {v}")
    print(f"Would call: PUT /nodes/{node}/{type}/{payload['vmid']}/config")

def _modify_vi_from_payload(payload: dict[str, Any], proxmox: ProxmoxAPI, node: str) -> int:
    """Modify a VM or LXC container from the given payload."""
    vm = _vmid_exists(proxmox, int(payload["vmid"]))
    vmid = int(payload["vmid"])
    type = vm["type"]
    restart = payload.pop("restart", False)
    # if restart and _stop_vi(proxmox, vmid) != 0:
    #     return 1
    # Continue with modification after stopping the VM
    try:
        # sleep(5)
        if type == "qemu":
            print(f"🛡️Modifying QEMU VMID {vmid} on node {node}")
            proxmox.nodes(node).qemu(vmid).config.put(**payload)
        elif type == "lxc":
            print(f"🛡️Modifying LXC VMID {vmid} on node {node}")
            proxmox.nodes(node).lxc(vmid).config.put(**payload)
        else:
            print(f"❌ Unknown VM type for VMID {vmid}: {type}")
            return 1
    except Exception as exc:
        print(f"❌ Modification failed for VMID {vmid} on node {node}: {exc}")
        return 1
    else:
        if restart:
            _reboot_vi(proxmox, vmid)
        print(f"✅ Modified VMID {vmid} on node {node}")
        return 0

def _modify_vi(proxmox: ProxmoxAPI, args: argparse.Namespace) -> int:
    """Modify a VM or LXC container with the given VMID based on the provided arguments."""
    vmid = int(args.vmid)
    vm_config = _get_vi_config(proxmox, vmid)
    if not vm_config:
        print(f"❌ VMID {vmid} does not exist in the cluster.")
        return 1
    try:
        # print(f"Modifying VMID {vmid} with args: {args}")
        # print(f"Current configuration for VMID {vmid}: {vm_config}")
        if vm_config["type"] == "qemu":
            payload = _build_qemu_modify_payload(vm_config, args)
            # if args.dry_run:
            #     _dump_payload(payload, args.type, vm_config["node"])
            # else:
            #     pass

            _modify_vi_from_payload(payload, proxmox, vm_config["node"])
        elif vm_config["type"] == "lxc":
            payload = _build_lxc_modify_payload(vm_config, args)
            if args.dry_run:
                _dump_payload(payload, args.type, vm_config["node"])
            else:
                pass
                # _modify_vi_from_payload(payload, proxmox, vm_config["node"])
        else:
            print(f"❌ Unknown VM type for VMID {vmid}: {vm_config['type']}")
            return 1
    except Exception as exc:
        print(f"❌ Modification failed for VMID {vmid}: {exc}")
        return 1
    else:
        print(f"✅ Modified VMID {vmid}")
        return 0
