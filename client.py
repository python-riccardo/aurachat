# client.py - Client per connettersi al server di chat Aura
import socket
import os
import sys
import threading
import time

PORTA_BROADCAST = 20498
LOCK_STAMPA = threading.Lock() # Evita che più thread stampino insieme

# Trova il server nella rete locale senza sapere IP e porta ma inviando in broadcast il proprio DISCOVERY aspettando che un server risponda con un OFFER
def scopri_server():
    print("Cerco il server...")
    udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    udp.settimeout(3)
    try:
        udp.sendto(b"AURA_DISCOVERY", ('<broadcast>', PORTA_BROADCAST))
        dati, indirizzo = udp.recvfrom(1024)
        msg = dati.decode('utf-8', errors='ignore')
        if "AURA_OFFER" in msg:
            porta = int(msg.split(":")[1])
            return indirizzo[0], porta
    except:
        pass
    return None, None

# Continua a ricevere finche non trova il carattere INVIO (\n). Analizza byte per byte
def ricevi_riga(sock, timeout=5.0):
    vecchio_timeout = sock.gettimeout()
    try:
        sock.settimeout(timeout)
        buffer = b""
        while True:
            carattere = sock.recv(1)
            if not carattere:
                break
            buffer += carattere
            if buffer.endswith(b'\n'):
                break
        if not buffer:
            return None
        return buffer.decode('utf-8', errors='ignore').rstrip('\n')
    except socket.timeout:
        return None
    finally:
        sock.settimeout(vecchio_timeout)

# Continua a ricevere finche non riceve un certo numero di byte
def ricevi_esatto(sock, dimensione):
    frammenti = []
    byte_ricevuti = 0
    while byte_ricevuti < dimensione:
        frammento = sock.recv(min(dimensione - byte_ricevuti, 4096))
        if not frammento:
            break
        frammenti.append(frammento)
        byte_ricevuti += len(frammento)
    return b''.join(frammenti)

# Crea una cartella locale sul client e ci salva i file
def salva_file_byte(nome_file, dati_byte):
    cartella_base = os.path.dirname(os.path.abspath(__file__))
    percorso_file = os.path.join(cartella_base, nome_file)
    cartella = os.path.dirname(percorso_file)
    if cartella and not os.path.exists(cartella):
        os.makedirs(cartella, exist_ok=True)
    with open(percorso_file, "wb") as f:
        f.write(dati_byte)
    with LOCK_STAMPA:
        print(f"\n[FILE] Salvato in: {percorso_file}\n")

# Thread per ricevere e leggere i messaggi del server no-stop
def thread_ricezione(sock, evento_stop):
    while not evento_stop.is_set():
        try:
            # Legge la prima riga (può essere testo normale o header di file)
            riga_intestazione = ricevi_riga(sock, timeout=None)  # modalità bloccante
            if riga_intestazione is None:
                # Socket chiuso
                break

            # Verifica se è un file in arrivo
            if riga_intestazione.startswith("__FILE__|"):
                parti = riga_intestazione.split("|")
                if len(parti) >= 3:
                    try:
                        dimensione = int(parti[2])
                    except:
                        dimensione = 0
                    nome_file = parti[1].strip()
                    dati = ricevi_esatto(sock, dimensione) if dimensione > 0 else b""
                    if dati:
                        salva_file_byte(nome_file, dati)
                    else:
                        with LOCK_STAMPA:
                            print("[ERR] file vuoto o non ricevuto.")
                else:
                    with LOCK_STAMPA:
                        print("[ERR] Header file non valido:", riga_intestazione)
            else:
                # Messaggio di testo normale: tenta di leggere eventuali dati aggiuntivi
                resto = b""
                sock.settimeout(0.05)
                try:
                    while True:
                        frammento = sock.recv(4096)
                        if not frammento:
                            break
                        resto += frammento
                        if len(frammento) < 4096:
                            break
                except socket.timeout:
                    pass
                finally:
                    sock.settimeout(None)

                # Visualizza il messaggio completo
                da_stampare = riga_intestazione + (("\n" + resto.decode('utf-8', errors='ignore')) if resto else "")
                with LOCK_STAMPA:
                    sys.stdout.write("\n" + da_stampare + "\n> ")
                    sys.stdout.flush()

        except Exception as e:
            with LOCK_STAMPA:
                print("Errore ricezione:", e)
            break

# Connessione al server con TCP, autenticazione e scambio di messaggi
def avvia_client():

    # Scoperta automatica del server
    ip, porta = scopri_server()
    if not ip:
        print("Server non trovato.")
        return

    print(f"Server trovato a {ip}:{porta}")
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((ip, porta))

    try:
        # Fase di autenticazione
        prompt = ricevi_riga(sock, timeout=5.0)
        if prompt and "USERNAME?" in prompt:
            u = input("Inserisci Username: ")
            sock.sendall(u.encode('utf-8'))

        prompt = ricevi_riga(sock, timeout=5.0)
        if prompt and "PASSWORD?" in prompt:
            p = input("Inserisci Password: ")
            sock.sendall(p.encode('utf-8'))

        # Legge risposta di login dal server
        risposta = ricevi_riga(sock, timeout=3.0)
        if risposta is None:
            # Fallback: legge ciò che è disponibile
            try:
                sock.settimeout(1.0)
                risposta = sock.recv(4096).decode('utf-8', errors='ignore')
            except:
                risposta = ""
            finally:
                sock.settimeout(None)
        print(risposta)

        # Se login fallito, chiude connessione
        if "Bye" in risposta:
            sock.close()
            return

        # Avvia thread di ricezione per gestire messaggi in background
        evento_stop = threading.Event()
        t = threading.Thread(target=thread_ricezione, args=(sock, evento_stop), daemon=True)
        t.start()

        print("\nPronto! Comandi: USERSLIST, CHAT [nome], INFO 1-5, LOG, EXPORT, CHAT_EX, ENDCHAT, EXIT")

        # Loop principale per inviare comandi al server
        while True:
            msg = input("> ").strip()
            if not msg:
                continue
            sock.sendall(msg.encode('utf-8'))

            if msg.upper() == "EXIT":
                break
            # Le risposte vengono gestite dal thread di ricezione

        # Chiusura pulita della connessione
        evento_stop.set()
        try:
            sock.shutdown(socket.SHUT_RDWR)
        except:
            pass

    except Exception as e:
        print("Errore client:", e)
    finally:
        try:
            sock.close()
        except:
            pass


# Punto di ingresso del programma
if __name__ == "__main__":
    avvia_client()