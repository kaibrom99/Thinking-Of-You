# Deploying Thinking of You for free (Neon + Render + Streamlit Community Cloud)

## Updating the existing app

The working checkout is currently on `v2`. Local edits do not update the public website
until they are committed and pushed to the branch used by the deployed services.

1. Commit the intended app updates and push them to GitHub. Include the new
   `welcome.py` and `mobile.css` files, `App.py`, `.streamlit/config.toml`, and
   `requirements.txt`, along with the earlier backend changes in `main.py` and `thumbs.py`.
   The updated requirements pin Streamlit to the version used for local checks.
2. Check which branch your existing Streamlit app and Render backend deploy.
   If they deploy `main`, merge the completed `v2` changes into `main` and push `main`.
   If they deploy `v2`, push the updates to `v2`.
3. Deploy the backend on Render first. With auto-deploy enabled, the push triggers
   this automatically; otherwise choose **Manual Deploy → Deploy latest commit**.
   Keep the existing production `DATABASE_URL` so accounts and lists use the same database.
4. Streamlit Community Cloud updates from its configured repository branch.
   Dependency changes trigger reinstallation. If the app still appears stale after
   the deployment finishes, use **Reboot app** in its management menu and refresh the browser.
   The entrypoint remains `App.py`; its `API_URL` secret should point to the deployed Render API.
5. Open your public `*.streamlit.app` address on your phone. Check the welcome page
   while signed out, sign in, and check People, My list, Add item, and Settings.
   Tap an owner's fire score to check the points popup.

The mobile formatting changes do not require reinstalling the browser extension.
If distributing the earlier extension updates too, reload or replace the unpacked extension.

References: [Streamlit app updates](https://docs.streamlit.io/deploy/streamlit-community-cloud/manage-your-app),
[Render deployments](https://render.com/docs/deploys).

## Running the updated app locally on Windows

If the local app is already running, refresh `http://127.0.0.1:8501/`.
If Streamlit offers a rerun, select it. A fresh browser tab starts a new signed-out session
and shows the welcome page.

To start it again, open two PowerShell terminals in `C:\Users\kaibr\Desktop\ThinkingOfYou`.
Use the existing virtual environment. If setting up a new computer, first create it with
`py -m venv .venv`.

In the first terminal:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
$env:TOY_DB = "sqlite:///thinking_of_you.db"
.\.venv\Scripts\python.exe -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

In the second terminal:

```powershell
$env:API_URL = "http://127.0.0.1:8000"
.\.venv\Scripts\python.exe -m streamlit run App.py --server.address 127.0.0.1 --server.port 8501
```

Open `http://127.0.0.1:8501/` on that computer. Keep both processes running;
press Ctrl+C in each terminal to stop them. The local database is separate from
your hosted database. On a phone, use the public website address: `127.0.0.1`
on the phone points to the phone itself.

---

## First-time deployment

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
1. Sign in at share.streamlit.io with GitHub. **Create app**, pick your repo, and select the branch
   that contains the version you want to deploy (`v2` for this checkout; use `main` after merging it).
   Set the main file to `App.py` (capitalization matters on Linux hosts).
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
