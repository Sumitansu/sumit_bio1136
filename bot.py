import discord
from discord.ext import commands
import speech_recognition as sr
import asyncio
from googletrans import Translator
import wave
import io
from datetime import datetime
import os

intents = discord.Intents.default()
intents.voice_states = True
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)
translator = Translator()

class VoiceTranslator:
    def __init__(self, bot):
        self.bot = bot
        self.recognizer = sr.Recognizer()
        self.is_translating = False
        self.text_channel = None
        self.voice_client = None
        self.last_message_time = datetime.now()
        self.stats = {
            'start_time': None,
            'messages': 0,
            'speakers': set()
        }

    async def start_translation(self, voice_channel, text_channel):
        try:
            self.is_translating = True
            self.stats['start_time'] = datetime.now()
            self.text_channel = text_channel
            
            if voice_channel.guild.voice_client:
                self.voice_client = voice_channel.guild.voice_client
            else:
                self.voice_client = await voice_channel.connect()
            
            await self.text_channel.send("🎙️ Translation started! I'll send translations in this channel.")
            print(f"Connected to voice channel: {voice_channel.name}")
            
            while self.is_translating:
                sink = discord.sinks.WaveSink()
                print("Starting recording...")
                self.voice_client.start_recording(
                    sink,
                    self.finished_callback,
                    self.text_channel
                )
                await asyncio.sleep(5)  # Record for 5 seconds
                if hasattr(self.voice_client, 'recording'):
                    print("Stopping recording...")
                    self.voice_client.stop_recording()
                await asyncio.sleep(0.1)
                
        except Exception as e:
            print(f"Error in start_translation: {e}")
            await text_channel.send(f"❌ Error starting translation: {str(e)}")
            self.is_translating = False

    async def stop_translation(self):
        self.is_translating = False
        if self.voice_client and self.voice_client.is_connected():
            if hasattr(self.voice_client, 'recording'):
                self.voice_client.stop_recording()
            await self.voice_client.disconnect()
        
        if self.text_channel:
            await self.text_channel.send("🛑 Translation stopped!")

    async def finished_callback(self, sink, text_channel):
        try:
            for user_id, audio in sink.audio_data.items():
                user = self.bot.get_user(user_id)
                if not user:  # Skip if user not found
                    continue
                    
                display_name = user.display_name
                print(f"Processing audio from: {display_name}")
                
                try:
                    audio.file.seek(0)
                    audio_bytes = audio.file.read()
                    
                    if len(audio_bytes) > 1000:  # Only process if there's significant audio
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        filename = f"temp_audio_{timestamp}.wav"
                        
                        with wave.open(filename, 'wb') as wave_file:
                            wave_file.setnchannels(2)
                            wave_file.setsampwidth(2)
                            wave_file.setframerate(48000)
                            wave_file.writeframes(audio_bytes)
                        
                        with sr.AudioFile(filename) as source:
                            self.recognizer.energy_threshold = 300
                            self.recognizer.dynamic_energy_threshold = True
                            audio_data = self.recognizer.record(source)
                            
                            try:
                                text = self.recognizer.recognize_google(audio_data, language='ru-RU')
                                if text.strip():
                                    translation = translator.translate(text, src='ru', dest='en')
                                    await text_channel.send(f"{display_name}: {translation.text}")
                                    self.stats['messages'] += 1
                                    self.stats['speakers'].add(display_name)
                                    self.last_message_time = datetime.now()
                            except sr.UnknownValueError:
                                pass  # No speech detected
                            except sr.RequestError as e:
                                print(f"Could not request results; {e}")
                        
                        try:
                            os.remove(filename)
                        except:
                            pass
                    
                except Exception as e:
                    print(f"Error processing audio: {str(e)}")
                
        except Exception as e:
            print(f"Error in callback: {str(e)}")

@bot.event
async def on_ready():
    print(f'Bot is ready: {bot.user.name}')
    bot.voice_translator = VoiceTranslator(bot)

@bot.command()
async def join(ctx):
    if ctx.author.voice:
        channel = ctx.author.voice.channel
        if ctx.voice_client is None:
            await channel.connect()
        else:
            await ctx.voice_client.move_to(channel)
        await ctx.send(f"Joined {channel.name}")
    else:
        await ctx.send("You need to be in a voice channel first!")

@bot.command()
async def leave(ctx):
    if ctx.voice_client:
        await bot.voice_translator.stop_translation()
        await ctx.voice_client.disconnect()
        await ctx.send("Left the voice channel")
    else:
        await ctx.send("I'm not in a voice channel!")

@bot.command()
async def start(ctx):
    if not ctx.author.voice:
        await ctx.send("You need to be in a voice channel!")
        return
    
    if not ctx.voice_client:
        await ctx.send("I need to be in a voice channel! Use !join first")
        return
    
    await bot.voice_translator.start_translation(ctx.author.voice.channel, ctx.channel)

@bot.command()
async def stop(ctx):
    await bot.voice_translator.stop_translation()
    await ctx.send("Translation stopped!")

bot.run('your_token_here')
