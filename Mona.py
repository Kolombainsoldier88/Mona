import os
import threading
from flask import Flask
import discord
from google import genai

# Initialize Flask app for Render health checks and port binding
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# Initialize the Gemini client with your API key
gemini_client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

# Set up Discord intents
intents = discord.Intents.default()
intents.message_content = True

class MyClient(discord.Client):
    async def on_ready(self):
        print(f'Logged on as {self.user}!')

    async def on_message(self, message):
        # Don't respond to the bot's own messages
        if message.author == self.user:
            return

        # Check if the bot is mentioned or if it's in a direct message
        if self.user.mentioned_in(message) or isinstance(message.channel, discord.DMChannel):
            # Clean up the prompt by removing the bot mention
            prompt = message.content.replace(f'<@!{self.user.id}>', '').replace(f'<@{self.user.id}>', '').strip()
            
            if not prompt:
                return

            print(f"Message from {message.author}: {prompt}")

            try:
                # Generate response using Gemini 3.8 Flash
                response = gemini_client.models.generate_content(
                    model='gemini-3.8-flash',
                    contents=prompt,
                )
                
                # Send the response back to Discord
                await message.channel.send(response.text)
            except Exception as e:
                print(f"Error generating response: {e}")
                await message.channel.send("Sorry, I encountered an error processing your request.")

if __name__ == "__main__":
    # Start the Flask web server in a background thread so it binds to the port for Render
    web_thread = threading.Thread(target=run_web)
    web_thread.daemon = True
    web_thread.start()

    # Start the Discord bot
    client = MyClient(intents=intents)
    client.run(os.environ.get("DISCORD_TOKEN"))
