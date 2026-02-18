"""
Short-Form Script Generator — Backend
Flask API that:
  1. Accepts a YouTube URL
  2. Fetches the transcript via youtube-transcript-api
  3. Builds the system prompt by reading your .md files from /prompts/
  4. Sends everything to Claude and returns 5 formatted scripts
  5. Optionally exports to Google Docs
"""

import os
import re
import json
from pathlib import Path
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)


# ─────────────────────────────────────────────
# LOAD SYSTEM PROMPT FROM YOUR MARKDOWN FILES
# ─────────────────────────────────────────────

def load_system_prompt() -> str:
    """
    Reads all .md files from the /prompts directory and combines them
    into a single system prompt that gets sent to Claude on every request.

    To update the writing rules: edit the .md files in /prompts/ and redeploy.
    To add new expertise: drop another .md file into /prompts/ — it gets picked up automatically.
    """
    prompts_dir = Path(__file__).parent / "prompts"

    if not prompts_dir.exists():
        raise RuntimeError(
            f"No /prompts directory found at {prompts_dir}. "
            "Create it and add your markdown instruction files."
        )

    md_files = sorted(prompts_dir.glob("*.md"))

    if not md_files:
        raise RuntimeError(
            "No .md files found in /prompts/. "
            "Add your PROJECT_INSTRUCTIONS.md and MASTERCLASS.md files there."
        )

    parts = []
    for f in md_files:
        content = f.read_text(encoding="utf-8").strip()
        parts.append(f"# {f.stem}\n\n{content}")
        print(f"  ✓ Loaded prompt file: {f.name} ({len(content):,} chars)")

    combined = "\n\n---\n\n".join(parts)
    print(f"\n✅ System prompt built from {len(md_files)} file(s) — {len(combined):,} total chars\n")
    return combined


# Load once at startup — cached for all requests
print("\nLoading writing framework from /prompts/...")
try:
    SYSTEM_PROMPT = load_system_prompt()
except RuntimeError as e:
    print(f"⚠️  WARNING: {e}")
    SYSTEM_PROMPT = "You are a short-form video script writer. Generate 5 script variations from the transcript."


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def extract_video_id(url: str) -> str | None:
    patterns = [
        r'(?:youtube\.com/watch\?.*v=)([a-zA-Z0-9_-]{11})',
        r'(?:youtu\.be/)([a-zA-Z0-9_-]{11})',
        r'(?:youtube\.com/shorts/)([a-zA-Z0-9_-]{11})',
        r'^([a-zA-Z0-9_-]{11})$',
    ]
    for p in patterns:
        m = re.search(p, url.strip())
        if m:
            return m.group(1)
    return None


def fetch_transcript(video_id: str) -> str:
    from youtube_transcript_api import YouTubeTranscriptApi
    entries = YouTubeTranscriptApi.get_transcript(video_id)
    return ' '.join(re.sub(r'\s+', ' ', e['text']) for e in entries).strip()


def generate_scripts(transcript: str) -> str:
    import anthropic
    client = anthropic.Anthropic(api_key=os.environ['ANTHROPIC_API_KEY'])

    message = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=4096,
        system=SYSTEM_PROMPT,  # ← your full markdown knowledge, loaded from /prompts/
        messages=[{
            "role": "user",
            "content": (
                "Here is the transcript. "
                "Apply your full writing framework and generate the five scripts now.\n\n"
                "---\n\n"
                f"{transcript}"
            )
        }]
    )
    return message.content[0].text


def push_to_google_docs(title: str, content: str, access_token: str) -> str:
    """Creates a Google Doc and returns the URL."""
    import requests

    doc_resp = requests.post(
        'https://docs.googleapis.com/v1/documents',
        headers={'Authorization': f'Bearer {access_token}', 'Content-Type': 'application/json'},
        json={'title': title}
    )
    doc_resp.raise_for_status()
    doc_id = doc_resp.json()['documentId']

    requests_body = build_doc_requests(content)
    if requests_body:
        update_resp = requests.post(
            f'https://docs.googleapis.com/v1/documents/{doc_id}:batchUpdate',
            headers={'Authorization': f'Bearer {access_token}', 'Content-Type': 'application/json'},
            json={'requests': requests_body}
        )
        update_resp.raise_for_status()

    return f'https://docs.google.com/document/d/{doc_id}/edit'


def build_doc_requests(content: str) -> list:
    """Parses the 5-script markdown and builds Google Docs API formatting requests."""
    reqs = []
    index = 1

    def insert(text, heading=None, bold=False, color=None):
        nonlocal index
        end = index + len(text)
        reqs.append({'insertText': {'location': {'index': index}, 'text': text}})

        if heading:
            reqs.append({
                'updateParagraphStyle': {
                    'range': {'startIndex': index, 'endIndex': end},
                    'paragraphStyle': {'namedStyleType': heading},
                    'fields': 'namedStyleType'
                }
            })
        else:
            style = {}
            if bold: style['bold'] = True
            if color: style['foregroundColor'] = {'color': {'rgbColor': color}}
            if style:
                reqs.append({
                    'updateTextStyle': {
                        'range': {'startIndex': index, 'endIndex': end},
                        'textStyle': style,
                        'fields': ','.join(style.keys())
                    }
                })
        index = end

    for line in content.split('\n'):
        if line.startswith('## V'):
            insert(line.lstrip('# ') + '\n', heading='HEADING_1')
        elif line.startswith('### '):
            insert(line.lstrip('# ') + '\n', heading='HEADING_2')
        elif line.strip() == '---':
            insert('─────────────────────────────\n',
                   color={'red': 0.8, 'green': 0.8, 'blue': 0.8})
        elif line.startswith('[PERSONAL STORY SLOT'):
            insert(line + '\n',
                   color={'red': 0.9, 'green': 0.6, 'blue': 0.0}, bold=True)
        elif line.strip():
            insert(line + '\n')
        else:
            insert('\n')

    return reqs


# ─────────────────────────────────────────────
# ROUTES
# ─────────────────────────────────────────────

@app.route('/health', methods=['GET'])
def health():
    """Shows which prompt files are loaded — useful for debugging."""
    prompts_dir = Path(__file__).parent / "prompts"
    files = [f.name for f in sorted(prompts_dir.glob("*.md"))] if prompts_dir.exists() else []
    return jsonify({
        'status': 'ok',
        'prompt_files_loaded': files,
        'system_prompt_chars': len(SYSTEM_PROMPT)
    })


@app.route('/generate', methods=['POST'])
def generate():
    data = request.get_json()
    url = data.get('url', '').strip()
    access_token = data.get('access_token')

    if not url:
        return jsonify({'error': 'No URL provided'}), 400

    video_id = extract_video_id(url)
    if not video_id:
        return jsonify({'error': 'Could not parse a valid YouTube video ID from that URL.'}), 400

    # Fetch transcript
    try:
        transcript = fetch_transcript(video_id)
    except Exception as e:
        err = str(e)
        if 'disabled' in err.lower():
            return jsonify({'error': 'Transcripts are disabled for this video.'}), 400
        if 'no transcript' in err.lower():
            return jsonify({'error': 'No transcript found. The video may not have captions.'}), 400
        return jsonify({'error': f'Transcript error: {err}'}), 500

    # Generate scripts
    try:
        scripts = generate_scripts(transcript)
    except Exception as e:
        return jsonify({'error': f'Script generation failed: {str(e)}'}), 500

    result = {'video_id': video_id, 'scripts': scripts, 'doc_url': None}

    # Push to Google Docs if token provided
    if access_token:
        try:
            title = f"Scripts — youtube.com/watch?v={video_id}"
            result['doc_url'] = push_to_google_docs(title, scripts, access_token)
        except Exception as e:
            result['doc_warning'] = f'Google Docs export failed: {str(e)}'

    return jsonify(result)


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"✅  Script Generator API running → http://localhost:{port}\n")
    app.run(host='0.0.0.0', port=port, debug=False)
