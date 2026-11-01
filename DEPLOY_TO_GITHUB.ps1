# ============================================================================
# Script Deploy PrioMed-Rec ke GitHub Repository
# https://github.com/azkastudying1-hub/PrioMed-Rec
# ============================================================================

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Deploy PrioMed-Rec ke GitHub" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Konfigurasi
$GITHUB_USERNAME = "azkastudying1-hub"
$REPO_NAME = "PrioMed-Rec"
$GITHUB_URL = "https://github.com/$GITHUB_USERNAME/$REPO_NAME.git"

Write-Host "📍 Repository URL: $GITHUB_URL" -ForegroundColor Yellow
Write-Host ""

# ============================================================================
# STEP 1: Verifikasi Git Setup
# ============================================================================
Write-Host "[STEP 1] Verifikasi Git Configuration..." -ForegroundColor Green

$gitUser = git config --global user.name
$gitEmail = git config --global user.email

if (-not $gitUser) {
    Write-Host "❌ Git user.name tidak dikonfigurasi" -ForegroundColor Red
    Write-Host "Jalankan perintah ini terlebih dahulu:" -ForegroundColor Yellow
    Write-Host "  git config --global user.name 'Your Name'" -ForegroundColor Gray
    Write-Host "  git config --global user.email 'your.email@example.com'" -ForegroundColor Gray
    exit 1
}

Write-Host "✅ Git User: $gitUser ($gitEmail)" -ForegroundColor Green
Write-Host ""

# ============================================================================
# STEP 2: Cek Status Repository Lokal
# ============================================================================
Write-Host "[STEP 2] Cek Status Repository Lokal..." -ForegroundColor Green

cd d:\Hacktiv8\priomed-rec

$status = git status -s
if ($status) {
    Write-Host "⚠️  Ada perubahan yang belum di-commit:" -ForegroundColor Yellow
    Write-Host $status
    Write-Host ""
    Write-Host "Commit perubahan sebelum melanjutkan? (Y/n)" -ForegroundColor Yellow
    $choice = Read-Host
    
    if ($choice -ne "n") {
        Write-Host "Committing changes..." -ForegroundColor Cyan
        git add -A
        $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
        git commit -m "Deploy update: $timestamp"
    }
}

Write-Host "✅ Repository lokal clean" -ForegroundColor Green
Write-Host ""

# ============================================================================
# STEP 3: Konfigurasi Remote GitHub
# ============================================================================
Write-Host "[STEP 3] Konfigurasi Remote GitHub..." -ForegroundColor Green

$remoteOrigin = git remote get-url origin 2>$null

if ($remoteOrigin -eq $GITHUB_URL) {
    Write-Host "✅ Remote 'origin' sudah dikonfigurasi dengan benar" -ForegroundColor Green
} elseif ($remoteOrigin) {
    Write-Host "⚠️  Remote 'origin' menunjuk ke: $remoteOrigin" -ForegroundColor Yellow
    Write-Host "Mengupdate ke: $GITHUB_URL" -ForegroundColor Cyan
    git remote remove origin
    git remote add origin $GITHUB_URL
    Write-Host "✅ Remote updated" -ForegroundColor Green
} else {
    Write-Host "➕ Menambahkan remote 'origin'..." -ForegroundColor Cyan
    git remote add origin $GITHUB_URL
    Write-Host "✅ Remote added" -ForegroundColor Green
}

Write-Host ""

# ============================================================================
# STEP 4: Verifikasi Koneksi ke GitHub
# ============================================================================
Write-Host "[STEP 4] Verifikasi Koneksi ke GitHub..." -ForegroundColor Green

try {
    $testConnection = git ls-remote --heads $GITHUB_URL 2>&1
    if ($testConnection -match "Authentication") {
        Write-Host "❌ Autentikasi GitHub gagal" -ForegroundColor Red
        Write-Host "Setup GitHub token atau SSH key:" -ForegroundColor Yellow
        Write-Host "  - https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/creating-a-personal-access-token" -ForegroundColor Gray
        exit 1
    }
    Write-Host "✅ Koneksi ke GitHub berhasil" -ForegroundColor Green
} catch {
    Write-Host "⚠️  Tidak bisa verify koneksi (akan coba push)" -ForegroundColor Yellow
}

Write-Host ""

# ============================================================================
# STEP 5: Fetch Latest dari Remote
# ============================================================================
Write-Host "[STEP 5] Fetch Latest dari Remote..." -ForegroundColor Green

git fetch origin 2>$null
Write-Host "✅ Fetch complete" -ForegroundColor Green
Write-Host ""

# ============================================================================
# STEP 6: Push ke GitHub
# ============================================================================
Write-Host "[STEP 6] Push ke GitHub..." -ForegroundColor Green
Write-Host "Mengupload kode ke branch 'main'..." -ForegroundColor Cyan
Write-Host ""

git push -u origin main --force

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "  ✅ DEPLOY BERHASIL!" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "Repository GitHub Anda:" -ForegroundColor Green
    Write-Host "  🔗 $GITHUB_URL" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Langkah Selanjutnya:" -ForegroundColor Yellow
    Write-Host "  1. Verifikasi di: $GITHUB_URL" -ForegroundColor Gray
    Write-Host "  2. Update GitHub Pages settings jika ingin deploy frontend" -ForegroundColor Gray
    Write-Host "  3. Setup environment variables di platform deployment Anda" -ForegroundColor Gray
    Write-Host ""
} else {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Red
    Write-Host "  ❌ DEPLOY GAGAL" -ForegroundColor Red
    Write-Host "========================================" -ForegroundColor Red
    Write-Host ""
    Write-Host "Troubleshooting:" -ForegroundColor Yellow
    Write-Host "  1. Pastikan GitHub token/SSH key sudah setup" -ForegroundColor Gray
    Write-Host "  2. Cek internet connection" -ForegroundColor Gray
    Write-Host "  3. Verifikasi repository URL benar" -ForegroundColor Gray
    exit 1
}
