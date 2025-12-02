# Development Workflow

Complete workflow for building and running the album recognition system.

## 📋 Complete Setup Process

### Phase 1: Initial Setup

```bash
# 1. Setup backend
cd backend
./setup.sh

# 2. Configure environment (pulls from env.local per user preference)
cp .env.example .env.local
# Edit .env.local and add:
# DISCOGS_API_TOKEN=your_token_here
# MODEL_PATH=./models/album_classifier.pth
# IMAGES_PATH=./data/images

# 3. Setup frontend
cd ../frontend
npm install
```

### Phase 2: Data Preparation

```bash
# 4. Start backend (in terminal 1)
cd backend
./run.sh

# 5. Download album images (in terminal 2)
curl -X POST http://localhost:8000/api/download-images
# Wait for download to complete (~50 images, ~1-2 minutes with rate limiting)
```

### Phase 3: Model Training

```bash
# 6. Train the model
curl -X POST http://localhost:8000/api/train
# Training takes 5-10 minutes depending on your hardware
# Progress will be displayed in the backend terminal
```

### Phase 4: Running the App

```bash
# 7. Start frontend (in terminal 3)
cd frontend
npm run dev

# 8. Open browser
open http://localhost:3000
```

## 🔄 Daily Development Workflow

### Backend Development

```bash
cd backend
source venv/bin/activate  # Activate virtual environment
python main.py            # Start server with hot reload
```

### Frontend Development

```bash
cd frontend
npm run dev              # Start with hot reload
```

### Testing Changes

```bash
# Test API
cd backend
python test_api.py

# Test prediction
curl -X POST -F "file=@test_album.jpg" http://localhost:8000/api/predict
```

## 🎯 Common Tasks

### Adding More Albums

1. Update `data/releases_manifest_50.jsonl` with more releases
2. Download images for new releases:
   ```bash
   curl -X POST http://localhost:8000/api/download-images
   ```
3. Retrain model:
   ```bash
   curl -X POST http://localhost:8000/api/train
   ```

### Improving Model Accuracy

1. **More training epochs**: Edit `model_trainer.py` and increase epochs
2. **Better data augmentation**: Modify transforms in `model_trainer.py`
3. **More data**: Add more albums to the dataset
4. **Different architecture**: Try ResNet101 or EfficientNet

### Debugging

```bash
# Check API health
curl http://localhost:8000/api/health

# Check releases loaded
curl http://localhost:8000/api/releases | jq '.count'

# Check images downloaded
ls -l backend/data/images/ | wc -l

# Check model exists
ls -lh backend/models/album_classifier.pth
```

## 📊 Expected Results

### Image Download
- Expected: 50 images downloaded
- Time: 1-2 minutes (rate limited)
- Location: `backend/data/images/`

### Model Training
- Expected accuracy: 60-90% on validation set (50 classes)
- Time: 5-10 minutes
- Output: `backend/models/album_classifier.pth` (~95 MB)

### Predictions
- Response time: < 1 second
- Top-5 accuracy: Higher than top-1
- Confidence scores: 0-1 (0-100%)

## 🚀 Production Deployment

### Backend Deployment (AWS SageMaker)

```bash
# 1. Package model
cd backend
tar -czf model.tar.gz models/album_classifier.pth

# 2. Upload to S3
aws s3 cp model.tar.gz s3://your-bucket/models/

# 3. Create SageMaker endpoint
# Use PyTorch inference container
# Point to your model in S3
```

### Frontend Deployment (Vercel)

```bash
cd frontend
npm run build
vercel deploy --prod
```

### Environment Variables for Production

Backend:
- `DISCOGS_API_TOKEN`: Discogs API token
- `MODEL_PATH`: Path to model in EFS/S3
- `IMAGES_PATH`: Path to images in EFS/S3

Frontend:
- `NEXT_PUBLIC_API_URL`: Production API URL

## 🔧 Maintenance

### Update Dependencies

```bash
# Backend
cd backend
pip install --upgrade -r requirements.txt

# Frontend
cd frontend
npm update
```

### Monitor Performance

```bash
# Check API response times
curl -w "@curl-format.txt" -o /dev/null -s http://localhost:8000/api/health

# Monitor model predictions
tail -f backend/*.log
```

### Backup Model

```bash
# Backup trained model
cp backend/models/album_classifier.pth backup/model_$(date +%Y%m%d).pth

# Backup images
tar -czf backup/images_$(date +%Y%m%d).tar.gz backend/data/images/
```

## 📈 Scaling Considerations

1. **More Albums**: Currently 50, can scale to thousands
2. **Batch Processing**: Add batch prediction endpoint
3. **Caching**: Add Redis for prediction caching
4. **Load Balancing**: Use multiple backend instances
5. **GPU Inference**: Deploy on GPU instances for faster predictions
6. **Model Versioning**: Implement A/B testing for model improvements

## 🐛 Troubleshooting

### Issue: Low Prediction Accuracy

**Solutions:**
- Train for more epochs
- Add more training data
- Improve image quality
- Use data augmentation
- Try different model architectures

### Issue: Slow Predictions

**Solutions:**
- Use GPU for inference
- Reduce model size
- Implement caching
- Use model quantization
- Batch predictions

### Issue: Out of Memory

**Solutions:**
- Reduce batch size
- Use smaller model
- Free up GPU memory
- Use CPU for inference
- Increase system memory

### Issue: Images Not Downloading

**Solutions:**
- Check Discogs API token
- Verify rate limits
- Check network connection
- Look at error logs
- Try manual download for one image

## 📚 Resources

- [PyTorch Documentation](https://pytorch.org/docs/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Next.js Documentation](https://nextjs.org/docs)
- [Discogs API](https://www.discogs.com/developers)
- [Transfer Learning Guide](https://pytorch.org/tutorials/beginner/transfer_learning_tutorial.html)

