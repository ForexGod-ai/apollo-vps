# ForexGod Dashboard - Cloud Deployment

## Option 1: Railway.app (EASIEST - FREE)
1. Go to https://railway.app
2. Sign up with GitHub
3. New Project → Deploy from GitHub
4. Upload this folder
5. Railway gives you: https://your-app.railway.app

## Option 2: Vercel (FREE - RECOMMENDED)
1. Install Vercel: npm i -g vercel
2. Run: vercel --prod
3. Auto-deploy on every git push
4. URL: https://your-dashboard.vercel.app

## Option 3: Render.com (FREE - 24/7)
1. Go to https://render.com
2. New → Static Site
3. Connect GitHub repo
4. Deploy: https://your-dashboard.onrender.com

## Option 4: DigitalOcean / AWS / VPS
See DEPLOY_VPS.md for VPS setup instructions.

## Auto-Sync trade_history.json
Run sync_trades.sh on your local machine to keep cloud updated.
