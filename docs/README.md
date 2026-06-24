# GitHub Pages Setup

## Quick Deploy

1. **Push to GitHub**
   ```bash
   cd "/Users/qp252220/Documents/Youtube downloader"
   git add .
   git commit -m "Convert to static GitHub Pages site"
   git push origin main
   ```

2. **Enable GitHub Pages**
   - Go to your repo on GitHub
   - Settings → Pages
   - Source: "Deploy from a branch"
   - Branch: `main` / folder: `/docs`
   - Click Save

3. **Your site will be live at:**
   ```
   https://<your-username>.github.io/<repo-name>/
   ```

## How It Works (No Backend!)

| Feature | API Used | CORS |
|---------|----------|------|
| **Videos** | [Cobalt API](https://cobalt.tools) | ✅ Yes |
| **Papers (DOI)** | OpenAlex + Unpaywall | ✅ Yes |
| **arXiv** | arXiv API | ✅ Yes |
| **PubMed** | OpenAlex (search) | ✅ Yes |

All processing happens client-side. No Python server needed.

## File Structure

```
docs/
  index.html    ← The entire app (single file!)
```

## Self-Host Cobalt (Optional)

If the public Cobalt API has rate limits, you can self-host:

```bash
# Docker
docker run -p 9000:9000 ghcr.io/imputnet/cobalt:latest

# Then update COBALT_API in index.html to your instance
```

## Custom Domain

1. Add a `CNAME` file in `/docs`:
   ```
   universl.app
   ```

2. Configure DNS:
   ```
   CNAME  universl.app  →  <username>.github.io
   ```

3. Enable in GitHub Settings → Pages → Custom domain
