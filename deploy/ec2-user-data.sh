#!/bin/bash
# DialAgent EC2 user-data script (Ubuntu 22.04/24.04 LTS, t2.micro free tier).
# Paste the whole script into the EC2 launch wizard under Advanced details > User data.
# It clones the PUBLIC repo, installs deps, and runs DialAgent as a systemd
# service that restarts on reboot, so the endpoint stays up through Nov 9.
# Prerequisite: the GitHub repo https://github.com/Akshay7273/dialagent must
# already exist (repo creation runs separately). Security group must allow
# inbound TCP 8000 from 0.0.0.0/0, plus SSH (22) if shell access is wanted.
set -e
exec > /var/log/dialagent-install.log 2>&1

apt-get update -y
apt-get install -y python3-venv python3-pip git

if [ ! -d /opt/dialagent ]; then
  git clone https://github.com/Akshay7273/dialagent /opt/dialagent
fi
cd /opt/dialagent
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt

cat > /etc/systemd/system/dialagent.service <<'UNIT'
[Unit]
Description=DialAgent gauge-reading endpoint
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/dialagent
ExecStart=/opt/dialagent/.venv/bin/uvicorn app:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
UNIT

systemctl daemon-reload
systemctl enable dialagent
systemctl start dialagent
sleep 5
curl -sf http://localhost:8000/health || echo "HEALTH CHECK FAILED"
