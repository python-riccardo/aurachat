# server.py - Server multi-utente con logging ed export 
import socket
import threading
import json
import os
import xml.etree.ElementTree as ET
from datetime import datetime
from xml.sax.saxutils import escape

# Percorsi
CARTELLA_BASE = os.path.dirname(os.path.abspath(__file__))
PERCORSO_CONFIG = os.path.join(CARTELLA_BASE, 'util', 'config.json')
PERCORSO_LOG = os.path.join(CARTELLA_BASE, 'util', 'log.xml')

# Configurazione
try:
    with open(PERCORSO_CONFIG, 'r') as f:
        configurazione = json.load(f)
    PORTA = configurazione.get('server_port', 20498)
    UTENTI = configurazione.get('users', {"admin": "admin"})
except:
    PORTA = 20498
    UTENTI = {"admin": "admin"}

clienti = {}  # socket -> username


def trova_ip_locale():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1))
        ip = s.getsockname()[0]
    except:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip


IP_SERVER = trova_ip_locale()


def assicura_cartella_util():
    os.makedirs(os.path.join(CARTELLA_BASE, 'util'), exist_ok=True)


def scrivi_log(tipo, utente, messaggio):
    try:
        assicura_cartella_util()
        if not os.path.exists(PERCORSO_LOG) or os.stat(PERCORSO_LOG).st_size == 0:
            root = ET.Element("logs")
            tree = ET.ElementTree(root)
        else:
            tree = ET.parse(PERCORSO_LOG)
            root = tree.getroot()

        ev = ET.SubElement(root, "event")
        ev.set("time", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        ev.set("type", tipo)
        ev.set("user", utente)
        ev.text = str(messaggio)

        tree.write(PERCORSO_LOG, encoding="utf-8", xml_declaration=True)
    except Exception as e:
        print("Errore log:", e)


def invia_testo(sock, testo):
    try:
        if not testo.endswith("\n"):
            testo += "\n"
        sock.sendall(testo.encode("utf-8"))
    except:
        pass


def scoperta_udp():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    try:
        sock.bind(('', PORTA))
    except Exception as e:
        print("Errore UDP:", e)
        return

    print(f"[UDP] Discovery attivo su porta {PORTA}")
    while True:
        try:
            data, addr = sock.recvfrom(1024)
            if data.decode().strip() == "AURA_DISCOVERY":
                sock.sendto(f"AURA_OFFER:{PORTA}".encode(), addr)
        except:
            pass


def prepara_export(parametri):
    if not os.path.exists(PERCORSO_LOG):
        return None, "Nessun log presente."

    tree = ET.parse(PERCORSO_LOG)
    root = tree.getroot()

    formato = "txt"
    numero = None
    filtro = "ALL"

    if len(parametri) > 0:
        formato = parametri[0].lower()
    if len(parametri) > 1:
        try:
            numero = int(parametri[1])
        except:
            pass
    if len(parametri) > 2:
        filtro = parametri[2].upper()

    eventi = []
    for ev in root.findall("event"):
        user = ev.get("user", "")
        if filtro == "SERVER" and user != "SERVER":
            continue
        if filtro == "CLIENT" and user == "SERVER":
            continue
        eventi.append(ev)

    if numero:
        eventi = eventi[-numero:]

    righe = []
    if formato == "xml":
        righe.append('<?xml version="1.0" encoding="utf-8"?>')
        righe.append("<logs>")
        for ev in eventi:
            righe.append(
                f'<event time="{escape(ev.get("time",""))}" '
                f'user="{escape(ev.get("user",""))}" '
                f'type="{escape(ev.get("type",""))}">'
                f'{escape(ev.text or "")}</event>'
            )
        righe.append("</logs>")
    else:
        for ev in eventi:
            t = ev.get("time", "")
            u = ev.get("user", "")
            ty = ev.get("type", "")
            m = ev.text or ""
            if formato == "csv":
                m = m.replace(",", ";").replace("\n", " ")
                righe.append(f"{t},{u},{ty},{m}")
            else:
                righe.append(f"[{t}] {u} ({ty}): {m}")

    nome = f"export_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{formato}"
    return nome, "\n".join(righe)


def invia_file(sock, nome, contenuto):
    try:
        data = contenuto.encode("utf-8")
        header = f"__FILE__|{nome}|{len(data)}\n".encode()
        sock.sendall(header + data)
    except:
        invia_testo(sock, "Errore invio file")


def gestisci_client(sock, addr):
    utente = None
    ip = addr[0]
    sock.settimeout(120)
    print("[NEW]", addr)

    try:
        invia_testo(sock, "USERNAME?")
        u = sock.recv(1024).decode().strip()
        invia_testo(sock, "PASSWORD?")
        p = sock.recv(1024).decode().strip()

        if u not in UTENTI or UTENTI[u] != p:
            invia_testo(sock, "Credenziali errate.")
            return
        if u in clienti.values():
            invia_testo(sock, "Utente già connesso.")
            return

        utente = u
        clienti[sock] = utente
        invia_testo(sock, f"Login OK. Benvenuto {utente}")
        scrivi_log("LOGIN", utente, f"IP {ip}")

        while True:
            try:
                data = sock.recv(4096)
                if not data:
                    break
                msg = data.decode().strip()
            except socket.timeout:
                invia_testo(sock, "Timeout inattività.")
                break

            parti = msg.split()
            if not parti:
                continue

            cmd = parti[0].upper()
            par = parti[1:]

            if cmd == "HELP":
                invia_testo(sock, """COMANDI:
TIME
NAME
INFO [1-5]
USERSLIST
LOG [num] [ALL/CLIENT/SERVER]
EXPORT / EX [txt/csv/xml] [num] [ALL/CLIENT/SERVER]
EXIT
""")

            elif cmd == "TIME":
                invia_testo(sock, datetime.now().strftime("%H:%M:%S"))

            elif cmd == "NAME":
                invia_testo(sock, f"Server: Aura | Client: {utente}")

            elif cmd == "INFO":
                if par and par[0] == "1":
                    invia_testo(sock, f"Client online: {len(clienti)}")
                elif par and par[0] == "2":
                    invia_testo(sock, f"Utenti registrati: {len(UTENTI)}")
                elif par and par[0] == "3":
                    invia_testo(sock, f"{IP_SERVER}:{PORTA}")
                elif par and par[0] == "4":
                    invia_testo(sock, f"IP Client: {ip}")
                elif par and par[0] == "5":
                    altri = [x for x in clienti.values() if x != utente]
                    invia_testo(sock, ", ".join(altri) if altri else "Nessuno")
                else:
                    invia_testo(sock, "INFO [1-5]")

            elif cmd == "USERSLIST":
                altri = [x for x in clienti.values() if x != utente]
                invia_testo(sock, ", ".join(altri) if altri else "Nessun altro utente")

            elif cmd in ("EXPORT", "EX"):
                nome, cont = prepara_export(par)
                if nome:
                    invia_file(sock, nome, cont)
                else:
                    invia_testo(sock, cont)

            elif cmd == "LOG":
                nome, cont = prepara_export(["txt"] + par)
                invia_testo(sock, cont)

            elif cmd == "EXIT":
                break

            else:
                invia_testo(sock, "Comando sconosciuto")

            scrivi_log("CMD", utente, cmd)

    finally:
        if sock in clienti:
            del clienti[sock]
        try:
            sock.close()
        except:
            pass
        if utente:
            scrivi_log("LOGOUT", utente, "Disconnesso")
        print("[CLOSE]", utente)


if __name__ == "__main__":
    assicura_cartella_util()

    threading.Thread(target=scoperta_udp, daemon=True).start()

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((IP_SERVER, PORTA))
    server.listen(5)

    print(f"AURA SERVER ATTIVO SU {IP_SERVER}:{PORTA}")
    scrivi_log("SERVER", "SERVER", f"Avviato su {IP_SERVER}:{PORTA}")

    while True:
        c, a = server.accept()
        threading.Thread(target=gestisci_client, args=(c, a), daemon=True).start()