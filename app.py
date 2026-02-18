"""
Short-Form Script Generator — Backend
Flask API that:
  1. Accepts a YouTube URL
  2. Fetches the transcript via youtube-transcript-api
  3. Sends it to Claude with your full writing system prompt
  4. Returns 5 formatted scripts
  5. Optionally exports to Google Docs
"""

import os
import re
import json
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# ─────────────────────────────────────────────
# SYSTEM PROMPT — built from your markdown files
# ─────────────────────────────────────────────

SYSTEM_PROMPT = """
You are a short-form video script writer. Your job is to take a video transcript and produce five ready-to-film script variations in a specific format.

You do not summarise transcripts. You do not give feedback or analysis unless asked. You read the transcript, extract the single highest-value insight, and produce five scripts. That is the output.

---

## What You Are Doing and Why

The person using this tool is building a social media following to grow a service business. They are not a recognised authority yet. Their strategy is the **Messenger Voice** — positioning themselves as someone who finds high-value ideas and passes them on, rather than claiming to be the expert themselves. Every script you write must reflect this positioning.

---

## Step One: Read the Transcript and Find the One Thing

Before writing a single word, identify:

1. The single highest-value insight — not the topic, the specific idea that would make someone stop scrolling. Usually it is buried. Find it.
2. The best specific, concrete, falsifiable line in the transcript — a number, a comparison, a counterintuitive claim. This is likely your hook material.
3. Which viewer this is really for — not a demographic, a specific person with a specific problem. Name the problem.
4. Any personal story or lived experience in the transcript that you cannot use verbatim — flag these for substitution.

Do not output this analysis. Use it internally to write better scripts.

---

## Step Two: Apply the Three Copy Rules to Every Line You Write

Run every sentence through these three filters. If a sentence fails, rewrite it before moving on.

**Rule 1 — Can I visualise it?**
Close your eyes. Can you see it? Abstract language disappears. Concrete language sticks. If a sentence is vague, zoom in — keep asking "what do I actually mean?" until you hit something specific enough to picture.

**Rule 2 — Can I falsify it?**
Is this claim true or false? Vague claims create no tension. Specific, falsifiable claims create credibility because the person making them is willing to be wrong. Replace adjectives with facts.

**Rule 3 — Could nobody else say this?**
If a competitor could film this exact script, it is not specific enough. The angle, the framing, the source, the example — something must be unique to the person using this tool.

Kaplan's Law: Every word not working for you is working against you. Cut anything that does not earn its place.

---

## Step Three: Write in the Messenger Voice

Every script uses one of four Messenger Voice frames. Choose the one that fits the content naturally.

**The Overheard Frame** — you encountered this in a video, book, or interview and you're passing it on.
**The Conversation Frame** — this came up in a real or representative conversation.
**The Personal Discovery Frame** — you went looking for an answer and found this.
**The Passing It On Frame** — direct and honest.

Rules:
- Always credit the source by type even if not by name.
- Never claim to have lived an experience you haven't.
- After delivering the idea, add your own "here's why this matters" commentary.

---

## Step Four: Write the Five Variations

**V1 — Hot Take Hook:** Open with a contrarian or surprising claim.
**V2 — Data/Insight Hook:** Open with a specific, falsifiable number or finding.
**V3 — Story Hook:** Open with one concrete moment — a person, a situation, a specific event.
**V4 — Question Hook:** Open with a question that creates a loop the viewer needs to close.
**V5 — Preview Hook:** Tell them exactly what they're about to get.

---

## Step Five: Format Every Script

Every script uses this exact five-section format. No exceptions.

---

### HOOK
1–3 sentences maximum. Topic clarity + on-target curiosity + contrast. Delivered in the Messenger Voice.

Hook rules:
- Topic arrives on line one. Never after.
- "You/your" framing, not "I/my"
- Short sentences. One idea each. Dense.
- Contrast must be present — stated (A vs B) or implied (B only, viewer infers A)

---

### VISUAL HOOK
What appears on screen. Two components:
1. **Text overlay** — 3 to 5 bold words that work as a hook even with sound off
2. **Opening visual** — what the camera sees. Describe it specifically.

---

### BODY
The content. Written as individual lines, not paragraphs — each line is one thought, filmed as one breath.

Body rules:
- Reverse reveal structure where possible
- "But" and "therefore" connect ideas. Never "and then"
- Each point opens a loop and closes it before the next one opens
- No jargon unless it is the viewer's own jargon
- Personal Story Slots flagged clearly

When a Personal Story Slot is needed, use this format:
[PERSONAL STORY SLOT — Function: [what this story does]. Substitute: one sentence, specific and visual, from your own experience. E.g. "[example of the type of moment needed]." One line only.]

---

### CLOSE
No wind-down. No summary. No "so that's it" or "hope this helped."
Two options only: Hard stop (land the final insight and cut) OR Hook-curiosity-action.

---

## Output Format

Present all five variations in order. For each one use EXACTLY this format:

---

## V[number] — [Hook Type Name]

### HOOK
[hook lines]

### VISUAL HOOK
**Text overlay:** [3-5 bold words]
**Opening visual:** [specific camera direction]

### BODY
[body lines — one thought per line, blank line between beats]

### CLOSE
[close lines]

---

No preamble. No analysis. No explanation of what you did. Just the five scripts, starting immediately with "---" then "## V1 — Hot Take Hook".
"""

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
        system=SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": f"Here is the transcript. Generate the five scripts now.\n\n---\n\n{transcript}"
        }]
    )
    return message.content[0].text


def push_to_google_docs(title: str, content: str, access_token: str) -> str:
    """
    Creates a Google Doc and returns the URL.
    Requires an OAuth2 access token from the frontend Google Sign-In.
    """
    import requests

    # 1. Create the document
    doc_resp = requests.post(
        'https://docs.googleapis.com/v1/documents',
        headers={'Authorization': f'Bearer {access_token}', 'Content-Type': 'application/json'},
        json={'title': title}
    )
    doc_resp.raise_for_status()
    doc_id = doc_resp.json()['documentId']
    doc_url = f'https://docs.google.com/document/d/{doc_id}/edit'

    # 2. Build batchUpdate requests to style the content
    requests_body = build_doc_requests(content)

    if requests_body:
        update_resp = requests.post(
            f'https://docs.googleapis.com/v1/documents/{doc_id}:batchUpdate',
            headers={'Authorization': f'Bearer {access_token}', 'Content-Type': 'application/json'},
            json={'requests': requests_body}
        )
        update_resp.raise_for_status()

    return doc_url


def build_doc_requests(content: str) -> list:
    """
    Parses the 5-script markdown content and builds Google Docs API requests
    that format it cleanly: headings for V1–V5, section labels, body text.
    """
    requests = []
    index = 1  # Google Docs text index starts at 1

    def insert_text(text, heading_style=None, bold=False, font_size=None, color=None):
        nonlocal index
        end = index + len(text)

        requests.append({
            'insertText': {
                'location': {'index': index},
                'text': text
            }
        })

        style = {}
        if bold:
            style['bold'] = True
        if font_size:
            style['fontSize'] = {'magnitude': font_size, 'unit': 'PT'}
        if color:
            style['foregroundColor'] = {'color': {'rgbColor': color}}

        if heading_style:
            requests.append({
                'updateParagraphStyle': {
                    'range': {'startIndex': index, 'endIndex': end},
                    'paragraphStyle': {'namedStyleType': heading_style},
                    'fields': 'namedStyleType'
                }
            })
        elif style:
            requests.append({
                'updateTextStyle': {
                    'range': {'startIndex': index, 'endIndex': end},
                    'textStyle': style,
                    'fields': ','.join(style.keys())
                }
            })

        index = end

    lines = content.split('\n')
    i = 0
    while i < len(lines):
        line = lines[i]

        if line.startswith('## V'):
            insert_text(line.lstrip('# ') + '\n', heading_style='HEADING_1')
        elif line.startswith('### '):
            insert_text(line.lstrip('# ') + '\n', heading_style='HEADING_2')
        elif line.startswith('**') and line.endswith('**'):
            insert_text(line.strip('*') + '\n', bold=True)
        elif line.strip() == '---':
            insert_text('─────────────────────────────\n',
                        color={'red': 0.8, 'green': 0.8, 'blue': 0.8})
        elif line.startswith('[PERSONAL STORY SLOT'):
            insert_text(line + '\n',
                        color={'red': 0.9, 'green': 0.6, 'blue': 0.0}, bold=True)
        elif line.strip():
            insert_text(line + '\n')
        else:
            insert_text('\n')

        i += 1

    return requests


# ─────────────────────────────────────────────
# ROUTES
# ─────────────────────────────────────────────

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'})


@app.route('/generate', methods=['POST'])
def generate():
    data = request.get_json()
    url = data.get('url', '').strip()
    access_token = data.get('access_token')  # optional — only needed for Google Docs export

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
            return jsonify({'error': 'No transcript found for this video. It may not have captions.'}), 400
        return jsonify({'error': f'Transcript error: {err}'}), 500

    # Generate scripts via Claude
    try:
        scripts = generate_scripts(transcript)
    except Exception as e:
        return jsonify({'error': f'Script generation failed: {str(e)}'}), 500

    result = {
        'video_id': video_id,
        'scripts': scripts,
        'doc_url': None
    }

    # Push to Google Docs if access token provided
    if access_token:
        try:
            title = f"Scripts — youtube.com/watch?v={video_id}"
            doc_url = push_to_google_docs(title, scripts, access_token)
            result['doc_url'] = doc_url
        except Exception as e:
            result['doc_warning'] = f'Google Docs export failed: {str(e)}'

    return jsonify(result)


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"\n✅  Script Generator API running on http://localhost:{port}\n")
    app.run(host='0.0.0.0', port=port, debug=False)
