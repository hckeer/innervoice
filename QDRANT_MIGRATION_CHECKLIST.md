# 📋 Qdrant Migration Checklist

Use this checklist to migrate your RAG system to Qdrant Cloud.

---

## Pre-Migration (Local Setup)

- [ ] **Install dependencies**
  ```bash
  pip install -r requirements.txt
  ```

- [ ] **Verify conversations.jsonl exists**
  ```bash
  ls -lh data/conversations.jsonl
  # Should show ~86MB file
  ```

- [ ] **Create .env file with Qdrant credentials**
  ```bash
  cat > .env << 'EOF'
  GROQ_API_KEY=your_groq_key_here
  USE_QDRANT=true
  QDRANT_URL=https://f22a7b8d-64cd-446a-9399-4fa98688472a.us-east4-0.gcp.cloud.qdrant.io:6333
  QDRANT_API_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhY2Nlc3MiOiJtIn0.BcF5OYB-ZkYjDJagNZxjFZ9R7tZFh6KVKG_PB9n5lIg
  QDRANT_COLLECTION=conversations
  EOF
  ```

---

## Step 1: Upload Data to Qdrant

- [ ] **Run upload script**
  ```bash
  python upload_to_qdrant.py
  ```

- [ ] **Verify successful upload**
  - Look for: `✅ SUCCESS - Qdrant upload complete!`
  - Note the final count (e.g., "Points in Qdrant: 50,000")

- [ ] **Test Qdrant connection manually (optional)**
  ```python
  from qdrant_client import QdrantClient
  
  client = QdrantClient(
      url="https://f22a7b8d-64cd-446a-9399-4fa98688472a.us-east4-0.gcp.cloud.qdrant.io:6333",
      api_key="eyJhbG..."
  )
  
  info = client.get_collection("conversations")
  print(f"Collection has {info.points_count} points")
  # Should match upload count
  ```

---

## Step 2: Test Locally (Before Production Deploy)

- [ ] **Run app locally with Qdrant**
  ```bash
  streamlit run app.py
  ```

- [ ] **Test in browser** (http://localhost:8501)
  - [ ] Send a test message: "Hey, how are you?"
  - [ ] Verify response is generated
  - [ ] Check "Retrieved Context" panel shows examples
  - [ ] Check browser console for errors (F12)

- [ ] **Check logs for Qdrant mode**
  - Look for: `use_qdrant=True`
  - Look for: `corpus_size=50000` (or your actual count)
  - No FAISS errors

---

## Step 3: Update Render Configuration

Choose ONE method:

### Method A: Update render.yaml (Recommended)

- [ ] **Backup old config**
  ```bash
  cp render.yaml render_faiss_backup.yaml
  ```

- [ ] **Use new Qdrant config**
  ```bash
  cp render_qdrant.yaml render.yaml
  ```

- [ ] **Review the changes**
  ```bash
  git diff render_faiss_backup.yaml render.yaml
  ```

### Method B: Use Render Dashboard (Alternative)

- [ ] **Go to Render Dashboard** → Your Service → Environment
- [ ] **Add environment variables:**
  - `USE_QDRANT` = `true`
  - `QDRANT_URL` = `https://f22a7b8d-64cd-446a-9399-4fa98688472a.us-east4-0.gcp.cloud.qdrant.io:6333`
  - `QDRANT_API_KEY` = `eyJhbG...` (**Mark as SECRET**)
  - `QDRANT_COLLECTION` = `conversations`

---

## Step 4: Deploy to Production

- [ ] **Commit changes**
  ```bash
  git add .
  git status  # Review what's being committed
  git commit -m "Migrate to Qdrant Cloud for production scalability"
  ```

- [ ] **Push to trigger deployment**
  ```bash
  git push origin main
  ```

- [ ] **Monitor deployment in Render dashboard**
  - Watch build logs for errors
  - Look for: "BUILD SUCCESS"
  - Wait for "Live" status

---

## Step 5: Verify Production Deployment

- [ ] **Check deployment logs**
  - Look for: `AsyncRAGPipeline initialized: ... use_qdrant=True`
  - Look for: `Qdrant collection loaded: 50,000 points`
  - No errors about "FAISS Index Not Found"

- [ ] **Test production app**
  - Visit: https://innervoice-2x7v.onrender.com
  - [ ] Page loads successfully
  - [ ] No error messages on homepage
  - [ ] Send test message: "Hey, how are you?"
  - [ ] Verify response appears
  - [ ] Check "Retrieved Context" shows examples

- [ ] **Performance check**
  - First query: Should complete in 1-2 seconds
  - Subsequent queries: Should complete in <500ms
  - If slower, check Render logs for issues

---

## Step 6: Cleanup (Optional)

- [ ] **Remove FAISS files from local directory** (save space)
  ```bash
  # Backup first (optional)
  tar -czf faiss_backup.tar.gz data/index.faiss data/metadata.pkl
  
  # Remove
  rm data/index.faiss data/metadata.pkl
  ```

- [ ] **Update documentation** (if you have custom docs)
  - Note that system now uses Qdrant
  - Remove references to building FAISS index

---

## Troubleshooting

If anything fails, check these common issues:

### ❌ "Qdrant credentials missing" error

**Fix:**
- [ ] Verify `.env` has correct `QDRANT_URL` and `QDRANT_API_KEY`
- [ ] Check Render environment variables are set
- [ ] Ensure `QDRANT_API_KEY` is marked as "secret" in Render

### ❌ "Collection 'conversations' not found" error

**Fix:**
- [ ] Run `python upload_to_qdrant.py` again
- [ ] Check Qdrant dashboard to verify collection exists

### ❌ Still seeing "FAISS Index Not Found" error

**Fix:**
- [ ] Verify `USE_QDRANT=true` in Render environment
- [ ] Check app logs for "use_qdrant=True"
- [ ] Redeploy: Render Dashboard → Manual Deploy

### ❌ Slow responses (>2 seconds)

**Fix:**
- [ ] Check Render logs for memory issues
- [ ] Reduce `top_k` to 3-5 in Settings
- [ ] Consider upgrading Qdrant plan

---

## Rollback Plan (If Needed)

If you need to rollback:

- [ ] **Set `USE_QDRANT=false` in Render environment**
- [ ] **Restore old render.yaml**
  ```bash
  cp render_faiss_backup.yaml render.yaml
  git add render.yaml
  git commit -m "Rollback to FAISS (temporary)"
  git push
  ```

- [ ] **Build small sample index**
  ```bash
  head -n 100 data/conversations.jsonl > data/sample_conversations.jsonl
  python build_index_production.py
  ```

---

## Success Criteria ✅

Your migration is successful if:

- ✅ App loads without errors
- ✅ Chat messages get responses
- ✅ Retrieved context shows relevant examples
- ✅ Logs show `use_qdrant=True`
- ✅ Response time < 1 second
- ✅ No memory crashes

---

## Next Steps After Success

- [ ] **Monitor performance** for 24-48 hours
- [ ] **Check Qdrant usage** in Qdrant Cloud dashboard
- [ ] **Consider upgrading** if you hit free tier limits:
  - Qdrant Starter: $25/mo (10GB storage, unlimited queries)
  - Render Starter: $7/mo (persistent disk)

---

**Estimated Total Time:** 20-30 minutes

**Date:** March 24, 2026  
**Status:** Ready to Execute
