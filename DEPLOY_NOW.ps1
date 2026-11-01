# ============================================================================
# QUICK DEPLOYMENT TO PRODUCTION
# Deploy Frontend (Vercel) + Backend (Railway)
# ============================================================================

Write-Host ""
Write-Host "========================================" -ForegroundColor Magenta
Write-Host "  PrioMed-Rec Production Deployment" -ForegroundColor Magenta
Write-Host "========================================" -ForegroundColor Magenta
Write-Host ""

# Check if Vercel CLI is installed
Write-Host "Checking for Vercel CLI..." -ForegroundColor Cyan
$vercelCmd = Get-Command vercel -ErrorAction SilentlyContinue

if (-not $vercelCmd) {
    Write-Host "Installing Vercel CLI (required for deployment)..." -ForegroundColor Yellow
    npm install -g vercel
    Write-Host "Vercel CLI installed!" -ForegroundColor Green
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  STEP 1: DEPLOY FRONTEND TO VERCEL" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""

Write-Host "Building React application..." -ForegroundColor Cyan
cd d:\Hacktiv8\priomed-rec\web

npm run build

if ($LASTEXITCODE -ne 0) {
    Write-Host "Build failed!" -ForegroundColor Red
    exit 1
}

Write-Host "Build complete!" -ForegroundColor Green
Write-Host ""
Write-Host "Now deploying to Vercel..." -ForegroundColor Cyan
Write-Host ""
Write-Host "IMPORTANT: Follow these steps in the Vercel prompt:" -ForegroundColor Yellow
Write-Host "  1. Login with your GitHub account"
Write-Host "  2. Choose 'Create a new project' if first time"
Write-Host "  3. Project name: PrioMed-Rec"
Write-Host "  4. Root directory: web"
Write-Host "  5. Let Vercel detect the framework (React)"
Write-Host "  6. Deploy!"
Write-Host ""

vercel --prod

Write-Host ""
Write-Host "Deployment started!" -ForegroundColor Green
Write-Host ""

# Ask for Vercel URL
$vercelUrl = Read-Host "Enter your Vercel URL (e.g., https://priomed-rec.vercel.app)"

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  STEP 2: SETUP BACKEND ON RAILWAY" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""

Write-Host "Railway setup (manual steps):" -ForegroundColor Cyan
Write-Host ""
Write-Host "1. Go to: https://railway.app/dashboard" -ForegroundColor Yellow
Write-Host "2. Click 'New Project' > 'Deploy from GitHub repo'"
Write-Host "3. Authorize GitHub if prompted"
Write-Host "4. Search: azkastudying1-hub/PrioMed-Rec"
Write-Host "5. Select and approve"
Write-Host ""
Write-Host "6. In Railway dashboard, go to Variables tab" -ForegroundColor Yellow
Write-Host "7. Add these environment variables:"
Write-Host ""
Write-Host "   LLM_PROVIDER = gemini" -ForegroundColor Gray
Write-Host "   LLM_API_KEY = your-api-key-here" -ForegroundColor Gray
Write-Host "   DATABASE_URL = sqlite:///data/priomed.db" -ForegroundColor Gray
Write-Host "   CORS_ALLOWED_ORIGINS = $vercelUrl,http://localhost:5173" -ForegroundColor Gray
Write-Host "   ENVIRONMENT = production" -ForegroundColor Gray
Write-Host "   DEBUG = False" -ForegroundColor Gray
Write-Host ""
Write-Host "8. Click 'Deploy' and wait 5-10 minutes" -ForegroundColor Yellow
Write-Host ""

$railwayUrl = Read-Host "Enter your Railway backend URL (e.g., https://priomed-rec-prod.railway.app)"

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  STEP 3: UPDATE CORS CONFIGURATION" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""

cd d:\Hacktiv8\priomed-rec

# Create frontend .env.production
Write-Host "Creating frontend environment file..." -ForegroundColor Cyan

$frontendEnv = @"
VITE_API_URL=$railwayUrl
VITE_APP_NAME=PrioMed-Rec
VITE_ENVIRONMENT=production
"@

$frontendEnv | Out-File "web\.env.production" -Encoding UTF8
Write-Host "Created web/.env.production" -ForegroundColor Green

# Create backend .env if doesn't exist
if (-not (Test-Path ".env")) {
    Write-Host "Creating backend environment file..." -ForegroundColor Cyan
    
    $backendEnv = @"
LLM_PROVIDER=gemini
LLM_API_KEY=your-gemini-api-key-here
JWT_SECRET_KEY=your-secret-key-here
DATABASE_URL=sqlite:///data/priomed.db
CORS_ALLOWED_ORIGINS=$vercelUrl,http://localhost:5173
ENVIRONMENT=production
DEBUG=False
FASTAPI_PORT=8000
"@
    
    $backendEnv | Out-File ".env" -Encoding UTF8
    Write-Host "Created .env" -ForegroundColor Green
}

Write-Host ""
Write-Host "Committing configuration changes..." -ForegroundColor Cyan
git add web\.env.production
git add .env 2>$null
git commit -m "Production deployment: Configure environment variables and CORS"
git push origin main

Write-Host "Pushed to GitHub!" -ForegroundColor Green

Write-Host ""
Write-Host "========================================" -ForegroundColor Magenta
Write-Host "  DEPLOYMENT COMPLETE!" -ForegroundColor Magenta
Write-Host "========================================" -ForegroundColor Magenta
Write-Host ""

Write-Host "Your Application URLs:" -ForegroundColor Cyan
Write-Host "  Frontend:  $vercelUrl" -ForegroundColor Green
Write-Host "  Backend:   $railwayUrl" -ForegroundColor Green
Write-Host "  GitHub:    https://github.com/azkastudying1-hub/PrioMed-Rec" -ForegroundColor Green
Write-Host ""

Write-Host "Next Steps:" -ForegroundColor Yellow
Write-Host "1. Open $vercelUrl in your browser"
Write-Host "2. Test the login and main features"
Write-Host "3. Check backend health at $railwayUrl/health"
Write-Host "4. View API documentation at $railwayUrl/docs"
Write-Host "5. Monitor deployments:"
Write-Host "   - Vercel: https://vercel.com/dashboard"
Write-Host "   - Railway: https://railway.app/dashboard"
Write-Host ""

Write-Host "Important Security Steps:" -ForegroundColor Yellow
Write-Host "1. Update LLM_API_KEY with real Gemini API key"
Write-Host "2. Update JWT_SECRET_KEY with a strong random value"
Write-Host "3. Add other LLM provider keys if needed"
Write-Host "4. Review CORS settings for your domain"
Write-Host ""

Write-Host "Success! Your app is in production now! 🚀" -ForegroundColor Green
Write-Host ""
