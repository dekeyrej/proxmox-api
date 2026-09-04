# PROXMOX_CLUSTER_NAME is required from environment, and used to read the cluster config file
"""
Connects to Proxmox API
using environment variables: 
PROXMOX_HOST, PROXMOX_USER, and either: 
PROXMOX_TOKEN_ID and PROXMOX_TOKEN_SECRET (preferred) or 
PROXMOX_PASSWORD (deprecated). 
Disable SSL verify with PROXMOX_VERIFY_SSL=0.
"""

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
        # print(vm)
        return vm
    return None

def _stop_vi(proxmox: ProxmoxAPI, vmid: int) -> int:
    """Stop a VM or LXC container with the given VMID."""
    vm = _vmid_exists(proxmox, vmid)
    if not vm:
        print(f"❌ VMID {vmid} does not exist in the cluster.")
        return 1
    node = vm["node"]
    status = vm["status"]
    type = vm["type"]
    try:
        if status != "stopped":
            print(f"ℹ️ Stopping VMID {vmid} on node {node}")
            if type == "qemu":
                proxmox.nodes(node).qemu(vmid).status.stop.post()
                while proxmox.nodes(node).qemu(vmid).status.current.get()["status"] != "stopped":
                    sleep(1)
            elif type == "lxc":
                proxmox.nodes(node).lxc(vmid).status.stop.post()
                while proxmox.nodes(node).lxc(vmid).status.current.get()["status"] != "stopped":
                    sleep(1)
            else:
                print(f"❌ Unknown VM type for VMID {vmid}: {type}")
                return 1
        else:
            print(f"ℹ️ VMID {vmid} is already stopped on node {node}")
    except Exception as exc:
        print(f"❌ Failed to stop VMID {vmid}: {exc}")
        return 1
    else:
        print(f"✅ Stopped VMID {vmid} on node {node}")
        return 0

def _start_vi(proxmox: ProxmoxAPI, vmid: int) -> int:
    """Start a VM or LXC container with the given VMID."""
    vm = _vmid_exists(proxmox, vmid)
    if not vm:
        print(f"❌ VMID {vmid} does not exist in the cluster.")
        return 1
    node = vm["node"]
    status = vm["status"]
    type = vm["type"]
    try:
        if status != "running":
            print(f"ℹ️ Starting VMID {vmid} on node {node}")
            if type == "qemu":
                proxmox.nodes(node).qemu(vmid).status.start.post()
                while proxmox.nodes(node).qemu(vmid).status.current.get()["status"] != "running":
                    sleep(1)
            elif type == "lxc":
                proxmox.nodes(node).lxc(vmid).status.start.post()
                while proxmox.nodes(node).lxc(vmid).status.current.get()["status"] != "running":
                    sleep(1)
            else:
                print(f"❌ Unknown VM type for VMID {vmid}: {type}")
                return 1
        else:
            print(f"ℹ️ VMID {vmid} is already running on node {node}")
    except Exception as exc:
        print(f"❌ Failed to start VMID {vmid}: {exc}")
        return 1
    else:
        print(f"✅ Started VMID {vmid} on node {node}")
        return 0

def _reboot_vi(proxmox: ProxmoxAPI, vmid: int) -> int:
    """Reboot a VM or LXC container with the given VMID."""
    vm = _vmid_exists(proxmox, vmid)
    if not vm:
        print(f"❌ VMID {vmid} does not exist in the cluster.")
        return 1
    node = vm["node"]
    status = vm["status"]
    type = vm["type"]
    try:
        if status == "running":
            print(f"ℹ️ Rebooting VMID {vmid} on node {node}")
            if type == "qemu":
                proxmox.nodes(node).qemu(vmid).status.reboot.post()
                while proxmox.nodes(node).qemu(vmid).status.current.get()["status"] != "running":
                    sleep(1)
            elif type == "lxc":
                proxmox.nodes(node).lxc(vmid).status.reset.post()
                while proxmox.nodes(node).lxc(vmid).status.current.get()["status"] != "running":
                    sleep(1)
            else:
                print(f"❌ Unknown VM type for VMID {vmid}: {type}")
                return 1
    except Exception as exc:
        print(f"❌ Failed to reboot VMID {vmid}: {exc}")
        return 1
    else:
        print(f"✅ Rebooted VMID {vmid} on node {node}")
        return 0
