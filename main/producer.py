import paho.mqtt.client as mqtt
import uuid
import time
import json
import argparse
from datetime import datetime, timezone
import random
import math

from pirlib.sampler import PirSampler
from pirlib.sampler import VirtualPirSampler
from pirlib.interpreter import PirInterpreter


class Producer:

    def __init__(self, broker, port, topic, device_id, bin_id, pin, sample_interval, cooldown, min_high, qos, is_virtual, latitude, longitude) :
        
        self.broker = broker
        self.port = port
        self.topic = topic
        self.device_id = device_id
        self.bin_id = bin_id
        self.pin = pin
        self.sample_interval = sample_interval
        self.qos = qos

        self.lat = latitude
        self.long = longitude

        self.is_virtual = is_virtual
        if self.is_virtual:
            print(f"🔄 Εκκίνηση σε VIRTUAL mode για τον κάδο {self.bin_id}/{self.device_id}")
            # Μπορείς να παίξεις με το probability για να έχεις πιο "busy" κάδους
            self.sampler = VirtualPirSampler(motion_probability=0.02, hold_time_s=1.5)
            self.lat, self.long = self._generate_random_location(self.lat, self.long, 250)
            print(f"the virtual gord is lat = {self.lat} and long = {self.long}")
        else:
            self.sampler = PirSampler(pin=self.pin)
        
        self.interp = PirInterpreter(cooldown_s=cooldown, min_high_s=min_high)

        self.run_id = str(uuid.uuid4())
        self.seq = 0
        self.is_running = False

        self.basic_topic = self.topic + "/" + self.bin_id + "/" + self.device_id + "/"

        self.consumer_topic = self.basic_topic + "events"
        print(f"Consumer_topic = {self.consumer_topic}")

        self.homeassistant_topic = self.basic_topic + "state"
        print(f"Homeassistant_topic = {self.homeassistant_topic}")

        self.sub_topic = self.basic_topic + "cleared"
        self.seq_topic = self.basic_topic + "seq"
        self.availability_topic = self.basic_topic + "availability"
        self.coorditates_topic = self.basic_topic + "coorditates"
        self.has_synced_seq = False

        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)

        self.client.will_set(self.availability_topic, payload="offline", qos=1, retain=True)


        self.client.on_message = self._on_message

    def _generate_random_location(self, base_lat, base_lon, radius_meters):
        random.seed(str(self.bin_id))
        earth_radius = 6371000 
        distance = radius_meters * math.sqrt(random.random())
        angle = random.uniform(0, 2 * math.pi)

        delta_lat = math.degrees(distance * math.cos(angle) / earth_radius)
        delta_lon = math.degrees(distance * math.sin(angle) / (earth_radius * math.cos(math.radians(base_lat))))

        return base_lat + delta_lat, base_lon + delta_lon

    def _on_message(self, client, userdata, msg):
        topic = msg.topic
        payload_str = msg.payload.decode("utf-8")

        if self.sub_topic == topic:
            try:
                payload_dict = json.loads(payload_str)
                if payload_dict.get("motion_state") == "empty":
                    print("The self.seq = 0")
                    self.seq = 0
                    self.client.publish(self.seq_topic, str(self.seq), qos=1, retain=True)
            except json.JSONDecodeError:
                pass

        elif self.seq_topic == topic:
            if not self.has_synced_seq:
                try:
                    self.seq = int(payload_str)
                    self.has_synced_seq = True
                    print(f"The seq is synced seq = {self.seq}")
                except ValueError:
                    print(f"Not valid seq from HA: {payload_str}")


    def _run_loop(self):

        while self.is_running:
            current_time_float = time.time()

            sample = self.sampler.read()
            events = self.interp.update(sample, current_time_float)

            for event in events:
                self.seq += 1

                self.client.publish(self.seq_topic, str(self.seq), qos=1, retain=True)

                event_iso_time = datetime.fromtimestamp(event["t"], timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")

                record = {
                    "@context": "https://raw.githubusercontent.com/michalis003/SmartBin/main/models/context.jsonld",
                    "@type": "Observation",
                    "madeBySensor": f"urn:ngsi-ld:Sensor:Motion_{self.device_id}", 
                    "hasFeatureOfInterest": f"urn:ngsi-ld:Wastebin:{self.bin_id}",
                    "event_time": event_iso_time,
                    "event_type": "motion",
                    "motion_state": "detected", 
                    "seq": self.seq,
                    "run_id": self.run_id,
                }

                json_record = json.dumps(record)

                self.client.publish(self.consumer_topic, json_record, self.qos) #For the consumer
                self.client.publish(self.homeassistant_topic, "detected", self.qos) #For the Home Assistan 

                print(f"[{datetime.now().strftime('%H:%M:%S')}] Published (QoS {self.qos}) to {self.consumer_topic}")                
    
            time.sleep(self.sample_interval)

    def start(self):
        print(f"Connect to Broker {self.broker}:{self.port}, QoS {self.qos}")
        self.client.connect(self.broker, self.port, 60)

        
        self.client.subscribe(self.sub_topic, self.qos)
        print(f"Sub to {self.sub_topic}")

        self.client.subscribe(self.seq_topic, self.qos)
        print(f"Sub to {self.seq_topic}")

        self.client.publish(self.availability_topic, "online", qos=self.qos, retain=True)

        coorditates_payload = {
            "latitude": self.lat,
            "longitude": self.long,
        }
        self.client.publish(self.coorditates_topic, json.dumps(coorditates_payload), qos=self.qos, retain=True)


        self.client.loop_start()
        self.is_running = True
        
        discovery_topic = f"homeassistant/binary_sensor/team09_{self.bin_id}_{self.device_id}_motion/config"
        state_topic = self.basic_topic + "state"
        
        discovery_payload = {
            "name": f"PIR Motion Sensor {self.device_id}",
            "state_topic": self.homeassistant_topic,
            "availability_topic": self.availability_topic,
            "json_attributes_topic": self.coorditates_topic,
            "payload_available": "online",
            "payload_not_available": "offline",
            "payload_on": "detected",
            "payload_off": "clear",
            "device_class": "motion",
            "off_delay": 4,
            "unique_id": f"team09_{self.bin_id}_{self.device_id}_motion",
            "device": {
                "identifiers": [f"smartbin-{self.bin_id}-{self.device_id}"],
                "name": f"Smart Wastebin {self.bin_id}-{self.device_id}",
                "model": "SmartBin",
                "manufacturer": "Team 09"
            }
        }

        self.client.publish(discovery_topic, json.dumps(discovery_payload), qos=self.qos, retain=True)
        print(f"Published HA discovery config to {discovery_topic}")


        capacity_discovery_topic = f"homeassistant/sensor/team09_{self.bin_id}_{self.device_id}_capacity/config"
        
        capacity_payload = {
            "name": f"Capacity ({self.bin_id})",
            "state_topic": self.seq_topic,
            "json_attributes_topic": self.coorditates_topic,
            "unique_id": f"team09_{self.bin_id}_{self.device_id}_capacity",
            "icon": "mdi:delete-variant",
            "state_class": "total_increasing", # Βοηθάει το Home Assistant να καταλάβει ότι είναι αθροιστικό νούμερο
            "device": {
                "identifiers": [f"smartbin-{self.bin_id}-{self.device_id}"],
                "name": f"Smart Wastebin {self.bin_id}-{self.device_id}",
                "model": "SmartBin",
                "manufacturer": "Team 09"
            }
        }
        self.client.publish(capacity_discovery_topic, json.dumps(capacity_payload), qos=self.qos, retain=True)
        print(f"Published HA discovery config for Capacity to {capacity_discovery_topic}")

        # 3. Discovery για το Κουμπί Αδειάσματος
        button_discovery_topic = f"homeassistant/button/team09_{self.bin_id}_{self.device_id}_empty/config"
        
        button_payload = {
            "name": f"Empty Bin {self.device_id}",
            "command_topic": self.sub_topic, # Όταν πατιέται, θα στέλνει στο ".../cleared" topic
            "payload_press": '{"motion_state": "empty"}', # Το JSON που περιμένει η _on_message σου!
            "unique_id": f"team09_{self.bin_id}_{self.device_id}_empty",
            "icon": "mdi:delete-empty",
            "device": {
                "identifiers": [f"smartbin-{self.bin_id}-{self.device_id}"],
                "name": f"Smart Wastebin {self.bin_id}-{self.device_id}",
                "model": "SmartBin",
                "manufacturer": "Team 09"
            }
        }
        self.client.publish(button_discovery_topic, json.dumps(button_payload), qos=self.qos, retain=True)

        try:
            self._run_loop()
        except KeyboardInterrupt:
            self.stop()

    def stop(self):
        self.is_running = False

        self.client.publish(self.availability_topic, "offline", qos=self.qos, retain=True)

        import time
        time.sleep(0.5)

        self.client.loop_stop()
        self.client.disconnect()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MQTT Producer for PIR Sensor")
    
    parser.add_argument("--broker", type=str, default="localhost")
    parser.add_argument("--port", type=int, default=1883)
    parser.add_argument("--topic", type=str, required=True)
    parser.add_argument("--device-id", type=str, required=True)
    parser.add_argument("--bin-id", type=str, required=True)
    parser.add_argument("--pin", type=int, required=True)
    parser.add_argument("--sample-interval", type=float, default=0.1)
    parser.add_argument("--cooldown", type=float, default=5.0)
    parser.add_argument("--min-high", type=float, default=0.2)
    parser.add_argument("--qos", type=int, choices=[0, 1, 2], default=0, help="MQTT QoS level (0, 1, or 2)")

    parser.add_argument("--virtual", action="store_true", help="Run in virtual mode generating fake data")
    parser.add_argument("--latitude", type=float, default= 38.287582)
    parser.add_argument("--longitude", type=float, default= 21.789629)


    args = parser.parse_args()

    producer = Producer(
        broker=args.broker,
        port=args.port,
        topic=args.topic,
        device_id=args.device_id,
        bin_id=args.bin_id,
        pin=args.pin,
        sample_interval=args.sample_interval,
        cooldown=args.cooldown,
        min_high=args.min_high,
        qos=args.qos,
        is_virtual=args.virtual,
        latitude = args.latitude,
        longitude = args.longitude
    )
    
    producer.start()