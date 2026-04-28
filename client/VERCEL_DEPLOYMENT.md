# Frontend Deployment to Vercel

## Setup Complete ✅

The frontend is now configured for Vercel deployment.

### Files Created/Updated:

1. **`.env`** - Local development configuration
   ```
   VITE_MOCK_MODE=false
   VITE_API_BASE_URL=http://127.0.0.1:8000
   ```

2. **`.env.production`** - Production configuration for Vercel
   ```
   VITE_MOCK_MODE=false
   VITE_API_BASE_URL=https://enrichsalesagent-project.vercel.app
   ```

3. **`vercel.json`** - Vercel deployment configuration
   - Configures build output (dist directory)
   - Sets up routing for SPA (all non-asset routes go to index.html)

4. **`.gitignore`** - Updated to exclude .env files from git

## Deployment Steps

### 1. Vercel Project Setup

1. Go to [vercel.com](https://vercel.com)
2. Connect your GitHub repository
3. Create a new project
4. **Project Name**: `enrichsalesagent` (will create `enrichsalesagent.vercel.app`)
5. **Framework**: Select "Vite"
6. **Build Command**: Leave default (or ensure it's `npm run build` or `bun run build`)
7. **Output Directory**: `dist`

### 2. Environment Variables in Vercel

You can optionally set environment variables in Vercel project settings, but `.env.production` will be used automatically:

- If you want to override via Vercel UI:
  - `VITE_API_BASE_URL` = `https://enrichsalesagent-project.vercel.app`
  - `VITE_MOCK_MODE` = `false`

### 3. Deploy

Click "Deploy" and Vercel will:
1. Clone your repo
2. Install dependencies (`npm install` or `bun install`)
3. Run `npm run build` (builds to `dist/`)
4. Deploy the static files

### 4. Verify

Once deployed, visit `https://enrichsalesagent.vercel.app` and:
- Test the search form
- Verify it connects to the backend at `https://enrichsalesagent-project.vercel.app`
- Check for any CORS errors in browser console

## Backend & Frontend URLs

| Component | URL |
|-----------|-----|
| **Backend** | `https://enrichsalesagent-project.vercel.app` |
| **Frontend** | `https://enrichsalesagent.vercel.app` |
| **Backend CORS** | Allows `https://enrichsalesagent.vercel.app` |

## Local Development

To test locally before deploying:

```bash
cd client
npm install        # or bun install
npm run dev        # Runs at http://localhost:5173
```

The frontend will connect to `http://127.0.0.1:8000` (local backend) via `.env`.

## Production vs Development

- **Development** (`.env`): Uses local backend `http://127.0.0.1:8000`
- **Production** (`.env.production`): Uses Vercel backend `https://enrichsalesagent-project.vercel.app`

Vite automatically picks the correct `.env.*` file based on the build mode.

## Troubleshooting

### CORS Errors
If you see CORS errors, verify:
1. Backend `.env` has `CORS_ALLOWED_ORIGINS=...https://enrichsalesagent.vercel.app`
2. Backend is deployed and responding at `https://enrichsalesagent-project.vercel.app`
3. Frontend `.env.production` has correct `VITE_API_BASE_URL`

### Blank Page / 404 on Refresh
The `vercel.json` routing rules should redirect all non-asset requests to `index.html`. If this doesn't work:
- Verify `vercel.json` is in the client root directory
- Check Vercel deployment logs

### API Calls Fail
1. Open browser DevTools → Network tab
2. Check the API request URL
3. Verify it matches `VITE_API_BASE_URL` from `.env.production`
4. Test the backend directly: `curl https://enrichsalesagent-project.vercel.app/research`

## Next Steps

1. ✅ Commit changes to git
2. ✅ Push to GitHub
3. ✅ Connect repo to Vercel
4. ✅ Deploy frontend
5. ✅ Verify both URLs are working
6. ✅ Test end-to-end (search → backend → response → display)
