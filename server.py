# server.py - Server di chat multi-utente con sistema di logging
import socket
import threading
import json
import os
import xml.etree.ElementTree as ET
from datetime import datetime
from xml.sax.saxutils import escape
import sys

# Percorsi dei file di configurazione e log
CARTELLA_BASE = os.path.dirname(os.path.abspath(__file__))
PERCORSO_CONFIG = os.path.join(CARTELLA_BASE, 'util', 'config.json')
PERCORSO_LOG = os.path.join(CARTELLA_BASE, 'util', 'log.xml')

# Carica configurazione da file JSON (porta e credenziali utenti)
try:
    with open(PERCORSO_CONFIG, 'r') as f:
        configurazione = json.load(f)
    PORTA = configurazione.get('server_port', 20498)
    UTENTI = configurazione.get('users', {"admin": "admin"})
except:
    # Valori di default se il file non esiste
    PORTA = 20498
    UTENTI = {"admin": "admin"}

# Dizionari per gestire connessioni e chat
clienti = {}  # Mappa socket -> nome_utente per i client connessi
coppie_chat = {}  # Mappa nome_utente -> altro_nome_utente per chat attive
cronologia_chat = {}  # Mappa (utente1,utente2) -> lista messaggi per salvare conversazioni


def trova_ip_locale():
    """Trova l'indirizzo IP locale della macchina"""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP


IP_SERVER = trova_ip_locale()


def assicura_cartella_util():
    """Crea la cartella 'util' se non esiste"""
    os.makedirs(os.path.join(CARTELLA_BASE, 'util'), exist_ok=True)


def scrivi_log(tipo, utente, messaggio):
    """Registra eventi nel file XML di log"""
    try:
        assicura_cartella_util()
        # Crea nuovo file XML se non esiste
        if not os.path.exists(PERCORSO_LOG) or os.stat(PERCORSO_LOG).st_size == 0:
            radice = ET.Element("logs")
            albero = ET.ElementTree(radice)
        else:
            albero = ET.parse(PERCORSO_LOG)
            radice = albero.getroot()
        # Aggiunge nuovo evento al log
        evento = ET.SubElement(radice, "event")
        evento.set("time", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        evento.set("type", tipo)
        evento.set("user", utente)
        evento.text = str(messaggio)
        albero.write(PERCORSO_LOG, encoding='utf-8', xml_declaration=True)
    except Exception as e:
        print("Errore Log:", e)


def invia_testo(sock, testo):
    """Invia testo al client aggiungendo newline finale"""
    try:
        if not testo.endswith("\n"):
            testo = testo + "\n"
        sock.sendall(testo.encode('utf-8'))
    except:
        pass


def scoperta_udp():
    """Thread per rispondere alle richieste di discovery UDP dei client"""
    sock_udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock_udp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock_udp.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    try:
        sock_udp.bind(('', PORTA))
    except Exception as e:
        print(f"[ERR] Errore Bind UDP: {e}")
        return
    print(f"[UDP] Discovery attivo su porta {PORTA}")
    while True:
        try:
            dati, indirizzo = sock_udp.recvfrom(1024)
            msg = dati.decode('utf-8', errors='ignore').strip()
            # Risponde alle richieste di discovery con la porta del server
            if msg == "AURA_DISCOVERY":
                risposta = f"AURA_OFFER:{PORTA}"
                sock_udp.sendto(risposta.encode('utf-8'), indirizzo)
        except:
            pass


def prepara_export(parametri, utente):
    """Prepara il contenuto da esportare dal log in formato txt/csv/xml"""
    try:
        if not os.path.exists(PERCORSO_LOG) or os.stat(PERCORSO_LOG).st_size == 0:
            return None, "Nessun log presente."
        albero = ET.parse(PERCORSO_LOG)
        radice = albero.getroot()

        # Parsing parametri: formato, numero eventi, filtro (ALL/CLIENT/SERVER)
        formato = "txt"
        numero = None
        chi = "ALL"
        if len(parametri) > 0 and parametri[0]:
            formato = parametri[0].lower()
        if len(parametri) > 1 and parametri[1]:
            try:
                numero = int(parametri[1])
            except:
                numero = None
        if len(parametri) > 2 and parametri[2]:
            chi = parametri[2].upper()

        # Filtra eventi in base al parametro 'chi'
        eventi = []
        for evento in radice.findall('event'):
            utente_evento = evento.get('user', '')
            if chi == "CLIENT" and utente_evento == "SERVER":
                continue
            if chi == "SERVER" and utente_evento != "SERVER":
                continue
            eventi.append(evento)

        # Limita al numero di eventi richiesti
        if numero:
            eventi = eventi[-numero:]

        # Formatta output in base al formato richiesto
        righe = []
        if formato == "xml":
            righe.append('<?xml version="1.0" encoding="utf-8"?>')
            righe.append("<logs>")
            for ev in eventi:
                t = ev.get('time', '')
                u = ev.get('user', '')
                ty = ev.get('type', '')
                m = ev.text or ''
                righe.append(f'  <event time="{escape(t)}" user="{escape(u)}" type="{escape(ty)}">{escape(m)}</event>')
            righe.append("</logs>")
            contenuto = "\n".join(righe)
        else:
            for ev in eventi:
                t = ev.get('time', '')
                u = ev.get('user', '')
                ty = ev.get('type', '')
                m = ev.text or ''
                if formato == "csv":
                    m_sicuro = m.replace('\n', ' ').replace('\r', ' ').replace(',', ';')
                    righe.append(f'{t},{u},{ty},{m_sicuro}')
                else:
                    righe.append(f'[{t}] {u} ({ty}): {m}')
            contenuto = "\n".join(righe)

        nome_file = f"export_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{formato}"
        return nome_file, contenuto
    except Exception as e:
        return None, f"Errore export: {e}"


def prepara_export_chat(utente, destinatario, formato="txt"):
    """Prepara l'export della cronologia chat tra due utenti"""
    try:
        chiave_chat = tuple(sorted([utente, destinatario]))
        if chiave_chat not in cronologia_chat or not cronologia_chat[chiave_chat]:
            return None, "Nessun messaggio nella chat corrente."
        righe = []
        if formato == "xml":
            righe.append('<?xml version="1.0" encoding="utf-8"?>')
            righe.append('<chat>')
            for m in cronologia_chat[chiave_chat]:
                ts = m['time']
                mittente = m['sender']
                testo = m['text']
                righe.append(f"  <message time='{escape(ts)}' sender='{escape(mittente)}'>{escape(testo)}</message>")
            righe.append('</chat>')
            contenuto = "\n".join(righe)
        else:
            for m in cronologia_chat[chiave_chat]:
                righe.append(f"[{m['time']}] {m['sender']}: {m['text']}")
            contenuto = "\n".join(righe)
        nome_file = f"chat_{utente}_{destinatario}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{formato}"
        return nome_file, contenuto
    except Exception as e:
        return None, f"Errore export chat: {e}"


def invia_file_tramite_socket(sock, nome_file, contenuto_str):
    """Invia un file al client con header contenente nome e dimensione"""
    try:
        contenuto_byte = contenuto_str.encode('utf-8')
        dimensione = len(contenuto_byte)
        # Protocollo: __FILE__|nome|dimensione\n + dati
        intestazione = f"__FILE__|{nome_file}|{dimensione}\n".encode('utf-8')
        sock.sendall(intestazione + contenuto_byte)
    except Exception as e:
        try:
            invia_testo(sock, f"Errore invio file: {e}")
        except:
            pass


def gestisci_client(socket_client, indirizzo):
    """Gestisce la connessione di un singolo client (eseguito in thread separato)"""
    utente = None
    socket_client.settimeout(120)  # Timeout di 2 minuti per inattività
    ip_client = indirizzo[0]
    print(f"[NEW] Connessione da {indirizzo}")
    try:
        # Fase di autenticazione
        invia_testo(socket_client, "USERNAME?")
        nome_utente = socket_client.recv(1024).decode().strip()
        invia_testo(socket_client, "PASSWORD?")
        password = socket_client.recv(1024).decode().strip()

        # Verifica credenziali
        if nome_utente in UTENTI and UTENTI[nome_utente] == password:
            if nome_utente in clienti.values():
                invia_testo(socket_client, "Sei già connesso altrove. Bye.")
                return
            utente = nome_utente
            clienti[socket_client] = utente
            invia_testo(socket_client, f"Login OK. Benvenuto {utente}!")
            scrivi_log("LOGIN", utente, f"Connesso da {ip_client}")
            print(f"[LOGIN] {utente}")
        else:
            invia_testo(socket_client, "Credenziali errate. Bye.")
            return

        # Loop principale per gestire i messaggi del client
        while True:
            try:
                dati = socket_client.recv(4096)
                if not dati:
                    break
                msg = dati.decode('utf-8', errors='ignore').strip()
            except socket.timeout:
                invia_testo(socket_client, "Timeout inattività (2 minuti).")
                scrivi_log("TIMEOUT", utente, "Disconnesso per inattività")
                break

            # MODALITÀ CHAT: se l'utente è in una chat attiva
            if utente in coppie_chat:
                destinatario = coppie_chat[utente]
                chiave_chat = tuple(sorted([utente, destinatario]))
                parti_maiuscole = msg.upper().split()

                # Comando per esportare la chat corrente
                if parti_maiuscole[0] == "CHAT_EX":
                    formato = parti_maiuscole[1].lower() if len(parti_maiuscole) > 1 else "txt"
                    nome_file, contenuto = prepara_export_chat(utente, destinatario, formato)
                    if nome_file is None:
                        invia_testo(socket_client, contenuto)
                    else:
                        invia_file_tramite_socket(socket_client, nome_file, contenuto)
                    scrivi_log("CMD", utente, "CHAT_EX")
                    continue

                # Chiusura della chat
                if msg.upper() in ["ENDCHAT", "EXIT"]:
                    if utente in coppie_chat: del coppie_chat[utente]
                    if destinatario in coppie_chat: del coppie_chat[destinatario]
                    invia_testo(socket_client, f"Chat con {destinatario} terminata.")
                    scrivi_log("CHAT_END", utente, f"Chiuso con {destinatario}")
                    # Notifica l'altro utente
                    for s, n in clienti.items():
                        if n == destinatario:
                            try:
                                invia_testo(s, f"[AVVISO] {utente} ha lasciato la chat.")
                            except:
                                pass
                            break
                else:
                    # Messaggio normale in chat: salva e inoltra
                    if chiave_chat not in cronologia_chat:
                        cronologia_chat[chiave_chat] = []
                    cronologia_chat[chiave_chat].append({
                        'time': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        'sender': utente,
                        'text': msg
                    })
                    # Inoltra il messaggio all'altro utente
                    trovato = False
                    for s, n in clienti.items():
                        if n == destinatario:
                            try:
                                invia_testo(s, f"[{utente}]: {msg}")
                                trovato = True
                            except:
                                pass
                            break
                    if not trovato:
                        invia_testo(socket_client, "L'altro utente non è più online. Chat chiusa.")
                        if utente in coppie_chat: del coppie_chat[utente]

            # MODALITÀ COMANDI: gestione dei comandi del server
            else:
                parti = msg.split()
                if not parti:
                    continue
                comando = parti[0].upper()
                parametri = parti[1:]

                if comando == "HELP":
                    testo_aiuto = """=== COMANDI DISPONIBILI ===
TIME - Mostra ora server
NAME - Nome server e client
INFO [1-5] - Informazioni
USERSLIST - Lista utenti disponibili
CHAT [user] - Apri chat con utente
ENDCHAT - Chiudi chat corrente
CHAT_EX [txt/csv/xml] - Esporta chat in file (inviato al client)
LOG [num] [ALL/CLIENT/SERVER] - Mostra log formattato
EXPORT [txt/csv/xml] [num] [ALL/CLIENT/SERVER] (Alias: EX) - Invia file da scaricare (client salva localmente)
EXIT - Disconnetti
"""
                    invia_testo(socket_client, testo_aiuto)

                elif comando == "TIME":
                    invia_testo(socket_client, f"Ora Server: {datetime.now().strftime('%H:%M:%S')}")

                elif comando == "NAME":
                    invia_testo(socket_client, f"Server: Aura | Client: {utente}")

                elif comando == "EXIT":
                    break

                elif comando == "LOG":
                    # Mostra il log formattato (senza salvare file)
                    p = ["txt"] + parametri
                    nome_file, contenuto = prepara_export(p, utente)
                    if nome_file is None:
                        invia_testo(socket_client, contenuto)
                    else:
                        invia_testo(socket_client, contenuto)
                    scrivi_log("CMD", utente, "LOG")

                elif comando == "INFO":
                    # Comandi INFO 1-5 per diverse informazioni
                    if parametri and parametri[0] == "1":
                        risposta = f"Client online: {len(clienti)}"
                    elif parametri and parametri[0] == "2":
                        risposta = f"Utenti registrati: {len(UTENTI)}"
                    elif parametri and parametri[0] == "3":
                        risposta = f"Server IP: {IP_SERVER}:{PORTA}"
                    elif parametri and parametri[0] == "4":
                        risposta = f"Client IP: {ip_client}"
                    elif parametri and parametri[0] == "5":
                        altri = [x for x in clienti.values() if x != utente and x not in coppie_chat]
                        risposta = ", ".join(altri) if altri else "Nessuno disponibile"
                    else:
                        risposta = "Usa: INFO [1-5]"
                    invia_testo(socket_client, risposta)

                elif comando == "USERSLIST":
                    # Lista utenti disponibili per chat
                    altri = [x for x in clienti.values() if x != utente and x not in coppie_chat]
                    risposta = ", ".join(altri) if altri else "Nessuno disponibile"
                    invia_testo(socket_client, f"Utenti disponibili: {risposta}")

                elif comando in ("EX", "EXPORT"):
                    # Esporta log e invia come file al client
                    nome_file, contenuto = prepara_export(parametri, utente)
                    if nome_file is None:
                        invia_testo(socket_client, contenuto)
                    else:
                        invia_file_tramite_socket(socket_client, nome_file, contenuto)
                    scrivi_log("CMD", utente, "EXPORT")

                elif comando == "CHAT":
                    # Avvia una chat 1-a-1 con un altro utente
                    if parametri:
                        tgt = parametri[0]
                        if tgt in clienti.values() and tgt != utente and tgt not in coppie_chat:
                            coppie_chat[utente] = tgt
                            coppie_chat[tgt] = utente
                            chiave_chat = tuple(sorted([utente, tgt]))
                            if chiave_chat not in cronologia_chat:
                                cronologia_chat[chiave_chat] = []
                            invia_testo(socket_client, f"Chat con {tgt} iniziata. Scrivi 'ENDCHAT' per uscire.")
                            scrivi_log("CHAT_START", utente, f"Chat con {tgt}")
                            # Notifica l'altro utente
                            for s, n in clienti.items():
                                if n == tgt:
                                    try:
                                        invia_testo(s,
                                                    f"[!] {utente} ha aperto chat con te. Scrivi 'ENDCHAT' per uscire.")
                                    except:
                                        pass
                                    break
                        else:
                            invia_testo(socket_client, "Utente non trovato, non online o già in chat.")
                    else:
                        invia_testo(socket_client, "Uso: CHAT [username]")

                else:
                    invia_testo(socket_client, "Comando sconosciuto. Usa HELP per vedere i comandi.")

                # Registra il comando nel log
                if comando:
                    scrivi_log("CMD", utente, comando)

    except Exception as e:
        print(f"[ERR] {utente}: {e}")
    finally:
        # Cleanup alla disconnessione
        if socket_client in clienti:
            del clienti[socket_client]
        if utente in coppie_chat:
            del coppie_chat[utente]
        try:
            socket_client.close()
        except:
            pass
        if utente:
            scrivi_log("LOGOUT", utente, "Disconnesso")
        print(f"[CLOSE] {utente} uscito.")


# Avvio del server
if __name__ == "__main__":
    assicura_cartella_util()

    # Avvia thread UDP per discovery automatica dei client
    t_udp = threading.Thread(target=scoperta_udp, daemon=True)
    t_udp.start()

    # Configura e avvia il server TCP
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((IP_SERVER, PORTA))
    server.listen(5)  # Massimo 5 connessioni in coda
    print(f"=== AURA SERVER ATTIVO SU {IP_SERVER}:{PORTA} ===")
    scrivi_log("SERVER", "SERVER", f"Avviato su {IP_SERVER}:{PORTA}")

    # Loop principale: accetta connessioni e crea thread per ogni client
    while True:
        client_socket, client_address = server.accept()
        threading.Thread(target=gestisci_client, args=(client_socket, client_address), daemon=True).start()
