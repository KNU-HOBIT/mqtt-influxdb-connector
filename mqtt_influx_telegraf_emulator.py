import yaml
import json
import base64
import schedule
from datetime import datetime
from paho.mqtt import client as mqtt_client
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import ASYNCHRONOUS
import hobit_pb2

# Load configuration
with open("config.yaml", "r") as yamlfile:
    config = yaml.safe_load(yamlfile)

influxdb_url = config['influxdb']['url']
token = config['influxdb']['token']
org = config['influxdb']['org']
bucket = config['influxdb']['bucket']

mqtt_server = config['mqtt']['server']
mqtt_port = config['mqtt']['port']
mqtt_topic = config['mqtt']['topic']
mqtt_username = config['mqtt']['username']
mqtt_password = config['mqtt']['password']

protobuf_mode = config['util']['protobuf_mode']

# Data buffer
data_buffer = []

# Connect to InfluxDB
client = InfluxDBClient(url=influxdb_url, token=token, org=org)
write_api = client.write_api(write_options=ASYNCHRONOUS)


def decode_payload(msg):
    if protobuf_mode:
        trans_obj = hobit_pb2.Transport()
        trans_obj.ParseFromString(msg.payload)
        return trans_obj
    else:
        payload = msg.payload.decode()
        data = json.loads(payload)
        return data

def extract_timestamp(data, trans_obj=None):
    if protobuf_mode:
        timestamp_str = trans_obj.timestamp
    else:
        timestamp_str = data.get("timestamp", "")
    
    if '.' not in timestamp_str:
        timestamp_str += '.000'
    return datetime.strptime(timestamp_str, "%Y-%m-%dT%H:%M:%S.%f")

def on_message(client, userdata, msg):
    try:
        if protobuf_mode:
            trans_obj = decode_payload(msg)
            timestamp = extract_timestamp(None, trans_obj)
            value = base64.b64encode(msg.payload).decode('utf-8')
        else:
            data = decode_payload(msg)
            timestamp = extract_timestamp(data)
            value = json.dumps(data)

        eqp_id = msg.topic.split('/')[-1] if '/' in msg.topic else None

        print(f"eqp_id: {eqp_id}, data: {data if not protobuf_mode else 'Protobuf data'}")

        if eqp_id:
            point = Point("transport")\
                    .tag("eqp_id", eqp_id)\
                    .field("value", value)\
                    .time(timestamp)

            data_buffer.append(point)
    except Exception as e:
        print(f"Failed to parse MQTT message: {str(e)}")

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("Connected to MQTT Broker!")
        client.subscribe(mqtt_topic)
    else:
        print(f"Failed to connect, return code {rc}")

def flush_data():
    if data_buffer:
        try:
            write_api.write(bucket=bucket, record=data_buffer)
            print(f"Flushed {len(data_buffer)} records to InfluxDB.")
            data_buffer.clear()
        except Exception as e:
            print(f"Failed to write to InfluxDB: {str(e)}")

def connect_mqtt():
    client = mqtt_client.Client()
    client.username_pw_set(mqtt_username, mqtt_password)
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(mqtt_server, mqtt_port)
    return client

def run():
    mqtt_client = connect_mqtt()
    # Schedule the flush task
    schedule.every(3).seconds.do(flush_data)
    while True:
        schedule.run_pending()
        mqtt_client.loop(timeout=1)  # Loop with timeout to allow the scheduler to run

if __name__ == '__main__':
    run()
