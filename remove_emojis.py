#!/usr/bin/env python3
"""
Remove all emojis and icons from Slack notification template
"""

# Read the file
with open('enhanced_link_checker.py', 'r') as f:
    content = f.read()

# Find and replace the send_report_notification method
start_marker = '    def send_report_notification(self, broken_links: List[Dict], public_url: str, by_category: Dict[str, List[Dict]], total_checked: int = 0):'
end_marker = '    def _get_category_emoji(self, category: str) -> str:'

start_idx = content.find(start_marker)
end_idx = content.find(end_marker)

if start_idx != -1 and end_idx != -1:
    # Replace the entire method
    new_method = '''    def send_report_notification(self, broken_links: List[Dict], public_url: str, by_category: Dict[str, List[Dict]], total_checked: int = 0):
        """Send Slack notification with report summary and public URL."""
        if not self.config.enable_slack or not self.config.slack_webhook:
            self.logger.info("Slack notifications disabled or webhook not configured")
            return

        try:
            total_broken = len(broken_links)
            scan_date = datetime.now().strftime('%Y-%m-%d')

            # Category bullet list (no emojis)
            cat_lines = ""
            for category in sorted(by_category.keys()):
                count = len(by_category[category])
                # Simplify category names for cleaner display
                cat_name = category.replace('Sonatype ', '').replace('Nexus Repository', 'Nexus Repository')
                cat_lines += f"• {cat_name}: {count}\\n"

            # Key issues — identify patterns in broken links
            from collections import Counter
            domain_counts = Counter()

            for lnk in broken_links:
                url = lnk.get('url', '')

                # Track which domains/paths have issues
                if 'jenkins' in url.lower() or 'jfrog' in url.lower():
                    domain_counts['Jenkins & JFrog docs (404s)'] += 1
                elif 'support.sonatype.com' in url:
                    domain_counts['Sonatype Support articles'] += 1
                elif 'npmjs.com' in url:
                    domain_counts['npm documentation'] += 1
                elif 'github.com' in url:
                    domain_counts['GitHub references'] += 1
                elif 'http://https://' in url:
                    domain_counts['Malformed URLs (double protocol)'] += 1
                else:
                    domain_counts['Other broken links'] += 1

            # Get top issue domains
            if domain_counts:
                key_issues = ', '.join(f"{k}" for k, v in domain_counts.most_common(3))
            else:
                key_issues = "No specific patterns detected"

            checked_str = f"{total_checked:,}" if total_checked else "—"

            message = {
                "channel": self.config.slack_channel if self.config.slack_channel else None,
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": (
                                "Hi Team,\\n\\n"
                                "Just sharing this week's broken links scan results. "
                                "Whenever you get a chance, could you take a quick look at the links in your respective areas? "
                                "No rush — just something to keep on the radar as we continue to keep our docs in great shape."
                            )
                        }
                    },
                    {"type": "divider"},
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"{checked_str} links checked | {total_broken} broken found"
                        }
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"*By Category:*\\n{cat_lines.strip()}"
                        }
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"<{public_url}|View detailed report>"
                        }
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"*Key Issues:* {key_issues}"
                        }
                    },
                    {"type": "divider"},
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "Thanks so much for all you do! Feel free to reach out if you have any questions or need help investigating anything."
                        }
                    },
                    {
                        "type": "context",
                        "elements": [
                            {
                                "type": "mrkdwn",
                                "text": f"Scan date: {scan_date}"
                            }
                        ]
                    }
                ]
            }

            # Send to Slack
            response = requests.post(
                self.config.slack_webhook,
                json=message,
                headers={'Content-Type': 'application/json'},
                timeout=10
            )

            if response.status_code == 200:
                self.logger.info("✅ Slack notification sent successfully!")
            else:
                self.logger.error(f"Failed to send Slack notification: {response.status_code} {response.text}")

        except Exception as e:
            self.logger.error(f"Error sending Slack notification: {e}")

'''

    # Build new content
    new_content = content[:start_idx] + new_method + content[end_idx:]

    # Write back
    with open('enhanced_link_checker.py', 'w') as f:
        f.write(new_content)

    print("✅ Successfully removed all emojis and icons from Slack template!")
    print("\n📝 Updated template:")
    print("   - No emojis or icons")
    print("   - Clean, professional text-only format")
    print("   - Simplified links checked | broken found")
    print("   - Plain text category names")

else:
    print("❌ Could not find the send_report_notification method")
