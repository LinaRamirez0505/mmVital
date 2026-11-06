#!/bin/bash
set -e
cd "$(dirname "$0")"

# Taller 1: usuario de servicio sin login, en los grupos del UART y del Bluetooth
id radar >/dev/null 2>&1 || sudo adduser --system --group --no-create-home --shell /usr/sbin/nologin radar
sudo usermod -aG dialout,bluetooth radar

# Carpeta del servicio
sudo mkdir -p /opt/radar
sudo cp app.py ld6002.py leer_anillo.py resumen.py /opt/radar/
sudo cp -r templates /opt/radar/
sudo cp datos_*.csv comparacion_*.csv /opt/radar/ 2>/dev/null || true

# Entorno de Python propio (con la libreria del anillo)
[ -d /opt/radar/venv ] || sudo python3 -m venv --system-site-packages /opt/radar/venv
sudo /opt/radar/venv/bin/pip install --no-cache-dir --ignore-requires-python colmi-r02-client
sudo chown -R radar:radar /opt/radar

# Talleres 2 y 3: demonio con prioridad
sudo tee /etc/systemd/system/radar.service >/dev/null <<'EOF'
[Unit]
Description=Radar LD6002 (monitor de signos vitales)
After=network.target bluetooth.target

[Service]
User=radar
Group=radar
WorkingDirectory=/opt/radar
ExecStart=/opt/radar/venv/bin/python -u app.py
Nice=-5
Restart=always
RestartSec=3
TimeoutStopSec=15

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now radar

# Taller 4: cron del usuario radar (resumen diario y limpieza)
( sudo crontab -u radar -l 2>/dev/null | grep -v '/opt/radar' ; \
  echo "10 0 * * * /opt/radar/venv/bin/python /opt/radar/resumen.py >> /opt/radar/cron.log 2>&1" ; \
  echo "30 0 * * * find /opt/radar -name '*_20*.csv' -mtime +30 -delete" ) | sudo crontab -u radar -

sudo timedatectl set-timezone America/Bogota
echo "Instalado. Estado:"
systemctl --no-pager status radar | head -n 8
