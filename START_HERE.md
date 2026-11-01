# 🚀 START HERE - Deployment PrioMed-Rec

## ✅ Status: GitHub Upload COMPLETE

Kode Anda sudah ada di GitHub! 🎉

```
Repository: https://github.com/azkastudying1-hub/PrioMed-Rec
Status: Public & Ready
Files: 434 uploaded
```

---

## ⏭️ What's Next?

Aplikasi perlu di-**deploy ke internet** agar bisa diakses oleh orang lain.

**Estimated time:** 30-45 minutes total

---

## 🎯 Langkah-Langkah (Pilih 1 dari setiap kategori)

### 1️⃣ Deploy Frontend (Choose One)

#### A. Vercel ⭐ (RECOMMENDED - 5 minutes)
```powershell
npm install -g vercel
cd web
vercel --prod
```
**Will give you URL like:** `https://priomed-rec.vercel.app`

#### B. Netlify (10 minutes)
```powershell
npm install -g netlify-cli
cd web
npm run build
netlify deploy --prod --dir=dist
```

#### C. GitHub Pages (15 minutes)
Go to repository settings and enable Pages

---

### 2️⃣ Deploy Backend (Choose One)

#### A. Railway ⭐ (RECOMMENDED - 10 minutes)
1. Go to https://railway.app
2. "New Project" → "Deploy from GitHub repo"
3. Select your repo
4. Add environment variables (see below)
5. Deploy!

**Will give you URL like:** `https://priomed-rec-prod.railway.app`

#### B. Render (15 minutes)
1. Go to https://dashboard.render.com
2. "New" → "Web Service"
3. Connect GitHub & deploy

#### C. PythonAnywhere (20 minutes)
Go to https://pythonanywhere.com

---

### 3️⃣ Configure CORS (5 minutes)

Update `backend/src/main.py` with your frontend URL:

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://priomed-rec.vercel.app",  # YOUR FRONTEND URL
        "http://localhost:3000",             # Keep for local dev
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

Then push to GitHub:
```bash
git add backend/src/main.py
git commit -m "Update CORS for production"
git push
```

---

## 🔐 Environment Variables

### For Railway Backend Dashboard
Add these:
```
DATABASE_URL=postgresql://user:pass@host/db    (if you have database)
OPENAI_API_KEY=sk-...                          (if using OpenAI)
GROQ_API_KEY=gsk-...                           (if using Groq)
GEMINI_API_KEY=...                             (if using Gemini)
FRONTEND_URL=https://priomed-rec.vercel.app    (YOUR FRONTEND URL)
ENVIRONMENT=production
DEBUG=False
```

### For Frontend (.env.production in web/)
```
VITE_API_URL=https://priomed-rec-prod.railway.app
```

---

## 📋 My Recommended Setup (Fast Track)

1. **Frontend:** Vercel (5 min)
   ```
   npm install -g vercel
   cd web
   vercel --prod
   ```

2. **Backend:** Railway (10 min)
   ```
   - Go to railway.app
   - Deploy from GitHub
   - Add env vars
   - Done!
   ```

3. **CORS:** Update & push (5 min)

4. **Test:** Open frontend URL in browser (5 min)

**Total: ~25 minutes to be live! 🎉**

---

## ✨ After Deployment

Frontend URL:
```
https://priomed-rec.vercel.app
```

Backend URL:
```
https://priomed-rec-prod.railway.app
```

API Docs (for testing):
```
https://priomed-rec-prod.railway.app/docs
```

---

## 📚 Full Documentation

If you need more details:

- `README_DEPLOYMENT.md` - Quick reference
- `DEPLOY_GUIDE.md` - Step-by-step guide
- `DEPLOYMENT_CHECKLIST.md` - Complete checklist

---

## ❓ FAQ

**Q: Do I need to setup database?**
A: If your app needs data persistence, yes. Otherwise no.

**Q: Can I use custom domain?**
A: Yes! Vercel & Railway support custom domains.

**Q: Will it auto-deploy on push?**
A: Yes! Both Vercel & Railway auto-deploy from GitHub.

**Q: How long will deployment take?**
A: Vercel: ~1 min | Railway: ~5 min

**Q: Can I monitor errors?**
A: Yes! Check platform dashboards (Vercel & Railway have logs).

---

## 🎯 Quick Links

- **Your Repository:** https://github.com/azkastudying1-hub/PrioMed-Rec
- **Deploy Frontend:** https://vercel.com
- **Deploy Backend:** https://railway.app
- **Alternative Frontend:** https://netlify.com
- **Alternative Backend:** https://render.com

---

## ⏱️ Timeline

- [ ] Deploy frontend (5 min) ← START HERE
- [ ] Deploy backend (10 min)
- [ ] Configure CORS (5 min)
- [ ] Test application (10 min)
- [ ] ✅ LIVE! 🚀

---

## 🎉 You're Almost There!

Once deployed, you'll have:
- ✅ Frontend URL accessible worldwide
- ✅ Backend API responding to requests
- ✅ Database connected (if needed)
- ✅ Production-ready application
- ✅ Auto-deploy on every push

**Ready? Start with Step 1️⃣ above!**

---

**Questions?** Open `README_DEPLOYMENT.md` for more details.

Last Updated: November 1, 2026
