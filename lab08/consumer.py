import paho.mqtt.client as mqtt
import json
import argparse
from datetime import datetime, timezone

class Consumer:

    def __init__(self, broker, port, topic, qos, out_file, verbose=False):
        self.broker = broker
        self.port = port
        self.topic = topic
        self.qos = qos
        self.out_file = out_file
        self.verbose = verbose

        self.total_messages_received = 0
        self.sum_of_all_latencies = 0.0

        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)

        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message

    def _on_connect(self, client, userdata, flags, rc):
        print(f"Connect to Broker (Code: {rc})")
        self.client.subscribe(self.topic, qos=self.qos)
        print(f"Subscribe to topic: {self.topic} (QoS: {self.qos})")
        print(f"Data save to : {self.out_file}\n")

    def _on_message(self, client, userdata, msg):
        # Καταγραφή του χρόνου άφιξης
        ingest_time = datetime.now(timezone.utc)
        ingest_time_iso = ingest_time.isoformat(timespec="milliseconds").replace("+00:00", "Z")
        
        payload_str = msg.payload.decode("utf-8")
        
        if payload_str == "Status : Offline":
            print("\n⚠️ Ο Producer is Offline.")
            return

        try:
            record = json.loads(payload_str)
            event_time_str = record.get("event_time")
            
            if event_time_str:
                event_time = datetime.fromisoformat(event_time_str.replace("Z", "+00:00"))
                latency = (ingest_time - event_time).total_seconds() * 1000
                
                record["ingest_time"] = ingest_time_iso
                record["latency_ms"] = round(latency, 2)
                
                self.total_messages_received += 1
                self.sum_of_all_latencies += latency
                average_latency = self.sum_of_all_latencies / self.total_messages_received
                
                print(f"Metrics Update [Seq: {record.get('seq', '?')}] ---")
                print(f"Latency:           {latency:.2f} ms")
                print(f"Total Messages:          {self.total_messages_received}")
                print(f"Avg Latency: {average_latency:.2f} ms")
                
                
            else:
                record["ingest_time"] = ingest_time_iso
                record["latency_ms"] = None

            record_json_string = json.dumps(record, ensure_ascii=False)
            with open(self.out_file, "a", encoding="utf-8") as f:
                f.write(record_json_string + "\n")
                
        except json.JSONDecodeError:
            print(payload_str)
        except Exception as e:
            print(e)

        if self.verbose:
            print(f"--- 📊 Metrics Update [Seq: {record.get('seq', '?')}] ---")
            print(f"🔹 Latency:           {latency:.2f} ms")

    def start(self):
        print(f"Connect to Broker {self.broker}:{self.port}...")
        self.client.connect(self.broker, self.port, 60)
        
        try:
            self.client.loop_forever()
        except KeyboardInterrupt:
            self.stop()
    
    def stop(self):
        print("\nConsumer Ctrl-C")
        self.client.disconnect()
        print("Disconnected.")

    # self.client.on_connect = self._on_connect
    # self.client.on_message = self._on_message

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MQTT Consumer")
    
    parser.add_argument("--broker", type=str, default="localhost", help="MQTT Broker")
    parser.add_argument("--port", type=int, default=1883, help="MQTT Broker PORT")
    parser.add_argument("--topic", type=str, required=True, help="MQTT Topic to Subscribe")
    parser.add_argument("--qos", type=int, choices=[0, 1, 2], default=0, help="MQTT QoS (0, 1 ή 2)")
    parser.add_argument("--out", type=str, required=True, help="Output file (π.χ. data.jsonl)")
    parser.add_argument("--verbose", action="store_true")

    args = parser.parse_args()

    consumer = Consumer(
        broker=args.broker,
        port=args.port,
        topic=args.topic,
        qos=args.qos,
        out_file=args.out,
        verbose=args.verbose
    )
    print("1")
    consumer.start()
    print("2")