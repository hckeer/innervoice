# Render Deployment Guide for InnerVoice

## 🚀 Quick Deploy

1. **Push to GitHub** (if not already done):
   ```bash
   git add .
   git commit -m "Prepare for Render deployment"
   git push origin main
   ```

2. **Create New Web Service on Render**:
   - Go to [render.com/dashboard](https://dashboard.render.com)
   - Click "New +" → "Web Service"
   - Connect your GitHub repository
   - Render will auto-detect the `render.yaml` configuration

3. **Set Environment Variables**:
   - In the Render dashboard, go to your service → "Environment"
   - Add: `GROQ_API_KEY` = `your_groq_api_key_here`
   - Save changes

4. **Deploy**:
   - Click "Manual Deploy" → "Deploy latest commit"
   - Wait for build to complete (3-5 minutes)

## 🔍 Troubleshooting

### Issue: "FAISS Index Not Found" Error

**Symptoms**: App shows index missing error despite successful build.

**Root Causes**:

1. **Build Script Failed Silently**
   - **Check**: View build logs in Render dashboard
   - **Look for**: "BUILD SUCCESSFUL" message
   - **If missing**: Build script crashed

2. **Missing Sample Data**
   - **Check**: Ensure `data/sample_conversations.jsonl` is committed to git
   - **Verify**:
     ```bash
     git ls-files data/sample_conversations.jsonl
     ```
   - **Fix**: If not tracked, add it:
     ```bash
     git add data/sample_conversations.jsonl
     git commit -m "Add sample conversations for production"
     git push
     ```

3. **Memory Limit Exceeded**
   - **Render Free Tier**: 512MB RAM
   - **Index Size**: Should be < 1MB for 100 samples
   - **Check logs**: Look for "Killed" or "Out of memory" messages

4. **File Permissions**
   - **Rare**: Render build may not have write permissions
   - **Check logs**: Look for permission errors

### Viewing Build Logs

1. Go to your service in Render dashboard
2. Click "Logs" tab
3. Filter by "Build Logs"
4. Search for:
   - `BUILD SUCCESSFUL` ✅
   - `ERROR` ❌
   - `index.faiss` (should show file size)

### Common Build Log Messages

✅ **Success**:
```
✅ BUILD SUCCESSFUL - Index ready for production
📂 Files created in: /opt/render/project/src/data
   - index.faiss (0.15 MB)
   - metadata.pkl (0.01 MB)
```

❌ **Failure - Sample Data Missing**:
```
❌ ERROR: Sample data not found at /opt/render/project/src/data/sample_conversations.jsonl
```
**Fix**: Ensure file is committed to git.

❌ **Failure - Out of Memory**:
```
Killed
```
**Fix**: Reduce sample dataset size or upgrade Render plan.

❌ **Failure - Dependency Error**:
```
❌ ERROR: Required dependencies not installed: No module named 'faiss'
```
**Fix**: Check `requirements.txt` is correct and build command runs `pip install -r requirements.txt`.

## 📊 Production Specifications

### Current Configuration

- **Plan**: Free Tier
- **RAM**: 512MB
- **Python**: 3.11.0
- **Index Size**: ~0.15 MB (100 samples)
- **Estimated RAM Usage**: ~50-100 MB at runtime
- **Buffer**: ~400MB available for Streamlit + app

### Scaling Options

If you need more capacity:

| Plan | RAM | Cost | Recommended For |
|------|-----|------|-----------------|
| Free | 512MB | $0 | Testing, demos (100-500 samples) |
| Starter | 1GB | $7/mo | Small production (~2,000 samples) |
| Standard | 2GB | $15/mo | Medium production (~10,000 samples) |

### Index Size Guidelines

| Samples | Index Size | RAM Needed | Render Plan |
|---------|-----------|------------|-------------|
| 100 | 0.15 MB | ~50 MB | Free ✅ |
| 500 | 0.75 MB | ~100 MB | Free ✅ |
| 1,000 | 1.5 MB | ~150 MB | Free ✅ |
| 5,000 | 7.5 MB | ~200 MB | Free ✅ |
| 10,000 | 15 MB | ~300 MB | Free ✅ |
| 50,000 | 75 MB | ~500 MB | Starter |
| 100,000 | 150 MB | ~800 MB | Starter |
| 645,692 (full) | 946 MB | ~2.5 GB | Standard+ |

## 🛠️ Manual Index Build on Render

If automatic build fails, you can build at runtime:

1. **Via App UI**:
   - Go to your deployed app
   - When you see "FAISS Index Not Found" error
   - Click "🔨 Build Index Now"
   - Wait 1-2 minutes

2. **Via Render Shell** (Advanced):
   - Go to service → "Shell" tab
   - Run:
     ```bash
     cd /opt/render/project/src
     python build_index_production.py
     ```
   - Check for success message

## 🔄 Redeployment

After making changes:

```bash
git add .
git commit -m "Your commit message"
git push origin main
```

Render will auto-deploy if auto-deploy is enabled. Otherwise:
- Go to dashboard → "Manual Deploy" → "Deploy latest commit"

## 📝 Checklist for Successful Deployment

- [ ] `data/sample_conversations.jsonl` is committed to git
- [ ] `.gitignore` excludes large files (`index.faiss`, `conversations.jsonl`)
- [ ] `requirements.txt` includes all dependencies
- [ ] `GROQ_API_KEY` is set in Render environment variables
- [ ] Build logs show "BUILD SUCCESSFUL"
- [ ] App health check passes at `/_stcore/health`

## 🆘 Still Having Issues?

1. **Check Build Logs**: Most issues show up here
2. **Test Locally**: Run `python build_index_production.py` locally
3. **Check File Sizes**: Ensure index is < 100MB
4. **Verify Sample Data**: Should have 100-1000 conversations
5. **Contact Support**: Share build logs and diagnostic output

## 🎯 Pro Tips

1. **Faster Builds**: Use smaller sample dataset (100-500 conversations)
2. **Cost Savings**: Free tier works great for demos and testing
3. **Monitoring**: Check Render logs regularly for errors
4. **Caching**: Dependencies are cached between builds (faster rebuilds)
5. **Health Checks**: Streamlit's built-in health check ensures uptime

## 📚 Additional Resources

- [Render Docs](https://render.com/docs)
- [Streamlit Deployment Guide](https://docs.streamlit.io/streamlit-community-cloud/get-started/deploy-an-app)
- [FAISS Documentation](https://github.com/facebookresearch/faiss/wiki)
