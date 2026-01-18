import discord
from discord.ext import commands
from discord import app_commands
import yt_dlp
import asyncio

# --- KONFIGURACE ---
TOKEN = 'TVŮJ_TOKEN_ZDE'

class MusicBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)
        self.history = []
        self.current_url = None # Pro funkci skoku v čase

    async def setup_hook(self):
        await self.tree.sync()
        print(f"Bot {self.user} je připraven!")

bot = MusicBot()

YDL_OPTIONS = {
    'format': 'bestaudio/best',
    'noplaylist': True,
    'quiet': True,
    'default_search': 'ytsearch',
    'nocheckcertificate': True,
}

# --- TLAČÍTKA PRO HISTORII ---
class HistoryView(discord.ui.View):
    def __init__(self, history):
        super().__init__(timeout=60)
        self.history = history

    async def handle_click(self, interaction: discord.Interaction, index: int):
        if len(self.history) > index:
            await interaction.response.defer()
            await play_logic(interaction, self.history[index]['url'])
        else:
            await interaction.response.send_message("Tato pozice v historii neexistuje.", ephemeral=True)

    @discord.ui.button(label="1", style=discord.ButtonStyle.gray)
    async def b1(self, interaction: discord.Interaction, button: discord.ui.Button): await self.handle_click(interaction, 0)
    @discord.ui.button(label="2", style=discord.ButtonStyle.gray)
    async def b2(self, interaction: discord.Interaction, button: discord.ui.Button): await self.handle_click(interaction, 1)
    @discord.ui.button(label="3", style=discord.ButtonStyle.gray)
    async def b3(self, interaction: discord.Interaction, button: discord.ui.Button): await self.handle_click(interaction, 2)
    @discord.ui.button(label="4", style=discord.ButtonStyle.gray)
    async def b4(self, interaction: discord.Interaction, button: discord.ui.Button): await self.handle_click(interaction, 3)
    @discord.ui.button(label="5", style=discord.ButtonStyle.gray)
    async def b5(self, interaction: discord.Interaction, button: discord.ui.Button): await self.handle_click(interaction, 4)

# --- LOGIKA PŘEHRÁVÁNÍ (S PODPOROU SKOKU V ČASE) ---
async def play_logic(interaction: discord.Interaction, query: str, seek_time=None):
    if not interaction.user.voice:
        return await interaction.followup.send("❌ Musíš být ve voice kanálu!")

    voice_client = interaction.guild.voice_client
    if not voice_client:
        voice_client = await interaction.user.voice.channel.connect()

    # Ošetření Apple Music a vyhledávání
    processed_query = query
    if "music.apple.com" in query:
        parts = query.split('/')
        song_name = parts[-2].replace('-', ' ') if len(parts) > 2 else "music"
        processed_query = f"ytsearch1:{song_name} official audio"
    elif not query.startswith("http"):
        processed_query = f"ytsearch1:{query} audio"

    with yt_dlp.YoutubeDL(YDL_OPTIONS) as ydl:
        try:
            info = ydl.extract_info(processed_query, download=False)
            if 'entries' in info: info = info['entries'][0]
            
            url_stream = info['url']
            title = info['title']
            web_url = info.get('webpage_url', query)

            # Uložíme aktuální URL pro případný příkaz /to
            bot.current_url = web_url

            # FFmpeg nastavení (přidáme -ss pokud chceme skočit v čase)
            before_args = "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5"
            if seek_time:
                before_args += f" -ss {seek_time}"

            ffmpeg_opts = {'before_options': before_args, 'options': '-vn'}

            if voice_client.is_playing():
                voice_client.stop()

            # Historie
            entry = {"title": title, "url": web_url}
            if not seek_time: # Do historie dáváme jen nové písničky, ne skoky v čase
                if not bot.history or bot.history[0]['url'] != web_url:
                    bot.history.insert(0, entry)
                    if len(bot.history) > 5: bot.history.pop()

            source = discord.FFmpegOpusAudio(url_stream, **ffmpeg_opts)
            voice_client.play(source)

            if seek_time:
                await interaction.followup.send(f"⏩ Skočeno na **{seek_time}** v: **{title}**")
            else:
                await interaction.followup.send(f"🎶 Právě hraju: **{title}**")

        except Exception as e:
            await interaction.followup.send(f"⚠️ Chyba při načítání.")
            print(e)

# --- PŘÍKAZY ---

@bot.tree.command(name="play", description="Hraje hudbu")
async def play(interaction: discord.Interaction, hledat: str):
    await interaction.response.defer()
    await play_logic(interaction, hledat)

@bot.tree.command(name="last", description="Historie s tlačítky pro rychlé spuštění")
async def last(interaction: discord.Interaction):
    if not bot.history:
        return await interaction.response.send_message("Historie je prázdná.")
    
    embed = discord.Embed(title="📜 Posledních 5 skladeb", color=0x2b2d31)
    popis = ""
    for i, s in enumerate(bot.history, 1):
        popis += f"**{i}.** [{s['title']}]({s['url']})\n"
    embed.description = popis
    
    # Přidáme tlačítka 1-5
    view = HistoryView(bot.history)
    await interaction.response.send_message(embed=embed, view=view)

@bot.tree.command(name="to", description="Skočí na určitý čas v písničce (např. 1:30 nebo 90)")
async def to(interaction: discord.Interaction, cas: str):
    if not bot.current_url:
        return await interaction.response.send_message("Teď nic nehraje.", ephemeral=True)
    
    await interaction.response.defer()
    # Znovu spustíme play_logic se stejnou URL, ale s parametrem seek_time
    await play_logic(interaction, bot.current_url, seek_time=cas)

@bot.tree.command(name="stop", description="Zastaví a odpojí bota")
async def stop(interaction: discord.Interaction):
    if interaction.guild.voice_client:
        await interaction.guild.voice_client.disconnect()
        bot.current_url = None
        await interaction.response.send_message("👋 Čau!")
    else:
        await interaction.response.send_message("Nejsem v kanále.")

bot.run('MTQ2MjM4MDA4MTcyNzkzNDUxNw.GyAd17.g4WC8F7ZXsIIEGYrTk5dEL0hiNAsBVDTOHGFTI')