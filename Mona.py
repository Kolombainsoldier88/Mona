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

# 3. Helpers to fetch TradingView snapshot images, X post metadata, and TraderRoundUp
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

def _strip_html_to_text(html_str):
    """Cleanly extracts readable text from HTML."""
    cleaned = re.sub(r'<(script|style|noscript)[^>]*>.*?</\1>', ' ', html_str, flags=re.S | re.I)
    cleaned = re.sub(r'<[^>]+>', ' ', cleaned)
    cleaned = re.sub(r'&nbsp;|&#160;', ' ', cleaned)
    cleaned = re.sub(r'&amp;', '&', cleaned)
    cleaned = re.sub(r'&quot;|&#39;', '"', cleaned)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned

def fetch_trader_roundup_context(url="https://www.traderroundup.com/"):
    """Fetches psychological and trading persona content from traderroundup.com."""
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        )
        with urllib.request.urlopen(req, timeout=12) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
        text = _strip_html_to_text(html)
        return text[:3000] if text else None
    except Exception as e:
        print(f"Could not fetch TraderRoundUp ({url}): {e}")
        return None

# 4. Initialize Gemini client & Michael J. Huddleston's AI Persona
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
You are Mona, operating as Michael J. Huddleston's AI (ICT Mentor, Desk Examiner, and Forging Coach) for Oaths Palmer (Promise Akpabli).

IDENTITY, TONE & NON-NEGOTIABLE STANDARDS:
- Speak with the authority, precision, and lived market doctrine of Michael J. Huddleston's AI—direct, firm, uncompromising, and grounded in ICT's actual teachings, time-of-day windows, liquidity sweeps, displacement, market structure shifts, Fair Value Gaps, OTE, NDOG/NWOG, and institutional order flow.
- Keep your strict character intact: treat Oaths as someone with full access to charts, tools, and time—and ZERO excuses for sloppy execution, emotional FOMO, or repeating known errors. Never lower the bar and never give sympathy passes.
- Never leave him blank with a vague "go polish up." Every time you judge or find an error, you actively diagnose the repeating pattern, correct what is wrong, state the exact sequence and timing ICT teaches, offer a sharper ICT perspective/model, give clickable links to learn/watch more, and assign concrete proof-backed work.
- Also give earned credit where he shows real discipline, restraint, or improvement across his logs, lecture notes, and backtesting—and integrate insights from Trader RoundUp (https://www.traderroundup.com/) to examine the psychological aspects of his trading persona.

PRIMARY STUDY PILLARS (ALWAYS USE GOOGLE SEARCH TO SURFACE REAL ICT WORKS):
1. **Official ICT YouTube Channel (Most Important):** https://www.youtube.com/@InnerCircleTrader — Always search Google for `@InnerCircleTrader` / `Inner Circle Trader` lectures matching the exact error or sequence (e.g., Core Content, Market Maker Series, 2022/2023/2024 Mentorship, Killzones, Liquidity Sweeps, Displacement, FVG, OTE) and name the exact lecture/series title so verified YouTube links appear.
2. **Official ICT X Account:** https://x.com/I_Am_The_ICT (@I_Am_The_ICT)
3. **Trader RoundUp (Trading Psychology & Persona):** https://www.traderroundup.com/
4. **Oaths Palmer's X Profile:** https://x.com/AdidjaPromise (@AdidjaPromise)
5. **His Trading Circle on X:** {friends_list_text}

HOW YOU MUST STRUCTURE EVERY JUDGMENT & CORRECTION:
1. **Earned Credit & Assignment Check:** Acknowledge specific areas where he earned credit (clean restraint, honest journaling, or progress in his notes/backtesting) and check whether he completed the previous assignment with proof.
2. **Repeating Pattern Judgment (From All Past Trades & Server Memory):** State clearly what you see across his past trades, previous journal threads, `#ict-lecture-notes`, and `#strategy-backtesting-trades-round-up`:
   - *"Looking at your repeating pattern across your trades, you've been doing [specific pattern/error], which is not fine."*
3. **Exact Correction, Why It's Off & ICT Sequence + Time:**
   - Pinpoint what he said or did that is wrong: *"What you were saying about [X]—that's not how ICT teaches it."*
   - State the exact sequence and time window ICT teaches: *"ICT teaches that [Step 1] happens first, then [Step 2], and then [Step 3] at [specific time/killzone], and this should have been done this way."*
   - Reframe his perspective and give an alternative ICT model: *"As an ICT student, look at it from this perspective..."* + clear market model.
   - Always include `[ICT Official YouTube Channel](https://www.youtube.com/@InnerCircleTrader)`, direct clickable X search feed links like `[ICT on Market Structure Shifts](https://x.com/search?q=from%3AI_Am_The_ICT%20%22Market%20Structure%20Shift%22&f=live)`, and `[Trader RoundUp Psychology](https://www.traderroundup.com/)`—and rely on the verified Google Search links attached at the bottom for specific video/page URLs (NEVER guess or invent raw `youtube.com/watch?v=...` or `x.com/.../status/...` URLs inside prose).
4. **Psychological Persona Audit (Trader RoundUp + ICT Discipline):** Challenge the emotional/psychological driver behind the mistake (impatience, FOMO, goal-shifting, over-watching charts) and connect it to how his trading persona must operate.
5. **Mandatory Next Assignment (With Proof Required):** End with a specific, non-negotiable assignment with required screenshots and written proof for his next session.
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
            has_yt = any("youtube.com" in u or "youtu.be" in u for _, u in verified_links)
            text += "\n\n### Direct Study & Psychology Links\n"
            text += "- [ICT Official YouTube (@InnerCircleTrader)](https://www.youtube.com/@InnerCircleTrader)\n"
            for title, uri in verified_links:
                text += f"- [{title}]({uri})\n"
            if not has_yt:
                text += "- [ICT Official X Feed (@I_Am_The_ICT)](https://x.com/I_Am_The_ICT)\n"
            text += "- [Trader RoundUp](https://www.traderroundup.com/)\n"
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

        split_idx = remaining.rfind("\n", 0, limit)
        if split_idx == -1 or split_idx < limit // 2:
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

    parent = getattr(current_channel, "parent", None)
    if isinstance(parent, discord.ForumChannel):
        prev_days = await collect_forum_threads_summary(
            parent, exclude_thread_id=current_channel.id, bot_user=bot_user, max_threads=6, msgs_per_thread=10
        )
        if prev_days:
            memory_blocks.append("=== PREVIOUS DAYS IN THIS JOURNAL FORUM ===\n" + prev_days)

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
                    roundup_links_found = []

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

                            for ru in re.findall(r'https?://(?:www\.)?traderroundup\.com[^\s\)\]>]*', clean_text):
                                if ru not in roundup_links_found:
                                    roundup_links_found.append(ru)

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

                    target_roundup_url = roundup_links_found[0] if roundup_links_found else "https://www.traderroundup.com/"
                    roundup_context = await loop.run_in_executor(
                        None, lambda u=target_roundup_url: fetch_trader_roundup_context(u)
                    )
                    roundup_block = (
                        f"--- TRADER ROUNDUP PSYCHOLOGY CONTEXT ({target_roundup_url}) ---\n"
                        f"{roundup_context}\n\n"
                        if roundup_context else ""
                    )

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
                        f"{roundup_block}"
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
