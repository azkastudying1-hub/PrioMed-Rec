# 🚀 PrioMed-Rec Deployment Guide

## 📍 Current Status

✅ **Code sudah di-upload ke GitHub!**

- Repository: https://github.com/azkastudying1-hub/PrioMed-Rec
- Status: Public (dapat diakses oleh semua)
- Files: 434 uploaded
- Branch: main

---

## 🎯 Apa Langkah Selanjutnya?

Sekarang aplikasi perlu di-**deploy ke platform publik** agar dapat diakses oleh user secara online.

Ada 2 bagian:

1. **Frontend** (React/Vite) → Vercel, Netlify, atau GitHub Pages
2. **Backend** (FastAPI) → Railway, Render, atau PythonAnywhere

---

## ⚡ Quick Start (Rekomendasi)

### Frontend ke Vercel (5 menit)

```powershell
# 1. Install Vercel CLI
npm install -g vercel

# 2. Deploy
cd d:\Hacktiv8\priomed-rec\web
vercel --prod

# 3. Follow prompts dan login dengan GitHub
# 4. Done! Vercel akan auto-deploy setiap kali Anda push
```

**Hasil:** URL seperti `https://priomed-rec.vercel.app`

---

### Backend ke Railway (10 menit)

1. Go to https://railway.app
2. Click "New Project" → "Deploy from GitHub repo"
3. Search & select: `azkastudying1-hub/PrioMed-Rec`
4. Railway auto-detects Python project
5. Add environment variables (API keys, database URL, etc.)
6. Deploy!

**Hasil:** URL seperti `https://priomed-rec-prod.railway.app`

---

## 📋 Deployment Options

### Frontend
| Platform | Pros | Cons | Setup Time |
|----------|------|------|-----------|
| **Vercel** ⭐ | Auto-deploy dari GitHub, fast, free | - | 5 min |
| **Netlify** | Easy drag-drop, free tier | Slightly slower | 10 min |
| **GitHub Pages** | No extra account | Limited features | 15 min |

### Backend
| Platform | Pros | Cons | Setup Time |
|----------|------|------|-----------|
| **Railway** ⭐ | Auto-deploy, generous free tier | - | 10 min |
| **Render** | Auto-deploy, free tier | Slower spin-up | 15 min |
| **PythonAnywhere** | Traditional hosting | Manual deploy | 20 min |

---

## 🛠️ Scripts Tersedia

### 1. Deploy Script (Run Deployment)

```powershell
.\DEPLOY_TO_GITHUB.ps1
```

*Sudah done! Ini untuk push ke GitHub.*

### 2. Public Deploy Script (Coming Soon)

```powershell
.\DEPLOY_PUBLIC.ps1
```

*Script interaktif untuk deploy ke Vercel, Railway, etc.*

### 3. Dokumentasi Lengkap

- `DEPLOY_GUIDE.md` - Panduan detail
- `DEPLOYMENT_CHECKLIST.md` - Checklist lengkap
- `README_DEPLOYMENT.md` - File ini

---

## 🔐 Environment Variables yang Diperlukan

### Backend (Railway/Render)

```env
# Database (jika ada)
DATABASE_URL=postgresql://user:password@host/dbname

# LLM APIs
OPENAI_API_KEY=sk-...
GROQ_API_KEY=gsk-...
GEMINI_API_KEY=...

# Frontend URL (untuk CORS)
FRONTEND_URL=https://priomed-rec.vercel.app

# App Config
ENVIRONMENT=production
DEBUG=False
```

### Frontend (.env.production)

```env
VITE_API_URL=https://priomed-rec-prod.railway.app
```

---

## 📱 Frontend Deployment Details

### Vercel (Recommended)

**Keuntungan:**
- ✅ Automatic deploy dari GitHub
- ✅ Very fast (CDN global)
- ✅ Free tier generous
- ✅ Great dashboard

**Steps:**

1. Install Vercel CLI:
   ```powershell
   npm install -g vercel
   ```

2. Deploy:
   ```powershell
   cd web
   vercel --prod
   ```

3. Follow prompts untuk login & authorize GitHub

4. Selesai! Vercel akan auto-deploy setiap push ke main branch

**Dashboard:** https://vercel.com/dashboard

**Custom Domain:**
- Di Vercel dashboard, settings → domains
- Tambahkan custom domain (e.g., priomed.dev)
- Update DNS records

---

### Netlify

**Steps:**

1. Build frontend:
   ```powershell
   cd web
   npm run build
   ```

2. Install Netlify CLI:
   ```powershell
   npm install -g netlify-cli
   ```

3. Deploy:
   ```powershell
   netlify deploy --prod --dir=dist
   ```

4. Authorize GitHub untuk auto-deploy

**Dashboard:** https://app.netlify.com

---

### GitHub Pages

**Steps:**

1. Update `package.json` di folder web/:
   ```json
   {
     "homepage": "https://azkastudying1-hub.github.io/PrioMed-Rec",
     "scripts": {
       "deploy": "gh-pages -d dist"
     }
   }
   ```

2. Install gh-pages:
   ```powershell
   cd web
   npm install --save-dev gh-pages
   ```

3. Deploy:
   ```powershell
   npm run deploy
   ```

4. Go to repo settings → Pages dan enable

**URL:** https://azkastudying1-hub.github.io/PrioMed-Rec

---

## 🔧 Backend Deployment Details

### Railway (Recommended)

**Keuntungan:**
- ✅ Automatic deploy dari GitHub
- ✅ Free tier with $5/month credit
- ✅ Good for Python/FastAPI
- ✅ Simple UI

**Steps:**

1. Go to https://railway.app
2. Create new project
3. Select "Deploy from GitHub repo"
4. Search & select `azkastudying1-hub/PrioMed-Rec`
5. Railway auto-detects Python
6. Add environment variables
7. Deploy!

**URL Format:** `https://[project-name].railway.app`

**Add Environment Variables:**
- In Railway dashboard
- Under your project → Variables
- Add one by one (API keys, DATABASE_URL, etc.)

**Monitor Logs:**
- Dashboard → Logs tab
- Real-time application logs

---

### Render

**Keuntungan:**
- ✅ Automatic deploy
- ✅ Free tier
- ✅ Easy setup

**Steps:**

1. Go to https://dashboard.render.com
2. Create new → Web Service
3. Connect GitHub & select repo
4. Configure:
   ```
   Name: priomed-rec-api
   Build Command: pip install -r requirements.txt
   Start Command: uvicorn backend.src.main:app --host 0.0.0.0 --port $PORT
   ```
5. Add environment variables
6. Create service

**URL Format:** `https://[service-name].onrender.com`

---

### PythonAnywhere

**Steps:**

1. Go to https://pythonanywhere.com
2. Sign up & login
3. Web → Add new web app
4. Choose Python 3.10 + Flask
5. Upload kode via Git
6. Configure WSGI file
7. Reload app

**URL:** `https://[username].pythonanywhere.com`

---

## 🔗 API Integration (CORS Setup)

Setelah frontend & backend ter-deploy di domain berbeda, update CORS:

**File:** `backend/src/main.py`

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://priomed-rec.vercel.app",           # Frontend Vercel
        "https://azkastudying1-hub.github.io",      # GitHub Pages
        "http://localhost:3000",                    # Local dev
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

Kemudian push & re-deploy di Railway.

---

## ✅ Testing Checklist

### Frontend
- [ ] Open URL di browser
- [ ] Login works
- [ ] Dashboard loads
- [ ] Check console (no errors)
- [ ] Responsive design (mobile/desktop)
- [ ] API calls work (network tab)

### Backend
- [ ] Open `[backend-url]/docs` (Swagger UI)
- [ ] Try endpoint yang ada
- [ ] Check response format
- [ ] Check status codes

### Integration
- [ ] Login dari frontend
- [ ] Create data via API
- [ ] Data tersimpan di backend
- [ ] Bisa retrieve data
- [ ] Real-time updates work (jika ada)

---

## 🎯 Deployment Timeline

| Step | Time | Status |
|------|------|--------|
| Push ke GitHub | ✅ Done | 5 min |
| Deploy Frontend | Vercel: 5 min | Pending |
| Deploy Backend | Railway: 10 min | Pending |
| Setup CORS | 5 min | Pending |
| Testing | 15 min | Pending |
| **Total** | **~40 min** | **Pending** |

---

## 🆘 Troubleshooting

### CORS Error di Frontend
```
Access to XMLHttpRequest at 'http://backend' from origin 'http://frontend' 
has been blocked by CORS policy
```

**Solution:**
- Update `allow_origins` di backend CORS middleware
- Add frontend URL
- Redeploy backend

### API Not Responding
- Check backend deployment status
- Check environment variables (especially API keys)
- Check logs di platform dashboard
- Verify backend URL di frontend

### Frontend Won't Load
- Check Vercel/Netlify deployment status
- Check build logs
- Verify environment variables
- Test build locally: `npm run build`

### Database Connection Error
- Verify DATABASE_URL format
- Check if database is accessible from platform IP
- Add firewall rules if needed

---

## 📞 Getting Help

1. **GitHub Issues:** https://github.com/azkastudying1-hub/PrioMed-Rec/issues
2. **Platform Docs:**
   - Vercel: https://vercel.com/docs
   - Railway: https://docs.railway.app
   - Render: https://render.com/docs
3. **FastAPI:** https://fastapi.tiangolo.com
4. **React/Vite:** https://vitejs.dev

---

## 🚀 What's Next?

After deployment:

1. **Share the URL** with your team/users
2. **Monitor performance** (add Sentry/Rollbar)
3. **Setup CI/CD** (GitHub Actions)
4. **Monitor uptime** (UptimeRobot)
5. **Collect feedback** from users
6. **Plan improvements** based on usage

---

## 📝 Summary

✅ **GitHub:** https://github.com/azkastudying1-hub/PrioMed-Rec  
🔄 **Frontend Deployment:** Choose Vercel/Netlify/GitHub Pages  
🔄 **Backend Deployment:** Choose Railway/Render/PythonAnywhere  
🔗 **Configure CORS:** Update backend with frontend URL  
🧪 **Test Everything:** Verify all features work  
🎉 **Go Live:** Share URLs with users!

---

**Questions?** Check the other documentation files:
- `DEPLOY_GUIDE.md` - Detailed guide
- `DEPLOYMENT_CHECKLIST.md` - Comprehensive checklist
- `DEPLOY_PUBLIC.ps1` - Deployment helper script

**Last Updated:** November 1, 2026
