import os
import threading
import asyncio
import time
import urllib.request
from flask import Flask
import discord
from google import genai

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

# 3. Initialize the Gemini client with your API key
gemini_client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

# 4. Set up Discord intents
intents = discord.Intents.default()
intents.message_content = True

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
                    loop = asyncio.get_running_loop()
                    response = await loop.run_in_executor(
                        None,
                        lambda: gemini_client.models.generate_content(
                            model='gemini-flash-latest',
                            contents=prompt,
                        )
                    )

                reply_text = response.text or "I didn't generate a response."

                # Split long responses into 1,900-char chunks so Discord never throws an error
                for i in range(0, len(reply_text), 1900):
                    await message.channel.send(reply_text[i:i + 1900])

            except Exception as e:
                print(f"Error generating response: {e}")
                await message.channel.send(f"Sorry, I encountered an error: `{type(e).__name__}`")

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
