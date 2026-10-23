import os
import discord
from google import genai

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
                # Generate response using Gemini 2.5 Flash
                response =gemini_client.models.generate_content(
                    model='gemini-3.8-flash',
                    contents=prompt,
                )
                
                # Send the response back to Discord
                await message.channel.send(response.text)
            except Exception as e:
                print(f"Error generating response: {e}")
                await message.channel.send("Sorry, I encountered an error processing your request.")

client = MyClient(intents=intents)

client.run('MTU2Mjk5ODg2NDQxODU3NDQyNg.GKYpls.6YcLPg5BY-aN02mC_CIZUhDse00KEOr_x2IRaY')
