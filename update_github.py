#!/usr/bin/env python3
# 每日调用：把生成的 live.json 推到 GitHub（走 Contents API），GitHub Pages 自动部署 -> 零操作每日实时
# 由每日自动化在写好 app/live.json 后执行
import os, json, base64, ssl, urllib.request, urllib.error, urllib.parse, sys
ssl._create_default_https_context = ssl._create_unverified_context

APP_DIR = os.path.dirname(os.path.abspath(__file__))

def get_token():
    if os.environ.get('GH_TOKEN'):
        return os.environ['GH_TOKEN']
    p = os.path.join(APP_DIR, '.github_token')
    if os.path.exists(p):
        return open(p, encoding='utf-8').read().strip()
    raise SystemExit('缺少 GH_TOKEN')

USER = os.environ.get('GH_USER')
REPO = os.environ.get('GH_REPO', 'man-app')
BRANCH = os.environ.get('GH_BRANCH', 'main')
TOKEN = get_token()
lf = os.path.join(APP_DIR, 'live.json')
if not os.path.exists(lf):
    raise SystemExit('未发现 live.json，跳过推送')

def enc(p):
    return urllib.parse.quote(p, safe='')

ep = f"/repos/{USER}/{REPO}/contents/{enc('live.json')}"
H = {'Authorization': f'Bearer {TOKEN}', 'Content-Type': 'application/json', 'Accept': 'application/vnd.github+json'}
sha = None
try:
    with urllib.request.urlopen(f"https://api.github.com{ep}?ref={BRANCH}", timeout=30) as r:
        j = json.loads(r.read())
        sha = j.get('sha') if isinstance(j, dict) else None
except urllib.error.HTTPError as e:
    if e.code != 404:
        raise

b64 = base64.b64encode(open(lf, 'rb').read()).decode()
payload = {'message': 'daily: live.json update', 'content': b64, 'branch': BRANCH}
if sha:
    payload['sha'] = sha
req = urllib.request.Request(f"https://api.github.com{ep}", method='PUT', data=json.dumps(payload).encode(), headers=H)
try:
    urllib.request.urlopen(req, timeout=60); print('live.json pushed -> GitHub Pages 自动部署')
except Exception as e:
    print('push failed', e); sys.exit(1)
print('UPDATED')
