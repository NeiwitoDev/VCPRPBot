import os
import discord
from dotenv import load_dotenv
from datetime import datetime, timezone

load_dotenv()
TOKEN = os.getenv("TOKEN")


Canal_bienvenidas = 1506067514491273300


Canales_recomendados = [
    1506067514491273300,
    1491503883019616346,
    1491503916016341083,
    1491504028197326898
]

intents = discord.Intents.default()
intents.members = True

bot = discord.Client(intents=intents)

@bot.event
async def on_member_join(member: discord.Member):
    canal = member.guild.get_channel(Canal_bienvenidas)

    if not canal:
        return

    canales = " · ".join(f"<#{cid}>" for cid in Canales_recomendados)

    embed = discord.Embed(
        title=f"¡Bienvenido/a a {member.guild.name}! 🎉",
        description=(
            f"Hola {member.mention}, ¡nos alegra tenerte acá!\n"
            f"Sos el miembro número {member.guild.member_count}."
        ),
        color=discord.Color.from_str("#5865F2"),
        timestamp=datetime.now(timezone.utc)
    )

    embed.set_thumbnail(url=member.display_avatar.url)

    if member.guild.icon:
        embed.set_author(
            name=member.guild.name,
            icon_url=member.guild.icon.url
        )

    embed.add_field(
        name="👤 Usuario",
        value=f"{member} — {member.id}",
        inline=True
    )

    embed.add_field(
        name="📅 Cuenta creada",
        value=member.created_at.strftime("%d/%m/%Y"),
        inline=True
    )

    embed.add_field(
        name="📌 Canales recomendados",
        value=canales,
        inline=False
    )

    embed.set_footer(
        text="¡Esperamos que disfrutes tu estadía!"
    )

    await canal.send(
        content=member.mention,
        embed=embed
    )

@bot.event
async def on_ready():
    print(f"✅ Bot conectado como {bot.user}")

bot.run(TOKEN)
