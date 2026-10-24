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
                # Run the blocking Gemini call in an executor to avoid freezing the event loop
                loop = asyncio.get_running_loop()
                response = await loop.run_in_executor(
                    None,
                    lambda: gemini_client.models.generate_content(
                        model='gemini-3.8-flash',
                        contents=prompt,
                    )
                )
                
                # Send the response back to Discord
                await message.channel.send(response.text)
            except Exception as e:
                print(f"Error generating response: {e}")
                await message.channel.send("Sorry, I encountered an error processing your request.")
