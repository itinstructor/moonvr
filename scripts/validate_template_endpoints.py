#!/usr/bin/env python3
"""Validate that endpoints referenced in templates via url_for(...) exist in the Flask app.

Usage:
    python scripts/validate_template_endpoints.py

Exits with code 0 if all endpoints exist, 1 if any missing.
"""
import re
import sys
from pathlib import Path

# Ensure project root is on sys.path so we can import main_app
project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Import app to collect endpoints
try:
    from main_app import app
except Exception as e:
    print(f"Failed to import app: {e}")
    sys.exit(2)

TEMPLATE_DIRS = [Path('templates'), Path('blog') / 'templates']
URLFOR_RE = re.compile(r"url_for\(\s*['\"]([^'\"]+)['\"]")

with app.app_context():
    registered = set(app.view_functions.keys())

missing = {}
for tdir in TEMPLATE_DIRS:
    if not tdir.exists():
        continue
    for p in tdir.rglob('*.html'):
        text = p.read_text(encoding='utf-8')
        for m in URLFOR_RE.finditer(text):
            endpoint = m.group(1)
            if endpoint not in registered:
                missing.setdefault(p.as_posix(), set()).add(endpoint)

if not missing:
    print('All template endpoints resolve against app.view_functions.')
    sys.exit(0)

print('Missing endpoints found in templates:')
for tpl, eps in missing.items():
    print(f'  {tpl}:')
    for e in sorted(eps):
        print(f'    - {e}')

sys.exit(1)
