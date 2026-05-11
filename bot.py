import os
import hmac
import hashlib
import json
import requests
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler

load_dotenv()

app = Flask(__name__)

# Configuration
SECRET = os.environ.get('GITHUB_WEBHOOK_SECRET')
TARGET_REPO = os.environ.get('raandomdev/Elixir-Macro')  # e.g., "raandomdev/Elixir-Macro"
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN')  # optional, but increases rate limit
POLL_INTERVAL_MINUTES = int(os.environ.get('POLL_INTERVAL_MINUTES', 5))

STATE_FILE = 'last_release.txt'

def get_latest_release_from_api():
    """Fetch the latest release from GitHub API."""
    url = f"https://api.githubusercontent.com/repos/{TARGET_REPO}/releases/latest"
    headers = {}
    if GITHUB_TOKEN:
        headers['Authorization'] = f'token {GITHUB_TOKEN}'
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json()
    elif response.status_code == 404:
        return None
    else:
        print(f"GitHub API error: {response.status_code}")
        return None

def process_new_release(release):
    """Do something with a new release (same as webhook handler)."""
    repo_full_name = TARGET_REPO
    release_name = release.get('name') or release.get('tag_name')
    release_url = release.get('html_url')
    release_body = release.get('body', '')

    print(f"🎉 New release detected: {release_name} in {repo_full_name}")
    print(f"URL: {release_url}")
    print(f"Description: {release_body[:200]}...")

    discord_url = os.environ.get('https://discord.com/api/webhooks/1488683205690261514/7DrHP27K6kEAfbjiUwdWA-BOo7MRT0Yn1-FPsRqT1Z8fXQda56Flrzq7b0iIMZMTGwfs')
    if discord_url:
        data = {"content": f"New release: {release_name}\n{release_url}"}
        requests.post(discord_url, json=data)

def poll_for_releases():
    """Check GitHub API for new releases."""
    latest = get_latest_release_from_api()
    if not latest:
        return

    current_tag = latest.get('tag_name')
    # Load last known tag
    try:
        with open(STATE_FILE, 'r') as f:
            last_tag = f.read().strip()
    except FileNotFoundError:
        last_tag = None

    if current_tag and current_tag != last_tag:
        # New release found
        process_new_release(latest)
        # Update stored tag
        with open(STATE_FILE, 'w') as f:
            f.write(current_tag)

# Start the background scheduler
scheduler = BackgroundScheduler()
scheduler.add_job(func=poll_for_releases, trigger="interval", minutes=POLL_INTERVAL_MINUTES)
scheduler.start()

# Shut down the scheduler when exiting
import atexit
atexit.register(lambda: scheduler.shutdown())

# -------------------------------
# Webhook handler (same as before)
# -------------------------------
def verify_signature(payload_body, signature_header):
    if not SECRET:
        return True
    if not signature_header:
        return False
    hash_algorithm, signature = signature_header.split('=', 1)
    if hash_algorithm != 'sha256':
        return False
    mac = hmac.new(SECRET.encode(), msg=payload_body, digestmod=hashlib.sha256)
    expected_signature = mac.hexdigest()
    return hmac.compare_digest(expected_signature, signature)

@app.route('/webhook', methods=['POST'])
def webhook():
    raw_body = request.get_data()
    signature = request.headers.get('X-Hub-Signature-256')
    if not verify_signature(raw_body, signature):
        return jsonify({'error': 'Invalid signature'}), 401

    event_type = request.headers.get('X-GitHub-Event')
    if event_type != 'release':
        return jsonify({'message': 'Ignored'}), 200

    payload = request.get_json()
    action = payload.get('action')
    if action != 'published':
        return jsonify({'message': 'Ignored'}), 200

    repo_full_name = payload.get('repository', {}).get('full_name')
    if TARGET_REPO and repo_full_name != TARGET_REPO:
        return jsonify({'message': 'Ignored'}), 200

    release = payload.get('release', {})
    process_new_release(release)  # reuse same logic
    return jsonify({'message': 'OK'}), 200

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'}), 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 3000))
    app.run(host='0.0.0.0', port=port)