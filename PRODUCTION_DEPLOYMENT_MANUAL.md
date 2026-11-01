# 🚀 Production Deployment - Step by Step Manual Guide

## Status: Frontend Build SUCCESS ✅

Frontend build telah berhasil diselesaikan! Output:

```
dist/index.html                   1.30 kB │ gzip:   0.70 kB
dist/assets/index-CQiibg9e.css   94.65 kB │ gzip:  15.75 kB
dist/assets/index-CaJWA_nN.js   513.29 kB │ gzip: 144.66 kB
Build time: 20.97s
```

Aplikasi siap untuk di-deploy! Mari lanjutkan dengan langkah manual.

---

## STEP 1: Deploy Frontend ke Vercel

### Option A: Via Vercel Web Dashboard (Recommended)

1. **Go to:** https://vercel.com/dashboard

2. **Click:** "Add New..." → "Project"

3. **Import GitHub Repository:**
   - Click "Import Git Repository"
   - Search for: `PrioMed-Rec`
   - Select: `azkastudying1-hub/PrioMed-Rec`
   - Click "Import"

4. **Configure Project:**
   - Project Name: `PrioMed-Rec` (atau nama lain)
   - Framework Preset: `React`
   - Root Directory: `web`
   - Build Command: `npm run build` (auto-detected)
   - Output Directory: `dist` (auto-detected)

5. **Environment Variables (optional):**
   - Leave empty for now (bisa diset nanti)

6. **Click:** "Deploy"

7. **Wait:** ~3-5 minutes untuk build & deploy

8. **Get Your URL:** Vercel akan provide URL seperti:
   ```
   https://priomed-rec-xyz.vercel.app
   atau custom domain Anda
   ```

### Option B: Via Vercel CLI (Local)

```bash
# 1. Install Vercel CLI globally
npm install -g vercel

# 2. Go to web folder
cd web

# 3. Deploy
vercel --prod

# 4. Follow prompts:
#    - Link to GitHub account
#    - Existing project or new?
#    - Configure settings
#    - Deploy!

# 5. Vercel akan print URL deployment
```

### Option C: Automatic Deploy (Recommended for Continuous Deployment)

Jika Anda setup Vercel via GitHub integration:
- Setiap kali push ke branch `main` → auto-deploy
- Tidak perlu manual deploy lagi
- Vercel akan handle build dan deployment otomatis

---

## STEP 2: Deploy Backend ke Railway

### Setup Railway

1. **Go to:** https://railway.app/dashboard

2. **Create New Project:**
   - Click "New Project"
   - Select "Deploy from GitHub repo"

3. **Authorize GitHub:**
   - Click "Select Repository"
   - Search: `PrioMed-Rec`
   - Authorize access

4. **Railway Auto-Detects Python:**
   - Framework: Python
   - Root Directory: (leave empty)

5. **Configure Variables:**

   Click "Variables" tab dan tambahkan:

   ```env
   LLM_PROVIDER=gemini
   LLM_API_KEY=your-gemini-api-key-here
   JWT_SECRET_KEY=CHANGE_ME_generate_long_random_string
   JWT_REFRESH_SECRET_KEY=CHANGE_ME_generate_long_random_string
   DATABASE_URL=sqlite:///data/priomed.db
   CORS_ALLOWED_ORIGINS=https://priomed-rec-xyz.vercel.app,http://localhost:5173
   LANGFLOW_SUPERUSER=langflow-admin
   LANGFLOW_SUPERUSER_PASSWORD=CHANGE_ME_strong_password
   ENVIRONMENT=production
   DEBUG=False
   FASTAPI_HOST=0.0.0.0
   FASTAPI_PORT=$PORT
   ```

   **PENTING:** 
   - Replace `priomed-rec-xyz.vercel.app` dengan URL Vercel Anda yang actual
   - Generate strong JWT secrets: `python -c "import secrets; print(secrets.token_hex(32))"`
   - Add real LLM API keys

6. **Click "Deploy"**
   - Railway akan build & deploy application
   - Build takes ~5-10 minutes
   - Saat selesai, Railway akan provide URL seperti:
     ```
     https://priomed-rec-prod-abc.railway.app
     ```

7. **Monitor Deployment:**
   - Buka Railway dashboard
   - Check "Deployments" tab
   - View logs dalam "Logs" tab
   - Status akan shown di top

---

## STEP 3: Get Your URLs

Setelah deployment selesai:

```
Frontend URL:  https://priomed-rec-xyz.vercel.app
Backend URL:   https://priomed-rec-prod-abc.railway.app
GitHub Repo:   https://github.com/azkastudying1-hub/PrioMed-Rec
```

Catat kedua URLs ini untuk langkah selanjutnya.

---

## STEP 4: Configure CORS in Backend

Sekarang kita perlu update backend CORS setting dengan frontend URL.

### Local Update (untuk test sebelum push)

Edit: `backend/src/main.py`

Cari section CORS (biasanya di awal file):

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

Update menjadi:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://priomed-rec-xyz.vercel.app",  # YOUR VERCEL URL
        "http://localhost:5173",                # Keep for local dev
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### Push to GitHub

```bash
cd d:\Hacktiv8\priomed-rec
git add backend/src/main.py
git commit -m "Production: Update CORS with Vercel URL"
git push origin main
```

### Railway Auto-Redeploy

- Railway akan detect push
- Auto-build & deploy backend again
- Takes ~3-5 minutes

---

## STEP 5: Create Frontend Environment File

Create: `web/.env.production`

```env
VITE_API_URL=https://priomed-rec-prod-abc.railway.app
VITE_APP_NAME=PrioMed-Rec
VITE_ENVIRONMENT=production
```

Push ke GitHub:

```bash
git add web/.env.production
git commit -m "Production: Add frontend environment configuration"
git push origin main
```

Vercel akan auto-redeploy dengan new config.

---

## STEP 6: Verify Deployments

### Test Frontend

1. Open: `https://priomed-rec-xyz.vercel.app` in browser
2. Should see login page
3. Check browser console (F12) - should be no errors
4. Test responsive design (resize window)

### Test Backend

1. Open: `https://priomed-rec-prod-abc.railway.app/health`
   - Should see JSON response: `{"status": "ok"}`

2. Open: `https://priomed-rec-prod-abc.railway.app/docs`
   - Should see Swagger UI with all API endpoints
   - You can test endpoints here

### Test Integration

1. Go to frontend URL
2. Try to login (if authentication required)
3. Open DevTools (F12)
4. Go to Network tab
5. Perform action (create patient, analyze, etc.)
6. Should see network requests to `/api/...` 
7. Responses should be 200 (success) or 4xx (client error), not 5xx (server error)

### Check Logs

**Vercel Logs:**
1. Go to: https://vercel.com/dashboard
2. Select project: PrioMed-Rec
3. Click "Logs" tab
4. See all deployment events

**Railway Logs:**
1. Go to: https://railway.app/dashboard
2. Select project
3. Click "Logs" tab
4. See application output & errors in real-time

---

## STEP 7: Setup Custom Domain (Optional)

### Vercel Custom Domain

1. Go to: https://vercel.com/dashboard
2. Select project: PrioMed-Rec
3. Settings → Domains
4. Add your domain (e.g., priomed.com)
5. Update DNS records per Vercel instructions
6. Wait 24-48 hours for DNS propagation

### Railway Custom Domain

1. Go to: https://railway.app/dashboard
2. Select project
3. Settings → Custom Domain
4. Add domain
5. Update DNS records
6. Wait for DNS update

---

## STEP 8: Production Checklist

- [ ] Frontend deployed to Vercel
- [ ] Backend deployed to Railway
- [ ] Frontend URL accessible in browser
- [ ] Backend health endpoint responding (`/health`)
- [ ] Frontend can make API calls to backend
- [ ] CORS configured correctly (no CORS errors)
- [ ] Login/authentication working
- [ ] Main features tested
- [ ] No console errors in browser
- [ ] Logs monitored in Vercel & Railway dashboards
- [ ] Environment variables set in Railway
- [ ] LLM API keys configured
- [ ] JWT secret keys are strong & unique
- [ ] Database connection working
- [ ] Ready for user access

---

## STEP 9: Post-Deployment

### Add to .gitignore (if not already)

Pastikan file sensitif tidak di-push:

```gitignore
.env
.env.local
.env.*.local
.venv/
node_modules/
dist/
```

### Setup Monitoring (Optional but Recommended)

**Uptime Monitoring:**
- Go to: https://uptimerobot.com
- Add your frontend URL
- Get alerts if website goes down

**Error Tracking:**
- Go to: https://sentry.io
- Create account
- Get Sentry key
- Add to your app
- Get alerts for errors

**Analytics:**
- Go to: https://vercel.com/analytics
- View user statistics
- Traffic patterns
- Performance metrics

---

## STEP 10: Troubleshooting

### CORS Error in Frontend

Error: `Access to XMLHttpRequest from origin 'https://priomed-rec-xyz' blocked by CORS policy`

**Solution:**
1. Update `CORS_ALLOWED_ORIGINS` in Railway dashboard
2. Add your Vercel URL
3. Railway will auto-redeploy
4. Wait 2-3 minutes
5. Refresh browser and try again

### API Not Responding

Error: `Failed to fetch from backend`

**Check:**
1. Backend URL is correct in `.env.production`
2. Backend is deployed (check Railway logs)
3. No errors in Railway logs
4. Health endpoint responds: `https://your-backend/health`
5. Database is connected

### Build Failed

**Check:**
1. Vercel build logs
2. Railway build logs
3. All dependencies installed
4. No syntax errors
5. Environment variables set

### Database Connection Error

1. Check `DATABASE_URL` in Railway variables
2. SQLite database should auto-create
3. Check file permissions in Railway
4. View logs for details

---

## Performance Optimization (Optional)

### Frontend

- Vercel automatically optimizes with CDN
- Images are auto-optimized
- Code is minified & compressed
- Static files cached

### Backend

- Add caching for frequent queries
- Use database indexing
- Monitor performance in Railway
- Scale if needed

---

## Security Checklist

- [ ] JWT secret keys are strong (32+ chars)
- [ ] No secrets committed to GitHub
- [ ] LLM API keys hidden in Railway variables
- [ ] Database has strong password (if not SQLite)
- [ ] CORS only allows your frontend
- [ ] HTTPS enabled (automatic on Vercel & Railway)
- [ ] No debug mode in production (DEBUG=False)
- [ ] Rate limiting configured (optional)
- [ ] Input validation enabled
- [ ] Error messages don't expose sensitive info

---

## Summary

After completing all steps:

1. ✅ Frontend running on Vercel
2. ✅ Backend running on Railway
3. ✅ Application accessible to public
4. ✅ Auto-deploy on GitHub push
5. ✅ Monitoring setup
6. ✅ Secure configuration
7. ✅ Ready for users!

---

## Next Steps

1. Share frontend URL with team/users
2. Gather feedback
3. Monitor performance & errors
4. Deploy updates (push to GitHub → auto-deploy)
5. Scale if needed

---

## Support Links

- **Vercel:** https://vercel.com/docs
- **Railway:** https://docs.railway.app
- **FastAPI:** https://fastapi.tiangolo.com
- **React/Vite:** https://vitejs.dev
- **GitHub:** https://docs.github.com

---

**Status:** ✅ Ready for Production
**Last Updated:** November 1, 2026
