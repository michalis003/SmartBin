import paho.mqtt.client as mqtt
import json
import argparse
from datetime import datetime, timezone
import time
from collections import deque
import threading
from datetime import timedelta

from file_read_backwards import FileReadBackwards

class Analyzer:

    def __init__(self, broker, port, topic, publish_topic, window, interval, qos, event_file, pir_id, bin_id):
        self.broker = broker
        self.port = port
        # self.topic = topic

        # self.publish_topic = publish_topic
        self.window = window
        self.interval = interval

        self.qos = qos
        self.event_file = event_file

        self.pir_id = pir_id
        self.bin_id = bin_id

        self.basic_topic = "smartbin/" + self.bin_id + "/" + self.pir_id + "/"
        self.topic = self.basic_topic + topic
        self.publish_topic = self.basic_topic + publish_topic

        self.total_messages_received = 0
        self.sum_of_all_latencies = 0.0


        self.event_times = deque()
        self.event_lock = threading.Lock()




        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, client_id= "virtual-sensor-rules")

        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message

    def _on_connect(self, client, userdata, flags, rc):
        print(f"Connect to Broker (Code: {rc})")
        self.client.subscribe(self.topic, qos=self.qos)
        print(f"Subscribe to topic: {self.topic} (QoS: {self.qos})")
        print(f"Window size : {self.window}")
        print(f"Interval time : {self.interval}")

    def _on_message(self, client, userdata, msg):
        if msg.retain: return

        ingest_time = datetime.now(timezone.utc)
        ingest_time_iso = ingest_time.isoformat(timespec="milliseconds").replace("+00:00", "Z")
        
        
        try:
            payload_str = msg.payload.decode("utf-8")
            payload_dict = json.loads(payload_str)

            if payload_dict.get("motion_state") == "detected":

                with self.event_lock:
                    self.event_times.append(datetime.now(timezone.utc))


        except json.JSONDecodeError: pass
        

    def evaluate_usage(self):

        cotoff_time = datetime.now(timezone.utc) - timedelta(minutes= self.window)

        with self.event_lock:
            while self.event_times and self.event_times[0] < cotoff_time:
                self.event_times.popleft()
            
            counter = len(self.event_times)

            if counter == 0:
                return "idle", counter
            elif counter <= 5:
                return "low", counter
            elif counter <= 15:
                return "medium", counter
            else:
                return "high", counter

    def _load_history(self, filepath):
        print(f"Loading History ....")
        cutoff_time = datetime.now(timezone.utc) - timedelta(minutes=self.window)
        
        try:
            with FileReadBackwards(filepath, encoding="utf-8") as f:
                for line in f:
                    try:
                        record = json.loads(line)
                        if record.get("motion_state") == "detected":
                            time_str = record.get("event_time") or record.get("ingest_time")
                            if time_str:
                                event_time = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
                                
                                if event_time < cutoff_time:
                                    break 
                                
                                self.event_times.appendleft(event_time)
                                
                    except (json.JSONDecodeError, ValueError):
                        pass
                        
            print(f"Loading is completed counter = {len(self.event_times)} .")
            
        except FileNotFoundError:
            print(f"file {filepath} cant be found. We start from 0.")
        except Exception as e:
            print(f"Error : {e}")
    
    def _publish_discovery(self):
        discovery_topic = f"homeassistant/sensor/team09_{self.bin_id}_{self.pir_id}_usage/config"
        
        discovery_payload = {
            "name": f"Usage Level ({self.bin_id})",
            "state_topic": self.publish_topic,
            "value_template": "{{ value_json.usage_level }}",
            "json_attributes_topic": self.publish_topic, # Έτσι το HA βλέπει το event_count και το window!
            "unique_id": f"team09_{self.bin_id}_{self.pir_id}_usage",
            "icon": "mdi:delete-variant", # Εικονίδιο κάδου
            "device": {
                "identifiers": [f"smartbin-{self.bin_id}-{self.pir_id}"],
                "name": f"Smart Wastebin {self.bin_id}-{self.pir_id}",
                "model": "SmartBin",
                "manufacturer": "Team 09"
            }
        }
        
        self.client.publish(discovery_topic, json.dumps(discovery_payload), qos=self.qos, retain=True)
        print(f"🛠️ Published HA discovery config to {discovery_topic}")

    

    def start(self):
        print(f"Connect to Broker {self.broker}:{self.port}...")
        self.client.connect(self.broker, self.port, 60)

        self._load_history(self.event_file)

        self._publish_discovery()

        self.client.loop_start()

        try:
            while True:
                usage_lvl, counter = self.evaluate_usage()
                print(f"Counter = {counter} and Usage level = {usage_lvl}")

                ingest_time = datetime.now(timezone.utc)
                ingest_time_iso = ingest_time.isoformat(timespec="milliseconds").replace("+00:00", "Z")

                payload = {
                    "usage_level": usage_lvl,
                    "event_count": counter,
                    "window_size_in_minutes": self.window,
                    "current_utc_evaluation_timestamp": ingest_time_iso
                }

                self.client.publish(self.publish_topic, json.dumps(payload), qos=self.qos, retain=True)
                time.sleep(self.interval)
            

        except KeyboardInterrupt:
            self.stop()
        finally:
            self.stop()
    
    def stop(self):
        print("Stopping Background Loop...")
        self.client.loop_stop()
        self.client.disconnect()
        print("Disconnected cleanly.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MQTT analyzer")
    
    parser.add_argument("--broker", type=str, default="localhost", help="MQTT Broker")
    parser.add_argument("--port", type=int, default=1883, help="MQTT Broker PORT")
    parser.add_argument("--topic", type=str, default = "events", help="MQTT Topic to Subscribe")

    parser.add_argument("--publishΤopic", type = str, default ="usage")
    parser.add_argument("--window", type = int, default=5, help= "usage evaluation window in minutes")
    parser.add_argument("--interval", type = int, default= 30, help= "time between evaluations in seconds")

    parser.add_argument("--qos", type=int, choices=[0, 1, 2], default=0, help="MQTT QoS (0, 1 ή 2)")
    parser.add_argument("--eventFile", type=str, default = "output/motion_events.jsonl", help="The file that will load past events")
    # parser.add_argument("--verbose", action="store_true")

    parser.add_argument("--pirId", type=str, default="pir-01", help="PIR id")
    parser.add_argument("--binId", type=str, default="bin-01", help="Bin id")

    # broker= localhost
    # port= 1883
    # topic= "smartbin/bin-01/pir-01/events"
    # qos= 0
    # out_file= "app/output/motion_events.jsonl"
    # verbose= True

    args = parser.parse_args()

    analyzer = Analyzer(
        broker=args.broker,
        port=args.port,
        topic=args.topic,

        publish_topic = args.publishΤopic,
        window = args.window,
        interval = args.interval,

        qos=args.qos,
        event_file = args.eventFile,

        pir_id = args.pirId,
        bin_id = args.binId

    )
    analyzer.start()