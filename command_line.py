import argparse

def _get_command_line_args(argv, DEFAULTS) -> list[str]:
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
    common_create_parser.add_argument("-v", "--vmid", type=int, help="VM ID (optional, auto-assigned if not provided)")
    common_create_parser.add_argument("-o", "--hostname", help="VM Hostname (optional, defaults to vm-VMID)")
    common_create_parser.add_argument("-c", "--cores", default=2, type=int, help="VM Number of CPU cores (default 2)")
    common_create_parser.add_argument("-m", "--memory", default=2048, type=int, help="VM Memory size in MB (default 2048)")
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
    common_modify_parser.add_argument("-c", "--cores", default=2, type=int, help="new VM/CT Number of CPU cores") # restart required for qemu, not for lxc
    common_modify_parser.add_argument("-m", "--memory", default=2048, type=int, help="new VM/CT Memory size in MB") # restart required for qemu, not for lxc
    common_modify_parser.add_argument("-b", "--boot_disk", default=0, type=int, help="new VM/CT boot disk size in GB") # restart required
    common_modify_parser.add_argument("-a", "--ipaddress", default="", help="new VM/CT IP address (optional), pass 'dhcp' to use DHCP") # restart required
    common_modify_parser.add_argument("-w", "--gateway", default=DEFAULTS["gateway"], help="VM Gateway (default is the value from DEFAULTS)")
    common_modify_parser.add_argument("-p", "--resource_pool", default="", help="new VM/CT Resource pool (optional)") # restart not required
    common_modify_parser.add_argument("-r", "--remarks", default="", help="new VM/CT Remarks (optional)") # restart not required
    common_modify_parser.add_argument("-g", "--tags", default="", help="new VM/CT Tags (optional)") # restart not required
    common_modify_parser.add_argument("-k", "--sshkeys", default="", help="VM (user)/CT (root) new SSH public keys (literal or path to LOCAL file)") # restart required
    common_modify_parser.add_argument("-s", "--storage_pool", default=DEFAULTS["storage_pool"], help="VM Storage pool (default is the value from DEFAULTS)")
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
