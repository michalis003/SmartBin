# SmartBin — Custom Ontology Terms

Base namespace: `https://github.com/michalis003/SmartBin/blob/main/docs/ontology.md#`

Prefixes used in JSON-LD: 
* `pipeline` (Telemetry & MQTT Data)
* `project` (Hardware & Domain Specifics)

---

## 1. Pipeline & Telemetry Terms (`pipeline:`)

### sequenceNumber
- **Type:** `xsd:integer`
- **Description:** A strictly increasing integer sequence number assigned to each event by the MQTT producer (sensor node) to detect missing or out-of-order packets.

### runId
- **Type:** `xsd:string`
- **Description:** A unique UUID string identifying the current execution session of the data collection pipeline.

### ingestTime
- **Type:** `xsd:dateTime`
- **Description:** The exact UTC timestamp when the MQTT broker/consumer successfully received and logged the event.

### latencyMs
- **Type:** `xsd:float`
- **Description:** Time in milliseconds between event creation by the producer (`event_time`) and ingestion by the consumer (`ingest_time`). Measures network and pipeline delay.

---

## 2. Hardware & SmartBin Terms (`project:`)

### hardwareConnection
- **Type:** `schema:StructuredValue`
- **Description:** An object describing how a sensor or actuator is physically wired to the main microcomputer (e.g., Raspberry Pi 5).

### dataPin
- **Type:** `xsd:string`
- **Description:** The specific GPIO pin identifier (e.g., "GPIO17") used for data transmission.

### capacityLiters
- **Type:** `xsd:integer`
- **Description:** The maximum internal volume of the waste container, measured in liters.

### fillLevelPercentage
- **Type:** `xsd:float`
- **Description:** The current amount of waste inside the container, expressed as a percentage (0.0 to 100.0) of its total capacity.