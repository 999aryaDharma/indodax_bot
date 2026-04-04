# Troubleshoot SSH Permission Denied - GCP VM

## Error:
```
ssh -i ~/.ssh/gcp_cicd_key ibs@34.70.82.114
ibs@34.70.82.114: Permission denied (publickey).
```

## Penyebab:
Public key belum ditambahkan ke file `~/.ssh/authorized_keys` di dalam VM.

---

## Solusi Step-by-Step:

### Step 1: Pastikan File Public Key Ada

Di Git Bash atau PowerShell (Windows):

```bash
# Cek apakah file public key ada
ls ~/.ssh/gcp_cicd_key.pub

# Lihat isi public key
cat ~/.ssh/gcp_cicd_key.pub
```

Output harusnya seperti:
```
ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIxxxxxxxxxxxxxxxxxxxxxx github-actions-cicd
```

**Copy seluruh baris ini** (dimulai dari `ssh-ed25519` sampai `github-actions-cicd`).

---

### Step 2: SSH ke VM dengan Metode yang Sudah Ada

Kalau kamu biasa SSH ke VM tanpa masalah, pakai cara yang biasa kamu pakai:

**Opsi A: Lewat GCP Console (Browser SSH)**
1. Buka https://console.cloud.google.com/compute/instances
2. Klik VM kamu
3. Klik **SSH** → **Open in browser window**

**Opsi B: Pakai SSH key yang sudah ada**
```bash
# Kalau kamu punya key lain yang sudah works
ssh -i ~/.ssh/<key_lain> ibs@34.70.82.114
```

---

### Step 3: Tambahkan Public Key ke VM

Setelah berhasil masuk ke VM:

```bash
# Pastikan folder .ssh ada
mkdir -p ~/.ssh

# Buka file authorized_keys dengan nano
nano ~/.ssh/authorized_keys
```

**Paste public key** yang sudah kamu copy di Step 1 ke baris baru di file ini.

Atau pakai cara one-liner (lebih cepat):

```bash
# Ganti dengan ISI PUBLIC KEY kamu yang sebenarnya
echo "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIxxxxxxxxxxxx github-actions-cicd" >> ~/.ssh/authorized_keys
```

Kemudian set permission yang benar:

```bash
chmod 700 ~/.ssh
chmod 600 ~/.ssh/authorized_keys
```

Verifikasi:

```bash
cat ~/.ssh/authorized_keys
```

Harusnya muncul public key yang baru saja di-paste.

Keluar dari VM:
```bash
exit
```

---

### Step 4: Test SSH Lagi dari Local

```bash
ssh -i ~/.ssh/gcp_cicd_key ibs@34.70.82.114
```

Kalau masih error, coba dengan verbose mode untuk debug:

```bash
ssh -v -i ~/.ssh/gcp_cicd_key ibs@34.70.82.114
```

---

## Kemungkinan Masalah Lain:

### Problem 1: User `ibs` tidak ada di VM

```bash
# Cek apakah user ibs ada
id ibs

# Kalau tidak ada, buat user dulu
sudo useradd -m -s /bin/bash ibs
sudo mkdir -p /home/ibs/.ssh
sudo chown ibs:ibs /home/ibs/.ssh
```

### Problem 2: Permission di .ssh salah

```bash
# Di VM, pastikan permission benar
sudo chown -R ibs:ibs /home/ibs/.ssh
chmod 700 /home/ibs/.ssh
chmod 600 /home/ibs/.ssh/authorized_keys
```

### Problem 3: SSH config tidak mengizinkan key authentication

```bash
# Di VM, cek SSH config
sudo nano /etc/ssh/sshd_config
```

Pastikan baris ini ada dan tidak dikomentari:
```
PubkeyAuthentication yes
AuthorizedKeysFile .ssh/authorized_keys
```

Kalau diubah, restart SSH service:
```bash
sudo systemctl restart sshd
```

---

## Cara Paling Gampang (Kalau Masih Bingung):

**Gunakan GCP Metadata untuk inject SSH key:**

1. Copy public key:
   ```bash
   cat ~/.ssh/gcp_cicd_key.pub
   ```

2. Buka GCP Console → Compute Engine → Metadata → SSH Keys
   
3. Klik **Edit** → **Add Item**
   
4. Paste public key kamu (format: `username:key`)
   ```
   ibs:ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIxxxx github-actions-cicd
   ```

5. Save dan tunggu ~30 detik

6. Test lagi:
   ```bash
   ssh -i ~/.ssh/gcp_cicd_key ibs@34.70.82.114
   ```

---

Mau aku bantu step mana dulu? Atau kamu mau coba cara GCP Metadata (paling gampang)?
