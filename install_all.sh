#!/bin/bash
set -e

# Script de instalación completa para Gearman PowerToy
# Crea entorno virtual, instala dependencias y el paquete en modo editable

echo "[+] Instalando dependencias de sistema (gearmand, build tools, libevent)..."
if command -v apt-get >/dev/null 2>&1; then
  sudo apt-get update
  sudo apt-get install -y gearman-job-server libgearman-dev build-essential python3-dev libevent-dev
elif command -v yum >/dev/null 2>&1; then
  sudo yum install -y gearmand gearmand-devel gcc python3-devel libevent-devel
else
  echo "[!] Instalación automática de gearmand no soportada en este sistema."
  echo "    Instala gearmand y libgearman-dev manualmente."
fi

VENV=".venv"
REQS="requirements.txt"

if [ ! -d "$VENV" ]; then
  echo "[+] Creando entorno virtual en $VENV..."
  python3 -m venv "$VENV"
fi

source "$VENV/bin/activate"

if [ -f "$REQS" ]; then
  echo "[+] Instalando dependencias desde $REQS..."
  pip install --upgrade pip
  pip install -r "$REQS"
fi

echo "[+] Instalando paquete en modo editable..."
pip install -e .

echo "[OK] Entorno listo. Activa con: source $VENV/bin/activate"
