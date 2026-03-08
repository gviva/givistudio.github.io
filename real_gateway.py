# ---------------------------------
# The software is provided as is. The author assumes no responsibility for its use.
# ---------------------------------
import socket
import struct
import paho.mqtt.client as mqtt
import sys
import time

# --- CONFIGURAZIONE ---
MQTT_SN_PORT = 1884
BROKER_URL = "broker.hivemq.com"
BROKER_PORT = 1883
# Prefisso univoco per HiveMQ
UNIQUE_PREFIX = "giorgio_vivaldi_debug_123"

# Variabile per memorizzare l'indirizzo dell'app (IP e Porta)
app_address = None

# Setup Client MQTT Standard (v2.x)
mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)

def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code == 0:
        print(f"✅ Connessione al broker HiveMQ riuscita!")
        # SOTTOSCRIZIONE: Il gateway ascolta i comandi in arrivo dal cloud
        command_topic = f"{UNIQUE_PREFIX}/commands"
        mqtt_client.subscribe(command_topic)
        print(f"📡 Sottoscritto al topic cloud: {command_topic}")
    else:
        print(f"❌ Errore connessione broker: {reason_code}")

def on_publish(client, userdata, mid, reason_code, properties):
    print(f"   ☁️  [APP -> CLOUD] Messaggio inviato a HiveMQ.")

def on_message(client, userdata, msg):
    """Gestisce i messaggi che arrivano da MQTT Explorer (Cloud -> App)"""
    global app_address
    if app_address is None:
        print("⚠️  [CLOUD -> APP] Messaggio ricevuto ma l'app non è ancora connessa!")
        return

    payload = msg.payload
    print(f"📩 [CLOUD -> APP] Ricevuto da Broker: {payload.decode('utf-8', 'ignore')}")

    # Costruiamo il pacchetto MQTT-SN PUBLISH (0x0C) per l'app
    # Usiamo il Topic ID 1 come default per i comandi in ricezione
    topic_id = 1
    msg_id = 1
    # Header: [Length, MsgType(0x0C), Flags(0x00), TopicId(2), MsgId(2)] = 7 byte
    header = struct.pack("!BBBH H", 7 + len(payload), 0x0C, 0x00, topic_id, msg_id)
    packet = header + payload

    # Invio via UDP all'ultimo indirizzo noto dell'app
    sn_sock.sendto(packet, app_address)
    print(f"   📲 [GATEWAY -> APP] Pacchetto UDP inviato a {app_address}")

mqtt_client.on_connect = on_connect
mqtt_client.on_publish = on_publish
mqtt_client.on_message = on_message

# Inizializzazione Socket UDP
sn_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sn_sock.bind(("0.0.0.0", MQTT_SN_PORT))
sn_sock.settimeout(1.0)

print(f"🔄 Tentativo di connessione a {BROKER_URL}...")
try:
    mqtt_client.connect(BROKER_URL, BROKER_PORT, 60)
    mqtt_client.loop_start()
except Exception as e:
    print(f"❌ Impossibile connettersi al broker: {e}")
    sys.exit(1)

print(f"\n🚀 REAL GATEWAY BIDIREZIONALE ATTIVO")
print(f"📡 Porta UDP: {MQTT_SN_PORT}")
print(f"🌍 Prefisso HiveMQ: {UNIQUE_PREFIX}")
print(f"⌨️  Premi CTRL+C per uscire\n")

try:
    while True:
        try:
            data, addr = sn_sock.recvfrom(2048)
            # Memorizziamo l'indirizzo dell'app ogni volta che comunica
            app_address = addr 
        except socket.timeout:
            continue
        
        if len(data) < 2: continue
        msg_type = data[1]
        
        # 1. CONNECT (0x04)
        if msg_type == 0x04:
            print(f"📱 [APP -> CONNECT] da {addr}")
            connack = bytes([0x03, 0x05, 0x00])
            sn_sock.sendto(connack, addr)

        # 2. REGISTER (0x0A)
        elif msg_type == 0x0A:
            msg_id = struct.unpack("!H", data[4:6])[0]
            topic_name = data[6:].decode('utf-8', 'ignore')
            print(f"📝 [APP -> REGISTER] Topic: '{topic_name}'")
            regack = struct.pack("!BBHHB", 7, 0x0B, 1, msg_id, 0x00)
            sn_sock.sendto(regack, addr)

        # 3. PUBLISH (0x0C)
        elif msg_type == 0x0C:
            topic_id = struct.unpack("!H", data[3:5])[0]
            payload = data[7:]
            msg_str = payload.decode('utf-8', 'ignore')
            topic_path = f"{UNIQUE_PREFIX}/topic_{topic_id}"
            print(f"📤 [APP -> PUBLISH] ID:{topic_id} -> {msg_str}")
            mqtt_client.publish(topic_path, payload, qos=0)

except KeyboardInterrupt:
    print("\n\n👋 Chiusura in corso...")
finally:
    mqtt_client.loop_stop()
    mqtt_client.disconnect()
    sn_sock.close()
    print("✨ Gateway spento.")
    sys.exit(0)