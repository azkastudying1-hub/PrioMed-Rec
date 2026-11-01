# 📖 Panduan Deploy PrioMed-Rec ke GitHub & Public Access

## 🎯 Tujuan
Mengirim kode aplikasi PrioMed-Rec ke GitHub repository: https://github.com/azkastudying1-hub/PrioMed-Rec

---

## ✅ Prasyarat

1. **Git Installed**
   ```powershell
   git --version
   ```

2. **GitHub Account**
   - Sudah membuat repository di: https://github.com/azkastudying1-hub/PrioMed-Rec

3. **Authentication Setup** - Pilih salah satu:

   ### Option A: GitHub Personal Access Token (Recommended)
   ```
   1. Go to https://github.com/settings/tokens
   2. Click "Generate new token" → "Generate new token (classic)"
   3. Scope: select repo, write:packages
   4. Copy token dan simpan dengan aman
   5. Saat git prompt password, paste token ini
   ```

   ### Option B: SSH Key
   ```powershell
   # Generate SSH key (jika belum ada)
   ssh-keygen -t ed25519 -C "your_email@example.com"
   
   # Copy public key
   Get-Content $env:USERPROFILE\.ssh\id_ed25519.pub | Set-Clipboard
   
   # Add ke GitHub: https://github.com/settings/keys
   ```

---

## 🚀 Langkah-Langkah Deploy

### **Langkah 1: Verifikasi & Setup Git**

```powershell
# Buka PowerShell di folder proyek
cd d:\Hacktiv8\priomed-rec

# Cek Git config
git config --global user.name
git config --global user.email

# Jika belum set, jalankan:
git config --global user.name "Your Name"
git config --global user.email "your.email@example.com"
```

### **Langkah 2: Commit Perubahan Lokal**

```powershell
# Lihat status
git status

# Tambah semua file
git add -A

# Commit dengan message
git commit -m "Initial PrioMed-Rec deployment"
```

### **Langkah 3: Konfigurasi Remote**

```powershell
# Tambah/update remote GitHub
git remote add origin https://github.com/azkastudying1-hub/PrioMed-Rec.git

# Atau jika sudah ada, update:
git remote set-url origin https://github.com/azkastudying1-hub/PrioMed-Rec.git

# Verifikasi
git remote -v
```

### **Langkah 4: Push ke GitHub**

```powershell
# Push branch main (dengan --force untuk replace existing content)
git push -u origin main --force

# Atau tanpa force (jika ingin merge):
git push -u origin main
```

**Saat diminta password**: Paste GitHub Personal Access Token Anda

### **Langkah 5: Verifikasi**

```powershell
# Cek history push
git log --oneline -5

# Buka di browser
Start-Process "https://github.com/azkastudying1-hub/PrioMed-Rec"
```

---

## 📝 Menggunakan Script Otomatis

Saya sudah membuat script untuk otomatis:

```powershell
# Jalankan script
.\DEPLOY_TO_GITHUB.ps1
```

Script akan:
- ✅ Verifikasi Git configuration
- ✅ Commit perubahan yang belum tersimpan
- ✅ Setup remote GitHub
- ✅ Verifikasi koneksi
- ✅ Push ke GitHub

---

## ⚠️ File yang TIDAK Boleh di-Push

Pastikan `.gitignore` sudah ada dan contains:

```
# Environment variables
.env
.env.local
.env.*.local

# Dependencies
.venv/
venv/
node_modules/

# IDE
.vscode/
.idea/
*.swp

# System
.DS_Store
__pycache__/
*.pyc

# Logs
logs/
*.log
```

---

## 🔍 Troubleshooting

| Issue | Solusi |
|-------|--------|
| `error: failed to push` | - Cek internet connection<br>- Verify GitHub token/SSH key<br>- Run: `git remote -v` |
| `Authentication failed` | Generate new token: https://github.com/settings/tokens |
| `rejected - non-fast-forward` | Use: `git push --force` |
| `fatal: not a git repository` | Pastikan di folder: `d:\Hacktiv8\priomed-rec` |

---

## 🌐 Deploy Frontend ke Public (Next Steps)

Setelah push ke GitHub, Anda bisa deploy frontend dengan:

### Option 1: GitHub Pages (Gratis)
```powershell
# Setup GitHub Pages di Settings → Pages
# Branch: main, folder: web/dist
```

### Option 2: Vercel (Recommended)
```powershell
# Install Vercel CLI
npm install -g vercel

# Di folder web/
cd web
vercel

# Follow prompts untuk connect ke GitHub
```

### Option 3: Netlify
```powershell
# Di folder web/
npm run build
# Drag & drop dist/ ke Netlify
```

---

## 🎉 Hasil Akhir

Setelah deploy:
- ✅ Kode ada di GitHub: https://github.com/azkastudying1-hub/PrioMed-Rec
- ✅ Bisa diakses oleh public (jika repository public)
- ✅ Siap untuk deploy ke production platform

---

## 📞 Support

Jika ada error, cek:
1. GitHub repository settings
2. Git configuration: `git config --list`
3. SSH/Token setup
4. Branch names (harus main atau master)

Untuk info lebih: https://docs.github.com/en/get-started/importing-your-project-to-github
