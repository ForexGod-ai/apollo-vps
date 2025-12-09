#!/bin/bash

# ForexGod Dashboard - Quick Deploy Options
# Choose your preferred hosting method

echo "🚀 ForexGod Dashboard - Deploy Options"
echo "======================================="
echo ""
echo "Choose deployment method:"
echo ""
echo "1️⃣  GitHub Pages (FREE forever, auto-sync)"
echo "   → Your repo needs to be on GitHub"
echo "   → URL: https://YOUR_USERNAME.github.io/YOUR_REPO"
echo "   → Run: python3 auto_deploy_dashboard.py"
echo ""
echo "2️⃣  Netlify Drop (FASTEST - 2 minutes)"
echo "   → Go to: https://app.netlify.com/drop"
echo "   → Drag 'deploy_dashboard' folder"
echo "   → Get instant URL: https://random-name.netlify.app"
echo ""
echo "3️⃣  Python SimpleHTTPServer (Local + ngrok)"
echo "   → Already running on port 8080"
echo "   → Install ngrok: brew install ngrok"
echo "   → Run: ngrok http 8080"
echo "   → Get public URL: https://xxx.ngrok.io"
echo ""
echo "4️⃣  VPS Deployment (Full control 24/7)"
echo "   → Need: DigitalOcean, Linode, AWS, etc."
echo "   → See: deploy_dashboard/DEPLOY_VPS.md"
echo ""
echo "======================================="
echo ""

read -p "Which option? (1-4): " choice

case $choice in
    1)
        echo "🚀 Deploying to GitHub Pages..."
        python3 auto_deploy_dashboard.py
        ;;
    2)
        echo "📦 Opening Netlify Drop..."
        echo "📁 Drag the 'deploy_dashboard' folder into the browser"
        open "https://app.netlify.com/drop"
        open "deploy_dashboard"
        ;;
    3)
        echo "🌐 Starting ngrok tunnel..."
        if ! command -v ngrok &> /dev/null; then
            echo "📥 Installing ngrok..."
            brew install ngrok
        fi
        echo "✅ HTTP server running on port 8080"
        echo "🌍 Creating public URL..."
        ngrok http 8080
        ;;
    4)
        echo "📖 Opening VPS deployment guide..."
        cat deploy_dashboard/DEPLOY_VPS.md
        ;;
    *)
        echo "❌ Invalid option"
        exit 1
        ;;
esac
