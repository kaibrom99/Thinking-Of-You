# Deploying Thinking of You for free (Neon + Render + Streamlit Community Cloud)

You'll create four free accounts: GitHub, Neon, Render, Streamlit. No credit card needed for these tiers
(check each site's current terms when you sign up).

## 1. Put the code on GitHub
1. Make a GitHub account and a **private** repository named `thinking-of-you`.
2. In PyCharm: **Git → Create Git Repository** (pick the project folder), then commit everything and
   **Git → Push** to your new repo. The `.gitignore` keeps your database and `.venv` out. Check the repo on
   GitHub afterwards: there should be **no `.db` file and no `.venv` folder**.

## 2. Database: Neon
1. Sign up at neon.com and create a project (any name, nearest region).
2. Copy the **connection string** (it starts with `postgresql://`). Treat it like a password.

## 3. Backend: Render
1. Sign up at render.com with GitHub. **New → Web Service**, choose your repo.
2. Settings:
   - **Build command:** `pip install -r requirements.txt`
   - **Start command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`
   - **Instance type:** Free
3. **Environment variables:**
   - `DATABASE_URL` = your Neon connection string
   - `PYTHON_VERSION` = `3.12.8` (if Render rejects it, use a 3.12 version it lists)
4. Deploy. When it's live, open `https://YOUR-NAME.onrender.com/health`. You should see `{"ok":true}`.
   `/docs` shows the API. Note the address: you need it twice below.

## 4. App: Streamlit Community Cloud
1. Sign in at share.streamlit.io with GitHub. **Create app**, pick your repo, branch `main`,
   main file `app.py`.
2. **Advanced settings → Secrets**, paste (with your real address, no trailing slash):
   `API_URL = "https://YOUR-NAME.onrender.com"`
   Also choose Python 3.12. Deploy. That `*.streamlit.app` address is what testers open.

## 5. Extension
1. Open `extension/config.js` and set `API` to `https://YOUR-NAME.onrender.com`.
2. In `chrome://extensions`, reload the extension and sign in from its popup to test.
3. To share: zip the `extension` folder. Testers unzip it, open `chrome://extensions`, turn on
   **Developer mode**, click **Load unpacked**, pick the folder, then sign in from the popup.

## 6. Smoke test
Sign up on the Streamlit address, create an invite code, link with a second account (private window),
browse a product with the extension, and check it shows up on both sides.

## Notes
- **Free Render sleeps after 15 minutes idle** and takes about a minute to wake. Before the couples start,
  upgrade the Render service to **Starter (about $7/month)** so it stays awake.
- **Forgotten password:** set `DATABASE_URL` to your Neon string on your computer, then run
  `python admin_reset_password.py their@email.com NewPassword123`.
- **Extension updates are manual:** send a new zip when you change it.