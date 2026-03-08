# ---------------------------------
# The software is provided as is. The author assumes no responsibility for its use.
# ---------------------------------
import socket
import struct
import paho.mqtt.client as mqtt
import sys
import argparse
import threading
import time

# --- CONFIGURAZIONE ---
APP_PORT = 1884
BROKER_URL = "broker.hivemq.com"
UNIQUE_PREFIX = "giorgio_vivaldi_debug_123"

# --- ARGOMENTI ---
parser = argparse.ArgumentParser(description="Bridge PC(Client) <-> App(Gateway)")
parser.add_argument("ip", help="Indirizzo IP del telefono Android (App Gateway)")
args = parser.parse_args()
target_ip = args.ip

# Socket UDP
udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
# Impostiamo un timeout per non bloccare il thread per sempre
udp_sock.settimeout(1.0) 
udp_sock.bind(("0.0.0.0", 0)) 

def on_message(client, userdata, message):
    """Riceve da MQTT Explorer e manda all'App (Gateway)"""
    try:
        payload = message.payload
        print(f"☁️  [CLOUD] Messaggio ricevuto su MQTT Explorer")
        
        # [Len, MsgType(0x0C), Flags(0), TopicId(2), MsgId(2), Payload]
        header = struct.pack("!BBBH H", 7 + len(payload), 0x0C, 0x00, 1, 1)
        udp_sock.sendto(header + payload, (target_ip, APP_PORT))
        print(f"   --> Inviato PUBLISH all'App Gateway")
    except Exception as e:
        print(f"❌ Errore durante l'inoltro verso l'App: {e}")

def udp_receiver_task():
    """Riceve i pacchetti che l'App (Gateway) invia al PC"""
    print(f"📡 Thread ascolto UDP avviato...")
    while True:
        try:
            try:
                data, addr = udp_sock.recvfrom(2048)
            except socket.timeout:
                continue # Il timeout permette allo script di restare reattivo al CTRL+C
            except ConnectionResetError:
                # Errore tipico di Windows se il telefono chiude il socket improvvisamente
                continue 
            
            if len(data) < 2: continue
            
            msg_type = data[1]

            if msg_type == 0x0A: # REGISTER
                msg_id = struct.unpack("!H", data[4:6])[0]
                topic_name = data[6:].decode('utf-8', 'ignore')
                print(f"📝 [RX REGISTER] Topic: '{topic_name}'")
                
                regack = struct.pack("!BBHHB", 7, 0x0B, 10, msg_id, 0x00)
                udp_sock.sendto(regack, (target_ip, APP_PORT))
                print(f"   --> Mandato REGACK (ID: 10)")

            elif msg_type == 0x0C: # PUBLISH
                topic_id = struct.unpack("!H", data[3:5])[0]
                payload = data[7:]
                msg_str = payload.decode('utf-8', 'ignore')
                print(f"📤 [RX PUBLISH] ID:{topic_id} -> {msg_str}")
                
                cloud_topic = f"{UNIQUE_PREFIX}/from_gateway/topic_{topic_id}"
                mqtt_client.publish(cloud_topic, payload)
                print(f"   ☁️  [BRIDGE -> CLOUD] Inviato su HiveMQ")

        except Exception as e:
            print(f"⚠️ Errore imprevisto nel thread UDP: {e}")
            time.sleep(1) # Evita loop frenetici in caso di errore persistente

# --- SETUP MQTT CLOUD ---
mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
mqtt_client.on_message = on_message

try:
    print(f"🔄 Connessione a {BROKER_URL}...")
    mqtt_client.connect(BROKER_URL, 1883, 60)
    command_topic = f"{UNIQUE_PREFIX}/commands"
    mqtt_client.subscribe(command_topic)
    mqtt_client.loop_start()
except Exception as e:
    print(f"❌ Impossibile connettersi al Broker: {e}")
    sys.exit(1)

# Avvio thread ricezione UDP
t = threading.Thread(target=udp_receiver_task, daemon=True)
t.start()

# Invio CONNECT iniziale
print(f"📱 Invio CONNECT all'App Gateway...")
udp_sock.sendto(bytes([0x06, 0x04, 0x04, 0x01, 0x00, 0x3C]), (target_ip, APP_PORT))

print(f"\n✅ BRIDGE OPERATIVO")
print(f"🎯 IP App: {target_ip} | Porta: {APP_PORT}")
print(f"⌨️  Premi CTRL+C per terminare\n")

try:
    while True:
        # Se il thread di ricezione muore, lo logghiamo
        if not t.is_alive():
            print("🚨 ERRORE CRITICO: Il thread UDP si è interrotto!")
            break
        time.sleep(2)
except KeyboardInterrupt:
    print("\n👋 Chiusura bridge...")
finally:
    mqtt_client.loop_stop()
    mqtt_client.disconnect()
    udp_sock.close()