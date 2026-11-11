```mermaid
graph TD
    tunnel[tunnel]
    erech[erech]
    kubernetes[kubernetes]
    aragorn[aragorn]
    legolas[legolas]
    gimli[gimli]
    vault[vault]
    moria[moria]
    ollama[ollama]
    elendil[elendil]
    open-webui[open-webui]
    galadriel[galadriel]
    magicmirror[magicmirror]
    gandalf[gandalf]
    iot[iot]
    telegraf[telegraf]
    mqtt[mqtt]
    influxdb[influxdb]
    grafana[grafana]
    redis[redis]
    microservices[microservices]
    remote-admin[remote-admin]
    vectorstore[vectorstore]
    RAGaaS[RAGaaS]
    elrond[elrond]
    
    tunnel --> erech
    kubernetes --> aragorn
    kubernetes --> legolas
    kubernetes --> gimli
    vault --> moria
    vault --> kubernetes
    ollama --> elendil
    open-webui --> galadriel
    open-webui --> ollama
    magicmirror --> gandalf
    magicmirror --> iot
    telegraf --> kubernetes
    mqtt --> kubernetes
    influxdb --> kubernetes
    grafana --> kubernetes
    iot --> mqtt
    iot --> telegraf
    iot --> influxdb
    iot --> grafana
    redis --> kubernetes
    microservices --> kubernetes
    microservices --> vault
    microservices --> redis
    remote-admin --> tunnel
    vectorstore --> elrond
    RAGaaS --> ollama
    RAGaaS --> vectorstore
    
    classDef infraNode stroke:#818cf8,fill:#eef2ff
    classDef appNode stroke:#2dd4bf,fill:#f0fdfa
    classDef dataNode stroke:#a78bfa,fill:#f5f3ff
    classDef iotNode stroke:#fb923c,fill:#fff7ed
    classDef securityNode stroke:#e879f9,fill:#fdf4ff
    classDef virtualInstance stroke:#38bdf8,fill:#f0f9ff,stroke-width:2px,stroke-dasharray:5 3
    
    class kubernetes,iot infraNode
    class open-webui,ollama,RAGaaS appNode
    class influxdb,vectorstore,redis dataNode
    class telegraf,mqtt,grafana iotNode
    class vault,remote-admin,tunnel securityNode
    class erech,galadriel,elendil,elrond,moria,gandalf,aragorn,legolas,gimli virtualInstance