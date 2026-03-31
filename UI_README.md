# Configuration UI

A web-based interface to manage the Broken Link Checker configuration.

## Features

- ✅ **Toggle Settings**: Enable/disable notifications, external link checking, etc.
- ✅ **Manage Exclusion Patterns**: Add, edit, or remove URL patterns to ignore
- ✅ **Edit All Settings**: Documentation URLs, crawl depth, parallel workers, timeouts
- ✅ **Slack Configuration**: Set webhook URL and target channel
- ✅ **GitHub Pages Settings**: Configure auto-upload settings
- ✅ **Git Integration**: Save and push changes directly to Git

## How to Use

### 1. Start the UI

```bash
./start_ui.sh
```

Or manually:

```bash
python3 config_ui.py
```

### 2. Access the UI

Open your browser and navigate to:

```
http://localhost:5000
```

### 3. Make Changes

- Toggle switches for enabling/disabling features
- Edit text fields for URLs, timeouts, workers, etc.
- Add/remove exclusion patterns
- Click **Save Configuration** to save locally
- Click **Save & Push to Git** to save and commit changes

## Configuration Sections

### 📄 Documentation URLs
- URLs to check for broken links

### ⚙️ Crawl Settings
- Max crawl depth
- Max pages per site
- Max links to check
- Parallel workers
- Request timeout
- Follow/check external links

### 🚫 Exclusion Patterns
- Add regex patterns to skip specific URLs
- Examples:
  - `.*\.pdf$` - Skip PDF files
  - `.*cdn-cgi/l/email-protection.*` - Skip Cloudflare email protection
  - `.*localhost.*` - Skip localhost URLs

### 🔔 Notifications
- Desktop notifications toggle
- Slack notifications toggle
- Slack webhook URL
- Slack channel
- Minimum broken links for alert
- Notify on completion

### 📦 GitHub Pages
- Auto-upload reports toggle
- Repository name
- GitHub username

## Notes

- Changes are saved to `.env` file locally
- Workflow file (`.github/workflows/broken-links-checker.yml`) is updated for Slack settings
- Use "Save & Push to Git" to commit and push changes to remote repository
- The UI runs on port 5000 by default
- Press Ctrl+C in terminal to stop the UI server

## Requirements

- Python 3.x
- Flask (`pip install flask`)
- Git (for push functionality)

## Security

⚠️ **Important**: The UI is for local use only. Do not expose it to the internet as it has no authentication and can modify your configuration files.
