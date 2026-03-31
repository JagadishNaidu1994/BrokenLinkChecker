#!/usr/bin/env python3
"""
Configuration UI for Broken Link Checker
A simple web interface to manage settings and exclusion patterns
"""

import os
import json
import subprocess
from pathlib import Path
from flask import Flask, render_template, request, jsonify
from typing import Dict, Any

app = Flask(__name__)

ENV_FILE = Path(__file__).parent / '.env'
WORKFLOW_FILE = Path(__file__).parent / '.github/workflows/broken-links-checker.yml'


def load_env_config() -> Dict[str, Any]:
    """Load configuration from .env file."""
    config = {}

    if ENV_FILE.exists():
        with open(ENV_FILE, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    config[key] = value

    return config


def save_env_config(config: Dict[str, Any]) -> bool:
    """Save configuration to .env file."""
    try:
        # Read existing file to preserve comments
        lines = []
        section_map = {}
        current_section = None

        if ENV_FILE.exists():
            with open(ENV_FILE, 'r') as f:
                for line in f:
                    stripped = line.strip()
                    if stripped.startswith('#') and not stripped.startswith('# '):
                        # Section header
                        current_section = stripped
                        section_map[current_section] = []
                    elif '=' in stripped and not stripped.startswith('#'):
                        key = stripped.split('=', 1)[0]
                        if current_section:
                            section_map[current_section].append(key)

        # Write updated config
        with open(ENV_FILE, 'w') as f:
            f.write("# Broken Link Checker Configuration\n\n")

            # Documentation URLs
            f.write("# Documentation URLs to check (comma-separated)\n")
            f.write(f"DOCS_URLS={config.get('DOCS_URLS', '')}\n\n")

            # Crawl Settings
            f.write("# Crawl Settings\n")
            f.write(f"MAX_CRAWL_DEPTH={config.get('MAX_CRAWL_DEPTH', '4')}\n")
            f.write(f"MAX_PAGES_PER_SITE={config.get('MAX_PAGES_PER_SITE', '0')}\n")
            f.write(f"MAX_LINKS_TO_CHECK={config.get('MAX_LINKS_TO_CHECK', '0')}\n")
            f.write(f"FOLLOW_EXTERNAL_LINKS={config.get('FOLLOW_EXTERNAL_LINKS', 'false')}\n")
            f.write(f"CHECK_EXTERNAL_LINKS={config.get('CHECK_EXTERNAL_LINKS', 'false')}\n")
            f.write(f"REQUEST_TIMEOUT_SECONDS={config.get('REQUEST_TIMEOUT_SECONDS', '10')}\n")
            f.write(f"PARALLEL_WORKERS={config.get('PARALLEL_WORKERS', '100')}\n\n")

            # Exclude Patterns
            f.write("# Exclude Patterns (regex, comma-separated)\n")
            f.write("# Skip URLs matching these patterns\n")
            f.write(f"EXCLUDE_PATTERNS={config.get('EXCLUDE_PATTERNS', '')}\n\n")

            # Notification Settings
            f.write("# Notification Settings\n")
            f.write(f"ENABLE_DESKTOP_NOTIFICATIONS={config.get('ENABLE_DESKTOP_NOTIFICATIONS', 'true')}\n")
            f.write(f"ENABLE_SLACK_NOTIFICATIONS={config.get('ENABLE_SLACK_NOTIFICATIONS', 'false')}\n")
            f.write(f"NOTIFICATION_SOUND={config.get('NOTIFICATION_SOUND', 'Glass')}\n\n")

            # Slack Settings
            f.write("# Slack Settings\n")
            f.write(f"SLACK_WEBHOOK_URL={config.get('SLACK_WEBHOOK_URL', '')}\n")
            f.write(f"SLACK_CHANNEL={config.get('SLACK_CHANNEL', '')}\n\n")

            # GitHub Pages Settings
            f.write("# GitHub Pages Settings\n")
            f.write(f"ENABLE_GITHUB_UPLOAD={config.get('ENABLE_GITHUB_UPLOAD', 'true')}\n")
            f.write(f"GITHUB_REPO_NAME={config.get('GITHUB_REPO_NAME', 'broken-links-reports')}\n")
            f.write(f"GITHUB_USERNAME={config.get('GITHUB_USERNAME', '')}\n\n")

            # Alert Thresholds
            f.write("# Alert Thresholds\n")
            f.write(f"MIN_BROKEN_LINKS_FOR_ALERT={config.get('MIN_BROKEN_LINKS_FOR_ALERT', '1')}\n")
            f.write(f"NOTIFY_ON_COMPLETION={config.get('NOTIFY_ON_COMPLETION', 'true')}\n\n")

            # Scheduled Mode
            f.write("# Scheduled Mode\n")
            f.write(f"CHECK_INTERVAL_HOURS={config.get('CHECK_INTERVAL_HOURS', '24')}\n")

        return True
    except Exception as e:
        print(f"Error saving config: {e}")
        return False


def update_workflow_config(slack_enabled: bool) -> bool:
    """Update GitHub workflow with Slack notification setting."""
    try:
        if not WORKFLOW_FILE.exists():
            return False

        with open(WORKFLOW_FILE, 'r') as f:
            content = f.read()

        # Replace ENABLE_SLACK_NOTIFICATIONS line
        import re
        pattern = r'ENABLE_SLACK_NOTIFICATIONS=(true|false)'
        replacement = f'ENABLE_SLACK_NOTIFICATIONS={str(slack_enabled).lower()}'
        new_content = re.sub(pattern, replacement, content)

        with open(WORKFLOW_FILE, 'w') as f:
            f.write(new_content)

        return True
    except Exception as e:
        print(f"Error updating workflow: {e}")
        return False


@app.route('/')
def index():
    """Render the configuration UI."""
    return render_template('config.html')


@app.route('/api/config', methods=['GET'])
def get_config():
    """Get current configuration."""
    config = load_env_config()

    # Parse exclude patterns into a list
    exclude_patterns = config.get('EXCLUDE_PATTERNS', '').split(',')
    exclude_patterns = [p.strip() for p in exclude_patterns if p.strip()]

    return jsonify({
        'docs_urls': config.get('DOCS_URLS', ''),
        'max_crawl_depth': config.get('MAX_CRAWL_DEPTH', '4'),
        'max_pages_per_site': config.get('MAX_PAGES_PER_SITE', '0'),
        'max_links_to_check': config.get('MAX_LINKS_TO_CHECK', '0'),
        'follow_external_links': config.get('FOLLOW_EXTERNAL_LINKS', 'false') == 'true',
        'check_external_links': config.get('CHECK_EXTERNAL_LINKS', 'false') == 'true',
        'request_timeout': config.get('REQUEST_TIMEOUT_SECONDS', '10'),
        'parallel_workers': config.get('PARALLEL_WORKERS', '100'),
        'exclude_patterns': exclude_patterns,
        'enable_desktop_notifications': config.get('ENABLE_DESKTOP_NOTIFICATIONS', 'true') == 'true',
        'enable_slack_notifications': config.get('ENABLE_SLACK_NOTIFICATIONS', 'false') == 'true',
        'slack_webhook_url': config.get('SLACK_WEBHOOK_URL', ''),
        'slack_channel': config.get('SLACK_CHANNEL', ''),
        'enable_github_upload': config.get('ENABLE_GITHUB_UPLOAD', 'true') == 'true',
        'github_repo_name': config.get('GITHUB_REPO_NAME', ''),
        'github_username': config.get('GITHUB_USERNAME', ''),
        'min_broken_links_alert': config.get('MIN_BROKEN_LINKS_FOR_ALERT', '1'),
        'notify_on_completion': config.get('NOTIFY_ON_COMPLETION', 'true') == 'true',
    })


@app.route('/api/config', methods=['POST'])
def save_config():
    """Save configuration."""
    data = request.json

    # Convert exclude patterns list to comma-separated string
    exclude_patterns = ','.join(data.get('exclude_patterns', []))

    config = {
        'DOCS_URLS': data.get('docs_urls', ''),
        'MAX_CRAWL_DEPTH': str(data.get('max_crawl_depth', '4')),
        'MAX_PAGES_PER_SITE': str(data.get('max_pages_per_site', '0')),
        'MAX_LINKS_TO_CHECK': str(data.get('max_links_to_check', '0')),
        'FOLLOW_EXTERNAL_LINKS': 'true' if data.get('follow_external_links', False) else 'false',
        'CHECK_EXTERNAL_LINKS': 'true' if data.get('check_external_links', False) else 'false',
        'REQUEST_TIMEOUT_SECONDS': str(data.get('request_timeout', '10')),
        'PARALLEL_WORKERS': str(data.get('parallel_workers', '100')),
        'EXCLUDE_PATTERNS': exclude_patterns,
        'ENABLE_DESKTOP_NOTIFICATIONS': 'true' if data.get('enable_desktop_notifications', True) else 'false',
        'ENABLE_SLACK_NOTIFICATIONS': 'true' if data.get('enable_slack_notifications', False) else 'false',
        'SLACK_WEBHOOK_URL': data.get('slack_webhook_url', ''),
        'SLACK_CHANNEL': data.get('slack_channel', ''),
        'ENABLE_GITHUB_UPLOAD': 'true' if data.get('enable_github_upload', True) else 'false',
        'GITHUB_REPO_NAME': data.get('github_repo_name', ''),
        'GITHUB_USERNAME': data.get('github_username', ''),
        'MIN_BROKEN_LINKS_FOR_ALERT': str(data.get('min_broken_links_alert', '1')),
        'NOTIFY_ON_COMPLETION': 'true' if data.get('notify_on_completion', True) else 'false',
        'CHECK_INTERVAL_HOURS': '24',
    }

    # Save to .env
    if not save_env_config(config):
        return jsonify({'success': False, 'error': 'Failed to save configuration'}), 500

    # Update workflow file
    slack_enabled = data.get('enable_slack_notifications', False)
    update_workflow_config(slack_enabled)

    return jsonify({'success': True})


@app.route('/api/git/commit', methods=['POST'])
def git_commit_push():
    """Commit and push changes to git."""
    try:
        data = request.json
        commit_message = data.get('message', 'Update configuration via UI')

        # Git commands
        subprocess.run(['git', 'add', '.env', '.github/workflows/broken-links-checker.yml'],
                      check=True, cwd=Path(__file__).parent)
        subprocess.run(['git', 'commit', '-m', f'{commit_message}\n\nCo-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>'],
                      check=True, cwd=Path(__file__).parent)
        subprocess.run(['git', 'push'], check=True, cwd=Path(__file__).parent)

        return jsonify({'success': True})
    except subprocess.CalledProcessError as e:
        return jsonify({'success': False, 'error': str(e)}), 500


if __name__ == '__main__':
    print("🚀 Starting Broken Link Checker Configuration UI")
    print("📝 Access the UI at: http://localhost:5000")
    print("Press Ctrl+C to stop")
    app.run(debug=True, host='0.0.0.0', port=5000)
