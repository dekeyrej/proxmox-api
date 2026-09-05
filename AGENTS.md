# AGENTS.md

This file contains concise, agent‑specific guidance for working in the **proxmox‑api** repo.  It focuses on commands or configuration details that are **not** obvious from the project layout or documentation.

---

## 1.  Setting up the environment

* The repository is a tiny CLI tool.  The only runtime requirement is **Python 3.12** and the dependencies listed in `pyproject.toml`.
* A local virtualenv already exists (`.venv`).  The shipped `pvi` wrapper will automatically activate it.  If you prefer to work manually:
```
source .venv/bin/activate
uv sync          # install dependencies from pyproject.toml
```
* The tool expects a Proxmox cluster configuration file.  By default it looks for `~/.proxmox/example.env`.  Override the cluster name or location with:
```
export PROXMOX_CLUSTER_DIR="/path/to/cluster/dir"
export PROXMOX_CLUSTER_NAME="mycluster"
```
  The file must define at least `PROXMOX_HOST`, `PROXMOX_USER`, and either a token pair or a password.
  The directory/file permissions should be set to: 700/600 respectively

## 2.  How to run `pvi`

* The entry point is the shell wrapper `./pvi`.  It locates the virtualenv, activates it, then runs `pvi.py` with the supplied arguments.
* Most agents will simply run:
```
./pvi <subcommand> [options]
```
  For advanced users or CI you can skip the wrapper:
```
uv run pvi.py <subcommand> [options]
```
* Run `./pvi --help` to see all subcommands and flags.
* (optionally) Install to /usr/local/bin/pvi with `sudo install pvi /usr/local/bin`

## 3.  Default values driven by environment

| Variable | Purpose | Default (if unset) |
|----------|---------|--------------------|
| `PVENODE` | Node name for the VM/CT | `local` |
| `GATEWAY` | Default gateway for VMs/CTs | `192.168.1.1` |
| `STORAGE_POOL` | Storage pool used for a new VM/CT | `local-lvm` |
| `SSHKEYS` | SSH public‑key(s) added to the guest | `~/.ssh/authorized_keys` |
| `LOGICAL_IMPORT_PATH` | Path for importing QEMU images | `local:import` |
| `LOGICAL_TEMPLATE_PATH` | Path for importing LXC templates | `local:vztmpl` |

These defaults can be overridden per‑command with the corresponding flags (`-n`, `-w`, `-s`, …).  The wrapper automatically exports `PROXMOX_CLUSTER_DIR` to `/home/ubuntu/.proxmox`.

## 4.  Subcommands & key options

| Subcommand | Typical use | Important flags |
|------------|-------------|-----------------|
| `check` | Verify existence of a VM/CT | `--vmid` |
| `create` | Create a new VM (qemu) or LXC container | `--type qemu|lxc`; common flags: `-i`, `-v`, `-o`, `-c`, `-m`, `-b`, `-a`, `-n`, `-w`, `-s`; special QEMU flags: `-t`, `-e`, `-T`, `-d`, `-P`, `-l`; special LXC flags: `-l`, `-O`; flags: `-L list images`, `-R dry‑run`, `-S no‑start`, `-F fallback` |
| `modify` | Update an existing VM/CT | Command‑type `qemu|lxc`; core flags similar to `create`; `-y` to skip confirmation |
| `backup` | Create an offline backup of a VM/CT | `--vmid`, `--storage_id` |
| `delete` | Remove a VM/CT | `--vmid`, `-y` to skip confirmation |

### Quick command templates
```
# Check if VM 101 exists
./pvi check --vmid 101

# Create a QEMU VM with two cores and 4 GB RAM, start immediately
./pvi create qemu -i base.img -v 102 -c 2 -m 4096 -S  # -S keeps it stopped if you want

# List available images to import
./pvi create qemu -L # lists qcow2 images from `local:import`
./pvi create lxc -L  # lists tar.xz templates from `local:vztmpl`
```

## 5.  Common pitfalls

* **Missing Proxmox credentials** – if `uv run pvi.py` fails with a *credentials‑missing* error, confirm the `~/.proxmox/<name>.env` file contains `PROXMOX_TOKEN_ID` and `PROXMOX_TOKEN_SECRET` (or password).  Do not rely on local socket auth except when you are running on the Proxmox node itself.
* **SSL errors** – set `PROXMOX_VERIFY_SSL=0` to skip verification if you are using a self‑signed cert.
* **Incorrect node name** – use `PVENODE` or `--node` to point to the right cluster node.  The node name must exist in the cluster.
* **Large image transfer** – creating a VM from a large image may take several minutes.  Use `-R dry‑run` first to validate arguments.

## 6.  Existing instruction references

* Primary docs: `README.md` – quick usage guide.
* Example environment files: `example.env`, `ea.env`, etc.
* For the exact argument list, consult the source of `command_line.py`.

---

**End of AGENTS.md**
