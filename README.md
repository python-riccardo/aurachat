# AuraChat - Sistema di Chat Multi-Utente

Sistema di chat client-server sviluppato in Python con discovery automatico UDP e comunicazione TCP.

## Struttura del Progetto

```
root/
├── server.py          # Server principale
├── client.py          # Client per connettersi al server
└── util/
    ├── config.json    # Configurazione server e utenti
    └── log.xml        # Log degli eventi (generato automaticamente)
```

## Caratteristiche Implementate (Punti 1-4)

### ✅ Punto 1: Struttura del Progetto
- File organizzati secondo la specifica richiesta
- Cartella `util/` per configurazione e log

### ✅ Punto 2: ServerSocket TCP in Python
- Implementazione completa usando socket TCP
- Gestione multi-client con threading
- Timeout di 2 minuti per inattività

### ✅ Punto 3: Discovery Automatico UDP + TCP
- **Discovery UDP**: Il client invia un broadcast UDP sulla porta 20498
- **Risposta Server**: Il server risponde con `AURA_OFFER:porta`
- **Connessione TCP**: Il client si connette al server via TCP sulla porta ricevuta

### ✅ Punto 4: Log XML in util/
- Tutti gli eventi vengono registrati in `util/log.xml`
- Formato XML con attributi: time, type, user
- Log di: LOGIN, LOGOUT, TIMEOUT, CMD, CHAT_START, CHAT_END, SERVER

## Installazione e Avvio

### Requisiti
- Python 3.6 o superiore
- Nessuna libreria esterna richiesta (solo moduli standard)

### Avvio del Server
```bash
python server.py
```

Il server:
- Si avvia automaticamente sulla porta 20498
- Rileva l'IP locale automaticamente
- Attiva il servizio di discovery UDP
- Accetta connessioni TCP dai client

### Avvio del Client
```bash
python client.py
```

Il client:
1. Invia un broadcast UDP per trovare il server
2. Si connette automaticamente al server trovato
3. Chiede username e password
4. Entra in modalità interattiva

## Credenziali di Accesso

Le credenziali sono configurate in `util/config.json`:

| Username | Password    |
|----------|-------------|
| admin    | admin       |
| alice    | password123 |
| bob      | password456 |
| mario    | rossi       |

## Comandi Disponibili

### Comandi Base
- `TIME` - Mostra l'ora corrente del server
- `NAME` - Mostra nome server e client
- `EXIT` - Disconnette il client
- `HELP` - Mostra l'elenco comandi

### Comandi INFO
- `INFO 1` - Numero di client connessi
- `INFO 2` - Numero di utenti registrati nel DB
- `INFO 3` - Informazioni di rete del server (IP:porta)
- `INFO 4` - Informazioni di rete del client
- `INFO 5` - Lista utenti disponibili per chat

### Gestione Chat
- `USERSLIST` - Elenca utenti disponibili per chat
- `CHAT [username]` - Apre una chat 1-a-1 con l'utente specificato
- `ENDCHAT` - Chiude la chat corrente
- `CHAT_EX [txt/csv/xml]` - Esporta la cronologia della chat corrente

### Export Log
- `LOG` - Visualizza i log
- `EX [txt/csv/xml]` - Esporta log in file
- `EXPORT [txt/csv/xml]` - Alias di EX

#### Parametri Export:
- **Formato**: `txt` (default), `csv`, `xml`

## Funzionalità del Sistema

### Discovery Automatico
1. Client invia broadcast UDP: `AURA_DISCOVERY`
2. Server risponde: `AURA_OFFER:20498`
3. Client si connette via TCP all'IP e porta ricevuti

### Autenticazione
- Verifica username e password da `config.json`
- Impedisce connessioni duplicate dello stesso utente
- Log automatico di LOGIN/LOGOUT

### Sistema di Log
- Eventi salvati in XML: `util/log.xml`
- Tracciamento completo di tutte le attività

## Sicurezza e Gestione Errori

- Timeout di 2 minuti per inattività
- Gestione errori di rete e disconnessioni
- Protezione contro connessioni duplicate
- Encoding UTF-8 con gestione errori

## Test del Sistema

### Test Base (1 Client)
```bash
# Terminal 1: Avvia server
python server.py

# Terminal 2: Avvia client
python client.py
# Login con: admin / admin
# Prova comandi: TIME, NAME, INFO 1, LOG
```


### Test Export Log
```bash
# Sul client:
EX xml        # Esporta i log in XML
# Il file verrà salvato localmente (es: export_log_20260203_163022.xml)
```

## File Generati

### Durante l'esecuzione:
- `util/log.xml` - Log degli eventi (sul server)
- `export_log_*.txt/csv/xml` - Export log (sul client)

## Note Tecniche

### Protocollo di Comunicazione
- **UDP Port**: 20498 (discovery)
- **TCP Port**: 20498 (comunicazione)
- **Encoding**: UTF-8
- **Terminatore**: `\n` (newline)

### Threading
- Server: thread separato per ogni client connesso
- Client: thread separato per ricezione messaggi

## Timeout
- Il timeout di 2 minuti è normale per inattività
- Invia qualsiasi comando per mantenere la connessione attiva

## Autore
Sistema AuraChat - Progetto didattico per reti di computer
20205@studenti.marconiverona.edu.it - Riccardo Costantini
20388@studenti.marconiverona.edu.it - Dante Pastrello