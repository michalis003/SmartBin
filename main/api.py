import json
import os
import sys
import threading
import uuid
from flask import Flask, request
from flask_restx import Api, Resource, abort, fields
import paho.mqtt.client as mqtt
from datetime import datetime, timezone
from file_read_backwards import FileReadBackwards

# --- 1. Initialize Flask & Swagger ---
app = Flask(__name__)
api = Api(
    app,
    version="1.0",
    title="SmartBin API",
    description="REST API for querying Smart Wastebin sensor data, bin status, and live MQTT states.",
    doc="/"
)

# --- 2. Define Namespaces ---
bins_ns = api.namespace("bins", description="Wastebin operations & live data")
sensors_ns = api.namespace("sensors", description="Sensor static details")
mqtt_ns = api.namespace("mqtt", description="Raw MQTT Topic State Tracking")

# --- 3. Setup MQTT Client & State Tracker ---
topic_store = {}
topic_lock = threading.Lock()

def on_mqtt_message(client, userdata, msg):
    """Saves the latest message for each topic safely."""
    topic = msg.topic
    try:
        payload = json.loads(msg.payload.decode("utf-8"))
    except json.JSONDecodeError:
        payload = msg.payload.decode("utf-8")
        
    with topic_lock:
        topic_store[topic] = {
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
            "payload": payload,
            "retained": msg.retain
        }

api_mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"flask_api_{uuid.uuid4().hex[:8]}")
api_mqtt_client.on_message = on_mqtt_message

try:
    api_mqtt_client.connect("localhost", 1883)
    api_mqtt_client.subscribe("smartbin/#")
    api_mqtt_client.loop_start()
except Exception as e:
    print(f"Warning: API could not connect to MQTT Broker: {e}", file=sys.stderr)


# --- 4. Define Swagger Models (Populating the Models Section) ---

# Input Model
emptied_model = api.model('EmptiedPayload', {
    'emptied_by': fields.String(description='Who emptied the bin', example='maintenance-team-A'),
    'emptied_at': fields.String(description='ISO timestamp (optional)', example='2026-05-26T14:00:00Z')
})

# Output Models
coordinate_model = api.model('CoordinateData', {
    'latitude': fields.Float(description='Latitude coordinate', example=38.288852),
    'longitude': fields.Float(description='Longitude coordinate', example=21.789463),
    'timestamp': fields.String(description='Last update timestamp', example='2026-06-01T10:00:00Z')
})

availability_model = api.model('AvailabilityData', {
    'status': fields.String(description='Current LWT status', example='online', enum=['online', 'offline']),
    'timestamp': fields.String(description='Last update timestamp', example='2026-06-01T10:00:00Z')
})

event_model = api.model('Event', {
    'event_time': fields.String(description='Time the event occurred'),
    'motion_state': fields.String(description='State of motion', example='detected'),
    'seq': fields.Integer(description='Event sequence number')
})


# --- 5. Load Static JSON-LD Models ---
def load_json_file(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Warning: Could not load {filepath} - {e}")
        return None

bin_data = load_json_file("models/wastebin.jsonld")
sensor_data = load_json_file("models/sensor.jsonld")

STATIC_BINS = [bin_data] if bin_data else []
STATIC_SENSORS = [sensor_data] if sensor_data else []


# --- 6. Bins Endpoints ---
@bins_ns.route("")
class BinList(Resource):
    def get(self):
        """List all registered bins (Static)."""
        return STATIC_BINS, 200

@bins_ns.route("/<string:bin_id>")
@bins_ns.doc(params={'bin_id': 'The ID of the bin (e.g., Patras_bin-01)'})
class BinDetail(Resource):
    def get(self, bin_id):
        """Get static details for a specific bin."""
        for b in STATIC_BINS:
            if b.get("id", "").endswith(bin_id):
                return b, 200
        abort(404, f"Bin '{bin_id}' not found")

@bins_ns.route("/<string:bin_id>/sensors")
@bins_ns.doc(params={'bin_id': 'The ID of the bin'})
class BinSensors(Resource):
    def get(self, bin_id):
        """List sensors mounted on a specific bin."""
        bin_obj = next((b for b in STATIC_BINS if b.get("id", "").endswith(bin_id)), None)
        if not bin_obj:
            abort(404, f"Bin '{bin_id}' not found")
            
        attached_sensor_urns = bin_obj.get("hasSensor", [])
        attached_sensors = [s for s in STATIC_SENSORS if s.get("id") in attached_sensor_urns]
        return attached_sensors, 200

@bins_ns.route("/<string:bin_id>/events")
@bins_ns.doc(params={'bin_id': 'The ID of the bin (e.g., bin-01)'})
class BinEvents(Resource):
    @bins_ns.doc(params={'limit': 'Number of recent events to return (default 10)'})
    @bins_ns.response(200, 'Success', [event_model])
    def get(self, bin_id):
        """Get recent motion events for a specific bin."""
        limit = request.args.get('limit', default=10, type=int)
        events = []
        event_file = "output/motion_events.jsonl"
        
        try:
            with FileReadBackwards(event_file, encoding="utf-8") as f:
                for line in f:
                    if len(events) >= limit:
                        break
                    try:
                        record = json.loads(line)
                        if bin_id in record.get("hasFeatureOfInterest", ""):
                            events.append(record)
                    except json.JSONDecodeError:
                        continue
        except FileNotFoundError:
            pass 

        return events, 200

@bins_ns.route("/<string:bin_id>/emptied")
@bins_ns.doc(params={'bin_id': 'The ID of the bin'})
class BinEmptied(Resource):
    @bins_ns.expect(emptied_model)
    @bins_ns.doc(responses={201: 'Bin marked as emptied', 404: 'Bin not found'})
    def post(self, bin_id):
        """Record that a bin was emptied and publish an MQTT update"""
        data = request.json or {}
        emptied_by = data.get("emptied_by", "unknown")
        emptied_at = data.get("emptied_at", datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"))

        record = {"bin_id": bin_id, "emptied_at": emptied_at, "emptied_by": emptied_by}

        os.makedirs("output", exist_ok=True)
        with open("output/emptied_log.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")

        topic = f"smartbin/{bin_id}/status"
        payload = json.dumps({"state": "emptied", "emptied_at": emptied_at})
        api_mqtt_client.publish(topic, payload, qos=1, retain=True)

        return record, 201

# --- ΝΕΑ ENDPOINTS: Availability & Coordinates ---

@bins_ns.route("/<string:bin_id>/availability")
@bins_ns.doc(params={'bin_id': 'The ID of the bin (e.g., bin-01)'})
class BinAvailability(Resource):
    @bins_ns.response(200, 'Success', fields.Raw(description="Dictionary of sensor availabilities mapped by device_id"))
    @bins_ns.response(404, 'No data found')
    def get(self, bin_id):
        """Get the live availability (LWT) of sensors on a specific bin."""
        results = {}
        with topic_lock:
            for topic, data in topic_store.items():
                parts = topic.split("/")
                # Pattern: smartbin/{bin_id}/{device_id}/availability
                if len(parts) >= 4 and parts[0] == "smartbin" and parts[1] == bin_id and parts[3] == "availability":
                    device_id = parts[2]
                    results[device_id] = {
                        "status": data["payload"],
                        "timestamp": data["timestamp"]
                    }
        
        if not results:
            abort(404, f"No availability data tracked yet for bin '{bin_id}'")
        return results, 200

@bins_ns.route("/<string:bin_id>/coordinates")
@bins_ns.doc(params={'bin_id': 'The ID of the bin (e.g., bin-01)'})
class BinCoordinates(Resource):
    @bins_ns.response(200, 'Success', fields.Raw(description="Dictionary of sensor coordinates mapped by device_id"))
    @bins_ns.response(404, 'No data found')
    def get(self, bin_id):
        """Get the live GPS coordinates of sensors on a specific bin."""
        results = {}
        with topic_lock:
            for topic, data in topic_store.items():
                parts = topic.split("/")
                # Checking both spellings just in case (coordinates / coorditates)
                if len(parts) >= 4 and parts[0] == "smartbin" and parts[1] == bin_id and parts[3] in ["coordinates", "coorditates"]:
                    device_id = parts[2]
                    payload = data.get("payload", {})
                    if isinstance(payload, dict):
                        results[device_id] = {
                            "latitude": payload.get("latitude"),
                            "longitude": payload.get("longitude"),
                            "timestamp": data["timestamp"]
                        }
        
        if not results:
            abort(404, f"No coordinates data tracked yet for bin '{bin_id}'")
        return results, 200


# --- 7. Sensors Endpoints ---
@sensors_ns.route("")
class SensorList(Resource):
    def get(self):
        """List all registered sensors (Static)."""
        return STATIC_SENSORS, 200

@sensors_ns.route("/<string:sensor_id>")
@sensors_ns.doc(params={'sensor_id': 'The ID of the sensor'})
class SensorDetail(Resource):
    def get(self, sensor_id):
        """Get static details for a specific sensor."""
        for s in STATIC_SENSORS:
            if s.get("id", "").endswith(sensor_id):
                return s, 200
        abort(404, f"Sensor '{sensor_id}' not found")


# --- 8. MQTT State Endpoints ---
@mqtt_ns.route("/topics")
class MQTTTopics(Resource):
    def get(self):
        """List all known MQTT topics and their last received message."""
        with topic_lock:
            return {
                "topic_count": len(topic_store),
                "topics": topic_store
            }, 200

@mqtt_ns.route("/topics/<path:topic>")
@mqtt_ns.doc(params={'topic': 'MQTT topic path'})
class MQTTTopicDetail(Resource):
    @mqtt_ns.doc(responses={200: 'Success', 404: 'Topic not found'})
    def get(self, topic):
        """Get the last received message for a specific MQTT topic."""
        with topic_lock:
            if topic not in topic_store:
                abort(404, f"No message received on topic '{topic}' yet")
            return topic_store[topic], 200


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)