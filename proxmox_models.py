from abc import ABC

from pydantic import BaseModel, Field


class NetworkConfig(BaseModel):
    ip_address: str | None = None
    gateway: str | None = None

class DiskConfig(BaseModel):
    storage_pool: str
    image: str | None = None
    boot_disk_gb: int

class HardwareConfig(BaseModel):
    cores: int
    memory: int

class VirtualInstanceConfig(BaseModel, ABC):
    vmid: int
    hostname: str

    hardware: HardwareConfig
    disk: DiskConfig
    network: NetworkConfig

    tags: list[str] = Field(default_factory=list)

    pool: str | None = None
    display: str | None = None
    remarks: str | None = None

    onboot: bool = True
    start: bool = True

class LXCConfig(VirtualInstanceConfig):
    fuse: bool = False
    def render(self) -> dict:
        ip_string = f"ip={self.network.ip_address}/24,gw={self.network.gateway}" if self.network.ip_address else "ip=dhcp"
        
        return {
            "vmid": self.vmid,
            "hostname": self.hostname,
            "cores": self.hardware.cores,
            "memory": self.hardware.memory,
            "swap": 0,
            "ostemplate": f"ssd_pool:vztmpl/{self.disk.image}",  ## todo template directory should be configurable
            "rootfs": f"{self.disk.storage_pool}:{self.disk.boot_disk_gb}",
            "unprivileged": 1,
            "features": "nesting=1",
            "onboot": 1 if self.onboot else 0,
            "net0": f"name=eth0,bridge=vmbr0,{ip_string}",
            **({"pool": self.pool} if self.pool else {}),
            **({"tags": ",".join(self.tags)} if self.tags else {}),
            "start": 1 if self.start else 0,
        }

class CloudInitConfig(BaseModel): # VM only, LXC templates are pre-baked
    user: str
    vendor_config: str
    upgrade: bool = True
    ssh_keys: str | None = None
    password: str | None = None

class VMConfig(VirtualInstanceConfig):
    cloud_init: CloudInitConfig
    cpu_type: str | None = None
    display: str | None = None
    gpu_passthrough: str | None = None
    machine_type: str | None = None

    def render(self) -> dict:
        ip_string = f"ip={self.network.ip_address}/24,gw={self.network.gateway}" if self.network.ip_address else "ip=dhcp"
        user = "ubuntu" # todo args.user or _detect_user_from_image(args.image)
        return {
            "vmid": self.vmid,
            "name": self.hostname,
            "cores": self.hardware.cores,
            "memory": self.hardware.memory,
            "balloon": self.hardware.memory,
            "net0": "virtio,bridge=vmbr0",
            "scsihw": "virtio-scsi-single",
            "boot": "order=scsi0",
            "scsi0": f"{self.disk.storage_pool}:0,import-from=ssd_pool:import/{self.disk.image}", ## todo
            "ostype": "l26",
            "ide2": f"{self.disk.storage_pool}:cloudinit",
            "citype": "nocloud",
            "ciupgrade": 1, ## todo
            "ciuser": user,
            "agent": 1,
            "cicustom": f"vendor={self.cloud_init.vendor_config}", ## todo snippets location should be configurable
            "onboot": 1 if self.onboot else 0,
            "serial0": "socket",
            "ipconfig0": ip_string,
            **({"pool": self.pool} if self.pool else {}),
            **({"cpu": f"cputype={self.cpu_type},phys-bits=host"} if self.cpu_type == "host" else {"cpu": f"cputype={self.cpu_type}"} if self.cpu_type else {}),
            **({"tags": ",".join(self.tags)} if self.tags else {}),
            **({"hostpci0": self.gpu_passthrough} if self.gpu_passthrough else {}),
            **({"machine": self.machine_type} if self.machine_type else {}),
            "disk_size": self.disk.boot_disk_gb,
            "start": 1 if self.start else 0,
        }

class Identity(BaseModel):
    identity: str
    purpose: str | None = None

class State(BaseModel):
    node: str
    running: bool
    isha: bool

class Telemetry(BaseModel):
    cpu_usage: float
    memory_usage: float

class RebuildDefinition(BaseModel):
    playbook: str | None = None
    rebuildable: bool = True

class VirtualInstance(BaseModel):
    identity: Identity
    config: LXCConfig | VMConfig
    state: State
    telemetry: Telemetry | None
    rebuild: RebuildDefinition | None
    def render(self) -> dict:
        return self.config.render()

class Node(BaseModel):
    name: str
    cores: int
    memory: int
    telemetry: Telemetry | None

class Dependency(BaseModel):
    target: str
    dependency_type: str

class Service(BaseModel):
    name: str
    instances: list[str] = Field(default_factory=list)
    dependencies: list[Dependency] = Field(default_factory=list)

class Cluster(BaseModel):
    datacenter: str
    services: list[Service] = Field(default_factory=list)
    nodes: list[Node] = Field(default_factory=list)
    virtual_instances: list[VirtualInstance] = Field(default_factory=list)
    def get_instance(self, name: str) -> VirtualInstance | None:
        return next(
            (vi for vi in self.virtual_instances
             if vi.identity.identity == name),
            None,
        )

    def get_service(self, name: str) -> Service | None:
        return next(
            (s for s in self.services if s.name == name),
            None,
        )

    def get_node(self, name: str) -> Node | None:
        return next(
            (n for n in self.nodes if n.name == name),
            None,
        )

    def dump_graph(self):
        for service in self.services:
            for instance in service.instances:
                print(f"{service.name} --> {instance}")

            for dep in service.dependencies:
                print(f"{service.name} --> {dep.target}")
