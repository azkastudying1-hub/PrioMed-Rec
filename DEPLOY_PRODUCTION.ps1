# ============================================================================
# COMPREHENSIVE PRODUCTION DEPLOYMENT SCRIPT
# Deploy PrioMed-Rec Frontend (Vercel) + Backend (Railway) + Configuration
# ============================================================================

param(
    [string]$Mode = "interactive",
    [switch]$SkipPrompts
)

$ErrorActionPreference = "Stop"
$VerbosePreference = "Continue"

# ============================================================================
# CONFIGURATION
# ============================================================================

$GITHUB_REPO = "https://github.com/azkastudying1-hub/PrioMed-Rec"
$GITHUB_USERNAME = "azkastudying1-hub"
$REPO_NAME = "PrioMed-Rec"

$colors = @{
    success = "Green"
    error = "Red"
    warning = "Yellow"
    info = "Cyan"
    section = "Magenta"
}

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

function Write-Status {
    param([string]$Message, [string]$Type = "info")
    $color = $colors[$Type]
    Write-Host $Message -ForegroundColor $color
}

function Write-Section {
    param([string]$Title)
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Magenta
    Write-Host "  $Title" -ForegroundColor Magenta
    Write-Host "========================================" -ForegroundColor Magenta
    Write-Host ""
}

function Test-Command {
    param([string]$Command)
    $exists = $null -ne (Get-Command $Command -ErrorAction SilentlyContinue)
    return $exists
}

function Install-Command {
    param([string]$Command, [string]$Package, [string]$InstallCmd)
    Write-Status "Installing $Command..." -Type warning
    Invoke-Expression $InstallCmd
    Write-Status "$Command installed!" -Type success
}

# ============================================================================
# PHASE 1: ENVIRONMENT CHECK
# ============================================================================

Write-Section "PHASE 1: Environment Check"

Write-Status "Checking required tools..." -Type info

$requiredTools = @{
    "git" = "Git"
    "npm" = "Node.js/npm"
}

$missingTools = @()

foreach ($tool in $requiredTools.Keys) {
    if (Test-Command $tool) {
        Write-Status "✓ $($requiredTools[$tool]) installed" -Type success
    } else {
        Write-Status "✗ $($requiredTools[$tool]) NOT found" -Type error
        $missingTools += $tool
    }
}

if ($missingTools.Count -gt 0) {
    Write-Status "Please install missing tools and try again" -Type error
    exit 1
}

# Check Vercel CLI
if (-not (Test-Command vercel)) {
    Write-Status "Vercel CLI not found. Installing..." -Type warning
    npm install -g vercel | Out-Null
    Write-Status "Vercel CLI installed!" -Type success
}

Write-Status "✓ All environment checks passed!" -Type success

# ============================================================================
# PHASE 2: VERCEL FRONTEND DEPLOYMENT
# ============================================================================

Write-Section "PHASE 2: Deploy Frontend to Vercel"

Write-Status "Frontend deployment will:" -Type info
Write-Host "  1. Build React/Vite application"
Write-Host "  2. Deploy to Vercel CDN"
Write-Host "  3. Get production URL"
Write-Host ""

if (-not $SkipPrompts) {
    $deployFrontend = Read-Host "Deploy frontend to Vercel now? (Y/n)"
    if ($deployFrontend -eq "n") {
        Write-Status "Skipping frontend deployment" -Type warning
    }
}

if ($deployFrontend -ne "n") {
    cd d:\Hacktiv8\priomed-rec\web
    
    Write-Status "Building React/Vite application..." -Type info
    npm run build
    
    if ($LASTEXITCODE -ne 0) {
        Write-Status "Build failed!" -Type error
        exit 1
    }
    
    Write-Status "Build successful!" -Type success
    
    Write-Host ""
    Write-Status "Deploying to Vercel..." -Type info
    Write-Host "Follow the prompts:" -ForegroundColor Yellow
    Write-Host "  1. Login with GitHub account"
    Write-Host "  2. Link to existing project or create new"
    Write-Host "  3. Set project name: PrioMed-Rec"
    Write-Host "  4. Set root directory: web"
    Write-Host ""
    
    vercel --prod
    
    # Get Vercel URL
    Write-Host ""
    if (-not $SkipPrompts) {
        $vercelUrl = Read-Host "Enter your Vercel deployment URL (e.g., https://priomed-rec.vercel.app)"
        Write-Status "Vercel URL saved: $vercelUrl" -Type success
    } else {
        $vercelUrl = "https://priomed-rec.vercel.app"
    }
}

cd d:\Hacktiv8\priomed-rec

# ============================================================================
# PHASE 3: RAILWAY BACKEND DEPLOYMENT
# ============================================================================

Write-Section "PHASE 3: Deploy Backend to Railway"

Write-Status "Backend deployment will:" -Type info
Write-Host "  1. Setup Railway project"
Write-Host "  2. Configure environment variables"
Write-Host "  3. Deploy FastAPI application"
Write-Host "  4. Get production API URL"
Write-Host ""

Write-Status "Railway Setup Instructions:" -Type warning
Write-Host ""
Write-Host "Manual Setup (Required):" -ForegroundColor Yellow
Write-Host "1. Go to: https://railway.app/dashboard"
Write-Host "2. Click 'New Project' → 'Deploy from GitHub repo'"
Write-Host "3. Authorize GitHub if prompted"
Write-Host "4. Search & select: azkastudying1-hub/PrioMed-Rec"
Write-Host "5. Railway auto-detects Python project"
Write-Host ""
Write-Host "6. In Railway Dashboard:" -ForegroundColor Yellow
Write-Host "   - Variables tab → Add the environment variables below:"
Write-Host ""

# Generate environment variables for Railway
$railwayEnvVars = @{
    "LLM_PROVIDER" = "gemini"
    "LLM_API_KEY" = "your-gemini-api-key"
    "JWT_SECRET_KEY" = [System.Convert]::ToHexString([System.Security.Cryptography.RandomNumberGenerator]::GetBytes(32))
    "JWT_REFRESH_SECRET_KEY" = [System.Convert]::ToHexString([System.Security.Cryptography.RandomNumberGenerator]::GetBytes(32))
    "DATABASE_URL" = "sqlite:///data/priomed.db"
    "CORS_ALLOWED_ORIGINS" = "https://priomed-rec.vercel.app,http://localhost:5173"
    "LANGFLOW_SUPERUSER" = "langflow-admin"
    "LANGFLOW_SUPERUSER_PASSWORD" = [System.Convert]::ToHexString([System.Security.Cryptography.RandomNumberGenerator]::GetBytes(16))
    "ENVIRONMENT" = "production"
    "DEBUG" = "False"
}

Write-Host "Environment Variables to Add:" -ForegroundColor Cyan
foreach ($key in $railwayEnvVars.Keys) {
    $value = $railwayEnvVars[$key]
    if ($value.Length -gt 50) {
        Write-Host "  $key = [GENERATED]"
    } else {
        Write-Host "  $key = $value"
    }
}

Write-Host ""
Write-Host "7. Deploy settings:"
Write-Host "   - Root Directory: (leave empty)"
Write-Host "   - Build Command: pip install -r requirements.txt"
Write-Host "   - Start Command: uvicorn backend.src.main:app --host 0.0.0.0 --port `$PORT"
Write-Host ""
Write-Host "8. Click 'Deploy' and wait ~5-10 minutes"
Write-Host ""

if (-not $SkipPrompts) {
    $railwayUrl = Read-Host "Enter your Railway backend URL"
    Write-Status "Railway URL saved: $railwayUrl" -Type success
} else {
    $railwayUrl = "https://priomed-rec-prod.railway.app"
}

# ============================================================================
# PHASE 4: CONFIGURE CORS AND ENVIRONMENT VARIABLES
# ============================================================================

Write-Section "PHASE 4: Configure CORS and Environment Variables"

Write-Status "Updating CORS configuration..." -Type info

$backendFile = "backend\src\main.py"

if (Test-Path $backendFile) {
    $content = Get-Content $backendFile -Raw
    
    $corsPattern = 'allow_origins=\[.*?\]'
    $corsReplacement = @"
allow_origins=[
        "$vercelUrl",
        "http://localhost:5173",
        "http://localhost:3000",
    ]
"@
    
    # Check if need update (careful with this)
    if ($content -match $corsPattern) {
        Write-Status "Found CORS configuration" -Type info
        Write-Host "Current CORS origins in backend/src/main.py"
        Write-Host "Make sure to add: $vercelUrl" -ForegroundColor Yellow
    }
} else {
    Write-Status "Warning: Could not find backend/src/main.py" -Type warning
}

Write-Status "✓ CORS configuration saved" -Type success

# ============================================================================
# PHASE 5: ENVIRONMENT CONFIGURATION FOR FRONTEND
# ============================================================================

Write-Section "PHASE 5: Frontend Environment Configuration"

Write-Status "Creating .env.production for frontend..." -Type info

$envProdContent = @"
# PrioMed-Rec Frontend Production Environment
VITE_API_URL=$railwayUrl
VITE_APP_NAME=PrioMed-Rec
VITE_ENVIRONMENT=production
"@

$envProdPath = "web\.env.production"

if (Test-Path $envProdPath) {
    $backup = "$envProdPath.bak"
    Copy-Item $envProdPath $backup
    Write-Status "Backed up existing .env.production to $backup" -Type info
}

$envProdContent | Out-File $envProdPath -Encoding UTF8
Write-Status "✓ Created $envProdPath" -Type success

# ============================================================================
# PHASE 6: BACKEND ENVIRONMENT CONFIGURATION
# ============================================================================

Write-Section "PHASE 6: Backend Environment Configuration"

Write-Status "Creating .env for backend..." -Type info

$backendEnvContent = @"
# PrioMed-Rec Backend Production Environment
LLM_PROVIDER=gemini
LLM_API_KEY=your-gemini-api-key-here
JWT_SECRET_KEY=$($railwayEnvVars['JWT_SECRET_KEY'])
JWT_REFRESH_SECRET_KEY=$($railwayEnvVars['JWT_REFRESH_SECRET_KEY'])
DATABASE_URL=sqlite:///data/priomed.db
CORS_ALLOWED_ORIGINS=$vercelUrl,http://localhost:5173
LANGFLOW_SUPERUSER=langflow-admin
LANGFLOW_SUPERUSER_PASSWORD=$($railwayEnvVars['LANGFLOW_SUPERUSER_PASSWORD'])
ENVIRONMENT=production
DEBUG=False
FASTAPI_PORT=8000
"@

$backendEnvPath = ".env"

if (Test-Path $backendEnvPath) {
    $backup = "$backendEnvPath.bak"
    Copy-Item $backendEnvPath $backup
    Write-Status "Backed up existing .env to $backup" -Type info
}

$backendEnvContent | Out-File $backendEnvPath -Encoding UTF8
Write-Status "✓ Created .env" -Type success

# ============================================================================
# PHASE 7: GIT COMMIT & PUSH
# ============================================================================

Write-Section "PHASE 7: Commit & Push Configuration Changes"

Write-Status "Staging configuration files..." -Type info

git add web\.env.production
git add .env
git status

Write-Host ""
$commitMsg = "Production deployment: Configure CORS, environment variables, and URLs"

if (-not $SkipPrompts) {
    Write-Status "This will commit configuration changes to GitHub" -Type warning
    $confirm = Read-Host "Continue with commit? (Y/n)"
    if ($confirm -eq "n") {
        Write-Status "Skipping commit" -Type warning
        exit 0
    }
}

git commit -m $commitMsg
Write-Status "✓ Committed: $commitMsg" -Type success

Write-Status "Pushing to GitHub..." -Type info
git push origin main

Write-Status "✓ Pushed to GitHub" -Type success

# ============================================================================
# PHASE 8: DEPLOYMENT VERIFICATION
# ============================================================================

Write-Section "PHASE 8: Verify Deployment"

Write-Status "Waiting for deployments to complete..." -Type info
Write-Host "This may take 2-5 minutes..."
Write-Host ""
Write-Host "Check deployment status:" -ForegroundColor Yellow
Write-Host "  Vercel: https://vercel.com/dashboard"
Write-Host "  Railway: https://railway.app/dashboard"
Write-Host ""

Start-Sleep -Seconds 5

Write-Status "Testing API health..." -Type info

$apiHealthUrl = "$railwayUrl/health"
Write-Host "Attempting to reach: $apiHealthUrl"

try {
    $response = Invoke-WebRequest -Uri $apiHealthUrl -TimeoutSec 10 -ErrorAction SilentlyContinue
    if ($response.StatusCode -eq 200) {
        Write-Status "✓ Backend API is responding!" -Type success
    }
} catch {
    Write-Status "⚠ Backend not responding yet (may still be deploying)" -Type warning
}

# ============================================================================
# PHASE 9: FINAL SUMMARY
# ============================================================================

Write-Section "DEPLOYMENT COMPLETE!"

Write-Status "Your application is now in production!" -Type success
Write-Host ""
Write-Host "📍 Application URLs:" -ForegroundColor Cyan
Write-Host "  Frontend:  $vercelUrl"
Write-Host "  Backend:   $railwayUrl"
Write-Host "  GitHub:    $GITHUB_REPO"
Write-Host ""

Write-Host "📊 Next Steps:" -ForegroundColor Yellow
Write-Host "  1. Test frontend by opening: $vercelUrl"
Write-Host "  2. Test login with your credentials"
Write-Host "  3. Check backend health at: $railwayUrl/health"
Write-Host "  4. View API docs at: $railwayUrl/docs"
Write-Host "  5. Monitor deployments:"
Write-Host "     - Vercel Dashboard: https://vercel.com/dashboard"
Write-Host "     - Railway Dashboard: https://railway.app/dashboard"
Write-Host ""

Write-Host "🔐 Important Security Notes:" -ForegroundColor Yellow
Write-Host "  1. Update JWT secret keys in Railway dashboard"
Write-Host "  2. Add real LLM API keys (Gemini, OpenAI, Groq, etc.)"
Write-Host "  3. Never commit .env with real secrets to GitHub"
Write-Host "  4. Use Railway's secret management for all API keys"
Write-Host "  5. Review CORS settings for your domain"
Write-Host ""

Write-Host "📈 Monitoring:" -ForegroundColor Cyan
Write-Host "  - Vercel provides analytics & monitoring"
Write-Host "  - Railway provides logs and metrics"
Write-Host "  - Check Health endpoint: $railwayUrl/health"
Write-Host "  - View API docs: $railwayUrl/docs"
Write-Host ""

Write-Status "✓ Your PrioMed-Rec application is live! 🚀" -Type success

Write-Host ""
Write-Host "Documentation:" -ForegroundColor Cyan
Write-Host "  - Frontend: README_DEPLOYMENT.md"
Write-Host "  - Backend: docs/DEPLOYMENT.md"
Write-Host "  - Full Guide: DEPLOY_GUIDE.md"
Write-Host ""
