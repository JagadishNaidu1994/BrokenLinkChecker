# Broken Links Checker

Automated broken link checker for Sonatype documentation with GitHub Pages hosting and Slack notifications.

## Features

- ✅ Crawls documentation sites and checks all links
- ✅ Categorizes broken links by product/team
- ✅ Generates HTML and CSV reports
- ✅ Uploads reports to GitHub Pages automatically
- ✅ Sends Slack notifications with summary table
- ✅ Runs automatically via GitHub Actions
- ✅ Excludes false positives (localhost, example URLs, etc.)

## Setup for GitHub Actions

### 1. Create a GitHub Repository

```bash
# Initialize git in your project directory
cd /path/to/BrokenLinkChecker
git init
git add .
git commit -m "Initial commit"

# Create GitHub repository and push
gh repo create BrokenLinkChecker --private --source=. --remote=origin --push
```

### 2. Configure GitHub Secrets

Go to your GitHub repository → Settings → Secrets and variables → Actions

Add the following secrets:

| Secret Name | Value | Example |
|------------|-------|---------|
| `DOCS_URLS` | Documentation URLs to check | `https://help.sonatype.com/index.html?lang=en` |
| `EXCLUDE_PATTERNS` | Regex patterns to exclude | `.*\.pdf$,.*\.zip$,.*repo1\.dso\.mil.*,.*localhost.*` |
| `SLACK_WEBHOOK_URL` | Your Slack webhook URL | `https://hooks.slack.com/services/...` |
| `GITHUB_USERNAME` | Your GitHub username for Pages repo | `jagadishbondada-glitch` |
| `GH_PAT` | GitHub Personal Access Token | `ghp_xxxxxxxxxxxx` |

### 3. Create GitHub Personal Access Token (PAT)

1. Go to GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic)
2. Click "Generate new token (classic)"
3. Give it a name: "Broken Links Checker"
4. Select scopes:
   - ✅ `repo` (Full control of private repositories)
   - ✅ `workflow` (Update GitHub Action workflows)
5. Click "Generate token"
6. Copy the token and add it as `GH_PAT` secret in your repo

### 4. GitHub Pages Repository

The workflow will automatically use the `broken-links-reports` repository for hosting.
Make sure it exists and GitHub Pages is enabled.

## Running the Checker

### Automated (GitHub Actions)

The checker runs automatically:
- **Schedule**: Daily at 9 AM UTC (customize in `.github/workflows/broken-links-checker.yml`)
- **Manual**: Go to Actions → Broken Links Checker → Run workflow

### Manual (Local)

```bash
# Install dependencies
pip install -r requirements.txt

# Run the checker
python3 enhanced_link_checker.py
```

## Configuration

Edit `.env` file or GitHub Secrets to customize:

```bash
# Crawl Settings
MAX_PAGES_PER_SITE=0           # 0 = unlimited
PARALLEL_WORKERS=100           # Number of concurrent checks

# Exclude Patterns (regex)
EXCLUDE_PATTERNS=.*\.pdf$,.*localhost.*,.*example\.com.*

# Notifications
ENABLE_SLACK_NOTIFICATIONS=true
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
```

## Reports

- **GitHub Pages**: https://[username].github.io/broken-links-reports/
- **Slack**: Notifications sent to configured webhook
- **CSV**: Available in `reports/` directory
- **Artifacts**: Download from GitHub Actions run page

## Schedule Customization

To change the run schedule, edit `.github/workflows/broken-links-checker.yml`:

```yaml
schedule:
  - cron: '0 9 * * *'  # Daily at 9 AM UTC
  # Examples:
  # - cron: '0 */6 * * *'    # Every 6 hours
  # - cron: '0 9 * * 1'      # Every Monday at 9 AM
  # - cron: '0 0 1 * *'      # First day of month at midnight
```

Use [crontab.guru](https://crontab.guru/) to help create cron expressions.

## Troubleshooting

### Workflow fails with "Permission denied"
- Ensure `GH_PAT` token has correct permissions
- Check that the token hasn't expired

### No Slack notifications
- Verify `SLACK_WEBHOOK_URL` is correct
- Test webhook: `curl -X POST -H 'Content-type: application/json' --data '{"text":"Test"}' YOUR_WEBHOOK_URL`

### GitHub Pages not updating
- Check that `broken-links-reports` repository exists
- Verify GitHub Pages is enabled in repository settings
- Wait 1-2 minutes for GitHub Pages to build

## Development

### Test locally before pushing

```bash
# Test with a smaller crawl limit
MAX_PAGES_PER_SITE=10 python3 enhanced_link_checker.py

# Check specific URL
DOCS_URLS=https://help.sonatype.com/en/some-page.html python3 enhanced_link_checker.py
```

## License

Internal use only - Sonatype

## Support

For issues or questions, contact the Documentation team or file an issue in this repository.
