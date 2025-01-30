import os
import time
import smtplib
import sqlite3
import requests
from email.mime.text import MIMEText
from bs4 import BeautifulSoup
import threading
import matplotlib.pyplot as plt
from datetime import datetime

# Configurações do e-mail
EMAIL_USER = os.getenv('EMAIL_USER', 'contato.tecnica.epc@mailo.com')
EMAIL_PASS = os.getenv('EMAIL_PASS', 'Tecnica@123')
RADIO_URLS = {
    'tabajara': 'http://stm2.xcast.com.br:7524/index.html?sid=1',
    'parahyba': 'http://stm1.xcast.com.br:9538/index.html?sid=1'
}

# Configuração do banco de dados
conn = sqlite3.connect('radio_logs.db', check_same_thread=False)
cursor = conn.cursor()
cursor.execute('''CREATE TABLE IF NOT EXISTS logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    radio TEXT,
                    listeners INTEGER,
                    status INTEGER,
                    timestamp TEXT)''')
conn.commit()

# Lock para sincronizar acesso ao banco de dados
db_lock = threading.Lock()

# Variável global para controlar execução
running = True

def check_stream(radio):
    try:
        response = requests.get(RADIO_URLS[radio], timeout=5)
        soup = BeautifulSoup(response.text, 'html.parser')
        is_online = 'Stream is up' in soup.text
        listeners = int(soup.text.split('with ')[1].split(' listeners')[0]) if 'with ' in soup.text else 0
        
        with db_lock:
            cursor.execute('INSERT INTO logs (radio, listeners, status, timestamp) VALUES (?, ?, ?, ?)', 
                           (radio, listeners, int(is_online), datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
            conn.commit()
        
        return is_online, listeners
    except Exception as e:
        print(f'Erro ao verificar {radio}:', e)
        return False, 0

def send_email(radio, listeners):
    msg = MIMEText(f'A rádio {radio} caiu às {datetime.now().strftime("%Y-%m-%d %H:%M:%S")} com {listeners} ouvintes.')
    msg['Subject'] = f'Alerta: Rádio {radio} caiu!'
    msg['From'] = EMAIL_USER
    msg['To'] = EMAIL_USER
    
    try:
        with smtplib.SMTP('mail.mailo.com', 587) as server:
            server.starttls()
            server.login(EMAIL_USER, EMAIL_PASS)
            server.sendmail(EMAIL_USER, EMAIL_USER, msg.as_string())
    except Exception as e:
        print('Erro ao enviar e-mail:', e)

def monitor_radios():
    alert_sent = {'tabajara': False, 'parahyba': False}
    while running:
        for radio in RADIO_URLS.keys():
            is_online, listeners = check_stream(radio)
            if not is_online and not alert_sent[radio]:
                send_email(radio, listeners)
                alert_sent[radio] = True
            if is_online:
                alert_sent[radio] = False
        time.sleep(1)

def plot_graph():
    plt.ion()
    fig, ax = plt.subplots()
    
    while running:
        with db_lock:
            cursor.execute("SELECT timestamp, listeners FROM logs WHERE radio='tabajara' ORDER BY timestamp DESC LIMIT 10")
            tabajara_data = cursor.fetchall()[::-1]
            cursor.execute("SELECT timestamp, listeners FROM logs WHERE radio='parahyba' ORDER BY timestamp DESC LIMIT 10")
            parahyba_data = cursor.fetchall()[::-1]

        if tabajara_data and parahyba_data:
            times = [t[0].split()[1] for t in tabajara_data]
            tabajara_listeners = [t[1] for t in tabajara_data]
            parahyba_listeners = [t[1] for t in parahyba_data]

            ax.clear()
            ax.plot(times, tabajara_listeners, 'b-', label='Tabajara')
            ax.plot(times, parahyba_listeners, 'r-', label='Parahyba')
            ax.legend()
            plt.xticks(rotation=45)
            plt.pause(1)

    plt.close(fig)  # Fecha o gráfico ao sair

# Criar e iniciar threads como daemon
t1 = threading.Thread(target=monitor_radios, daemon=True)
t2 = threading.Thread(target=plot_graph, daemon=True)
t1.start()
t2.start()

# Manter o programa rodando e permitir encerramento com CTRL+C
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("\nEncerrando monitoramento...")
    running = False
    time.sleep(2)  # Tempo para encerrar as threads
