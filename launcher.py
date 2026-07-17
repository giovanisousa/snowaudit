import subprocess
import os
import sys

# Esconde a janela preta do terminal no Windows
startupinfo = subprocess.STARTUPINFO()
startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

# Caminho relativo para usar o Python do seu ambiente virtual e iniciar o Streamlit
caminho_python = os.path.join("venv", "Scripts", "python.exe")

# Comando que será rodado de forma invisível
comando = [caminho_python, "-m", "streamlit", "run", "1_❄️_Auditoria.py", "--server.headless=true"]

# Dispara o sistema e abre o navegador automaticamente no endereço local
subprocess.Popen(comando, startupinfo=startupinfo)

import webbrowser
import time
time.sleep(3) # Espera 3 segundos para o motor ligar
webbrowser.open("http://localhost:8501") # Abre o navegador do Fernando