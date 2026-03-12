# Railway deploy checklist

Before redeploying, confirm:

1. **Start command** (Railway dashboard → your service → Settings → Deploy → Custom Start Command):
   ```
   python -m gunicorn -w 1 -b 0.0.0.0:$PORT app:app
   ```
   If the field says "set in railway.toml", the repo already has this; otherwise paste the line above.

2. **Build command**: Leave **empty** (no `npm run build` or other command).

3. **Push and redeploy**:
   ```bash
   git add -A
   git status
   git commit -m "Railway: python -m gunicorn and deploy config"
   git push origin main
   ```
   Then trigger a new deploy on Railway (or wait for auto-deploy).

4. **Open**: https://minischool-production-e093.up.railway.app/
