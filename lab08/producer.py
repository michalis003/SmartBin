import paho.mqtt.client as mqtt
import uuid
import time
import json
import argparse
from datetime import datetime, timezone

from pirlib.sampler import PirSampler
from pirlib.interpreter import PirInterpreter


class Producer:

    def __init__(self, broker, port, topic, device_id, pin, sample_interval, cooldown, min_high, qos) :
        
        self.broker = broker
        self.port = port
        self.topic = topic
        self.device_id = device_id
        self.pin = pin
        self.sample_interval = sample_interval
        self.qos = qos

        self.sampler = PirSampler(pin=self.pin)
        self.interp = PirInterpreter(cooldown_s=cooldown, min_high_s=min_high)

        self.run_id = str(uuid.uuid4())
        self.seq = 0
        self.is_running = False

        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)


        self.client.on_message = self._on_message


    def _on_message(self, client, userdata, msg):
        print(3)
        topic = msg.topic
        payload_str = msg.payload.decode("utf-8")

        print(1)
        if self.topic == topic:
            print(2)
            try:
                payload_dict = json.loads(payload_str)
                if payload_dict.get("motion_state") == "empty":
                    print("The self.seq = 0")
                    self.seq = 0
            except json.JSONDecodeError:
                pass
            # if payload.g== {"motion_state": "empty"}:
            #     print("The self.seq=0")
            #     self.seq =0


    def _run_loop(self):

        while self.is_running:
            current_time_float = time.time()

            sample = self.sampler.read()
            events = self.interp.update(sample, current_time_float)

            for event in events:
                self.seq += 1
                event_iso_time = datetime.fromtimestamp(event["t"], timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")

                record = {
                    "@context": "https://raw.githubusercontent.com/michalis003/ECE-CK801-Advanced-Programming-Techniques/main/context.jsonld",
                    "@type": "sosa:Observation",
                    "madeBySensor": f"ngsi-ld:Sensor:Motion_{self.device_id}", 
                    "hasFeatureOfInterest": f"urn:ngsi-ld:Wastebin:Bin_{self.device_id}",
                    "event_time": event_iso_time,
                    "event_type": "motion",
                    "motion_state": "detected", 
                    "seq": self.seq,
                    "run_id": self.run_id,
                }

                json_record = json.dumps(record)

                self.client.publish(self.topic, json_record, self.qos) #For the consumer

                state_topic = f"smartbin/team09/{self.device_id}/state"
                self.client.publish(state_topic, "detected", self.qos) #For the Home Assistan 

                print(f"[{datetime.now().strftime('%H:%M:%S')}] Published (QoS {self.qos}) to {self.topic}")                
    
            time.sleep(self.sample_interval)

    def start(self):
        print(f"Connect to Broker {self.broker}:{self.port}, QoS {self.qos}")
        self.client.connect(self.broker, self.port, 60)
        self.client.subscribe(self.topic, self.qos)
        print(f"Sub to {self.topic}")

        self.client.loop_start()
        self.is_running = True
        
        discovery_topic = f"homeassistant/binary_sensor/team09_{self.device_id}_motion/config"
        state_topic = f"smartbin/team09/{self.device_id}/state"
        
        discovery_payload = {
            "name": f"PIR Motion Sensor {self.device_id}",
            "state_topic": state_topic,
            "payload_on": "detected",
            "payload_off": "clear",
            "device_class": "motion",
            "off_delay": 4,
            "unique_id": f"team09_{self.device_id}_motion",
            "device": {
                "identifiers": [f"smartbin-{self.device_id}"],
                "name": f"Smart Wastebin {self.device_id}",
                "model": "SmartBin v1",
                "manufacturer": "Team 09"
            }
        }
        self.client.publish(discovery_topic, json.dumps(discovery_payload), qos=self.qos, retain=True)
        print(f"Published HA discovery config to {discovery_topic}")

        try:
            self._run_loop()
        except KeyboardInterrupt:
            self.stop()

    def stop(self):
        self.is_running = False
        self.client.publish(self.topic, "Status : Offline", qos=self.qos, retain=True)
        self.client.loop_stop()
        self.client.disconnect()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MQTT Producer for PIR Sensor")
    
    parser.add_argument("--broker", type=str, default="localhost")
    parser.add_argument("--port", type=int, default=1883)
    parser.add_argument("--topic", type=str, required=True)
    parser.add_argument("--device-id", type=str, required=True)
    parser.add_argument("--pin", type=int, required=True)
    parser.add_argument("--sample-interval", type=float, default=0.1)
    parser.add_argument("--cooldown", type=float, default=5.0)
    parser.add_argument("--min-high", type=float, default=0.2)
    parser.add_argument("--qos", type=int, choices=[0, 1, 2], default=0, help="MQTT QoS level (0, 1, or 2)")

    args = parser.parse_args()

    producer = Producer(
        broker=args.broker,
        port=args.port,
        topic=args.topic,
        device_id=args.device_id,
        pin=args.pin,
        sample_interval=args.sample_interval,
        cooldown=args.cooldown,
        min_high=args.min_high,
        qos=args.qos 
    )
    
    producer.start()