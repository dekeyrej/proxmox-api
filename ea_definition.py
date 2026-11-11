from proxmox_models import (
    CloudInitConfig,
    Cluster,
    Dependency,
    DiskConfig,
    HardwareConfig,
    Identity,
    LXCConfig,
    NetworkConfig,
    Node,
    RebuildDefinition,
    Service,
    State,
    VirtualInstance,
    VMConfig,
)

manwe = VirtualInstance(
    identity = Identity(identity = "manwe", purpose = "Orchestrator"),
    config = VMConfig(
        vmid = 300,
        hostname = "manwe",
        cpu_type = "host",
        hardware = HardwareConfig(
            cores = 8,
            memory = 16384,
        ),
        disk = DiskConfig(
            storage_pool = "local-lvm",
            image = "ubuntu-26.04-server-cloudimg-amd64v3.qcow2",
            boot_disk_gb = 100
        ),
        network = NetworkConfig(
            ip_address = "192.168.86.10",
            gateway = "192.168.86.1"
        ),
        cloud_init = CloudInitConfig(
            user = "ubuntu",
            vendor_config = "local:snippets/ubuntu-vendor.yaml"
        ),
        tags = ["infrastructure","orchestrator"],
        pool = "Valinor",
        onboot = True,
        start = True
    ),
    state = State(
        node = "iluvatar",
        running = True,
        isha = False
    ),
    telemetry = None,
    rebuild = RebuildDefinition(
        playbook = "playbooks/the-creation-of-manwe.yaml",
        rebuildable = True
    )
)

erech = VirtualInstance(
    identity = Identity(identity = "erech", purpose = "CloudFlare Tunnel"),
    config = LXCConfig(
        vmid = 100,
        hostname = "erech",
        hardware = HardwareConfig(
            cores = 1,
            memory = 512,
        ),
        disk = DiskConfig(
            storage_pool = "local-lvm",
            image = "ubuntu-noble-latest-custom.tar.xz",
            boot_disk_gb = 4
        ),
        network = NetworkConfig(
            ip_address = "192.168.86.6",
            gateway = "192.168.86.1"
        ),
        tags = ["infrastructure","tunnel"],
        pool = "Lothlorien",
        onboot = True,
        start = True
    ),
    state = State(
        node = "iluvatar",
        running = True,
        isha = False
    ),
    telemetry = None,
    rebuild = RebuildDefinition(
        playbook = "playbooks/the-laying-of-erech.yaml",
        rebuildable = True
    )
)

iluvatar = Node(
    name = "iluvatar",
    cores = 32,
    memory = 131072,
    telemetry = None
)

tunnel = Service(
    name = "tunnel",
    instances = ["erech"],
    dependencies = []
)

kubernetes = Service(
    name = "kubernetes",
    instances = ["aragorn", "legolas", "gimli"],
    dependencies = []
)

vault = Service(
    name = "vault",
    instances = ["moria"],
    dependencies = [Dependency(target="kubernetes", dependency_type="requires")]
)

ollama = Service(
    name = "ollama",
    instances = ["elendil"],
    dependencies = []
)

open_webui = Service(
    name = "open-webui",
    instances = ["galadriel"],
    dependencies = [Dependency(target="ollama", dependency_type="requires")]
)

pbs = Service(
    name = "pbs",
    instances = ["cirdan"],
    dependencies = []
)

telegraf = Service(
    name = "telegraf",
    instances = [],
    dependencies = [Dependency(target="kubernetes", dependency_type="requires")]
)

mqtt = Service(
    name = "mqtt",
    instances = [],
    dependencies = [Dependency(target="kubernetes", dependency_type="requires")]
)

influxdb = Service(
    name = "influxdb",
    instances = [],
    dependencies = [Dependency(target="kubernetes", dependency_type="requires")]
)

grafana = Service(
    name = "grafana",
    instances = [],
    dependencies = [Dependency(target="kubernetes", dependency_type="requires")]
)

iot = Service(
    name = "iot",
    instances = [],
    dependencies = [Dependency(target="mqtt", dependency_type="requires"),
                    Dependency(target="telegraf", dependency_type="requires"),
                    Dependency(target="influxdb", dependency_type="requires"),
                    Dependency(target="grafana", dependency_type="requires")]
)

redis = Service(
    name = "redis",
    instances = [],
    dependencies = [Dependency(target="kubernetes", dependency_type="requires")]
)

microservices = Service(
    name = "microservices",
    instances = [],
    dependencies = [Dependency(target="kubernetes", dependency_type="requires"),
                    Dependency(target="vault", dependency_type="requires"),
                    Dependency(target="redis", dependency_type="requires")]
)

magicmirror = Service(
    name = "magicmirror",
    instances = ["gandalf"],
    dependencies = [Dependency(target="iot", dependency_type="requires")]
)

remote_admin = Service(
    name = "remote-admin",
    instances = [],
    dependencies = [Dependency(target="tunnel", dependency_type="requires")]
)

vectorstore = Service(
    name = "vectorstore",
    instances = ["elrond"],
    dependencies = []
)

RAGaaService = Service(
    name = "RAGaaS",
    instances = [],
    dependencies = [Dependency(target="ollama", dependency_type="requires"),
                    Dependency(target="vectorstore", dependency_type="requires")]
)

ea = Cluster(
    datacenter = "Ea",
    services=[tunnel, kubernetes, vault, ollama, open_webui, magicmirror, telegraf, mqtt, 
              influxdb, grafana, iot, redis, microservices, remote_admin, vectorstore, RAGaaService],
    nodes=[iluvatar],
    virtual_instances=[manwe, erech]
)

with open("ea.json", "w") as f:
    f.write(ea.model_dump_json(indent=2))

# with open("ea.json", "r") as f:
#     ea = Cluster.model_validate_json(f.read())

# print(json.dumps(ea.get_instance("manwe").render(), indent=2))  # outputs the rendered configuration of the "manwe" instance
# print(ea.get_service("magicmirror").model_dump_json(indent=2))
# print(ea.get_node("iluvatar").model_dump_json(indent=2))

# Visualize the services and instances graph
ea.dump_graph()