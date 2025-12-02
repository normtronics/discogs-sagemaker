# 🚀 Get Started in 3 Steps

Welcome! This guide will get your album recognition system up and running quickly.

## Prerequisites

- ✅ Python 3.8+ (You have: Python 3.13.3)
- ✅ Node.js 18+ (You have: Node.js v20.17.0)
- ✅ Discogs API credentials (Already configured!)

## Step 1: Backend Setup (2 minutes)

```bash
# Navigate to backend
cd backend

# Run setup script - installs Python dependencies
./setup.sh

# Your Discogs credentials are already configured!
# But if you need to update them:
# cp .env.example .env.local
# Edit .env.local with your DISCOGS_CONSUMER_KEY and DISCOGS_CONSUMER_SECRET
```

## Step 2: Download & Train (10 minutes)

```bash
# Start the backend server (in terminal 1)
cd backend
./run.sh

# In a new terminal (terminal 2), download album images
curl -X POST http://localhost:8000/api/download-images

# Train the model (~5 minutes)
curl -X POST http://localhost:8000/api/train
```

**What's happening:**
- Downloads 50 album cover images from Discogs
- Trains a ResNet50 neural network to recognize them
- Saves the trained model for predictions

## Step 3: Launch the App (30 seconds)

```bash
# In a new terminal (terminal 3)
cd frontend
npm run dev

# Open your browser
open http://localhost:3000
```

## 🎉 You're Done!

Now you can:
1. Upload or drag & drop an album cover image
2. Click "Identify Album"
3. See the top 5 predictions with confidence scores!

## 📊 Quick Test

```bash
# Verify everything is working
./verify-setup.sh

# Test the complete workflow
./test-full-workflow.sh
```

## 🎯 Example Workflow

1. **Find an album cover**: Search Google Images for an album from your dataset
2. **Download the image**: Save it to your computer
3. **Upload to the app**: Drag it into the upload box at http://localhost:3000
4. **Get predictions**: See how confident the model is!

## 📚 Learn More

- **Full documentation**: See `README.md`
- **Quick start guide**: See `QUICKSTART.md`
- **Development workflow**: See `WORKFLOW.md`
- **Project details**: See `PROJECT_SUMMARY.md`

## 🐛 Troubleshooting

### "Cannot connect to API"
- Make sure backend is running: `cd backend && ./run.sh`
- Check it's on port 8000: `curl http://localhost:8000/api/health`

### "Model not loaded"
- Train the model first: `curl -X POST http://localhost:8000/api/train`
- Wait for training to complete (~5 minutes)

### "No predictions"
- Make sure images were downloaded: `ls backend/data/images/ | wc -l`
- Should show at least 40-50 images
- If not, run: `curl -X POST http://localhost:8000/api/download-images`

### "Low confidence scores"
- This is normal with only 50 albums and limited training
- Try training for more epochs (edit `model_trainer.py`)
- Add more albums to improve accuracy

## 💡 Tips

- **Better accuracy**: Train on more albums (add to `releases_manifest_50.jsonl`)
- **Faster predictions**: The first prediction is slower, subsequent ones are faster
- **Try different images**: Test with various angles and lighting
- **Check confidence**: Higher confidence (>0.5) means more certain prediction

## 🎨 What You've Built

```
┌─────────────────────────────┐
│   Frontend (Next.js)        │
│   - Upload interface        │
│   - Predictions display     │
└──────────┬──────────────────┘
           │
┌──────────▼──────────────────┐
│   Backend (FastAPI)         │
│   - Image processing        │
│   - Model serving           │
└──────────┬──────────────────┘
           │
┌──────────▼──────────────────┐
│   ML Model (PyTorch)        │
│   - ResNet50                │
│   - 50 album classes        │
└─────────────────────────────┘
```

## 🚀 Next Steps

Once you're comfortable with the basics:

1. **Expand the catalog**: Add more albums to the dataset
2. **Improve the model**: Train for more epochs or try different architectures
3. **Customize the UI**: Modify the frontend to match your style
4. **Deploy it**: Put it online with Vercel (frontend) and AWS (backend)

## 📞 Need Help?

1. Check the troubleshooting section above
2. Review the documentation files
3. Run `./test-full-workflow.sh` for diagnostics
4. Check the terminal output for error messages

## 🎵 Have Fun!

You now have a working AI-powered album recognition system. Experiment with different images, add more albums, and see how accurate you can make it!

---

**Pro tip**: Start with album covers that have distinctive artwork. The model learns visual patterns, so unique designs are easier to recognize!

