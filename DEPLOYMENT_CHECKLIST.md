# ✅ PrioMed-Rec Deployment Checklist

## 🎯 Phase 1: GitHub Upload ✅ COMPLETED

- [x] Commit semua perubahan lokal
- [x] Configure remote GitHub (`origin`)
- [x] Push ke repository https://github.com/azkastudying1-hub/PrioMed-Rec
- [x] Verify push berhasil (434 files uploaded)
- [x] Repository publicly accessible

**Status:** ✅ DONE

---

## 🚀 Phase 2: Frontend Deployment ke Public

### Option A: Vercel (⭐ Recommended)

- [ ] Install Vercel CLI: `npm install -g vercel`
- [ ] Run: `cd web && vercel --prod`
- [ ] Connect dengan GitHub account
- [ ] Follow Vercel setup wizard
- [ ] Vercel auto-deploy setiap push ke main branch
- [ ] Frontend URL: `https://priomed-rec.vercel.app` (atau custom domain)
- [ ] Test responsive design di mobile & desktop
- [ ] Verify environment variables di Vercel dashboard

**Estimated Time:** 5-10 minutes

**Vercel Dashboard:** https://vercel.com/dashboard

---

### Option B: Netlify

- [ ] Build frontend locally: `cd web && npm run build`
- [ ] Install Netlify CLI: `npm install -g netlify-cli`
- [ ] Run: `netlify deploy --prod --dir=dist`
- [ ] Connect dengan GitHub untuk auto-deploy
- [ ] Setup environment variables di Netlify
- [ ] Frontend URL: `https://[sitename].netlify.app`
- [ ] Enable auto-deploy from main branch

**Estimated Time:** 5-10 minutes

**Netlify Dashboard:** https://app.netlify.com

---

### Option C: GitHub Pages

- [ ] Go to repository settings: https://github.com/azkastudying1-hub/PrioMed-Rec/settings/pages
- [ ] Source: Deploy from a branch
- [ ] Branch: `main` / Folder: `/web/dist`
- [ ] Install gh-pages: `cd web && npm install --save-dev gh-pages`
- [ ] Update `package.json`:
  ```json
  {
    "homepage": "https://azkastudying1-hub.github.io/PrioMed-Rec",
    "scripts": {
      "deploy": "gh-pages -d dist"
    }
  }
  ```
- [ ] Run: `npm run deploy`
- [ ] Frontend URL: `https://azkastudying1-hub.github.io/PrioMed-Rec`
- [ ] Wait ~2 minutes untuk deploy selesai

**Estimated Time:** 10-15 minutes

**GitHub Pages:** https://github.com/azkastudying1-hub/PrioMed-Rec/pages

---

## 🔧 Phase 3: Backend Deployment ke Public

### Option A: Railway (⭐ Recommended)

- [ ] Go to https://railway.app
- [ ] Create new project
- [ ] Select: Deploy from GitHub repo
- [ ] Choose: `azkastudying1-hub/PrioMed-Rec`
- [ ] Railway auto-detects Python project
- [ ] Configure environment variables:
  - [ ] `DATABASE_URL` (jika ada database)
  - [ ] `OPENAI_API_KEY`
  - [ ] `GROQ_API_KEY`
  - [ ] `GEMINI_API_KEY` (jika ada)
  - [ ] `FRONTEND_URL` (untuk CORS)
  - [ ] `ENVIRONMENT=production`
  - [ ] `DEBUG=False`
- [ ] Set Python version to 3.10
- [ ] Railway auto-deploy setiap push
- [ ] Backend URL: `https://priomed-rec-prod.railway.app`
- [ ] Test API di `/docs` endpoint
- [ ] Monitor logs di Railway dashboard

**Estimated Time:** 10-15 minutes

**Railway Dashboard:** https://railway.app/dashboard

---

### Option B: Render

- [ ] Go to https://dashboard.render.com
- [ ] Create new Web Service
- [ ] Connect GitHub & select: `azkastudying1-hub/PrioMed-Rec`
- [ ] Configure:
  - Name: `priomed-rec-api`
  - Build Command: `pip install -r requirements.txt`
  - Start Command: `uvicorn backend.src.main:app --host 0.0.0.0 --port $PORT`
- [ ] Add environment variables (same as Railway)
- [ ] Create Web Service
- [ ] Backend URL: `https://priomed-rec-api.onrender.com`
- [ ] Test API functionality

**Estimated Time:** 15-20 minutes

**Render Dashboard:** https://dashboard.render.com

---

### Option C: PythonAnywhere

- [ ] Go to https://pythonanywhere.com
- [ ] Upload via Git: `git clone https://github.com/azkastudying1-hub/PrioMed-Rec.git`
- [ ] Create virtual environment
- [ ] Install dependencies: `pip install -r requirements.txt`
- [ ] Configure WSGI file untuk FastAPI
- [ ] Setup environment variables
- [ ] Backend URL: `https://[username].pythonanywhere.com`
- [ ] Test endpoints

**Estimated Time:** 20-30 minutes

**PythonAnywhere:** https://pythonanywhere.com

---

## 🔗 Phase 4: Integration & CORS Configuration

- [ ] Get frontend URL dari deployment (Vercel/Netlify/GitHub Pages)
- [ ] Get backend URL dari deployment (Railway/Render)
- [ ] Update `backend/src/main.py` CORS settings:
  ```python
  app.add_middleware(
      CORSMiddleware,
      allow_origins=[
          "https://priomed-rec.vercel.app",      # Frontend URL
          "https://azkastudying1-hub.github.io",  # GitHub Pages
          "http://localhost:3000",                # Local dev
      ],
      allow_credentials=True,
      allow_methods=["*"],
      allow_headers=["*"],
  )
  ```
- [ ] Update frontend API URL di `web/.env.production`:
  ```
  VITE_API_URL=https://priomed-rec-prod.railway.app
  ```
- [ ] Commit & push perubahan
- [ ] Wait untuk auto-deploy di platform deployment
- [ ] Test API calls dari frontend

---

## 🧪 Phase 5: Testing & Verification

### Frontend Testing
- [ ] Open production URL di browser
- [ ] Test login functionality
- [ ] Test dashboard loading
- [ ] Test API calls (network tab di DevTools)
- [ ] Test responsive design (mobile, tablet, desktop)
- [ ] Check console untuk errors
- [ ] Test semua main features

### Backend Testing
- [ ] Buka `[backend-url]/docs` (Swagger UI)
- [ ] Test semua endpoints di Swagger
- [ ] Check status code & responses
- [ ] Test error handling
- [ ] Monitor backend logs

### Integration Testing
- [ ] Login dari frontend
- [ ] Create/read/update data via frontend
- [ ] Verify data saved di backend database
- [ ] Test file uploads (jika ada)
- [ ] Test real-time updates (jika ada)

---

## 📊 Phase 6: Monitoring & Maintenance

- [ ] Setup error tracking (Sentry, Rollbar)
- [ ] Setup uptime monitoring (UptimeRobot, Pingdom)
- [ ] Setup analytics (Google Analytics, Plausible)
- [ ] Configure email alerts untuk critical errors
- [ ] Setup database backups
- [ ] Document API endpoints
- [ ] Create runbook untuk troubleshooting

### Monitoring URLs
- [ ] Vercel Dashboard: https://vercel.com/dashboard
- [ ] Railway Dashboard: https://railway.app/dashboard
- [ ] GitHub Repository: https://github.com/azkastudying1-hub/PrioMed-Rec

---

## 🛠️ Phase 7: Production Configuration

- [ ] Enable HTTPS (auto untuk Vercel/Railway)
- [ ] Setup custom domain (optional)
- [ ] Configure DNS records (jika custom domain)
- [ ] Setup SSL certificate (auto untuk hosting modern)
- [ ] Configure security headers
- [ ] Setup rate limiting di backend
- [ ] Enable caching di frontend
- [ ] Configure CDN (jika perlu)

---

## 📝 Environment Variables Checklist

### Backend (Railway/Render)
```env
DATABASE_URL=                    # [ ] Set
OPENAI_API_KEY=                  # [ ] Set (jika menggunakan OpenAI)
GROQ_API_KEY=                    # [ ] Set (jika menggunakan Groq)
GEMINI_API_KEY=                  # [ ] Set (jika menggunakan Gemini)
FRONTEND_URL=                    # [ ] Set (URL frontend Anda)
ENVIRONMENT=production           # [ ] Set to "production"
DEBUG=False                      # [ ] Set to False
CORS_ORIGINS=*                   # [ ] Or specific origins
```

### Frontend (.env.production di web/)
```env
VITE_API_URL=                    # [ ] Set backend URL
VITE_APP_NAME=PrioMed-Rec       # [ ] Optional
```

---

## 🎯 Quick Deploy Commands

### Frontend
```bash
# Vercel
cd web
npm install -g vercel
vercel --prod

# Netlify
npm run build
netlify deploy --prod --dir=dist

# GitHub Pages
npm install --save-dev gh-pages
npm run deploy
```

### Backend
```bash
# Railway (manual di dashboard)
# Render (manual di dashboard)

# PythonAnywhere
git clone https://github.com/azkastudying1-hub/PrioMed-Rec.git
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

---

## ✅ Success Criteria

- [ ] Frontend accessible di public URL
- [ ] Backend API accessible di public URL
- [ ] Frontend can make API calls to backend
- [ ] Login functionality works
- [ ] All main features functional
- [ ] No console errors
- [ ] Mobile responsive
- [ ] Monitoring setup
- [ ] Documentation updated
- [ ] Backup strategy in place

---

## 📞 Troubleshooting

| Issue | Solution |
|-------|----------|
| CORS Error | Update CORS settings di backend + redeploy |
| API not responding | Check backend deployment status & logs |
| Frontend can't load | Check frontend deployment & network |
| Environment variables missing | Add ke platform dashboard |
| Database connection error | Verify DATABASE_URL & network access |
| Deployment fails | Check build logs di platform dashboard |

---

## 📚 Useful Links

- **GitHub Repository:** https://github.com/azkastudying1-hub/PrioMed-Rec
- **Vercel Docs:** https://vercel.com/docs
- **Railway Docs:** https://docs.railway.app
- **Render Docs:** https://render.com/docs
- **FastAPI Docs:** https://fastapi.tiangolo.com
- **Vite Docs:** https://vitejs.dev

---

## 📋 Deployment Status

| Component | Platform | Status | URL |
|-----------|----------|--------|-----|
| Frontend | ☐ Vercel / ☐ Netlify / ☐ GitHub Pages | ☐ Pending | |
| Backend | ☐ Railway / ☐ Render / ☐ PythonAnywhere | ☐ Pending | |
| Database | ☐ | ☐ Pending | |
| Monitoring | ☐ | ☐ Pending | |

---

## 🎉 Final Checklist

- [ ] All deployment phases completed
- [ ] All testing passed
- [ ] Monitoring active
- [ ] Documentation updated
- [ ] Team notified of public URL
- [ ] Ready for user access

---

**Last Updated:** November 1, 2026  
**Status:** Ready for deployment  
**Next Action:** Choose frontend & backend platform & deploy

Untuk bantuan lebih lanjut, lihat: `DEPLOY_GUIDE.md`
