# 💌 Thinking of You

Thinking of You is a privacy-focused gift discovery app for couples.

It helps partners find thoughtful gifts without requiring someone to explicitly ask for a specific item. With the optional browser extension enabled, the app recognizes products viewed or added to a cart on supported shopping websites and creates a ranked gift list. Linked partners can see one another's non-private lists while keeping browsing history private.

## Features

- Account registration and login
- Partner linking through invite codes
- Automatically generated gift lists
- Manually added wishlist items
- Product interest scoring
- Private items hidden from a partner
- Optional browser-extension tracking
- Tracking consent and pause controls
- Account and data deletion
- Product deduplication
- Automated API tests

## Supported Shopping Sites

The browser extension currently supports product pages on:

- Amazon
- Etsy
- Target
- Walmart
- eBay
- Shein

The extension ignores pages that do not match recognized product-page patterns.

## How It Works

1. Create an account in the Thinking of You app.
2. Link your account with your partner using an invite code.
3. Choose whether to enable shopping activity tracking.
4. Install the browser extension and sign in.
5. Browse supported shopping websites normally.
6. Recognized products are added to your list.
7. Your linked partner can see your non-private gift ideas.

The app stores product-level events rather than a general browsing history.

## Interest Scoring

Items are ranked using product activity:

- Product view: 1 point
- Add to cart: 3 points
- Manually added item: starts with 5 points

Repeated views within the view cooldown period do not increase the score.

## Privacy

Thinking of You is designed around user consent and control.

- Shopping tracking requires user consent.
- Tracking can be paused.
- Only supported product pages are processed.
- General browsing history is not shared with a partner.
- Items can be marked private.
- Private items are never included in the partner's list.
- Users can remove individual items.
- Users can delete their account and associated data.
- Authentication tokens are stored as hashes by the backend.
- Passwords are hashed with unique salts.

Users should still review the source code and privacy behavior before installing the extension or supplying personal information.

## Technology Stack

### Frontend

- Streamlit
- Python
- Requests

### Backend

- FastAPI
- SQLModel
- Uvicorn
- SQLite by default

### Browser Extension

- Chrome Manifest V3
- JavaScript
- Chrome local storage
- Content script and background service worker

### Testing

- pytest
- FastAPI TestClient
- HTTPX

## Project Structure

The repository contains files similar to the following:

Thinking-Of-You/
├── App.py
├── main.py
├── requirements.txt
├── requirements-dev.txt
├── pytest.ini
├── .gitignore
├── README.md
│
├── .streamlit/
│   └── config.toml
│
├── tests/
│   └── test_api.py
│
└── extension/
    ├── manifest.json
    ├── background.js
    ├── content.js
    ├── popup.html
    └── popup.js
```

### Main Application Files

- `App.py` contains the Streamlit user interface. It provides account registration, login, partner linking, wishlist management, privacy settings, consent controls, and account deletion.
- `main.py` contains the FastAPI backend, database models, authentication system, partner-linking logic, item-management endpoints, and browser-extension event processing.
- `requirements.txt` contains the dependencies needed to run the application.
- `requirements-dev.txt` contains the dependencies used for development and automated testing.
- `pytest.ini` configures pytest and identifies the `tests` folder.
- `.gitignore` prevents local databases, virtual environments, secrets, tokens, and generated files from being committed.
- `README.md` contains the project documentation.

### Streamlit Configuration

- `.streamlit/config.toml` defines the Streamlit application's light theme, colors, and typography.
- `.streamlit/secrets.toml`, if created locally or during deployment, is excluded from Git and must not contain values that are committed to the repository.

### Automated Tests

- `tests/test_api.py` contains automated tests for authentication, token expiration, logout, rate limiting, partner linking, privacy controls, tracking consent, product deduplication, item deletion, and account deletion.

### Browser Extension

- `extension/manifest.json` defines the Chrome Manifest V3 extension, permissions, supported shopping websites, popup, service worker, and content script.
- `extension/content.js` identifies supported product pages, extracts product information, detects product views and add-to-cart actions, and sends events to the background worker.
- `extension/background.js` receives events from the content script and sends authenticated requests to the FastAPI backend.
- `extension/popup.html` provides the extension's sign-in and tracking controls.
- `extension/popup.js` handles extension authentication, local tracking preferences, and logout behavior.



