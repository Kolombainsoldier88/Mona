import os
import re
import urllib.parse
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
- Speak like an uncompromising, sharp female head trader who reads his daily trade logs, his own `#ict-lecture-notes` forum, and his `#strategy-backtesting-trades-round-up` channel—and holds him to his own written words.

YOUR LIVE KNOWLEDGE SOURCES (USE GOOGLE SEARCH ON BOTH YOUTUBE & X):
1. Official ICT YouTube Channel: https://www.youtube.com/@InnerCircleTrader
2. Official ICT X Account: https://x.com/I_Am_The_ICT (@I_Am_The_ICT)
3. Oaths Palmer's X Profile: https://x.com/AdidjaPromise (@AdidjaPromise)
4. His Trading Circle on X: {friends_list_text}

HOW YOU FORGE HIM IN EVERY RESPONSE:
1. **Cross-Server Audit (Daily Threads + Lecture Notes + Backtesting):**
   - Compare today's execution against his **previous days' journal threads** (to catch repeating leaks like unplanned trades, mid-week goal changes, or FOMO).
   - Cross-check his trades against his **own notes in `#ict-lecture-notes`** and his **data in `#strategy-backtesting-trades-round-up`**. When he violates a rule he himself documented in his lecture notes, quote his own note back to him!
   - Check if he completed and submitted your previous mandatory assignment.
2. **Off-Grid & Chart Inspection:** Examine every uploaded chart screenshot, TradingView `/x/` snapshot, and note chronologically. Pinpoint everywhere he went off-grid from ICT's rules.
3. **Hard Execution & Psychological Grade:** Score his Technician vs. Operator performance bluntly. Tear apart FOMO, impatience, and over-complication.
4. **Clickable Study Links (NEVER tell him to "go search" manually):**
   - For YouTube: Name the exact ICT YouTube video/series title—the system automatically attaches verified clickable YouTube watch links from Google Search at the bottom of your message. NEVER invent or guess `youtube.com/watch?v=...` or `x.com/.../status/...` IDs in your text.
   - For X Feeds: Always give him a direct, clickable X feed URL using exact URL-encoded search queries (no spaces) so one click opens the exact topic feed on X—for example:
     `[ICT on Market Structure Shifts](https://x.com/search?q=from%3AI_Am_The_ICT%20%22Market%20Structure%20Shift%22&f=live)` or `[ICT on Draw on Liquidity](https://x.com/search?q=from%3AI_Am_The_ICT%20%22Draw%20on%20Liquidity%22&f=live)`.
5. **Mandatory Next Assignment (With Submission Proof Required):** End EVERY response with a concrete, non-negotiable chart markup, tape-reading, or backtesting assignment that he must submit in his journal with screenshots and written proof before his next session.
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
                    text += f"- [{title}]({uri})\n"
            else:
                text += (
                    "\n\n### Official Study Channels\n"
                    "- [ICT Official YouTube](https://www.youtube.com/@InnerCircleTrader)\n"
                    "- [ICT Official X Feed](https://x.com/I_Am_The_ICT)\n"
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

async def send_chunked_message(channel, text, limit=1900):
    """Splits long messages cleanly at newline/space boundaries so URLs are never cut in half."""
    remaining = text.strip()
    while remaining:
        if len(remaining) <= limit:
            await channel.send(remaining)
            break

        # Prefer splitting at a newline before the limit
        split_idx = remaining.rfind("\n", 0, limit)
        if split_idx == -1 or split_idx < limit // 2:
            # Fallback to splitting at a space so we never cut inside a URL
            split_idx = remaining.rfind(" ", 0, limit)
        if split_idx == -1:
            split_idx = limit

        chunk = remaining[:split_idx].rstrip()
        if chunk:
            await channel.send(chunk)
        remaining = remaining[split_idx:].lstrip()

async def collect_forum_threads_summary(forum_channel, exclude_thread_id, bot_user, max_threads=6, msgs_per_thread=8):
    """Collects opening notes and recent takeaways from threads in a ForumChannel."""
    threads = []
    seen_ids = {exclude_thread_id} if exclude_thread_id else set()

    for th in forum_channel.threads:
        if th.id not in seen_ids:
            threads.append(th)
            seen_ids.add(th.id)

    try:
        async for th in forum_channel.archived_threads(limit=12):
            if th.id not in seen_ids:
                threads.append(th)
                seen_ids.add(th.id)
    except Exception as arch_err:
        print(f"Could not fetch archived threads in {forum_channel.name}: {arch_err}")

    threads.sort(key=lambda t: t.created_at, reverse=True)
    sections = []

    for th in threads[:max_threads]:
        try:
            date_label = th.created_at.strftime("%Y-%m-%d")
            first_msgs = [m async for m in th.history(limit=3, oldest_first=True)]
            last_msgs = [m async for m in th.history(limit=msgs_per_thread, oldest_first=False)]
            last_msgs.reverse()

            lines = []
            added_ids = set()
            for m in first_msgs + last_msgs:
                if m.id in added_ids:
                    continue
                added_ids.add(m.id)
                sender = "Mona" if m.author == bot_user else m.author.display_name
                txt = (
                    m.content
                    .replace(f'<@!{bot_user.id}>', '')
                    .replace(f'<@{bot_user.id}>', '')
                    .strip()
                )
                if txt:
                    lines.append(f"  - {sender}: {txt[:420]}")

            if lines:
                sections.append(f"[{forum_channel.name} | {th.name} ({date_label})]\n" + "\n".join(lines))
        except Exception as err:
            print(f"Error reading thread {th.name}: {err}")

    return "\n\n".join(sections)

async def gather_server_trading_memory(current_channel, bot_user):
    """Scans sibling journal days, #ict-lecture-notes, and #strategy-backtesting-trades-round-up."""
    guild = getattr(current_channel, "guild", None)
    if not guild:
        return ""

    memory_blocks = []

    # A. Scan previous days inside the current forum (e.g., #charts-trades)
    parent = getattr(current_channel, "parent", None)
    if isinstance(parent, discord.ForumChannel):
        prev_days = await collect_forum_threads_summary(
            parent, exclude_thread_id=current_channel.id, bot_user=bot_user, max_threads=6, msgs_per_thread=10
        )
        if prev_days:
            memory_blocks.append("=== PREVIOUS DAYS IN THIS JOURNAL FORUM ===\n" + prev_days)

    # B. Scan other trading forums and channels across the server
    target_keywords = ("lecture", "backtest", "round-up", "charts-trades", "notes", "strategy")
    for ch in guild.channels:
        if ch.id == current_channel.id or (parent and ch.id == parent.id):
            continue

        ch_name_lower = ch.name.lower()
        if not any(kw in ch_name_lower for kw in target_keywords):
            continue

        if isinstance(ch, discord.ForumChannel):
            forum_summary = await collect_forum_threads_summary(
                ch, exclude_thread_id=current_channel.id, bot_user=bot_user, max_threads=5, msgs_per_thread=6
            )
            if forum_summary:
                memory_blocks.append(f"=== SERVER FORUM: #{ch.name} ===\n" + forum_summary)

        elif isinstance(ch, discord.TextChannel):
            try:
                recent_msgs = [m async for m in ch.history(limit=15, oldest_first=False)]
                recent_msgs.reverse()
                ch_lines = []
                for m in recent_msgs:
                    sender = "Mona" if m.author == bot_user else m.author.display_name
                    txt = (
                        m.content
                        .replace(f'<@!{bot_user.id}>', '')
                        .replace(f'<@{bot_user.id}>', '')
                        .strip()
                    )
                    if txt:
                        ch_lines.append(f"  - [{m.created_at.strftime('%Y-%m-%d')}] {sender}: {txt[:420]}")
                if ch_lines:
                    memory_blocks.append(f"=== SERVER CHANNEL: #{ch.name} ===\n" + "\n".join(ch_lines))
            except Exception as ch_err:
                print(f"Could not read channel #{ch.name}: {ch_err}")

    return "\n\n".join(memory_blocks)

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

                    # 1. Read the previous 50 messages in the CURRENT thread/channel
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

                    # 2. Scan previous journal days + #ict-lecture-notes + #strategy-backtesting-trades-round-up
                    server_memory = await gather_server_trading_memory(message.channel, self.user)

                    thread_title = getattr(message.channel, "name", "Direct Message")
                    parent_name = getattr(getattr(message.channel, "parent", None), "name", "")
                    location_info = f"{parent_name} > {thread_title}" if parent_name else thread_title

                    server_memory_block = (
                        f"--- CROSS-SERVER MEMORY (PREVIOUS DAYS, LECTURE NOTES & BACKTESTING) ---\n"
                        f"{server_memory}\n\n"
                        if server_memory else ""
                    )

                    full_context_prompt = (
                        f"Journal Location: {location_info}\n"
                        f"Total Chart Images Attached for Visual Review: {len(image_parts)}\n\n"
                        f"{server_memory_block}"
                        f"--- TODAY'S THREAD HISTORY (LAST 50 MESSAGES, CHRONOLOGICAL) ---\n"
                        + "\n".join(history_lines)
                        + f"\n\n--- CURRENT QUESTION FROM {message.author.display_name} ---\n{prompt}"
                    )

                    contents_list = [full_context_prompt] + image_parts

                    reply_text = await loop.run_in_executor(
                        None,
                        lambda: generate_auto(contents_list)
                    )

                reply_text = reply_text or "I didn't generate a response."

                # Send cleanly without ever splitting inside a URL or Markdown link
                await send_chunked_message(message.channel, reply_text)

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
