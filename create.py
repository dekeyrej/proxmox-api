from __future__ import annotations

import argparse
import os
from time import sleep
from typing import Any
from urllib import parse

from proxmoxer import ProxmoxAPI

from proxmox_utils import _vmid_exists

def _validate_vmid(proxmox: ProxmoxAPI, vmid: int, fallback: bool = False) -> int:
    try:
        if vmid:
            found_vm = _vmid_exists(proxmox, int(vmid))
            if found_vm:
                print(f"VMID {vmid} (type={found_vm['type']}) in {found_vm['status']} on node {found_vm['node']} as '{found_vm['name']}'.")
                if fallback:
                    vmid = int(proxmox.cluster.nextid.get())
                    print(f"VMID {found_vm['vmid']} is in use, falling back to next available VMID: {vmid}")
                else:
                    return 1
        else:
            vmid = int(proxmox.cluster.nextid.get())
            print(f"No VMID specified, using next available VMID: {vmid}")
    except Exception as exc:
        print(f"Error validating VMID: {exc}")
        raise
    else:
        return vmid

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

def _create_vi(proxmox: ProxmoxAPI, args: argparse.Namespace) -> int:
    """Create a VM or LXC container with the given (or inferred) VMID based on the provided arguments."""
    if args.list:
        args.storage_id = args.logical_import_path.split(":")[0] if args.type == "qemu" else args.logical_template_path.split(":")[0]
        _list_available_images(proxmox, args.node, args.storage_id, args.type)
        return 0
    elif not args.image and not args.list:
        print("❌ Error: --image is required for create command unless --list is specified.")
        return 2
    else:
        args.vmid = _validate_vmid(proxmox, args.vmid, args.fallback)
        if args.vmid < 100:
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
        return 0
