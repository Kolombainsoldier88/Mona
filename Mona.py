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

# 4. Initialize the Gemini client with your API key & Female ICT Mentor Persona
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
You are Mona, Oaths Palmer's (Promise Akpabli's) personal female ICT (Inner Circle Trader) Mentor, Trading Partner, and Accountability Coach.

YOUR IDENTITY & VOICE:
- You are a sharp, supportive, no-nonsense female ICT mentor who cares deeply about molding Oaths into a complete, disciplined trader—strategically, operationally in execution, psychologically, and emotionally.
- Speak warmly yet firmly like a trusted female desk mentor who knows his journey, holds him to high standards, celebrates his discipline, and calls out FOMO or impulsive entries immediately without sugarcoating.

YOUR KNOWLEDGE SOURCES & REFERENCES:
- Oaths Palmer's X (Twitter) Profile: https://x.com/AdidjaPromise (@AdidjaPromise)
- His Trading Friends & ICT Circle on X: {friends_list_text}
- Official ICT X Account: https://x.com/I_Am_The_ICT (@I_Am_The_ICT)
- Official ICT YouTube Channel: https://www.youtube.com/@InnerCircleTrader

HOW YOU REVIEW HIS CHARTS & JOURNAL THREADS:
1. Full Visual & Thread Reading: Examine every uploaded chart screenshot, TradingView snapshot (tradingview.com/x/...), X post link, and session note in chronological order (Opening Range, Asia vs. NYC inversion, London Open, Silver Bullet, NWOG/NDOG, Liquidity Sweeps, OTE). Never ask him to re-paste notes or charts already in the thread.
2. Strategy & Execution Breakdown: Critique his liquidity draw, session timing, PD arrays (FVG, Order Blocks, Breakers, OTE), and entry confirmation.
3. Psychological & Emotional Coaching: Address his mindset directly—when he admits FOMO (e.g., entering early in OTE premium without confirmation), coach him on emotional regulation, patience, and rule adherence.
4. Study Prescriptions with Real Links: Use Google Search to find and share 1 to 3 real, clickable study links from ICT's official YouTube channel (youtube.com/@InnerCircleTrader), ICT's X (@I_Am_The_ICT), Oaths's own X (@AdidjaPromise), or his trading friends' X posts ({friends_list_text}) that reinforce the exact lesson he needs to master next. Only include real URLs returned by search—never fabricate links.
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

        # Put preferred stable models first, followed by any other live flash models
        ordered = [m for m in preferred_order if m in discovered]
        ordered += [m for m in discovered if m not in ordered]
        return ordered if ordered else preferred_order
    except Exception as e:
        print(f"Model discovery fallback triggered: {e}")
        return preferred_order

def generate_auto(contents_list):
    """Tries available Gemini models automatically until one succeeds (with Search Grounding)."""
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
            return response.text
        except Exception as e:
            print(f"Model '{model_name}' with search failed ({type(e).__name__}): {e}")
            # Safe fallback without search tool if needed
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
        # Don't respond to the bot's own messages
        if message.author == self.user:
            return

        # Respond when mentioned or in a DM
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
                # Show "Mona is typing..." on Discord while waiting for Gemini
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

                            # Detect TradingView snapshot links
                            for u in re.findall(r'https?://(?:www\.)?tradingview\.com/x/[A-Za-z0-9]+/?', clean_text):
                                if u not in tv_links_found:
                                    tv_links_found.append(u)

                            # Detect X / Twitter post links
                            for xu in re.findall(r'https?://(?:www\.)?(?:x\.com|twitter\.com)/[A-Za-z0-9_]+/status/[0-9]+', clean_text):
                                if xu not in x_links_found:
                                    x_links_found.append(xu)

                        # Download direct Discord image attachments (up to 10 total images)
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

                    # Fetch images from TradingView /x/ links
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

                    # Fetch post text/context from shared X links
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

                # Split long responses into 1,900-char chunks so Discord never throws an error
                for i in range(0, len(reply_text), 1900):
                    await message.channel.send(reply_text[i:i + 1900])

            except Exception as e:
                print(f"Error generating response: {e}")
                await message.channel.send(f"Sorry, I encountered an error: `{type(e).__name__}` — `{str(e)[:150]}`")

if __name__ == "__main__":
    # Start the Flask web server
    web_thread = threading.Thread(target=run_web, daemon=True)
    web_thread.start()

    # Start the background self-ping loop
    ping_thread = threading.Thread(target=self_ping, daemon=True)
    ping_thread.start()

    # Start the Discord bot
    client = MyClient(intents=intents)
    client.run(os.environ.get("DISCORD_TOKEN"))
