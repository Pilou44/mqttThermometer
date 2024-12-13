import network
import time
import machine
import onewire
import ds18x20
import dht
from umqtt.simple import MQTTClient
import ujson
import config
from core import getId, initialize_wifi


UNIQUE_ID = getId()
# Constants for MQTT Topics
MQTT_TOPIC_TEMP = f"sensor/wechantloup/temp_{UNIQUE_ID}"
MQTT_TOPIC_HUM = f"sensor/wechantloup/hum_{UNIQUE_ID}"

# MQTT Parameters
MQTT_SERVER = config.mqtt_server
MQTT_PORT = 0
MQTT_USER = config.mqtt_username
MQTT_PASSWORD = config.mqtt_password
MQTT_CLIENT_ID = UNIQUE_ID
MQTT_KEEPALIVE = 7200
MQTT_SSL = False   # set to False if using local Mosquitto MQTT broker
MQTT_SSL_PARAMS = {'server_hostname': MQTT_SERVER}

STATE_TEMP_TOPIC = f"{MQTT_TOPIC_TEMP}/state"
STATE_HUM_TOPIC = f"{MQTT_TOPIC_HUM}/state"

dht11_pin = machine.Pin(27)
ds18b20_pin = machine.Pin(28)
led_R_pin = machine.Pin(26, mode=machine.Pin.OUT, value=1)
led_G_pin = machine.Pin(22, mode=machine.Pin.OUT, value=1)

ds18b20_connected = False
dht11_connected = False

dht11_sensor = dht.DHT11(dht11_pin)

ds18b20_sensor = ds18x20.DS18X20(onewire.OneWire(ds18b20_pin))
ds18b20_rom = 0

# Connect to MQTT Broker
def connect_mqtt():
    try:
        client = MQTTClient(client_id=MQTT_CLIENT_ID,
                            server=MQTT_SERVER,
                            port=MQTT_PORT,
                            user=MQTT_USER,
                            password=MQTT_PASSWORD,
                            keepalive=MQTT_KEEPALIVE,
                            ssl=MQTT_SSL,
                            ssl_params=MQTT_SSL_PARAMS)
        client.connect()
        return client
    except Exception as e:
        print('Error connecting to MQTT:', e)

def publish_temp_discovery():
    payload = {
        "name": "Pico Temperature",
        "unique_id": f"temp_{UNIQUE_ID}",
        "device": {
            "manufacturer": "Wechant Loup",
            "identifiers": UNIQUE_ID,
        },
        "state_topic": STATE_TEMP_TOPIC,
    }
    
    # Convert payload to JSON string for publishing
    payload_json = ujson.dumps(payload)
    
    conf_topic = f"homeassistant/{MQTT_TOPIC_TEMP}/config"
    
    # Print the payload for debugging
    print(f"Publishing to {conf_topic}: {payload_json}")
    
    client.publish(conf_topic, ujson.dumps(payload), retain=True)

def publish_hum_discovery():
    payload = {
        "name": "Pico Humidity",
        "unique_id": f"hum_{UNIQUE_ID}",
        "device": {
            "manufacturer": "Wechant Loup",
            "identifiers": UNIQUE_ID,
        },
        "state_topic": STATE_HUM_TOPIC,
    }
    
    # Convert payload to JSON string for publishing
    payload_json = ujson.dumps(payload)
    
    conf_topic = f"homeassistant/{MQTT_TOPIC_HUM}/config"
    
    # Print the payload for debugging
    print(f"Publishing to {conf_topic}: {payload_json}")
    
    client.publish(conf_topic, ujson.dumps(payload), retain=True)

def initTemperature():
    global dht11_connected
    global ds18b20_connected

    try:
        dht11_sensor.measure()
        print("DHT11 connected")
        dht11_connected = True
    except OSError as e:
        print("DHT11 not connected")
        dht11_connected = False

    global ds18b20_rom
    roms = ds18b20_sensor.scan()
    if roms:
        ds18b20_rom = roms[0]
        print("DS18B20 connected")
        ds18b20_connected = True
    else:
        print("DS18B20 not connected")
        ds18b20_connected = False

    return ds18b20_connected or dht11_connected

def readTemperature():
    if ds18b20_connected:
        ds18b20_sensor.convert_temp()
        time.sleep_ms(750)
        return ds18b20_sensor.read_temp(ds18b20_rom)
    elif dht11_connected:
        temp = dht11_sensor.measure()
        return dht11_sensor.temperature()
    else:
        return float(-1)

def readHumidity():
    if dht11_connected:
        return dht11_sensor.humidity()
    else:
        return -1

def init():
    led_R_pin.low()
    has_sensor = initTemperature()
    if not has_sensor:
        print("No temperature sensor")
        return False
    wlan.active(True)
    led_G_pin.low()
    return True

def run():
    global client
    # Initialize Wi-Fi
    if not initialize_wifi(config.wifi_ssid, config.wifi_password):
        print('Error connecting to the network... exiting program')
    else:
        # Connect to MQTT broker, start MQTT client
        client = connect_mqtt()
        publish_temp_discovery()
        
        if dht11_connected:
            publish_hum_discovery()
        
        # Continuously checking for messages
        while True:
            sleep(1)
            client.check_msg()
            print('Loop running')
            
            #Get the measurements from the sensor
            temperature = readTemperature()
            print(f"Temperature: {temperature}°C")
            client.publish(TEMPERATURE_TOPIC, temperature)
            
            if dht11_connected:
                humidity = readHumidity()
                print(f"Humidity: {humidity}%")
                client.publish(HUMIDITY_TOPIC, humidity)

if init():
    while True:
        try:
            print('Run')
            run()
        except KeyboardInterrupt:
            machine.reset()
        except Exception as e:
            print(e)
            pass

