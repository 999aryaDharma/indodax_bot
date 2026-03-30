#!/usr/bin/env bash
# ==============================================================================
# setup.sh — One-Command Server Setup untuk GCP e2-micro Ubuntu 22.04
#
# Penggunaan: bash setup.sh
# Prasyarat: Kamu sudah SSH ke server GCP dan punya akses sudo.
# ==============================================================================

set -euo pipefail  # Hentikan script jika ada error

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info()    { echo -e "${GREEN}[INFO]${NC}  $1"; }
log_warn()    { echo -e "${YELLOW}[WARN]${NC}  $1"; }
log_error()   { echo -e "${RED}[ERROR]${NC} $1"; }
log_section() { echo -e "\n${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"; echo -e "${BLUE}  $1${NC}"; echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"; }

APP_USER="ibs"
APP_DIR="/home/${APP_USER}/indobot-signal"
REPO_URL=""  # Akan ditanyakan saat setup
PYTHON_VERSION="3.11"

# ==============================================================================
# STEP 1: System Update
# ==============================================================================
log_section "STEP 1: Update sistem Ubuntu"
sudo apt-get update -q
sudo apt-get upgrade -y -q
log_info "Sistem berhasil diupdate"

# ==============================================================================
# STEP 2: Install Dependencies
# ==============================================================================
log_section "STEP 2: Install Python & tools"
sudo apt-get install -y -q \
    python${PYTHON_VERSION} \
    python${PYTHON_VERSION}-pip \
    python${PYTHON_VERSION}-venv \
    git \
    curl \
    ufw

log_info "Python $(python${PYTHON_VERSION} --version) terinstall"

# ==============================================================================
# STEP 3: Buat user khusus (principle of least privilege)
# ==============================================================================
log_section "STEP 3: Setup user aplikasi"
if id "${APP_USER}" &>/dev/null; then
    log_warn "User '${APP_USER}' sudah ada, dilewati"
else
    sudo useradd -m -s /bin/bash "${APP_USER}"
    log_info "User '${APP_USER}' berhasil dibuat"
fi

# ==============================================================================
# STEP 4: Clone repository
# ==============================================================================
log_section "STEP 4: Clone repository"
echo ""
read -p "Masukkan URL Git repository (atau tekan Enter untuk skip jika sudah ada): " REPO_URL

if [ -n "${REPO_URL}" ]; then
    sudo -u "${APP_USER}" git clone "${REPO_URL}" "${APP_DIR}"
    log_info "Repository berhasil di-clone ke ${APP_DIR}"
else
    log_warn "Clone dilewati. Pastikan kode sudah ada di ${APP_DIR}"
fi

# Pastikan direktori ada
sudo mkdir -p "${APP_DIR}/logs"
sudo chown -R "${APP_USER}:${APP_USER}" "${APP_DIR}"

# ==============================================================================
# STEP 5: Setup Python virtual environment & install dependencies
# ==============================================================================
log_section "STEP 5: Setup virtual environment"
sudo -u "${APP_USER}" python${PYTHON_VERSION} -m venv "${APP_DIR}/.venv"
sudo -u "${APP_USER}" "${APP_DIR}/.venv/bin/pip" install --upgrade pip -q
sudo -u "${APP_USER}" "${APP_DIR}/.venv/bin/pip" install -r "${APP_DIR}/requirements.txt" -q
log_info "Dependencies berhasil diinstall"

# ==============================================================================
# STEP 6: Setup file .env
# ==============================================================================
log_section "STEP 6: Konfigurasi environment variables"
echo ""
log_warn "Kamu akan diminta mengisi API keys. Ini HANYA disimpan di server, tidak dikirim ke mana pun."
echo ""

ENV_FILE="${APP_DIR}/.env"

read -p "Indodax API Key    : " INDODAX_API_KEY
read -s -p "Indodax Secret Key : " INDODAX_SECRET_KEY
echo ""
read -p "Telegram Bot Token : " TELEGRAM_BOT_TOKEN
read -p "Telegram Chat ID   : " TELEGRAM_CHAT_ID

sudo -u "${APP_USER}" tee "${ENV_FILE}" > /dev/null <<EOF
INDODAX_API_KEY=${INDODAX_API_KEY}
INDODAX_SECRET_KEY=${INDODAX_SECRET_KEY}
TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}
TELEGRAM_CHAT_ID=${TELEGRAM_CHAT_ID}
LOG_LEVEL=INFO
EOF

sudo chmod 600 "${ENV_FILE}"  # Hanya owner yang bisa baca
log_info "File .env berhasil dibuat dengan permission 600"

# ==============================================================================
# STEP 7: Register systemd service
# ==============================================================================
log_section "STEP 7: Setup systemd service"
sudo cp "${APP_DIR}/deploy/ibs.service" /etc/systemd/system/ibs.service

# Update path di service file sesuai user yang digunakan
sudo sed -i "s|/home/ibs|/home/${APP_USER}|g" /etc/systemd/system/ibs.service

sudo systemctl daemon-reload
sudo systemctl enable ibs.service
log_info "Service ibs.service berhasil didaftarkan dan di-enable"

# ==============================================================================
# STEP 8: Setup log rotation
# ==============================================================================
log_section "STEP 8: Setup log rotation"
sudo cp "${APP_DIR}/deploy/logrotate.conf" /etc/logrotate.d/ibs
sudo sed -i "s|/home/ibs|/home/${APP_USER}|g" /etc/logrotate.d/ibs
log_info "Log rotation dikonfigurasi (rotate harian, simpan 7 hari)"

# ==============================================================================
# STEP 9: Firewall
# ==============================================================================
log_section "STEP 9: Konfigurasi firewall (UFW)"
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
sudo ufw --force enable
log_info "Firewall aktif — hanya SSH yang diizinkan masuk"

# ==============================================================================
# STEP 10: Start service
# ==============================================================================
log_section "STEP 10: Menjalankan bot"
sudo systemctl start ibs.service
sleep 3

if sudo systemctl is-active --quiet ibs.service; then
    log_info "✅ Bot berhasil berjalan!"
else
    log_error "❌ Bot gagal berjalan. Cek log dengan: sudo journalctl -u ibs -n 50"
fi

# ==============================================================================
# SUMMARY
# ==============================================================================
log_section "✅ Setup Selesai!"
echo ""
echo "  Perintah berguna:"
echo "  • Lihat log real-time : sudo journalctl -u ibs -f"
echo "  • Status service      : sudo systemctl status ibs"
echo "  • Restart bot         : sudo systemctl restart ibs"
echo "  • Stop bot            : sudo systemctl stop ibs"
echo "  • Lihat log file      : tail -f ${APP_DIR}/logs/ibs.log"
echo ""
log_info "Cek Telegram kamu — bot seharusnya sudah mengirim pesan startup!"
