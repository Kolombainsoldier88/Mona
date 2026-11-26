import os
import re
import threading
import asyncio
import time
import urllib.request
from flask import Flask
import discord
from google import genai
from google.genai import types

# 1. Initialize Flask app for Render health checks and port binding
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# 2. Self-ping thread to keep Render warm (pings every 45 seconds)
def self_ping():
    url = os.environ.get("RENDER_EXTERNAL_URL")
    while True:
        time.sleep(45)
        if url:
            try:
                urllib.request.urlopen(url, timeout=10)
            except Exception as e:
                print(f"Self-ping failed: {e}")

# 3. Helpers to fetch TradingView snapshot images and X post metadata
def fetch_tradingview_image(tv_url):
    """Extracts and downloads the chart PNG from a TradingView /x/ snapshot link."""
    try:
        req = urllib.request.Request(
            tv_url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8", errors="ignore")

        match = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', html)
        if not match:
            match = re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']', html)

        if match:
            img_url = match.group(1)
            img_req = urllib.request.Request(
                img_url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
            )
            with urllib.request.urlopen(img_req, timeout=10) as img_resp:
                return img_resp.read(), "image/png"
    except Exception as e:
        print(f"Could not fetch TradingView link {tv_url}: {e}")
    return None, None

def fetch_x_post_context(x_url):
    """Fetches public text/metadata from any shared X (Twitter) post URL."""
    try:
        api_url = re.sub(r'https?://(?:www\.)?(?:x\.com|twitter\.com)', 'https://api.fxtwitter.com', x_url)
        req = urllib.request.Request(
            api_url,
            headers={"User-Agent": "Mozilla/5.0"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw_json = resp.read().decode("utf-8", errors="ignore")
        return raw_json[:2500]
    except Exception as e:
        print(f"Could not fetch X post {x_url}: {e}")
        return None

# 4. Initialize Gemini client & Strict Female ICT Mentor Persona
gemini_client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

FRIENDS_X_HANDLES = [
    "@PIPMUNCH",
    "@AndrewTradezFX",
    "@Kitt_Concepts",
    "@Drevox_ict",
    "@TSLA_ICT",
    "@ICT_Daughter",
    "@Mona_Trades1",
    "@paxtrader777",
    "@peter_trades",
    "@RichardsFx17",
    "@LDoyle487549",
    "@Observing96",
    "@CryptoLanzasero",
    "@Pippy_Banks",
    "@ChxrlieTrades",
    "@RohitJadhav_FX",
    "@DanDowdTrading",
    "@Focus97815018",
    "@R888_19",
]

friends_list_text = ", ".join(FRIENDS_X_HANDLES)

SYSTEM_INSTRUCTION = f"""
You are Mona, Oaths Palmer's (Promise Akpabli's) personal female ICT (Inner Circle Trader) Mentor, Desk Examiner, and Forging Coach.

YOUR MINDSET & STANDARD:
- Treat Oaths as someone who has ALL the resources, charts, tools, and time in the world—and ZERO excuses for failing to change his execution habits. Never lower the bar, never offer sympathy passes, and never tolerate sloppy entries or emotional FOMO.
- Your sole mission is to forge him through fire into the exact caliber of disciplined, ruthless, patient trader that Michael J. Huddleston (ICT) wants to see—someone worthy of managing institutional PAMM capital.
- Speak like an uncompromising, sharp female head trader who refuses to let him waste another day repeating the same mistakes.

YOUR LIVE KNOWLEDGE SOURCES (USE GOOGLE SEARCH ON BOTH YOUTUBE & X):
1. Official ICT YouTube Channel: https://www.youtube.com/@InnerCircleTrader (Search `site:youtube.com "Inner Circle Trader"` + the exact concept/mistake such as Asian Range, Wednesday High/Low of Week, Order Block, Volume Imbalance, OTE, NDOG/NWOG, Silver Bullet, or Discipline).
2. Official ICT X Account: https://x.com/I_Am_The_ICT (@I_Am_The_ICT) (Search `site:x.com/I_Am_The_ICT` + the concept/mindset lesson).
3. Oaths Palmer's X Profile: https://x.com/AdidjaPromise (@AdidjaPromise)
4. His Trading Circle on X: {friends_list_text}

HOW YOU FORGE HIM IN EVERY RESPONSE:
1. **Audit Prior Assignments First:** Check the thread history immediately to see if he actually completed and submitted the previous assignment/challenge you gave him (e.g., pre-trade chart markups, confirmation statements, or backtest studies). If he skipped it or submitted weak work, call him out directly and refuse to move forward until he submits it properly.
2. **Off-Grid & Chart Inspection:** Examine every uploaded chart screenshot, TradingView `/x/` snapshot, and note chronologically. Pinpoint everywhere he went off-grid from ICT's rules (e.g., entering OTE without displacement/MSS, misreading session liquidity, or forcing reversals against HTF order flow).
3. **Hard Execution & Psychological Grade:** Score his Technician vs. Operator performance bluntly. Tear apart FOMO, impatience, and over-complication.
4. **Dual-Platform Correction (YouTube + X):** Direct him to the exact ICT YouTube lecture and X post he must study right now to fix his specific error.
   - CRITICAL URL RULE: NEVER write or guess raw `https://x.com/.../status/12345...` or `youtube.com/watch?v=...` URLs inside your prose, because guessed IDs cause 404 errors. Name the exact ICT YouTube video/series title and X account/topic clearly in your text—the system automatically attaches the real, verified clickable links returned by Google Search at the bottom of your message.
5. **Mandatory Next Assignment (With Submission Proof Required):** End EVERY response with a concrete, non-negotiable chart markup, tape-reading, or backtesting assignment that he must submit in this thread with screenshots and written proof before his next session.
""".strip()

def get_available_flash_models():
    """Automatically discovers active Gemini Flash models supported by your API key."""
    preferred_order = [
        "gemini-2.5-flash",
        "gemini-2.5-flash-lite",
        "gemini-2.0-flash",
        "gemini-1.5-flash",
    ]
    try:
        discovered = []
        for m in gemini_client.models.list():
            name = m.name.replace("models/", "")
            actions = getattr(m, "supported_actions", []) or []
            if "flash" in name and "generateContent" in actions:
                discovered.append(name)

        ordered = [m for m in preferred_order if m in discovered]
        ordered += [m for m in discovered if m not in ordered]
        return ordered if ordered else preferred_order
    except Exception as e:
        print(f"Model discovery fallback triggered: {e}")
        return preferred_order

def extract_verified_grounding_links(response):
    """Extracts real, verified YouTube and X URLs directly from Google Search grounding metadata."""
    yt_links = []
    x_links = []
    other_links = []
    try:
        candidates = getattr(response, "candidates", []) or []
        if not candidates:
            return []
        metadata = getattr(candidates[0], "grounding_metadata", None)
        chunks = getattr(metadata, "grounding_chunks", []) or []
        seen = set()
        for chunk in chunks:
            web = getattr(chunk, "web", None)
            uri = getattr(web, "uri", None)
            title = getattr(web, "title", None) or "Study Resource"
            if not uri or uri in seen:
                continue
            seen.add(uri)
            if "youtube.com" in uri or "youtu.be" in uri:
                yt_links.append((title, uri))
            elif "x.com" in uri or "twitter.com" in uri:
                x_links.append((title, uri))
            else:
                other_links.append((title, uri))
    except Exception as e:
        print(f"Could not extract grounding chunks: {e}")

    return (yt_links[:4] + x_links[:4] + other_links[:2])[:6]

def generate_auto(contents_list):
    """Tries available Gemini models automatically with Google Search Grounding."""
    models = get_available_flash_models()
    last_error = None
    for model_name in models:
        try:
            response = gemini_client.models.generate_content(
                model=model_name,
                contents=contents_list,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_INSTRUCTION,
                    tools=[types.Tool(google_search=types.GoogleSearch())],
                ),
            )
            text = response.text or ""
            verified_links = extract_verified_grounding_links(response)
            if verified_links:
                text += "\n\n### Direct Study Links (Verified via Google Search)\n"
                for title, uri in verified_links:
                    text += f"- **{title}**: <{uri}>\n"
            else:
                text += (
                    "\n\n### Official Study Channels\n"
                    "- **ICT Official YouTube**: <https://www.youtube.com/@InnerCircleTrader>\n"
                    "- **ICT Official X**: <https://x.com/I_Am_The_ICT>\n"
                )
            return text
        except Exception as e:
            print(f"Model '{model_name}' with search failed ({type(e).__name__}): {e}")
            try:
                response = gemini_client.models.generate_content(
                    model=model_name,
                    contents=contents_list,
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM_INSTRUCTION,
                    ),
                )
                return response.text
            except Exception as inner_e:
                print(f"Model '{model_name}' unavailable ({type(inner_e).__name__}): {inner_e}")
                last_error = inner_e
    raise last_error

# 5. Set up Discord intents
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True

class MyClient(discord.Client):
    async def on_ready(self):
        print(f'Logged on as {self.user}!')

    async def on_message(self, message):
        if message.author == self.user:
            return

        if self.user.mentioned_in(message) or isinstance(message.channel, discord.DMChannel):
            prompt = (
                message.content
                .replace(f'<@!{self.user.id}>', '')
                .replace(f'<@{self.user.id}>', '')
                .strip()
            )

            if not prompt:
                return

            print(f"Message from {message.author}: {prompt}")

            try:
                async with message.channel.typing():
                    history_lines = []
                    image_parts = []
                    tv_links_found = []
                    x_links_found = []

                    # Read the previous 50 messages in the thread or channel
                    past_messages = [msg async for msg in message.channel.history(limit=50, oldest_first=False)]
                    past_messages.reverse()

                    for msg in past_messages:
                        sender = "Mona" if msg.author == self.user else msg.author.display_name
                        timestamp = msg.created_at.strftime("%Y-%m-%d %H:%M UTC")
                        clean_text = (
                            msg.content
                            .replace(f'<@!{self.user.id}>', '')
                            .replace(f'<@{self.user.id}>', '')
                            .strip()
                        )
                        if clean_text:
                            history_lines.append(f"[{timestamp}] {sender}: {clean_text}")

                            for u in re.findall(r'https?://(?:www\.)?tradingview\.com/x/[A-Za-z0-9]+/?', clean_text):
                                if u not in tv_links_found:
                                    tv_links_found.append(u)

                            for xu in re.findall(r'https?://(?:www\.)?(?:x\.com|twitter\.com)/[A-Za-z0-9_]+/status/[0-9]+', clean_text):
                                if xu not in x_links_found:
                                    x_links_found.append(xu)

                        for attachment in msg.attachments:
                            if attachment.content_type and attachment.content_type.startswith("image/") and len(image_parts) < 10:
                                try:
                                    img_bytes = await attachment.read()
                                    image_parts.append(
                                        types.Part.from_bytes(
                                            data=img_bytes,
                                            mime_type=attachment.content_type,
                                        )
                                    )
                                except Exception as img_err:
                                    print(f"Failed to read Discord attachment: {img_err}")

                    loop = asyncio.get_running_loop()

                    for tv_url in tv_links_found:
                        if len(image_parts) >= 10:
                            break
                        img_bytes, mime_type = await loop.run_in_executor(
                            None, lambda u=tv_url: fetch_tradingview_image(u)
                        )
                        if img_bytes:
                            image_parts.append(
                                types.Part.from_bytes(data=img_bytes, mime_type=mime_type)
                            )
                            history_lines.append(f"[System Note: Attached chart image from {tv_url}]")

                    for x_url in x_links_found[:5]:
                        x_data = await loop.run_in_executor(
                            None, lambda u=x_url: fetch_x_post_context(u)
                        )
                        if x_data:
                            history_lines.append(f"[X Post Data from {x_url}]: {x_data}")

                    thread_title = getattr(message.channel, "name", "Direct Message")
                    parent_name = getattr(getattr(message.channel, "parent", None), "name", "")
                    location_info = f"{parent_name} > {thread_title}" if parent_name else thread_title

                    full_context_prompt = (
                        f"Journal Location: {location_info}\n"
                        f"Total Chart Images Attached for Visual Review: {len(image_parts)}\n\n"
                        f"--- THREAD HISTORY (LAST 50 MESSAGES, CHRONOLOGICAL) ---\n"
                        + "\n".join(history_lines)
                        + f"\n\n--- CURRENT QUESTION FROM {message.author.display_name} ---\n{prompt}"
                    )

                    contents_list = [full_context_prompt] + image_parts

                    reply_text = await loop.run_in_executor(
                        None,
                        lambda: generate_auto(contents_list)
                    )

                reply_text = reply_text or "I didn't generate a response."

                for i in range(0, len(reply_text), 1900):
                    await message.channel.send(reply_text[i:i + 1900])

            except Exception as e:
                print(f"Error generating response: {e}")
                await message.channel.send(f"Sorry, I encountered an error: `{type(e).__name__}` — `{str(e)[:150]}`")

if __name__ == "__main__":
    web_thread = threading.Thread(target=run_web, daemon=True)
    web_thread.start()

    ping_thread = threading.Thread(target=self_ping, daemon=True)
    ping_thread.start()

    client = MyClient(intents=intents)
    client.run(os.environ.get("DISCORD_TOKEN"))
