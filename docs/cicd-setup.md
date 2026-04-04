# CI/CD Setup Guide - Auto Deploy ke GCP VM

Dokumen ini menjelaskan cara setup automatic deployment dari GitHub ke GCP VM menggunakan GitHub Actions.

## 📋 Prerequisites

Sebelum setup, pastikan:
- ✅ Repository sudah di-push ke GitHub
- ✅ GCP VM sudah berjalan dan bisa diakses via SSH
- ✅ Bot sudah berjalan di VM menggunakan systemd service (`ibs.service`)

---

## 🔧 Step-by-Step Setup

### Step 1: Generate SSH Key Pair

Di **local machine** (Windows), buka Git Bash atau PowerShell:

```bash
ssh-keygen -t ed25519 -C "github-actions-cicd" -f ~/.ssh/gcp_cicd_key
```

- Tekan Enter untuk skip passphrase (biar otomatis)
- Ini akan generate 2 file:
  - `~/.ssh/gcp_cicd_key` (private key)
  - `~/.ssh/gcp_cicd_key.pub` (public key)

### Step 2: Copy Public Key ke GCP VM

```bash
# Copy isi public key
cat ~/.ssh/gcp_cicd_key.pub

# SSH ke VM kamu (ganti dengan IP dan user kamu)
ssh ibs@<GCP_VM_EXTERNAL_IP>
```

Di dalam VM, tambahkan public key ke `authorized_keys`:

```bash
# Di dalam VM
mkdir -p ~/.ssh
echo "<paste_isi_public_key>" >> ~/.ssh/authorized_keys
chmod 700 ~/.ssh
chmod 600 ~/.ssh/authorized_keys
exit
```

### Step 3: Test SSH Access dari Local

```bash
ssh -i ~/.ssh/gcp_cicd_key ibs@<GCP_VM_EXTERNAL_IP>
```

Jika berhasil login tanpa password, berarti SSH key sudah benar.

### Step 4: Copy Private Key untuk GitHub Secrets

```bash
# Copy isi private key (termasuk BEGIN dan END lines)
cat ~/.ssh/gcp_cicd_key
```

Copy **seluruh isi** file (termasuk `-----BEGIN OPENSSH PRIVATE KEY-----` dan `-----END OPENSSH PRIVATE KEY-----`).

### Step 5: Setup GitHub Secrets

Buka repository kamu di GitHub:
1. Klik **Settings** (tab di atas)
2. Klik **Secrets and variables** → **Actions**
3. Klik **New repository secret** untuk setiap secret berikut:

#### Secret yang harus dibuat:

| Secret Name | Value |
|-------------|-------|
| `GCP_SSH_PRIVATE_KEY` | Isi file `gcp_cicd_key` (private key) |
| `GCP_VM_EXTERNAL_IP` | IP address VM kamu (contoh: `34.101.xxx.xxx`) |
| `GCP_VM_USER` | User SSH di VM (contoh: `ibs`) |

**Cara menambahkan:**
1. Klik **New repository secret**
2. Masukkan **Name** sesuai tabel di atas
3. Paste **Value** yang sesuai
4. Klik **Add secret**

### Step 6: Push Workflow ke GitHub

Commit dan push file workflow yang sudah dibuat:

```bash
git add .github/workflows/deploy.yml
git commit -m "ci: setup auto-deploy to GCP VM"
git push origin main
```

### Step 7: Verifikasi Deployment

Setelah push:
1. Buka repository di GitHub
2. Klik tab **Actions**
3. Kamu akan melihat workflow "Deploy to GCP VM" sedang berjalan
4. Klik untuk melihat log deployment
5. Jika sukses, akan ada centang hijau ✅

### Step 8: Test dengan Update Code

Buat perubahan kecil untuk test:

```bash
# Edit file apapun
echo "# Test CI/CD" >> README.md

git add README.md
git commit -m "test: trigger CI/CD deployment"
git push origin main
```

Lihat di **Actions** tab - workflow akan otomatis jalan dan deploy ke VM.

---

## 🚀 Cara Kerja

```mermaid
graph LR
    A[Push ke main] --> B[GitHub Actions Trigger]
    B --> C[Checkout Code]
    C --> D[SSH ke GCP VM]
    D --> E[git pull origin main]
    E --> F[Install dependencies]
    F --> G[Restart ibs.service]
    G --> H[Deploy Complete ✅]
```

Setiap kali kamu push ke `main`:
1. GitHub Actions akan otomatis trigger
2. Workflow SSH ke VM kamu
3. Pull code terbaru dari GitHub
4. Install dependencies baru (jika ada)
5. Restart service bot
6. Kamu dapat notifikasi di Actions tab

---

## 🔍 Monitoring & Troubleshooting

### Cek Status Deployment

1. Buka **Actions** tab di GitHub
2. Klik workflow run terbaru
3. Lihat log untuk detail

### Jika Deployment Gagal

Cek error di log Actions. Error umum:

| Error | Solusi |
|-------|--------|
| `Permission denied` | Pastikan SSH private key benar dan ada di `authorized_keys` VM |
| `Connection timed out` | Cek firewall GCP - pastikan port 22 (SSH) terbuka |
| `git pull failed` | Pastikan VM sudah clone repo dari GitHub dan branch `main` aktif |
| `systemctl restart failed` | SSH manual ke VM dan cek `sudo journalctl -u ibs -n 50` |

### Manual Deploy (Fallback)

Jika Actions gagal, deploy manual:

```bash
ssh ibs@<GCP_VM_IP>
cd /home/ibs/indobot-signal
git pull origin main
/home/ibs/indobot-signal/.venv/bin/pip install -r requirements.txt
sudo systemctl restart ibs.service
sudo systemctl status ibs.service
```

---

## 📝 Perintah Berguna

```bash
# Cek status service di VM
sudo systemctl status ibs

# Lihat log bot real-time
sudo journalctl -u ibs -f

# Restart bot
sudo systemctl restart ibs

# Lihat commit terakhir di VM
cd /home/ibs/indobot-signal && git log -1 --oneline
```

---

## 🔐 Security Notes

- ✅ SSH private key disimpan sebagai GitHub Secret (encrypted)
- ✅ Key hanya punya akses read-only ke repository
- ✅ VM user `ibs` punya permission terbatas (sesuai setup di `ibs.service`)
- ✅ Firewall hanya buka port SSH (port 22)
- ⚠️ Jangan commit `.env` atau API keys ke repository
- ⚠️ Rotate SSH key secara berkala (tiap 3-6 bulan)

---

## 📊 Contoh Workflow Run

Setelah push ke main, kamu akan melihat:

```
✅ Deploy to GCP VM #123
   ✓ Setup SSH key
   ✓ Deploy to VM
     📍 Current commit: abc1234
     🔄 Pulling latest code...
     📦 Installing dependencies...
     🔧 Restarting service...
     ✅ Deployment complete!
```

---

## 🎯 Next Steps (Optional)

Setelah CI/CD berjalan lancar, kamu bisa enhance:

1. **Notifications**: Tambah notifikasi ke Telegram jika deploy sukses
2. **Health Check**: Tambah step untuk verifikasi bot berjalan setelah deploy
3. **Rollback**: Buat workflow untuk rollback ke versi sebelumnya
4. **Staging**: Buat environment staging sebelum production

---

**Last Updated:** April 4, 2026
