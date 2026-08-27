#!/usr/bin/env python3
"""
Update HTML report template to use Sonatype Design System colors
"""
import re

# Read the new template
with open('sonatype_report_template.html', 'r') as f:
    new_template = f.read()

# Read the current script
with open('enhanced_link_checker.py', 'r') as f:
    content = f.read()

# Find the HTML template section and replace it
# Pattern: from html_content = f""" to the closing """
pattern = r'(html_content = f""")[^"]*?(""")'

# Read the template and format it properly for Python f-string
template_lines = new_template.split('\n')
formatted_template = '\n'.join(template_lines)

# Replace the template
match = re.search(pattern, content, re.DOTALL)
if match:
    # Extract parts
    before = content[:match.start()]
    after = content[match.end():]

    # Insert new template
    updated_content = before + f'html_content = f"""{formatted_template}"""' + after

    # Write back
    with open('enhanced_link_checker.py', 'w') as f:
        f.write(updated_content)

    print("✅ Successfully updated HTML template with Sonatype Design System colors!")
    print("🎨 New features:")
    print("   - Blue gradient header with tomato accent")
    print("   - Radix UI color palette")
    print("   - Inter font family")
    print("   - Gradient stat cards")
    print("   - Modern shadows and hover effects")
    print("   - Responsive design")
else:
    print("❌ Could not find HTML template in the file")
