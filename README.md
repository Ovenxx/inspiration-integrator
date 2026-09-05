# Inspirator — Inspiration Integrator

Turn a vague spark of inspiration into a polished micro-story, and then into a ready-to-use AI video prompt.

**Inspirator** is a Streamlit web app powered by the [DeepSeek API](https://platform.deepseek.com). It is a micro-fiction AI tool that goes back to the simple pleasure of words: describe a fuzzy idea in one sentence, and the app turns it into a vivid micro-story (微小说) — or, with one more click, into a structured Chinese prompt ready for AI video generation.

## Features

### ✍️ Mode 1 — "I Have an Idea"

Type any idea (e.g. *"a story about losing one's memory"*) and let the AI write a complete micro-story for you.

### 🎡 Mode 2 — "Find Inspiration" (Inspiration Playground)

No idea yet? Enter the playground and pick one of eight themed rides, each with eight pre-built story starters:

| Ride | Vibe |
|------|------|
| 🕵️ Suspense & Mystery | twists, mind games, chilling details |
| 💗 Romance | sweet, heartbreaking, second chances |
| 👻 Urban Legends | eerie, uncanny, everyday horror |
| 🤣 Comedy & Daily Life | awkward, relatable, painfully funny |
| 🤖 Sci-Fi Brainstorms | cyberpunk, wild ideas, unsettling futures |
| 🌊 Healing & Tears | tender, heartwarming, quietly devastating |
| ⚔️ Wuxia & Jianghu | honor, blades, wandering heroes |
| 🎓 Campus Youth | youthful, nostalgic, bittersweet summers |

Each ride assembles a story from four elements — **Character · Action · Object · Scene**. Flip (🎲) to remix them at random, lock (🔒) the parts you like, then generate the full story.

### 🎬 Story → Video Prompt

From any generated story, one click starts an interactive multiple-choice interview. Over five rounds the AI asks about:

1. **Subject appearance** — age, outfit, expression
2. **Scene & environment** — location, lighting, mood
3. **Action** — movement, rhythm, posture, emotion
4. **Visual style** — realistic, anime, cyberpunk, ink-wash, ...
5. **Cinematography** — shot size, camera movement, perspective, depth of field

The result is a 300–500 character Chinese prompt organized into five structured paragraphs, ready to paste into your favorite AI video tool. Don't like any option? Write your own answer instead.

## Tech Stack

| Technology | Purpose |
|------------|---------|
| Python 3.11 | Language |
| [Streamlit](https://streamlit.io) | Web UI framework |
| [DeepSeek API](https://platform.deepseek.com) (`deepseek-chat`, OpenAI-compatible SDK) | Story and prompt generation |
| python-dotenv | Local environment variables |

## Getting Started

### 1. Clone and install

```bash
git clone https://github.com/Ovenxx/inspiration-integrator.git
cd inspiration-integrator
pip install -r requirements.txt
```

### 2. Configure your DeepSeek API key

For local development, create a `.env` file in the project root:

```bash
DEEPSEEK_API_KEY=your-api-key
```

For Streamlit Community Cloud, set the key under **Settings → Secrets** instead (see below).

### 3. Run the app

```bash
streamlit run app.py
```

Then open the printed local URL (usually http://localhost:8501) in your browser.

## Deployment on Streamlit Community Cloud

1. Push this repository to GitHub.
2. Create a new app at [share.streamlit.io](https://share.streamlit.io).
3. Select repository `Ovenxx/inspiration-integrator`, branch `main`, and main file `app.py`.
4. Add `DEEPSEEK_API_KEY` under **Settings → Secrets**.
5. Deploy — the app is live at `https://inspiration-integrator.streamlit.app`.

## Project Structure

```
inspiration-integrator/
├── app.py                    # Main application (all logic)
├── assets/
│   └── style.css             # Custom UI styling
├── requirements.txt          # Python dependencies
├── .gitignore                # Excludes .env and secrets.toml
├── DEVELOPMENT_SUMMARY.md    # Development log (Chinese)
└── .claude/                  # Claude Code configuration
```

## Notes

- The UI and all generated content are in Chinese.
- Never commit your API key: `.env` and `.streamlit/secrets.toml` are already gitignored.