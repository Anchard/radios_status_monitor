import os
import smtplib
import sqlite3
import requests
import tkinter as tk
from tkinter import ttk
from email.mime.text import MIMEText
from bs4 import BeautifulSoup
from datetime import datetime
from dotenv import load_dotenv
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.dates as mdates

# Carregar variáveis de ambiente
load_dotenv()
EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASS = os.getenv("EMAIL_PASS")

# Configurações
RADIO_URLS = {
    "tabajara": "http://stm2.xcast.com.br:7524/index.html?sid=1",
    "parahyba": "http://stm1.xcast.com.br:9538/index.html?sid=1",
}
CHECK_INTERVAL = 10  # segundos

# Banco de dados
conn = sqlite3.connect("radio_logs.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute(
    """
    CREATE TABLE IF NOT EXISTS logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        radio TEXT,
        listeners INTEGER,
        status INTEGER,
        timestamp TEXT
    )
    """
)
conn.commit()

def check_stream(radio):
    try:
        response = requests.get(RADIO_URLS[radio], timeout=5)
        soup = BeautifulSoup(response.text, "html.parser")
        is_online = "Stream is up" in soup.text
        listeners = int(soup.text.split("with ")[1].split(" listeners")[0]) if "with " in soup.text else 0
        
        cursor.execute(
            "INSERT INTO logs (radio, listeners, status, timestamp) VALUES (?, ?, ?, ?)",
            (radio, listeners, int(is_online), datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        )
        conn.commit()
        
        return is_online, listeners
    except Exception as e:
        print(f"Erro ao verificar {radio}: {e}")
        return False, 0

def send_email(radio, listeners):
    try:
        msg_content = f"A rádio {radio} caiu às {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} com {listeners} ouvintes."
        msg = MIMEText(msg_content)
        msg["Subject"] = f"Alerta: Rádio {radio} caiu!"
        msg["From"] = EMAIL_USER
        msg["To"] = EMAIL_USER
        
        with smtplib.SMTP("mail.mailo.com", 587) as server:
            server.starttls()
            server.login(EMAIL_USER, EMAIL_PASS)
            server.sendmail(EMAIL_USER, EMAIL_USER, msg.as_string())
        
        print("Email de alerta enviado!")
    except Exception as e:
        print(f"Erro ao enviar email: {e}")

class RadioMonitorApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Monitor de Rádios")
        self.geometry("800x600")
        
        self.status_labels = {}
        for radio in RADIO_URLS:
            label = ttk.Label(self, text=f"{radio.capitalize()}: Verificando...", font=("Arial", 12))
            label.pack()
            self.status_labels[radio] = label
        
        self.fig, self.ax = plt.subplots()
        self.ax.set_title("Histórico de Ouvintes")
        self.ax.set_xlabel("Tempo")
        self.ax.set_ylabel("Ouvintes")
        self.ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
        
        self.lines = {radio: self.ax.plot([], [], label=radio)[0] for radio in RADIO_URLS}
        self.ax.legend()
        
        self.canvas = FigureCanvasTkAgg(self.fig, self)
        self.canvas.get_tk_widget().pack()
        
        self.time_data = []
        self.listener_data = {radio: [] for radio in RADIO_URLS}
        
        self.update_data()
    
    def update_data(self):
        current_time = datetime.now()
        self.time_data.append(current_time)
        
        for radio in RADIO_URLS:
            is_online, listeners = check_stream(radio)
            status_text = "Online" if is_online else "Offline"
            self.status_labels[radio].config(text=f"{radio.capitalize()}: {status_text} - {listeners} ouvintes")
            
            if not is_online:
                send_email(radio, listeners)
            
            self.listener_data[radio].append(listeners)
            
            if len(self.time_data) > 20:
                self.time_data.pop(0)
                self.listener_data[radio].pop(0)
            
            self.lines[radio].set_data(self.time_data, self.listener_data[radio])
        
        self.ax.set_xlim(self.time_data[0], self.time_data[-1])
        self.ax.set_ylim(0, max(max(self.listener_data[radio], default=0) for radio in RADIO_URLS) + 5)
        self.ax.figure.autofmt_xdate()
        self.canvas.draw()
        
        self.after(CHECK_INTERVAL * 1000, self.update_data)

if __name__ == "__main__":
    app = RadioMonitorApp()
    app.mainloop()
