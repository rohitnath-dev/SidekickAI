import os
import re
from PIL import Image

def get_paths():
    # Find project root relative to this script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    
    return {
        'logo_png': os.path.join(project_root, 'frontend', 'public', 'logo.png'),
        'logo_jpg': os.path.join(project_root, 'frontend', 'public', 'logo.jpg'),
        'favicon_app': os.path.join(project_root, 'frontend', 'src', 'app', 'favicon.ico'),
        'favicon_public': os.path.join(project_root, 'frontend', 'public', 'favicon.ico'),
        'privacy_md': os.path.join(project_root, 'PRIVACY.md'),
        'terms_md': os.path.join(project_root, 'TERMS.md'),
        'legal_ts': os.path.join(project_root, 'frontend', 'src', 'config', 'legal.ts'),
        'legal_config_dir': os.path.join(project_root, 'frontend', 'src', 'config')
    }

def generate_favicons(paths):
    logo_path = paths['logo_png']
    logo_jpg_path = paths['logo_jpg']
    
    if not os.path.exists(logo_path):
        if os.path.exists(logo_jpg_path):
            print(f"logo.png not found, but logo.jpg exists. Converting {logo_jpg_path} to {logo_path}...")
            try:
                img = Image.open(logo_jpg_path)
                img.save(logo_path, format='PNG')
                print("Converted logo.jpg to logo.png successfully.")
            except Exception as e:
                print(f"Error converting logo.jpg to logo.png: {e}")
                return
        else:
            print(f"Error: Neither logo.png nor logo.jpg exists at {logo_path}")
            return

    # Generate favicons from logo.png
    try:
        img = Image.open(logo_path).convert("RGBA")
        
        # Ensure target directories exist
        os.makedirs(os.path.dirname(paths['favicon_app']), exist_ok=True)
        
        # Save as favicon.ico in both places
        img.resize((32, 32)).save(paths['favicon_app'], format='ICO')
        img.resize((32, 32)).save(paths['favicon_public'], format='ICO')
        print("Generated favicon.ico successfully.")
    except Exception as e:
        print(f"Error generating favicons: {e}")


def clean_inline_markdown(text: str) -> str:
    # Bold **text**
    text = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', text)
    # Code `text`
    text = re.sub(r'`(.*?)`', r'<code>\1</code>', text)
    # Links [text](url)
    text = re.sub(r'\[(.*?)\]\((.*?)\)', r'<a href="\2">\1</a>', text)
    # Escape quotes for TypeScript template string
    text = text.replace('`', '\\`').replace('${', '\\${')
    return text


def parse_markdown_file(md_path: str) -> dict:
    if not os.path.exists(md_path):
        print(f"Error: {md_path} does not exist.")
        return {"title": "", "effectiveDate": "", "html": ""}
        
    with open(md_path, "r", encoding="utf-8") as f:
        content = f.read()

    lines = content.splitlines()
    title = ""
    effective_date = ""
    html_parts = []
    
    in_list = False
    in_sub_list = False

    for line in lines:
        stripped = line.strip()
        
        # Extract title
        if line.startswith("# ") and not title:
            title = line[2:].strip()
            continue
            
        # Extract effective date
        if "Effective Date:" in line or "effective date" in line.lower():
            date_match = re.search(r'\*\*Effective Date:\*\*\s*(.*)', line, re.IGNORECASE)
            if date_match:
                effective_date = date_match.group(1).strip()
                continue
            
        if not stripped:
            continue
            
        if stripped == "---":
            if in_sub_list:
                html_parts.append("  </ul>")
                in_sub_list = False
            if in_list:
                html_parts.append("</ul>")
                in_list = False
            html_parts.append("<hr />")
            continue
            
        if stripped.startswith("## "):
            if in_sub_list:
                html_parts.append("  </ul>")
                in_sub_list = False
            if in_list:
                html_parts.append("</ul>")
                in_list = False
            html_parts.append(f"<h2>{clean_inline_markdown(stripped[3:])}</h2>")
            continue
            
        if stripped.startswith("### "):
            if in_sub_list:
                html_parts.append("  </ul>")
                in_sub_list = False
            if in_list:
                html_parts.append("</ul>")
                in_list = False
            html_parts.append(f"<h3>{clean_inline_markdown(stripped[4:])}</h3>")
            continue
            
        # List items
        if stripped.startswith("* ") or stripped.startswith("- "):
            indent = len(line) - len(line.lstrip())
            item_text = clean_inline_markdown(stripped[2:])
            
            if indent >= 2:
                if not in_sub_list:
                    html_parts.append("  <ul>")
                    in_sub_list = True
                html_parts.append(f"    <li>{item_text}</li>")
            else:
                if in_sub_list:
                    html_parts.append("  </ul>")
                    in_sub_list = False
                if not in_list:
                    html_parts.append("<ul>")
                    in_list = True
                html_parts.append(f"  <li>{item_text}</li>")
            continue
            
        # If it's a normal paragraph
        if in_sub_list:
            html_parts.append("  </ul>")
            in_sub_list = False
        if in_list:
            html_parts.append("</ul>")
            in_list = False
            
        html_parts.append(f"<p>{clean_inline_markdown(stripped)}</p>")
        
    if in_sub_list:
        html_parts.append("  </ul>")
    if in_list:
        html_parts.append("</ul>")
        
    return {
        "title": title,
        "effectiveDate": effective_date,
        "html": "\n".join(html_parts)
    }


def generate_legal_config(paths):
    privacy = parse_markdown_file(paths['privacy_md'])
    terms = parse_markdown_file(paths['terms_md'])
    
    os.makedirs(paths['legal_config_dir'], exist_ok=True)
    
    config_content = f"""// This file is auto-generated by scripts/generate_assets.py. Do not edit directly.
export const LEGAL_CONTENT = {{
  privacy: {{
    title: {repr(privacy["title"])},
    effectiveDate: {repr(privacy["effectiveDate"])},
    html: `{privacy["html"]}`
  }},
  terms: {{
    title: {repr(terms["title"])},
    effectiveDate: {repr(terms["effectiveDate"])},
    html: `{terms["html"]}`
  }}
}};
"""
    
    with open(paths['legal_ts'], 'w', encoding='utf-8') as f:
        f.write(config_content)
    print(f"Generated {paths['legal_ts']} successfully.")


if __name__ == '__main__':
    paths = get_paths()
    generate_favicons(paths)
    generate_legal_config(paths)
