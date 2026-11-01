# ============================================================================
# Deploy PrioMed-Rec ke Public Platforms (Vercel, Railway, Netlify)
# ============================================================================

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Deploy PrioMed-Rec ke Platform Public" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Tampilkan opsi deployment
Write-Host "Pilih platform deployment:" -ForegroundColor Yellow
Write-Host ""
Write-Host "1. Vercel (Frontend) ⭐ Recommended" -ForegroundColor Green
Write-Host "2. Netlify (Frontend)" -ForegroundColor Green
Write-Host "3. GitHub Pages (Frontend)" -ForegroundColor Green
Write-Host "4. Railway (Backend) ⭐ Recommended" -ForegroundColor Cyan
Write-Host "5. Render (Backend)" -ForegroundColor Cyan
Write-Host "6. All of Above (Complete Setup)" -ForegroundColor Magenta
Write-Host "0. Exit" -ForegroundColor Red
Write-Host ""

$choice = Read-Host "Pilih opsi (0-6)"

# ============================================================================
# DEPLOYMENT FUNCTIONS
# ============================================================================

function Deploy-Vercel {
    Write-Host ""
    Write-Host "[VERCEL] Deploying Frontend..." -ForegroundColor Cyan
    
    # Check if Vercel CLI installed
    $vercelCmd = Get-Command vercel -ErrorAction SilentlyContinue
    if (-not $vercelCmd) {
        Write-Host "❌ Vercel CLI not installed" -ForegroundColor Red
        Write-Host "Installing Vercel CLI..." -ForegroundColor Yellow
        npm install -g vercel
    }
    
    Write-Host "📍 Navigate to frontend folder..." -ForegroundColor Green
    cd d:\Hacktiv8\priomed-rec\web
    
    Write-Host "🚀 Deploying to Vercel..." -ForegroundColor Green
    Write-Host "ℹ️  Browser akan membuka untuk login ke Vercel" -ForegroundColor Yellow
    Write-Host ""
    
    vercel --prod
    
    Write-Host ""
    Write-Host "✅ Vercel deployment complete!" -ForegroundColor Green
    Write-Host "Cek: https://vercel.com/dashboard" -ForegroundColor Cyan
}

function Deploy-Netlify {
    Write-Host ""
    Write-Host "[NETLIFY] Deploying Frontend..." -ForegroundColor Cyan
    
    # Build frontend
    Write-Host "🔨 Building frontend..." -ForegroundColor Green
    cd d:\Hacktiv8\priomed-rec\web
    npm run build
    
    if (-not $?) {
        Write-Host "❌ Build failed!" -ForegroundColor Red
        return
    }
    
    # Check if Netlify CLI installed
    $netlifyCmd = Get-Command netlify -ErrorAction SilentlyContinue
    if (-not $netlifyCmd) {
        Write-Host "Installing Netlify CLI..." -ForegroundColor Yellow
        npm install -g netlify-cli
    }
    
    Write-Host "🚀 Deploying to Netlify..." -ForegroundColor Green
    netlify deploy --prod --dir=dist
    
    Write-Host ""
    Write-Host "✅ Netlify deployment complete!" -ForegroundColor Green
    Write-Host "Cek: https://app.netlify.com" -ForegroundColor Cyan
}

function Deploy-GitHubPages {
    Write-Host ""
    Write-Host "[GITHUB PAGES] Deploying Frontend..." -ForegroundColor Cyan
    
    Write-Host "📋 Manual Steps untuk GitHub Pages:" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "1. Go to: https://github.com/azkastudying1-hub/PrioMed-Rec/settings/pages" -ForegroundColor Green
    Write-Host "2. Source: main branch" -ForegroundColor Green
    Write-Host "3. Folder: /web/dist" -ForegroundColor Green
    Write-Host "4. Save" -ForegroundColor Green
    Write-Host ""
    Write-Host "Then run:" -ForegroundColor Yellow
    Write-Host ""
    
    cd d:\Hacktiv8\priomed-rec
    
    # Install gh-pages
    Write-Host "Installing gh-pages..." -ForegroundColor Cyan
    cd web
    npm install --save-dev gh-pages
    
    Write-Host ""
    Write-Host "✅ gh-pages installed! Sekarang:" -ForegroundColor Green
    Write-Host ""
    Write-Host "1. Update package.json dengan:" -ForegroundColor Yellow
    Write-Host '   "homepage": "https://azkastudying1-hub.github.io/PrioMed-Rec"' -ForegroundColor Gray
    Write-Host '   "deploy": "gh-pages -d dist"' -ForegroundColor Gray
    Write-Host ""
    Write-Host "2. Run: npm run deploy" -ForegroundColor Yellow
    Write-Host ""
}

function Deploy-Railway {
    Write-Host ""
    Write-Host "[RAILWAY] Deploying Backend..." -ForegroundColor Cyan
    
    Write-Host "📋 Manual Steps untuk Railway:" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "1. Go to: https://railway.app/dashboard" -ForegroundColor Green
    Write-Host "2. Click 'New Project' → 'Deploy from GitHub repo'" -ForegroundColor Green
    Write-Host "3. Search & select: azkastudying1-hub/PrioMed-Rec" -ForegroundColor Green
    Write-Host "4. Railway auto-detects Python" -ForegroundColor Green
    Write-Host "5. Configure environment variables:" -ForegroundColor Green
    Write-Host "   - DATABASE_URL" -ForegroundColor Gray
    Write-Host "   - OPENAI_API_KEY" -ForegroundColor Gray
    Write-Host "   - GROQ_API_KEY" -ForegroundColor Gray
    Write-Host "   - FRONTEND_URL" -ForegroundColor Gray
    Write-Host "6. Deploy!" -ForegroundColor Green
    Write-Host ""
    Write-Host "✅ Railway will auto-deploy from GitHub!" -ForegroundColor Green
    Write-Host "Link: https://railway.app/dashboard" -ForegroundColor Cyan
}

function Deploy-Render {
    Write-Host ""
    Write-Host "[RENDER] Deploying Backend..." -ForegroundColor Cyan
    
    Write-Host "📋 Manual Steps untuk Render:" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "1. Go to: https://dashboard.render.com" -ForegroundColor Green
    Write-Host "2. Click 'New +' → 'Web Service'" -ForegroundColor Green
    Write-Host "3. Connect GitHub & select: azkastudying1-hub/PrioMed-Rec" -ForegroundColor Green
    Write-Host "4. Configure:" -ForegroundColor Green
    Write-Host "   Name: priomed-rec-api" -ForegroundColor Gray
    Write-Host "   Build Command: pip install -r requirements.txt" -ForegroundColor Gray
    Write-Host "   Start Command: uvicorn backend.src.main:app --host 0.0.0.0 --port `$PORT" -ForegroundColor Gray
    Write-Host "5. Add environment variables" -ForegroundColor Green
    Write-Host "6. Create Web Service" -ForegroundColor Green
    Write-Host ""
    Write-Host "✅ Render akan auto-deploy from GitHub!" -ForegroundColor Green
    Write-Host "Link: https://dashboard.render.com" -ForegroundColor Cyan
}

function Deploy-All {
    Write-Host ""
    Write-Host "[COMPLETE SETUP] Deploying Frontend & Backend..." -ForegroundColor Magenta
    Write-Host ""
    
    Write-Host "🚀 Recommended deployment configuration:" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Frontend:  Vercel ⭐" -ForegroundColor Green
    Write-Host "Backend:   Railway ⭐" -ForegroundColor Cyan
    Write-Host ""
    
    $setup = Read-Host "Lanjutkan dengan setup ini? (Y/n)"
    
    if ($setup -ne "n") {
        Write-Host ""
        Write-Host "1️⃣  Deploying Frontend ke Vercel..." -ForegroundColor Green
        Deploy-Vercel
        
        Write-Host ""
        Write-Host "2️⃣  Setting up Backend di Railway..." -ForegroundColor Cyan
        Deploy-Railway
        
        Write-Host ""
        Write-Host "========================================" -ForegroundColor Magenta
        Write-Host "✅ Setup Lengkap!" -ForegroundColor Magenta
        Write-Host "========================================" -ForegroundColor Magenta
        Write-Host ""
        Write-Host "✓ Frontend akan deployment otomatis saat Anda push ke GitHub" -ForegroundColor Green
        Write-Host "✓ Backend akan deployment otomatis di Railway" -ForegroundColor Cyan
        Write-Host ""
        Write-Host "Langkah Selanjutnya:" -ForegroundColor Yellow
        Write-Host "1. Configure environment variables di Railway" -ForegroundColor Gray
        Write-Host "2. Setup CORS di backend (lihat DEPLOY_GUIDE.md)" -ForegroundColor Gray
        Write-Host "3. Test aplikasi di production URLs" -ForegroundColor Gray
        Write-Host ""
    }
}

# ============================================================================
# EXECUTE CHOICE
# ============================================================================

switch ($choice) {
    "1" { Deploy-Vercel }
    "2" { Deploy-Netlify }
    "3" { Deploy-GitHubPages }
    "4" { Deploy-Railway }
    "5" { Deploy-Render }
    "6" { Deploy-All }
    "0" { 
        Write-Host "Exit." -ForegroundColor Yellow
        exit 0
    }
    default {
        Write-Host "❌ Invalid option" -ForegroundColor Red
        exit 1
    }
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "Script Selesai!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "📚 Documentation: DEPLOY_GUIDE.md" -ForegroundColor Cyan
Write-Host "🔗 GitHub Repository: https://github.com/azkastudying1-hub/PrioMed-Rec" -ForegroundColor Cyan
Write-Host ""
