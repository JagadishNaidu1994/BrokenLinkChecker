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
                    # Remove inline comments
                    value = value.split('#')[0].strip()
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


LOG_FILE = Path(__file__).parent / 'link_checker_enhanced.log'
PID_FILE = Path(__file__).parent / '.scanner.pid'


def _write_pid(pid: int):
    PID_FILE.write_text(str(pid))


def _read_pid() -> int | None:
    """Read PID from file and verify the process is still alive."""
    if not PID_FILE.exists():
        return None
    try:
        pid = int(PID_FILE.read_text().strip())
        os.kill(pid, 0)   # signal 0 = existence check only
        return pid
    except (ValueError, ProcessLookupError, PermissionError):
        PID_FILE.unlink(missing_ok=True)
        return None


def _clear_pid():
    PID_FILE.unlink(missing_ok=True)


def parse_log_line(line: str):
    """Parse a log line into a scanner event dict, or return None."""
    import re

    # Crawling a page
    m = re.search(r'Crawling .+?: (.+)', line)
    if m:
        return {'type': 'url', 'url': m.group(1).strip(), 'status': 'ok', 'label': 'CRAWL'}

    # Broken link  e.g.  ❌ BROKEN: https://... (404)
    m = re.search(r'BROKEN:\s+(\S+)\s+\((.+?)\)', line)
    if m:
        return {'type': 'url', 'url': m.group(1), 'status': m.group(2), 'label': 'BROKEN'}

    # Excluded link  e.g.  EXCLUDED: https://...
    m = re.search(r'EXCLUDED:\s+(\S+)', line)
    if m:
        return {'type': 'url', 'url': m.group(1), 'status': 'excluded', 'label': 'EXCL'}

    # Checked N/M links
    m = re.search(r'Checked (\d+)/(\d+) links', line)
    if m:
        checked, total = int(m.group(1)), int(m.group(2))
        pct = int(checked / total * 100) if total else 0
        return {'type': 'progress', 'checked': checked, 'total': total, 'percent': pct}

    # Check complete
    if 'Check Complete' in line or 'check complete' in line.lower():
        return {'type': 'complete'}

    # Starting crawl
    m = re.search(r'Starting crawl from:\s+(\S+)', line)
    if m:
        return {'type': 'url', 'url': m.group(1), 'status': 'start', 'label': 'START'}

    return None


def generate_scanner_stream():
    """Tail the log file and stream events as SSE."""
    import json, time, os

    yield f"data: {json.dumps({'type': 'heartbeat'})}\n\n"

    # Seek to current end of log (or beginning if new file)
    log_pos = LOG_FILE.stat().st_size if LOG_FILE.exists() else 0
    last_url_event = None  # dedupe consecutive duplicate url events

    while True:
        try:
            # Check if process is alive
            proc = subprocess.run(['pgrep', '-f', 'enhanced_link_checker.py'], capture_output=True)
            is_running = proc.returncode == 0

            if LOG_FILE.exists():
                current_size = LOG_FILE.stat().st_size
                if current_size > log_pos:
                    with open(LOG_FILE, 'r', errors='replace') as f:
                        f.seek(log_pos)
                        new_lines = f.read()
                        log_pos = f.tell()

                    for line in new_lines.splitlines():
                        event = parse_log_line(line)
                        if event:
                            # Drop exact duplicate url events (caused by double logger)
                            if event.get('type') == 'url':
                                key = (event.get('url'), event.get('status'))
                                if key == last_url_event:
                                    continue
                                last_url_event = key
                            yield f"data: {json.dumps(event)}\n\n"

            if not is_running:
                yield f"data: {json.dumps({'type': 'complete'})}\n\n"
                # Keep stream open for future scans, reset position
                while True:
                    time.sleep(2)
                    proc = subprocess.run(['pgrep', '-f', 'enhanced_link_checker.py'], capture_output=True)
                    if proc.returncode == 0:
                        # New scan started — seek to new end of log
                        log_pos = LOG_FILE.stat().st_size if LOG_FILE.exists() else 0
                        last_url_event = None
                        yield f"data: {json.dumps({'type': 'start'})}\n\n"
                        break
                    yield f": heartbeat\n\n"

            time.sleep(0.3)

        except GeneratorExit:
            break
        except Exception as e:
            print(f"SSE error: {e}")
            time.sleep(1)


@app.route('/api/scanner/stream')
def scanner_stream():
    """SSE endpoint for real-time scanner updates."""
    from flask import Response
    return Response(
        generate_scanner_stream(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no'
        }
    )


@app.route('/api/run-checker', methods=['POST'])
def run_checker():
    """Run the link checker."""
    try:
        script_path = Path(__file__).parent / 'enhanced_link_checker.py'

        # Truncate the log file so SSE only streams this run
        LOG_FILE.write_text('')

        with open(LOG_FILE, 'a') as log_out:
            process = subprocess.Popen(
                ['python3', str(script_path)],
                cwd=Path(__file__).parent,
                stdout=log_out,
                stderr=log_out
            )
        _write_pid(process.pid)

        return jsonify({'success': True, 'pid': process.pid})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/scanner/stop', methods=['POST'])
def scanner_stop():
    import signal
    pid = _read_pid()
    if not pid:
        return jsonify({'success': False, 'error': 'No scan running'})
    try:
        # Resume first so SIGTERM is delivered immediately (paused processes queue signals)
        try:
            os.kill(pid, signal.SIGCONT)
        except Exception:
            pass
        os.kill(pid, signal.SIGTERM)
        _clear_pid()
        return jsonify({'success': True})
    except Exception as e:
        _clear_pid()
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/scanner/pause', methods=['POST'])
def scanner_pause():
    import signal
    pid = _read_pid()
    if not pid:
        return jsonify({'success': False, 'error': 'No scan running'})
    try:
        os.kill(pid, signal.SIGSTOP)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/scanner/resume', methods=['POST'])
def scanner_resume():
    import signal
    pid = _read_pid()
    if not pid:
        return jsonify({'success': False, 'error': 'No scan running'})
    try:
        os.kill(pid, signal.SIGCONT)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


def _is_pid_paused(pid: int) -> bool:
    """Return True if the process exists but is stopped (SIGSTOP'd)."""
    try:
        with open(f'/proc/{pid}/status') as f:
            for line in f:
                if line.startswith('State:'):
                    return 'T' in line  # T = stopped/traced
    except Exception:
        pass
    # macOS fallback via ps
    try:
        out = subprocess.run(['ps', '-o', 'stat=', '-p', str(pid)],
                             capture_output=True, text=True)
        return 'T' in out.stdout
    except Exception:
        return False


@app.route('/api/checker-status', methods=['GET'])
def checker_status():
    """Check if the link checker is running."""
    try:
        pid = _read_pid()
        is_running = pid is not None
        is_paused = is_running and _is_pid_paused(pid)

        # Get latest report info
        reports_dir = Path(__file__).parent / 'reports'
        latest_report = None
        if reports_dir.exists():
            html_files = list(reports_dir.glob('broken_links_report_*.html'))
            if html_files:
                latest = max(html_files, key=lambda p: p.stat().st_mtime)
                latest_report = {
                    'name': latest.name,
                    'path': str(latest),
                    'timestamp': latest.stat().st_mtime
                }

        return jsonify({
            'is_running': is_running,
            'is_paused': is_paused,
            'latest_report': latest_report
        })
    except Exception as e:
        return jsonify({'is_running': False, 'is_paused': False, 'error': str(e)})


@app.route('/api/scanner/live-stats', methods=['GET'])
def scanner_live_stats():
    """Parse current log for live counters so frontend can restore after refresh."""
    import re
    stats = {'pages': 0, 'ok': 0, 'broken': 0, 'excluded': 0,
             'links_checked': 0, 'links_total': 0, 'percent': 0}
    if not LOG_FILE.exists():
        return jsonify(stats)
    try:
        seen_pages = set()
        seen_broken = set()
        seen_excluded = set()
        links_checked = 0
        links_total = 0
        with open(LOG_FILE, 'r', errors='replace') as f:
            for line in f:
                # Pages crawled — dedupe by URL to ignore double-logger duplicates
                m = re.search(r'Crawling \[\d+\] depth=\d+: (\S+)', line)
                if m:
                    seen_pages.add(m.group(1))
                    continue
                # Broken links — dedupe by URL
                m = re.search(r'BROKEN:\s+(\S+)', line)
                if m:
                    seen_broken.add(m.group(1))
                    continue
                # Excluded — dedupe by URL
                m = re.search(r'EXCLUDED:\s+(\S+)', line)
                if m:
                    seen_excluded.add(m.group(1))
                    continue
                # Progress — last value wins (already deduplicated by content)
                m = re.search(r'Checked (\d+)/(\d+) links', line)
                if m:
                    links_checked = int(m.group(1))
                    links_total = int(m.group(2))
        stats['pages'] = len(seen_pages)
        stats['broken'] = len(seen_broken)
        stats['excluded'] = len(seen_excluded)
        stats['ok'] = max(0, stats['pages'] - stats['broken'])
        stats['links_checked'] = links_checked
        stats['links_total'] = links_total
        stats['percent'] = int(links_checked / links_total * 100) if links_total else 0
    except Exception as e:
        stats['error'] = str(e)
    return jsonify(stats)


@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Get statistics from latest scan."""
    try:
        import re
        from datetime import datetime

        log_file = Path(__file__).parent / 'link_checker_enhanced.log'
        reports_dir = Path(__file__).parent / 'reports'

        stats = {
            'pages_crawled': 0,
            'total_links_scanned': 0,
            'broken_links': 0,
            'ignored_links': 0,
            'unique_links': 0,
            'scan_duration': '',
            'last_scan_time': '',
            'categories': {}
        }

        # Parse log file for latest scan
        if log_file.exists():
            with open(log_file, 'r') as f:
                log_content = f.read()

            # Find latest scan start
            start_matches = re.findall(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}).*Starting crawl', log_content)
            if start_matches:
                stats['last_scan_time'] = start_matches[-1]

            # Pages crawled
            crawl_match = re.search(r'Crawl complete: (\d+) pages visited', log_content)
            if crawl_match:
                stats['pages_crawled'] = int(crawl_match.group(1))

            # Links checked
            links_match = re.search(r'Checked (\d+)/(\d+) links', log_content)
            if links_match:
                stats['total_links_scanned'] = int(links_match.group(2))

            # Broken links by category
            category_matches = re.findall(r'(.*?):\s*(\d+)\s*broken links', log_content)
            for cat_match in category_matches:
                cat_name = cat_match[0].strip().replace('💻', '').replace('🔍', '').replace('📦', '').replace('🔗', '').strip()
                cat_count = int(cat_match[1])
                stats['categories'][cat_name] = cat_count
                stats['broken_links'] += cat_count

        # Get CSV report for more details
        if reports_dir.exists():
            csv_files = list(reports_dir.glob('broken_links_categorized_*.csv'))
            if csv_files:
                latest_csv = max(csv_files, key=lambda p: p.stat().st_mtime)
                import csv
                with open(latest_csv, 'r') as f:
                    reader = csv.reader(f)
                    next(reader)  # skip header
                    unique_broken = set()
                    for row in reader:
                        if len(row) >= 2:
                            unique_broken.add(row[1])  # broken link URL
                    stats['unique_links'] = len(unique_broken)

        # Estimate ignored links (total found - checked)
        config = load_env_config()
        exclude_patterns = config.get('EXCLUDE_PATTERNS', '').split(',')
        stats['ignored_patterns'] = len([p for p in exclude_patterns if p.strip()])

        return jsonify(stats)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    print("🚀 Starting Broken Link Checker Configuration UI")
    print("📝 Access the UI at: http://localhost:5000")
    print("Press Ctrl+C to stop")
    app.run(debug=True, host='0.0.0.0', port=5000)
