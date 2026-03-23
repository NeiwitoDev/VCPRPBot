import os
import asyncio
import discord
import requests
import json
from discord import app_commands
from dotenv import load_dotenv
from datetime import datetime, timedelta
from collections import defaultdict, deque

# ===============================
# CONFIG
# ===============================
load_dotenv()
TOKEN = os.getenv("TOKEN")

STAFF_ROLE_ID     = 1466245030334435398
CANAL_AUTO_LOGS   = 1485695253880246332
CANAL_STAFF_LOGS  = 1485695589294276818
CANAL_SOLICITUDES = 1469498959004172388
CANAL_COMANDOS        = 1466231866041307187
CANAL_CALIFICACIONES  = 1466240831609638923
CANAL_BIENVENIDA      = 1466215432418492416

CANALES_RECOMENDADOS  = [
    1466216894242492436,
    1466229592858558565,
    1472388178131423262,
    1466240677607244012,
]


COLORES = {
    "warn":   discord.Color.from_str("#F5A623"),
    "ban":    discord.Color.from_str("#D0021B"),
    "kick":   discord.Color.from_str("#E85D04"),
    "mute":   discord.Color.from_str("#7B2D8B"),
    "unmute": discord.Color.from_str("#27AE60"),
    "clear":  discord.Color.from_str("#2980B9"),
    "lock":   discord.Color.from_str("#C0392B"),
    "unlock": discord.Color.from_str("#27AE60"),
    "info":   discord.Color.from_str("#3498DB"),
    "auto":   discord.Color.from_str("#E74C3C"),
    "ok":     discord.Color.from_str("#2ECC71"),
}

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot  = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)

# ===============================
# UTILIDADES
# ===============================
def es_staff(member: discord.Member) -> bool:
    return any(r.id == STAFF_ROLE_ID for r in member.roles)

def cargar() -> dict:
    if not os.path.exists("sanciones.json"):
        return {}
    with open("sanciones.json", "r") as f:
        return json.load(f)

def guardar(data: dict):
    with open("sanciones.json", "w") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def gen_id(data: dict) -> str:
    total = sum(len(v) for v in data.values())
    return f"#{total + 1:04d}"

def registrar(uid, tipo: str, motivo: str, staff) -> str:
    data  = cargar()
    uid   = str(uid)
    data.setdefault(uid, [])
    sid   = gen_id(data)
    data[uid].append({
        "id":     sid,
        "tipo":   tipo,
        "motivo": motivo,
        "staff":  str(staff),
        "fecha":  datetime.now().strftime("%d/%m/%Y %H:%M"),
    })
    guardar(data)
    return sid

def ts() -> str:
    return datetime.now().strftime("%d/%m/%Y %H:%M")

# ===============================
# DM AL USUARIO SANCIONADO
# ===============================
async def enviar_dm_sancion(user: discord.User, guild: discord.Guild, tipo: str, motivo: str, sid: str, staff, duracion: str = None):
    """Envía un DM profesional y detallado al usuario sancionado."""
    iconos = {
        "WARN":       "⚠️",
        "BAN":        "🔨",
        "KICK":       "👢",
        "MUTE":       "🔇",
        "AUTO-FLOOD": "🤖",
        "AUTO-SPAM":  "🤖",
    }
    icono = iconos.get(tipo, "🚫")

    descripciones = {
        "WARN":       "Has recibido una **advertencia** en el servidor.",
        "BAN":        "Has sido **baneado permanentemente** del servidor.",
        "KICK":       "Has sido **expulsado** del servidor.",
        "MUTE":       f"Has sido **silenciado** en el servidor{f' por **{duracion}**' if duracion else ''}.",
        "AUTO-FLOOD": "El sistema automático detectó que estabas enviando mensajes demasiado rápido (**flood**).",
        "AUTO-SPAM":  "El sistema automático detectó un **link no permitido** en tus mensajes.",
    }
    desc = descripciones.get(tipo, "Has recibido una sanción en el servidor.")

    staff_nombre = staff.display_name if hasattr(staff, "display_name") else str(staff)
    staff_tag    = str(staff) if hasattr(staff, "name") else "Sistema Automático"

    embed = discord.Embed(
        title=f"{icono} Sanción recibida — {tipo}",
        description=f"{desc}\n\nSi crees que esto fue un error, contacta a un administrador.",
        color=COLORES.get(tipo.lower().replace("auto-", "auto"), COLORES["auto"]),
        timestamp=datetime.utcnow(),
    )
    embed.set_author(name=guild.name, icon_url=guild.icon.url if guild.icon else None)
    if hasattr(staff, "display_avatar"):
        embed.set_thumbnail(url=staff.display_avatar.url)

    embed.add_field(name="🏠 Servidor",  value=guild.name,       inline=True)
    embed.add_field(name="📋 Tipo",      value=tipo,             inline=True)
    embed.add_field(name="🆔 ID",        value=f"`{sid}`",       inline=True)
    embed.add_field(name="📝 Motivo",    value=motivo,           inline=False)
    embed.add_field(name="👮 Staff",     value=f"{staff_nombre} (`{staff_tag}`)", inline=True)
    embed.add_field(name="📅 Fecha",     value=ts(),             inline=True)
    if duracion:
        embed.add_field(name="⏳ Duración", value=duracion,      inline=True)

    embed.set_footer(text="No respondas a este mensaje — es automático.")

    try:
        await user.send(embed=embed)
    except Exception:
        pass

# ===============================
# LOGS
# ===============================
async def log_staff(guild: discord.Guild, embed: discord.Embed):
    canal = guild.get_channel(CANAL_STAFF_LOGS)
    if canal:
        await canal.send(embed=embed)

async def log_auto(guild: discord.Guild, embed: discord.Embed):
    canal = guild.get_channel(CANAL_AUTO_LOGS)
    if canal:
        await canal.send(embed=embed)

def embed_log(tipo: str, staff: discord.Member, usuario: discord.Member, motivo: str, sid: str, extra: str = None) -> discord.Embed:
    iconos = {"WARN": "⚠️", "BAN": "🔨", "KICK": "👢", "MUTE": "🔇", "UNMUTE": "🔊"}
    icono  = iconos.get(tipo.upper(), "📋")
    color  = COLORES.get(tipo.lower(), discord.Color.blurple())

    embed = discord.Embed(
        title=f"{icono} {tipo} — Registro de moderación",
        color=color,
        timestamp=datetime.utcnow(),
    )
    embed.set_author(name=str(staff), icon_url=staff.display_avatar.url)
    embed.set_thumbnail(url=usuario.display_avatar.url)
    embed.add_field(name="👤 Usuario",  value=f"{usuario.mention}\n`{usuario}` — `{usuario.id}`", inline=True)
    embed.add_field(name="👮 Staff",    value=f"{staff.mention}\n`{staff}`",                       inline=True)
    embed.add_field(name="🆔 ID",       value=f"`{sid}`",                                          inline=True)
    embed.add_field(name="📝 Motivo",   value=motivo,                                              inline=False)
    if extra:
        embed.add_field(name="📌 Extra", value=extra,                                             inline=False)
    embed.set_footer(text=f"Fecha: {ts()}")
    return embed

# ===============================
# AUTO MOD
# ===============================
user_msgs: dict = defaultdict(lambda: deque(maxlen=5))

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    # ── COMANDO DE PREFIJO: !panel-send ──
    if message.content.strip().lower() == "!panel-send":
        if not es_staff(message.author):
            try:
                await message.delete()
            except Exception:
                pass
            return
        try:
            await message.delete()
        except Exception:
            pass
        await enviar_panel_tickets(message.channel, message.guild)
        return

    # ── El staff está exento del auto-mod ──
    if isinstance(message.author, discord.Member) and es_staff(message.author):
        return

    now = datetime.now().timestamp()
    user_msgs[message.author.id].append(now)

    # FLOOD
    if len(user_msgs[message.author.id]) >= 5 and now - user_msgs[message.author.id][0] <= 5:
        try:
            await message.delete()
        except Exception:
            pass
        sid = registrar(message.author.id, "AUTO-FLOOD", "Flood detectado automáticamente", "Sistema")
        await enviar_dm_sancion(message.author, message.guild, "AUTO-FLOOD", "Enviaste demasiados mensajes en poco tiempo.", sid, "Sistema Automático")

        embed = discord.Embed(
            title="🤖 Auto-Mod — Flood detectado",
            color=COLORES["auto"],
            timestamp=datetime.utcnow(),
        )
        embed.set_thumbnail(url=message.author.display_avatar.url)
        embed.add_field(name="👤 Usuario", value=f"{message.author.mention} (`{message.author}`)", inline=True)
        embed.add_field(name="🆔 ID",      value=f"`{sid}`",                                       inline=True)
        embed.add_field(name="📋 Canal",   value=message.channel.mention,                          inline=True)
        embed.set_footer(text=ts())
        await log_auto(message.guild, embed)
        return

    # SPAM (links)
    if "http://" in message.content or "https://" in message.content:
        try:
            await message.delete()
        except Exception:
            pass
        sid = registrar(message.author.id, "AUTO-SPAM", "Link no permitido detectado automáticamente", "Sistema")
        await enviar_dm_sancion(message.author, message.guild, "AUTO-SPAM", "No está permitido enviar links en este servidor.", sid, "Sistema Automático")

        embed = discord.Embed(
            title="🤖 Auto-Mod — Link detectado",
            color=COLORES["auto"],
            timestamp=datetime.utcnow(),
        )
        embed.set_thumbnail(url=message.author.display_avatar.url)
        embed.add_field(name="👤 Usuario", value=f"{message.author.mention} (`{message.author}`)", inline=True)
        embed.add_field(name="🆔 ID",      value=f"`{sid}`",                                       inline=True)
        embed.add_field(name="📋 Canal",   value=message.channel.mention,                          inline=True)
        embed.set_footer(text=ts())
        await log_auto(message.guild, embed)

# ===============================
# COMANDO: WARN
# ===============================
@tree.command(name="warn", description="Advertir a un usuario")
@app_commands.describe(usuario="Usuario a advertir", motivo="Motivo de la advertencia")
async def warn(interaction: discord.Interaction, usuario: discord.Member, motivo: str):
    if not es_staff(interaction.user):
        return await interaction.response.send_message("❌ No tienes permisos de staff.", ephemeral=True)

    sid = registrar(usuario.id, "WARN", motivo, interaction.user.id)
    await enviar_dm_sancion(usuario, interaction.guild, "WARN", motivo, sid, interaction.user)

    embed = embed_log("WARN", interaction.user, usuario, motivo, sid)
    await interaction.response.send_message(embed=embed, ephemeral=False)
    await log_staff(interaction.guild, embed)

# ===============================
# COMANDO: BAN
# ===============================
@tree.command(name="ban", description="Banear a un usuario del servidor")
@app_commands.describe(usuario="Usuario a banear", motivo="Motivo del ban")
async def ban(interaction: discord.Interaction, usuario: discord.Member, motivo: str = "Sin motivo especificado"):
    if not es_staff(interaction.user):
        return await interaction.response.send_message("❌ No tienes permisos de staff.", ephemeral=True)

    sid = registrar(usuario.id, "BAN", motivo, interaction.user.id)
    await enviar_dm_sancion(usuario, interaction.guild, "BAN", motivo, sid, interaction.user)

    embed = embed_log("BAN", interaction.user, usuario, motivo, sid)

    try:
        await usuario.ban(reason=f"[{sid}] {motivo} — por {interaction.user}")
    except discord.Forbidden:
        return await interaction.response.send_message("❌ No tengo permisos para banear a ese usuario.", ephemeral=True)

    await interaction.response.send_message(embed=embed, ephemeral=False)
    await log_staff(interaction.guild, embed)

# ===============================
# COMANDO: KICK
# ===============================
@tree.command(name="kick", description="Expulsar a un usuario del servidor")
@app_commands.describe(usuario="Usuario a expulsar", motivo="Motivo de la expulsión")
async def kick(interaction: discord.Interaction, usuario: discord.Member, motivo: str = "Sin motivo especificado"):
    if not es_staff(interaction.user):
        return await interaction.response.send_message("❌ No tienes permisos de staff.", ephemeral=True)

    sid = registrar(usuario.id, "KICK", motivo, interaction.user.id)
    await enviar_dm_sancion(usuario, interaction.guild, "KICK", motivo, sid, interaction.user)

    embed = embed_log("KICK", interaction.user, usuario, motivo, sid)

    try:
        await usuario.kick(reason=f"[{sid}] {motivo} — por {interaction.user}")
    except discord.Forbidden:
        return await interaction.response.send_message("❌ No tengo permisos para expulsar a ese usuario.", ephemeral=True)

    await interaction.response.send_message(embed=embed, ephemeral=False)
    await log_staff(interaction.guild, embed)

# ===============================
# COMANDO: MUTE (timeout)
# ===============================
@tree.command(name="mute", description="Silenciar a un usuario por un tiempo determinado")
@app_commands.describe(usuario="Usuario a silenciar", minutos="Duración en minutos", motivo="Motivo del mute")
async def mute(interaction: discord.Interaction, usuario: discord.Member, minutos: int, motivo: str = "Sin motivo especificado"):
    if not es_staff(interaction.user):
        return await interaction.response.send_message("❌ No tienes permisos de staff.", ephemeral=True)

    if minutos <= 0 or minutos > 40320:
        return await interaction.response.send_message("❌ La duración debe ser entre 1 y 40320 minutos (28 días).", ephemeral=True)

    duracion_str = f"{minutos} minuto{'s' if minutos != 1 else ''}"
    sid = registrar(usuario.id, "MUTE", motivo, interaction.user.id)
    await enviar_dm_sancion(usuario, interaction.guild, "MUTE", motivo, sid, interaction.user, duracion=duracion_str)

    try:
        await usuario.timeout(discord.utils.utcnow() + timedelta(minutes=minutos), reason=f"[{sid}] {motivo} — por {interaction.user}")
    except discord.Forbidden:
        return await interaction.response.send_message("❌ No tengo permisos para silenciar a ese usuario.", ephemeral=True)

    embed = embed_log("MUTE", interaction.user, usuario, motivo, sid, extra=f"⏳ Duración: **{duracion_str}**")
    await interaction.response.send_message(embed=embed, ephemeral=False)
    await log_staff(interaction.guild, embed)

# ===============================
# COMANDO: UNMUTE
# ===============================
@tree.command(name="unmute", description="Quitar el silencio a un usuario")
@app_commands.describe(usuario="Usuario a desmutear")
async def unmute(interaction: discord.Interaction, usuario: discord.Member):
    if not es_staff(interaction.user):
        return await interaction.response.send_message("❌ No tienes permisos de staff.", ephemeral=True)

    try:
        await usuario.timeout(None)
    except discord.Forbidden:
        return await interaction.response.send_message("❌ No tengo permisos para desmutear a ese usuario.", ephemeral=True)

    embed = discord.Embed(
        title="🔊 UNMUTE — Silencio removido",
        color=COLORES["unmute"],
        timestamp=datetime.utcnow(),
    )
    embed.set_author(name=str(interaction.user), icon_url=interaction.user.display_avatar.url)
    embed.set_thumbnail(url=usuario.display_avatar.url)
    embed.add_field(name="👤 Usuario", value=f"{usuario.mention} (`{usuario}`)", inline=True)
    embed.add_field(name="👮 Staff",   value=interaction.user.mention,           inline=True)
    embed.set_footer(text=f"Fecha: {ts()}")

    await interaction.response.send_message(embed=embed, ephemeral=False)
    await log_staff(interaction.guild, embed)

# ===============================
# COMANDO: CLEAR
# ===============================
@tree.command(name="clear", description="Eliminar mensajes del canal actual")
@app_commands.describe(cantidad="Cantidad de mensajes a eliminar (1–100)")
async def clear(interaction: discord.Interaction, cantidad: int):
    if not es_staff(interaction.user):
        return await interaction.response.send_message("❌ No tienes permisos de staff.", ephemeral=True)

    if cantidad < 1 or cantidad > 100:
        return await interaction.response.send_message("❌ La cantidad debe ser entre 1 y 100.", ephemeral=True)

    await interaction.response.defer(ephemeral=True)
    deleted = await interaction.channel.purge(limit=cantidad)

    embed = discord.Embed(
        title="🧹 CLEAR — Mensajes eliminados",
        color=COLORES["clear"],
        timestamp=datetime.utcnow(),
    )
    embed.set_author(name=str(interaction.user), icon_url=interaction.user.display_avatar.url)
    embed.add_field(name="🗑️ Eliminados", value=f"**{len(deleted)}** mensajes",   inline=True)
    embed.add_field(name="📋 Canal",      value=interaction.channel.mention,       inline=True)
    embed.add_field(name="👮 Staff",      value=interaction.user.mention,          inline=True)
    embed.set_footer(text=f"Fecha: {ts()}")

    await interaction.followup.send(embed=embed, ephemeral=True)
    await log_staff(interaction.guild, embed)

# ===============================
# COMANDO: LOCK
# ===============================
@tree.command(name="lock", description="Bloquear el canal actual")
@app_commands.describe(motivo="Motivo del bloqueo (opcional)")
async def lock(interaction: discord.Interaction, motivo: str = "Sin motivo especificado"):
    if not es_staff(interaction.user):
        return await interaction.response.send_message("❌ No tienes permisos de staff.", ephemeral=True)

    try:
        await interaction.channel.set_permissions(interaction.guild.default_role, send_messages=False)
    except discord.Forbidden:
        return await interaction.response.send_message("❌ No tengo permisos para bloquear este canal.", ephemeral=True)

    embed = discord.Embed(
        title="🔒 LOCK — Canal bloqueado",
        description=f"Este canal ha sido bloqueado por {interaction.user.mention}.",
        color=COLORES["lock"],
        timestamp=datetime.utcnow(),
    )
    embed.add_field(name="📝 Motivo", value=motivo, inline=False)
    embed.set_footer(text=f"Staff: {interaction.user} • {ts()}")

    await interaction.response.send_message(embed=embed)
    await log_staff(interaction.guild, embed)

# ===============================
# COMANDO: UNLOCK
# ===============================
@tree.command(name="unlock", description="Desbloquear el canal actual")
async def unlock(interaction: discord.Interaction):
    if not es_staff(interaction.user):
        return await interaction.response.send_message("❌ No tienes permisos de staff.", ephemeral=True)

    try:
        await interaction.channel.set_permissions(interaction.guild.default_role, send_messages=True)
    except discord.Forbidden:
        return await interaction.response.send_message("❌ No tengo permisos para desbloquear este canal.", ephemeral=True)

    embed = discord.Embed(
        title="🔓 UNLOCK — Canal desbloqueado",
        description=f"Este canal ha sido desbloqueado por {interaction.user.mention}.",
        color=COLORES["unlock"],
        timestamp=datetime.utcnow(),
    )
    embed.set_footer(text=f"Staff: {interaction.user} • {ts()}")

    await interaction.response.send_message(embed=embed)
    await log_staff(interaction.guild, embed)

# ===============================
# COMANDO: SLOWMODE
# ===============================
@tree.command(name="slowmode", description="Activar o desactivar el modo lento en el canal")
@app_commands.describe(segundos="Segundos de espera entre mensajes (0 para desactivar)")
async def slowmode(interaction: discord.Interaction, segundos: int):
    if not es_staff(interaction.user):
        return await interaction.response.send_message("❌ No tienes permisos de staff.", ephemeral=True)

    if segundos < 0 or segundos > 21600:
        return await interaction.response.send_message("❌ El valor debe ser entre 0 y 21600 segundos.", ephemeral=True)

    try:
        await interaction.channel.edit(slowmode_delay=segundos)
    except discord.Forbidden:
        return await interaction.response.send_message("❌ No tengo permisos para modificar este canal.", ephemeral=True)

    if segundos == 0:
        desc   = "El modo lento ha sido **desactivado** en este canal."
        titulo = "⚡ SLOWMODE — Desactivado"
        color  = COLORES["ok"]
    else:
        desc   = f"El modo lento ha sido activado: **{segundos} segundos** entre mensajes."
        titulo = "🐢 SLOWMODE — Activado"
        color  = COLORES["mute"]

    embed = discord.Embed(title=titulo, description=desc, color=color, timestamp=datetime.utcnow())
    embed.add_field(name="👮 Staff",  value=interaction.user.mention,    inline=True)
    embed.add_field(name="📋 Canal", value=interaction.channel.mention, inline=True)
    embed.set_footer(text=f"Fecha: {ts()}")

    await interaction.response.send_message(embed=embed)
    await log_staff(interaction.guild, embed)

# ===============================
# COMANDO: WARNINGS
# ===============================
class BorrarSancionSelect(discord.ui.Select):
    def __init__(self, usuario: discord.Member, sanciones: list):
        options = [
            discord.SelectOption(
                label=f"{s['id']} — {s['tipo']}",
                description=s["motivo"][:100],
                value=s["id"],
            )
            for s in sanciones
        ]
        super().__init__(placeholder="Selecciona una sanción para eliminar...", options=options)
        self.usuario = usuario

    async def callback(self, interaction: discord.Interaction):
        if not es_staff(interaction.user):
            return await interaction.response.send_message("❌ No tienes permisos.", ephemeral=True)

        data = cargar()
        uid  = str(self.usuario.id)
        antes = len(data.get(uid, []))
        data[uid] = [s for s in data.get(uid, []) if s["id"] != self.values[0]]
        guardar(data)
        despues = len(data[uid])

        if antes != despues:
            await interaction.response.send_message(f"✅ Sanción `{self.values[0]}` eliminada correctamente.", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ No se encontró la sanción `{self.values[0]}`.", ephemeral=True)

class VistaWarnings(discord.ui.View):
    def __init__(self, usuario: discord.Member, sanciones: list):
        super().__init__(timeout=120)
        self.add_item(BorrarSancionSelect(usuario, sanciones))

@tree.command(name="warnings", description="Ver el historial de sanciones de un usuario")
@app_commands.describe(usuario="Usuario a consultar")
async def warnings(interaction: discord.Interaction, usuario: discord.Member):
    if not es_staff(interaction.user):
        return await interaction.response.send_message("❌ No tienes permisos de staff.", ephemeral=True)

    data = cargar()
    uid  = str(usuario.id)
    sanciones = data.get(uid, [])

    if not sanciones:
        embed = discord.Embed(
            title="📋 Historial limpio",
            description=f"{usuario.mention} no tiene sanciones registradas.",
            color=COLORES["ok"],
        )
        embed.set_thumbnail(url=usuario.display_avatar.url)
        return await interaction.response.send_message(embed=embed, ephemeral=True)

    iconos = {"WARN": "⚠️", "BAN": "🔨", "KICK": "👢", "MUTE": "🔇", "AUTO-FLOOD": "🤖", "AUTO-SPAM": "🤖"}

    embed = discord.Embed(
        title=f"📋 Historial de sanciones — {usuario.display_name}",
        description=f"Total de sanciones: **{len(sanciones)}**",
        color=COLORES["info"],
        timestamp=datetime.utcnow(),
    )
    embed.set_thumbnail(url=usuario.display_avatar.url)
    embed.set_author(name=f"{usuario}", icon_url=usuario.display_avatar.url)

    for s in sanciones[-10:]:
        icono = iconos.get(s["tipo"], "📋")
        embed.add_field(
            name=f"{icono} {s['id']} — {s['tipo']}",
            value=(
                f"**Motivo:** {s['motivo']}\n"
                f"**Staff:** {s['staff']}\n"
                f"**Fecha:** {s['fecha']}"
            ),
            inline=False,
        )

    if len(sanciones) > 10:
        embed.set_footer(text=f"Mostrando las últimas 10 de {len(sanciones)} sanciones.")
    else:
        embed.set_footer(text=f"Solicitado por {interaction.user}")

    await interaction.response.send_message(embed=embed, view=VistaWarnings(usuario, sanciones), ephemeral=True)

# ===============================
# COMANDO: USERINFO
# ===============================
@tree.command(name="userinfo", description="Ver información detallada de un usuario")
@app_commands.describe(usuario="Usuario a consultar")
async def userinfo(interaction: discord.Interaction, usuario: discord.Member = None):
    if not es_staff(interaction.user):
        return await interaction.response.send_message("❌ No tienes permisos de staff.", ephemeral=True)

    target = usuario or interaction.user
    data   = cargar()
    uid    = str(target.id)
    total_sanciones = len(data.get(uid, []))

    roles = [r.mention for r in reversed(target.roles) if r.id != interaction.guild.id]
    roles_str = " ".join(roles) if roles else "Sin roles"

    embed = discord.Embed(
        title=f"👤 Información de {target.display_name}",
        color=COLORES["info"],
        timestamp=datetime.utcnow(),
    )
    embed.set_thumbnail(url=target.display_avatar.url)
    embed.add_field(name="🏷️ Tag",         value=str(target),                                         inline=True)
    embed.add_field(name="🆔 ID",          value=f"`{target.id}`",                                    inline=True)
    embed.add_field(name="🤖 Bot",         value="Sí" if target.bot else "No",                        inline=True)
    embed.add_field(name="📅 Cuenta creada", value=target.created_at.strftime("%d/%m/%Y"),            inline=True)
    embed.add_field(name="📅 Se unió",     value=target.joined_at.strftime("%d/%m/%Y") if target.joined_at else "Desconocido", inline=True)
    embed.add_field(name="⚠️ Sanciones",   value=f"**{total_sanciones}** registradas",               inline=True)
    embed.add_field(name="🎭 Roles",       value=roles_str[:1024],                                    inline=False)
    embed.set_footer(text=f"Solicitado por {interaction.user}")

    await interaction.response.send_message(embed=embed, ephemeral=True)

# ===============================
# MODERACIÓN AVANZADA: UNBAN
# ===============================
@tree.command(name="unban", description="Desbanear a un usuario usando su ID")
@app_commands.describe(usuario_id="ID del usuario a desbanear", motivo="Motivo del desbaneo")
async def unban(interaction: discord.Interaction, usuario_id: str, motivo: str = "Sin motivo especificado"):
    if not es_staff(interaction.user):
        return await interaction.response.send_message("❌ No tienes permisos de staff.", ephemeral=True)

    try:
        uid = int(usuario_id)
    except ValueError:
        return await interaction.response.send_message("❌ El ID debe ser un número válido.", ephemeral=True)

    try:
        user = await bot.fetch_user(uid)
        await interaction.guild.unban(user, reason=f"{motivo} — por {interaction.user}")
    except discord.NotFound:
        return await interaction.response.send_message("❌ No se encontró ningún ban para ese ID.", ephemeral=True)
    except discord.Forbidden:
        return await interaction.response.send_message("❌ No tengo permisos para desbanear.", ephemeral=True)

    embed = discord.Embed(
        title="✅ UNBAN — Usuario desbaneado",
        color=COLORES["ok"],
        timestamp=datetime.utcnow(),
    )
    embed.set_author(name=str(interaction.user), icon_url=interaction.user.display_avatar.url)
    embed.set_thumbnail(url=user.display_avatar.url)
    embed.add_field(name="👤 Usuario", value=f"`{user}` — `{user.id}`", inline=True)
    embed.add_field(name="👮 Staff",   value=interaction.user.mention,  inline=True)
    embed.add_field(name="📝 Motivo",  value=motivo,                    inline=False)
    embed.set_footer(text=f"Fecha: {ts()}")

    await interaction.response.send_message(embed=embed)
    await log_staff(interaction.guild, embed)

# ===============================
# MODERACIÓN AVANZADA: NICK
# ===============================
@tree.command(name="nick", description="Cambiar el apodo de un usuario")
@app_commands.describe(usuario="Usuario al que cambiar el apodo", nombre="Nuevo apodo (vacío para resetear)")
async def nick(interaction: discord.Interaction, usuario: discord.Member, nombre: str = None):
    if not es_staff(interaction.user):
        return await interaction.response.send_message("❌ No tienes permisos de staff.", ephemeral=True)

    apodo_anterior = usuario.display_name
    try:
        await usuario.edit(nick=nombre)
    except discord.Forbidden:
        return await interaction.response.send_message("❌ No tengo permisos para cambiar el apodo de ese usuario.", ephemeral=True)

    embed = discord.Embed(
        title="✏️ NICK — Apodo cambiado",
        color=COLORES["info"],
        timestamp=datetime.utcnow(),
    )
    embed.set_thumbnail(url=usuario.display_avatar.url)
    embed.add_field(name="👤 Usuario",     value=f"{usuario.mention} (`{usuario}`)", inline=False)
    embed.add_field(name="📛 Antes",       value=apodo_anterior,                     inline=True)
    embed.add_field(name="✅ Ahora",        value=nombre or usuario.name,             inline=True)
    embed.add_field(name="👮 Staff",       value=interaction.user.mention,           inline=True)
    embed.set_footer(text=f"Fecha: {ts()}")

    await interaction.response.send_message(embed=embed, ephemeral=True)
    await log_staff(interaction.guild, embed)

# ===============================
# MODERACIÓN AVANZADA: ROL-ADD / ROL-REMOVE
# ===============================
@tree.command(name="rol-add", description="Añadir un rol a un usuario")
@app_commands.describe(usuario="Usuario objetivo", rol="Rol a añadir")
async def rol_add(interaction: discord.Interaction, usuario: discord.Member, rol: discord.Role):
    if not es_staff(interaction.user):
        return await interaction.response.send_message("❌ No tienes permisos de staff.", ephemeral=True)

    if rol in usuario.roles:
        return await interaction.response.send_message(f"❌ {usuario.mention} ya tiene el rol {rol.mention}.", ephemeral=True)

    try:
        await usuario.add_roles(rol, reason=f"Por {interaction.user}")
    except discord.Forbidden:
        return await interaction.response.send_message("❌ No tengo permisos para asignar ese rol.", ephemeral=True)

    embed = discord.Embed(
        title="➕ ROL AÑADIDO",
        color=rol.color if rol.color.value else COLORES["ok"],
        timestamp=datetime.utcnow(),
    )
    embed.set_thumbnail(url=usuario.display_avatar.url)
    embed.add_field(name="👤 Usuario", value=f"{usuario.mention} (`{usuario}`)", inline=True)
    embed.add_field(name="🎭 Rol",     value=rol.mention,                        inline=True)
    embed.add_field(name="👮 Staff",   value=interaction.user.mention,           inline=True)
    embed.set_footer(text=f"Fecha: {ts()}")

    await interaction.response.send_message(embed=embed, ephemeral=True)
    await log_staff(interaction.guild, embed)

@tree.command(name="rol-remove", description="Quitar un rol a un usuario")
@app_commands.describe(usuario="Usuario objetivo", rol="Rol a quitar")
async def rol_remove(interaction: discord.Interaction, usuario: discord.Member, rol: discord.Role):
    if not es_staff(interaction.user):
        return await interaction.response.send_message("❌ No tienes permisos de staff.", ephemeral=True)

    if rol not in usuario.roles:
        return await interaction.response.send_message(f"❌ {usuario.mention} no tiene el rol {rol.mention}.", ephemeral=True)

    try:
        await usuario.remove_roles(rol, reason=f"Por {interaction.user}")
    except discord.Forbidden:
        return await interaction.response.send_message("❌ No tengo permisos para quitar ese rol.", ephemeral=True)

    embed = discord.Embed(
        title="➖ ROL QUITADO",
        color=COLORES["warn"],
        timestamp=datetime.utcnow(),
    )
    embed.set_thumbnail(url=usuario.display_avatar.url)
    embed.add_field(name="👤 Usuario", value=f"{usuario.mention} (`{usuario}`)", inline=True)
    embed.add_field(name="🎭 Rol",     value=rol.mention,                        inline=True)
    embed.add_field(name="👮 Staff",   value=interaction.user.mention,           inline=True)
    embed.set_footer(text=f"Fecha: {ts()}")

    await interaction.response.send_message(embed=embed, ephemeral=True)
    await log_staff(interaction.guild, embed)

# ===============================
# MODERACIÓN AVANZADA: BANS
# ===============================
@tree.command(name="bans", description="Ver la lista de usuarios baneados del servidor")
async def bans(interaction: discord.Interaction):
    if not es_staff(interaction.user):
        return await interaction.response.send_message("❌ No tienes permisos de staff.", ephemeral=True)

    await interaction.response.defer(ephemeral=True)

    try:
        ban_list = [entry async for entry in interaction.guild.bans()]
    except discord.Forbidden:
        return await interaction.followup.send("❌ No tengo permisos para ver los bans.", ephemeral=True)

    if not ban_list:
        return await interaction.followup.send("✅ No hay usuarios baneados en este servidor.", ephemeral=True)

    embed = discord.Embed(
        title=f"🔨 Lista de baneados — {len(ban_list)} usuario{'s' if len(ban_list) != 1 else ''}",
        color=COLORES["ban"],
        timestamp=datetime.utcnow(),
    )
    lineas = []
    for entry in ban_list[:25]:
        motivo = entry.reason or "Sin motivo"
        lineas.append(f"• **{entry.user}** (`{entry.user.id}`) — {motivo[:60]}")

    embed.description = "\n".join(lineas)
    if len(ban_list) > 25:
        embed.set_footer(text=f"Mostrando 25 de {len(ban_list)} bans.")
    else:
        embed.set_footer(text=f"Solicitado por {interaction.user}")

    await interaction.followup.send(embed=embed, ephemeral=True)

# ===============================
# SERVIDOR: SERVERINFO
# ===============================
@tree.command(name="serverinfo", description="Ver información detallada del servidor")
async def serverinfo(interaction: discord.Interaction):
    if not es_staff(interaction.user):
        return await interaction.response.send_message("❌ No tienes permisos de staff.", ephemeral=True)

    g = interaction.guild
    total_bots    = sum(1 for m in g.members if m.bot)
    total_humanos = g.member_count - total_bots
    canales_texto = len(g.text_channels)
    canales_voz   = len(g.voice_channels)
    nivel_boost   = g.premium_tier
    boosts        = g.premium_subscription_count

    embed = discord.Embed(
        title=f"🏠 {g.name}",
        description=g.description or "Sin descripción.",
        color=COLORES["info"],
        timestamp=datetime.utcnow(),
    )
    if g.icon:
        embed.set_thumbnail(url=g.icon.url)
    if g.banner:
        embed.set_image(url=g.banner.url)

    embed.add_field(name="🆔 ID",            value=f"`{g.id}`",                              inline=True)
    embed.add_field(name="👑 Dueño",         value=g.owner.mention if g.owner else "?",      inline=True)
    embed.add_field(name="📅 Creado",        value=g.created_at.strftime("%d/%m/%Y"),        inline=True)
    embed.add_field(name="👥 Miembros",      value=f"**{total_humanos}** humanos • **{total_bots}** bots", inline=True)
    embed.add_field(name="💬 Canales",       value=f"**{canales_texto}** texto • **{canales_voz}** voz",  inline=True)
    embed.add_field(name="🎭 Roles",         value=f"**{len(g.roles)}**",                    inline=True)
    embed.add_field(name="🚀 Boost",         value=f"Nivel **{nivel_boost}** — **{boosts}** boosts", inline=True)
    embed.add_field(name="😀 Emojis",        value=f"**{len(g.emojis)}**",                   inline=True)
    embed.add_field(name="🔒 Verificación",  value=str(g.verification_level).capitalize(),   inline=True)
    embed.set_footer(text=f"Solicitado por {interaction.user}")

    await interaction.response.send_message(embed=embed, ephemeral=True)

# ===============================
# NOTAS INTERNAS DE STAFF
# ===============================
def cargar_notas() -> dict:
    if not os.path.exists("notas.json"):
        return {}
    with open("notas.json", "r") as f:
        return json.load(f)

def guardar_notas(data: dict):
    with open("notas.json", "w") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

@tree.command(name="nota", description="Añadir una nota interna de staff sobre un usuario")
@app_commands.describe(usuario="Usuario sobre el que añadir la nota", texto="Contenido de la nota")
async def nota(interaction: discord.Interaction, usuario: discord.Member, texto: str):
    if not es_staff(interaction.user):
        return await interaction.response.send_message("❌ No tienes permisos de staff.", ephemeral=True)

    notas = cargar_notas()
    uid   = str(usuario.id)
    notas.setdefault(uid, [])
    notas[uid].append({
        "texto":  texto,
        "staff":  str(interaction.user),
        "fecha":  ts(),
    })
    guardar_notas(notas)

    embed = discord.Embed(
        title="📝 Nota añadida",
        color=COLORES["info"],
        timestamp=datetime.utcnow(),
    )
    embed.set_thumbnail(url=usuario.display_avatar.url)
    embed.add_field(name="👤 Usuario", value=f"{usuario.mention} (`{usuario}`)", inline=True)
    embed.add_field(name="👮 Staff",   value=interaction.user.mention,           inline=True)
    embed.add_field(name="📝 Nota",    value=texto,                              inline=False)
    embed.set_footer(text=f"Total de notas: {len(notas[uid])}")

    await interaction.response.send_message(embed=embed, ephemeral=True)

@tree.command(name="notas", description="Ver las notas internas de un usuario")
@app_commands.describe(usuario="Usuario a consultar")
async def notas_cmd(interaction: discord.Interaction, usuario: discord.Member):
    if not es_staff(interaction.user):
        return await interaction.response.send_message("❌ No tienes permisos de staff.", ephemeral=True)

    notas = cargar_notas()
    uid   = str(usuario.id)
    lista = notas.get(uid, [])

    if not lista:
        return await interaction.response.send_message(
            f"📝 {usuario.mention} no tiene notas internas.", ephemeral=True
        )

    embed = discord.Embed(
        title=f"📝 Notas internas — {usuario.display_name}",
        description=f"Total: **{len(lista)}** nota{'s' if len(lista) != 1 else ''}",
        color=COLORES["info"],
        timestamp=datetime.utcnow(),
    )
    embed.set_thumbnail(url=usuario.display_avatar.url)
    for i, n in enumerate(lista[-10:], 1):
        embed.add_field(
            name=f"📌 Nota #{i}",
            value=f"{n['texto']}\n— *{n['staff']}* • {n['fecha']}",
            inline=False,
        )
    embed.set_footer(text=f"Solicitado por {interaction.user}")

    await interaction.response.send_message(embed=embed, ephemeral=True)

# ===============================
# REPORTES
# ===============================
class ReporteView(discord.ui.View):
    def __init__(self, reportado: discord.Member, reportador: discord.Member, motivo: str):
        super().__init__(timeout=None)
        self.reportado  = reportado
        self.reportador = reportador
        self.motivo     = motivo

    @discord.ui.button(label="⚠️ Warn", style=discord.ButtonStyle.danger)
    async def btn_warn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not es_staff(interaction.user):
            return await interaction.response.send_message("❌ No tienes permisos.", ephemeral=True)
        sid = registrar(self.reportado.id, "WARN", f"Reporte: {self.motivo}", interaction.user.id)
        await enviar_dm_sancion(self.reportado, interaction.guild, "WARN", f"Reporte: {self.motivo}", sid, interaction.user)
        embed = embed_log("WARN", interaction.user, self.reportado, f"Reporte: {self.motivo}", sid)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        await log_staff(interaction.guild, embed)
        self.disable_all_items()
        await interaction.message.edit(view=self)

    @discord.ui.button(label="🔇 Mute 10min", style=discord.ButtonStyle.secondary)
    async def btn_mute(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not es_staff(interaction.user):
            return await interaction.response.send_message("❌ No tienes permisos.", ephemeral=True)
        try:
            sid = registrar(self.reportado.id, "MUTE", f"Reporte: {self.motivo}", interaction.user.id)
            await self.reportado.timeout(discord.utils.utcnow() + timedelta(minutes=10))
            await enviar_dm_sancion(self.reportado, interaction.guild, "MUTE", f"Reporte: {self.motivo}", sid, interaction.user, "10 minutos")
            embed = embed_log("MUTE", interaction.user, self.reportado, f"Reporte: {self.motivo}", sid, extra="⏳ Duración: **10 minutos**")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            await log_staff(interaction.guild, embed)
        except Exception:
            await interaction.response.send_message("❌ No se pudo mutear.", ephemeral=True)
        self.disable_all_items()
        await interaction.message.edit(view=self)

    @discord.ui.button(label="✅ Ignorar", style=discord.ButtonStyle.success)
    async def btn_ignorar(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not es_staff(interaction.user):
            return await interaction.response.send_message("❌ No tienes permisos.", ephemeral=True)
        await interaction.response.send_message("✅ Reporte ignorado.", ephemeral=True)
        self.disable_all_items()
        await interaction.message.edit(view=self)

    def disable_all_items(self):
        for item in self.children:
            item.disabled = True

@tree.command(name="report", description="Reportar a un usuario al equipo de staff")
@app_commands.describe(usuario="Usuario a reportar", motivo="Motivo del reporte")
async def report(interaction: discord.Interaction, usuario: discord.Member, motivo: str):
    if usuario.id == interaction.user.id:
        return await interaction.response.send_message("❌ No puedes reportarte a ti mismo.", ephemeral=True)
    if usuario.bot:
        return await interaction.response.send_message("❌ No puedes reportar a un bot.", ephemeral=True)

    canal_staff = interaction.guild.get_channel(CANAL_STAFF_LOGS)
    if not canal_staff:
        return await interaction.response.send_message("❌ No se pudo enviar el reporte.", ephemeral=True)

    embed = discord.Embed(
        title="🚨 Nuevo reporte recibido",
        description=f"Un miembro ha reportado a un usuario. El equipo de staff debe revisar el caso.",
        color=discord.Color.from_str("#FF4500"),
        timestamp=datetime.utcnow(),
    )
    embed.set_thumbnail(url=usuario.display_avatar.url)
    embed.add_field(name="🎯 Reportado",   value=f"{usuario.mention}\n`{usuario}` — `{usuario.id}`",         inline=True)
    embed.add_field(name="📢 Reportador",  value=f"{interaction.user.mention}\n`{interaction.user}`",         inline=True)
    embed.add_field(name="📝 Motivo",      value=motivo,                                                       inline=False)
    embed.add_field(name="📋 Canal",       value=interaction.channel.mention,                                  inline=True)
    embed.set_footer(text="Usa los botones para actuar sobre el reporte.")

    view = ReporteView(usuario, interaction.user, motivo)
    await canal_staff.send(embed=embed, view=view)

    await interaction.response.send_message(
        "✅ Tu reporte fue enviado al equipo de staff. Gracias por ayudar a mantener el servidor.",
        ephemeral=True,
    )

# ===============================
# SEGURIDAD: RAID MODE
# ===============================
raid_guilds: set = set()

@tree.command(name="raid-mode", description="Activar o desactivar el modo anti-raid")
@app_commands.describe(estado="on para activar, off para desactivar")
@app_commands.choices(estado=[
    app_commands.Choice(name="Activar", value="on"),
    app_commands.Choice(name="Desactivar", value="off"),
])
async def raid_mode(interaction: discord.Interaction, estado: app_commands.Choice[str]):
    if not es_staff(interaction.user):
        return await interaction.response.send_message("❌ No tienes permisos de staff.", ephemeral=True)

    gid = interaction.guild.id

    if estado.value == "on":
        raid_guilds.add(gid)
        color  = COLORES["ban"]
        titulo = "🛡️ RAID MODE — ACTIVADO"
        desc   = (
            "**El modo anti-raid está activo.**\n\n"
            "Cualquier cuenta nueva que ingrese al servidor será silenciada automáticamente por 30 minutos "
            "hasta que un staff la revise y libere manualmente con `/unmute`."
        )
    else:
        raid_guilds.discard(gid)
        color  = COLORES["ok"]
        titulo = "🛡️ RAID MODE — DESACTIVADO"
        desc   = "El modo anti-raid ha sido desactivado. Los nuevos miembros podrán unirse con normalidad."

    embed = discord.Embed(title=titulo, description=desc, color=color, timestamp=datetime.utcnow())
    embed.add_field(name="👮 Activado por", value=interaction.user.mention, inline=True)
    embed.add_field(name="📅 Fecha",        value=ts(),                     inline=True)
    embed.set_footer(text=interaction.guild.name)

    await interaction.response.send_message(embed=embed)
    await log_staff(interaction.guild, embed)

@bot.event
async def on_member_join(member: discord.Member):
    # ── Bienvenida ──
    canal_bienvenida = member.guild.get_channel(CANAL_BIENVENIDA)
    if canal_bienvenida:
        menciones = " · ".join(f"<#{cid}>" for cid in CANALES_RECOMENDADOS)
        embed_bv = discord.Embed(
            title=f"¡Bienvenido/a a {member.guild.name}! 🎉",
            description=(
                f"Hola {member.mention}, ¡nos alegra tenerte acá!\n\n"
                f"Sos el miembro número **{member.guild.member_count}** del servidor.\n"
                f"Leé las reglas y explorá los canales para integrarte a la comunidad."
            ),
            color=discord.Color.from_str("#5865F2"),
            timestamp=datetime.utcnow(),
        )
        embed_bv.set_thumbnail(url=member.display_avatar.url)
        if member.guild.icon:
            embed_bv.set_author(name=member.guild.name, icon_url=member.guild.icon.url)
        embed_bv.add_field(name="👤 Usuario",              value=f"`{member}` — `{member.id}`",              inline=True)
        embed_bv.add_field(name="📅 Cuenta creada",        value=member.created_at.strftime("%d/%m/%Y"),     inline=True)
        embed_bv.add_field(name="📌 Canales recomendados", value=menciones,                                  inline=False)
        embed_bv.set_footer(text=f"¡Esperamos que disfrutes tu estadía!")
        try:
            await canal_bienvenida.send(content=member.mention, embed=embed_bv)
        except Exception:
            pass

    # ── Raid mode ──
    if member.guild.id not in raid_guilds:
        return
    try:
        await member.timeout(discord.utils.utcnow() + timedelta(minutes=30), reason="[Raid Mode] Cuenta nueva silenciada automáticamente")
        embed_rm = discord.Embed(
            title="🛡️ Raid Mode — Nuevo miembro silenciado",
            description=f"{member.mention} fue silenciado automáticamente por 30 minutos al unirse durante el modo anti-raid.",
            color=COLORES["mute"],
            timestamp=datetime.utcnow(),
        )
        embed_rm.set_thumbnail(url=member.display_avatar.url)
        embed_rm.add_field(name="👤 Usuario", value=f"`{member}` — `{member.id}`",          inline=True)
        embed_rm.add_field(name="📅 Cuenta",  value=member.created_at.strftime("%d/%m/%Y"), inline=True)
        embed_rm.set_footer(text="Revisalo y usá /unmute si es legítimo.")
        canal_rm = member.guild.get_channel(CANAL_STAFF_LOGS)
        if canal_rm:
            await canal_rm.send(embed=embed_rm)
    except Exception:
        pass

# ===============================
# SEGURIDAD: BORRAR SANCIONES
# ===============================
class ConfirmarBorradoView(discord.ui.View):
    def __init__(self, usuario: discord.Member, total: int):
        super().__init__(timeout=30)
        self.usuario = usuario
        self.total   = total

    @discord.ui.button(label="✅ Sí, borrar todo", style=discord.ButtonStyle.danger)
    async def confirmar(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not es_staff(interaction.user):
            return await interaction.response.send_message("❌ No tienes permisos.", ephemeral=True)

        data = cargar()
        uid  = str(self.usuario.id)
        data[uid] = []
        guardar(data)

        embed = discord.Embed(
            title="🗑️ Sanciones eliminadas",
            description=f"Se eliminaron **{self.total}** sanciones de {self.usuario.mention}.",
            color=COLORES["ok"],
            timestamp=datetime.utcnow(),
        )
        embed.add_field(name="👮 Staff", value=interaction.user.mention, inline=True)
        embed.set_footer(text=f"Fecha: {ts()}")

        self.disable_all_items()
        await interaction.response.edit_message(embed=embed, view=self)
        await log_staff(interaction.guild, embed)

    @discord.ui.button(label="❌ Cancelar", style=discord.ButtonStyle.secondary)
    async def cancelar(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.disable_all_items()
        await interaction.response.edit_message(content="❌ Operación cancelada.", embed=None, view=self)

    def disable_all_items(self):
        for item in self.children:
            item.disabled = True

@tree.command(name="borrar-sanciones", description="Borrar TODAS las sanciones de un usuario")
@app_commands.describe(usuario="Usuario al que limpiar el historial")
async def borrar_sanciones(interaction: discord.Interaction, usuario: discord.Member):
    if not es_staff(interaction.user):
        return await interaction.response.send_message("❌ No tienes permisos de staff.", ephemeral=True)

    data     = cargar()
    uid      = str(usuario.id)
    sanciones = data.get(uid, [])

    if not sanciones:
        return await interaction.response.send_message(
            f"✅ {usuario.mention} no tiene sanciones registradas.", ephemeral=True
        )

    embed = discord.Embed(
        title="⚠️ ¿Confirmar borrado total?",
        description=(
            f"Estás a punto de eliminar **{len(sanciones)}** sanción(es) de {usuario.mention}.\n\n"
            "**Esta acción no se puede deshacer.**"
        ),
        color=COLORES["warn"],
    )
    embed.set_thumbnail(url=usuario.display_avatar.url)
    embed.set_footer(text="Esta confirmación expira en 30 segundos.")

    await interaction.response.send_message(
        embed=embed,
        view=ConfirmarBorradoView(usuario, len(sanciones)),
        ephemeral=True,
    )

# ===============================
# CALIFICACIONES — UTILIDADES
# ===============================
def cargar_calificaciones() -> dict:
    if not os.path.exists("calificaciones.json"):
        return {}
    with open("calificaciones.json", "r") as f:
        return json.load(f)

def guardar_calificaciones(data: dict):
    with open("calificaciones.json", "w") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def estrellas(promedio: float) -> str:
    llenas  = int(round(promedio))
    vacias  = 5 - llenas
    return "⭐" * llenas + "✦" * vacias

def barra_progreso(valor: float, maximo: float = 5.0, longitud: int = 10) -> str:
    if maximo == 0:
        return "▱" * longitud
    relleno = round((valor / maximo) * longitud)
    return "▰" * relleno + "▱" * (longitud - relleno)

# ===============================
# CALIFICACIONES — MODAL
# ===============================
class CalificarModal(discord.ui.Modal, title="✦ Calificar miembro del staff"):
    puntuacion = discord.ui.TextInput(
        label="Puntuación (1 al 5)",
        placeholder="Ingresá un número del 1 al 5...",
        min_length=1,
        max_length=1,
        required=True,
    )
    comentario = discord.ui.TextInput(
        label="Comentario (opcional)",
        placeholder="¿Qué destacás de este staff?",
        style=discord.TextStyle.paragraph,
        required=False,
        max_length=300,
    )

    def __init__(self, staff_member: discord.Member):
        super().__init__()
        self.staff_member = staff_member

    async def on_submit(self, interaction: discord.Interaction):
        try:
            score = int(self.puntuacion.value)
            if score < 1 or score > 5:
                raise ValueError
        except ValueError:
            return await interaction.response.send_message(
                "❌ La puntuación debe ser un número entre **1** y **5**.", ephemeral=True
            )

        uid    = str(self.staff_member.id)
        data   = cargar_calificaciones()
        data.setdefault(uid, [])

        ya_califico = any(str(c["calificador_id"]) == str(interaction.user.id) for c in data[uid])
        if ya_califico:
            return await interaction.response.send_message(
                "❌ Ya calificaste a este staff. Solo se permite **una calificación por persona**.", ephemeral=True
            )

        comentario_texto = self.comentario.value.strip() or "Sin comentario."
        data[uid].append({
            "puntuacion":     score,
            "comentario":     comentario_texto,
            "calificador_id": str(interaction.user.id),
            "calificador":    str(interaction.user),
            "fecha":          ts(),
        })
        guardar_calificaciones(data)

        promedio  = sum(c["puntuacion"] for c in data[uid]) / len(data[uid])
        total_cal = len(data[uid])

        canal = interaction.guild.get_channel(CANAL_CALIFICACIONES)
        if canal:
            embed = discord.Embed(
                description=(
                    f"```\n"
                    f"  ✦ NUEVA CALIFICACIÓN DE STAFF ✦\n"
                    f"```"
                ),
                color=discord.Color.from_str("#FFD700"),
                timestamp=datetime.utcnow(),
            )

            embed.set_author(
                name=f"✦  {self.staff_member.display_name}  ✦",
                icon_url=self.staff_member.display_avatar.url,
            )
            embed.set_thumbnail(url=self.staff_member.display_avatar.url)

            embed.add_field(
                name="╔═ 👮 Staff calificado",
                value=(
                    f"┃ {self.staff_member.mention}\n"
                    f"┗ `{self.staff_member}`"
                ),
                inline=True,
            )
            embed.add_field(
                name="╔═ 📢 Calificado por",
                value=(
                    f"┃ {interaction.user.mention}\n"
                    f"┗ `{interaction.user}`"
                ),
                inline=True,
            )
            embed.add_field(name="\u200b", value="\u200b", inline=False)

            embed.add_field(
                name="╔═ ⭐ Puntuación recibida",
                value=(
                    f"┃ {estrellas(score)}  **{score} / 5**\n"
                    f"┗ {barra_progreso(score)}"
                ),
                inline=True,
            )
            embed.add_field(
                name="╔═ 📊 Promedio actual",
                value=(
                    f"┃ {estrellas(promedio)}  **{promedio:.2f} / 5**\n"
                    f"┗ {barra_progreso(promedio)} — {total_cal} reseña{'s' if total_cal != 1 else ''}"
                ),
                inline=True,
            )
            embed.add_field(name="\u200b", value="\u200b", inline=False)

            embed.add_field(
                name="╔═ 💬 Comentario",
                value=f"┗ *\"{comentario_texto}\"*",
                inline=False,
            )

            embed.set_footer(
                text=f"✦ Sistema de calificaciones  •  {ts()}",
                icon_url=interaction.guild.icon.url if interaction.guild.icon else None,
            )
            await canal.send(embed=embed)

        confirmacion = discord.Embed(
            title="✅ Calificación enviada",
            description=f"Gracias por calificar a **{self.staff_member.display_name}**.\nTu opinión ayuda a mejorar el equipo de staff.",
            color=COLORES["ok"],
        )
        confirmacion.add_field(name="⭐ Tu puntuación", value=f"{estrellas(score)}  **{score}/5**", inline=True)
        confirmacion.set_footer(text="Solo se permite una calificación por staff.")
        await interaction.response.send_message(embed=confirmacion, ephemeral=True)


# ===============================
# COMANDO: CALIFICAR-STAFF
# ===============================
@tree.command(name="calificar-staff", description="Califica a un miembro del equipo de staff")
@app_commands.describe(staff="Miembro del staff a calificar")
async def calificar_staff(interaction: discord.Interaction, staff: discord.Member):
    if interaction.channel_id != CANAL_COMANDOS:
        canal = interaction.guild.get_channel(CANAL_COMANDOS)
        ref   = canal.mention if canal else f"`#{CANAL_COMANDOS}`"
        return await interaction.response.send_message(
            f"❌ Este comando solo se puede usar en {ref}.", ephemeral=True
        )

    if not any(r.id == STAFF_ROLE_ID for r in staff.roles):
        return await interaction.response.send_message(
            "❌ Ese usuario no es miembro del staff.", ephemeral=True
        )

    if staff.id == interaction.user.id:
        return await interaction.response.send_message(
            "❌ No puedes calificarte a ti mismo.", ephemeral=True
        )

    if staff.bot:
        return await interaction.response.send_message(
            "❌ No puedes calificar a un bot.", ephemeral=True
        )

    await interaction.response.send_modal(CalificarModal(staff))


# ===============================
# COMANDO: STATS-MOD
# ===============================
@tree.command(name="stats-mod", description="Ver estadísticas completas de un miembro del staff")
@app_commands.describe(staff="Staff a consultar (omitir para ver el tuyo)")
async def stats_mod(interaction: discord.Interaction, staff: discord.Member = None):
    if not es_staff(interaction.user):
        return await interaction.response.send_message("❌ No tienes permisos de staff.", ephemeral=True)

    target = staff or interaction.user

    if not any(r.id == STAFF_ROLE_ID for r in target.roles):
        return await interaction.response.send_message("❌ Ese usuario no es miembro del staff.", ephemeral=True)

    sanciones_data     = cargar()
    calificaciones_data = cargar_calificaciones()

    conteo = {"WARN": 0, "BAN": 0, "KICK": 0, "MUTE": 0, "UNMUTE": 0, "AUTO-FLOOD": 0, "AUTO-SPAM": 0}
    total_acciones = 0

    for uid, lista in sanciones_data.items():
        for s in lista:
            if s.get("staff") == str(target.id):
                tipo = s.get("tipo", "OTRO")
                conteo[tipo] = conteo.get(tipo, 0) + 1
                total_acciones += 1

    cal_lista  = calificaciones_data.get(str(target.id), [])
    total_cal  = len(cal_lista)
    promedio   = sum(c["puntuacion"] for c in cal_lista) / total_cal if cal_lista else 0.0

    dist = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    for c in cal_lista:
        dist[c["puntuacion"]] = dist.get(c["puntuacion"], 0) + 1

    embed = discord.Embed(
        description=(
            "```\n"
            f"  ✦ ESTADÍSTICAS DE STAFF ✦\n"
            "```"
        ),
        color=discord.Color.from_str("#5865F2"),
        timestamp=datetime.utcnow(),
    )
    embed.set_author(
        name=f"✦  {target.display_name}  ✦",
        icon_url=target.display_avatar.url,
    )
    embed.set_thumbnail(url=target.display_avatar.url)

    if total_cal > 0:
        embed.add_field(
            name="╔═ ⭐ Calificación promedio",
            value=(
                f"┃ {estrellas(promedio)}  **{promedio:.2f} / 5.00**\n"
                f"┃ {barra_progreso(promedio)}\n"
                f"┗ Basado en **{total_cal}** reseña{'s' if total_cal != 1 else ''}"
            ),
            inline=False,
        )
        dist_txt = "  ".join(f"**{k}★** {v}" for k, v in sorted(dist.items(), reverse=True) if v > 0)
        embed.add_field(name="╔═ 📊 Distribución", value=f"┗ {dist_txt}", inline=False)
    else:
        embed.add_field(
            name="╔═ ⭐ Calificación",
            value="┗ Sin calificaciones aún.",
            inline=False,
        )

    embed.add_field(name="\u200b", value="\u200b", inline=False)

    sanciones_txt = (
        f"┃ ⚠️ Warns aplicados:  **{conteo.get('WARN', 0)}**\n"
        f"┃ 🔨 Bans aplicados:   **{conteo.get('BAN', 0)}**\n"
        f"┃ 👢 Kicks aplicados:  **{conteo.get('KICK', 0)}**\n"
        f"┃ 🔇 Mutes aplicados:  **{conteo.get('MUTE', 0)}**\n"
        f"┗ 📦 Total acciones:   **{total_acciones}**"
    )
    embed.add_field(
        name="╔═ 🛡️ Acciones de moderación",
        value=sanciones_txt,
        inline=False,
    )

    embed.set_footer(
        text=f"✦ Solicitado por {interaction.user}  •  {ts()}",
        icon_url=interaction.user.display_avatar.url,
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)


# ===============================
# TICKETS — UTILIDADES
# ===============================
TIPOS_TICKET = {
    "soporte_general":     ("Soporte General",      "member",    1485682448300904668, "Consultas y preguntas generales del servidor."),
    "soporte_tecnico":     ("Soporte Técnico",       "Developer", 1485682311373656326, "Problemas técnicos o bugs del servidor."),
    "reclamar_beneficios": ("Reclamar Beneficios",   "Vip",       1485682412179554355, "Reclamá tus beneficios VIP u otros premios."),
    "solicitar_superiores":("Solicitar Superiores",  "Owner",     1485682488952098917, "Contacta directamente con la administración."),
}

def cargar_tickets() -> dict:
    if not os.path.exists("tickets.json"):
        return {"counter": 0, "tickets": {}}
    with open("tickets.json", "r") as f:
        return json.load(f)

def guardar_tickets(data: dict):
    with open("tickets.json", "w") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

async def enviar_panel_tickets(canal: discord.TextChannel, guild: discord.Guild):
    embed = discord.Embed(
        title="🎫  Centro de Soporte",
        description=(
            "¡Bienvenido al sistema de tickets de **{}**!\n\n"
            "Si necesitás ayuda o tenés alguna consulta, abrí un ticket seleccionando "
            "la categoría correspondiente en el menú de abajo.\n\n"
            "Un miembro del equipo de staff te atenderá a la brevedad.\n"
            "Por favor sé claro y detallado al describir tu situación."
        ).format(guild.name),
        color=discord.Color.from_str("#5865F2"),
    )
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)

    embed.add_field(
        name="<:member:1485682448300904668>  Soporte General",
        value="Consultas generales, dudas o preguntas sobre el servidor.",
        inline=False,
    )
    embed.add_field(
        name="<:Developer:1485682311373656326>  Soporte Técnico",
        value="Problemas técnicos, bugs o errores que hayas encontrado.",
        inline=False,
    )
    embed.add_field(
        name="<:Vip:1485682412179554355>  Reclamar Beneficios",
        value="Reclamá tu rango VIP, premios u otros beneficios pendientes.",
        inline=False,
    )
    embed.add_field(
        name="<:Owner:1485682488952098917>  Solicitar Superiores",
        value="Contacto directo con la administración para asuntos importantes.",
        inline=False,
    )
    embed.set_footer(
        text=f"{guild.name}  •  Solo abrí un ticket si realmente lo necesitás.",
        icon_url=guild.icon.url if guild.icon else None,
    )
    await canal.send(embed=embed, view=TicketPanelView())

# ===============================
# TICKETS — VIEW CIERRE (PERSISTENTE)
# ===============================
# Modal que pide el motivo de cierre
class CerrarTicketModal(discord.ui.Modal, title="🔒 Cerrar ticket"):
    motivo = discord.ui.TextInput(
        label="Motivo del cierre",
        placeholder="Escribí el motivo por el que cerrás el ticket...",
        style=discord.TextStyle.paragraph,
        max_length=300,
        required=True,
    )

    async def on_submit(self, interaction: discord.Interaction):
        tdata = cargar_tickets()
        ch_id = str(interaction.channel_id)
        info  = tdata["tickets"].get(ch_id)

        embed_cierre = discord.Embed(
            title="🔒 Ticket cerrado",
            description="Este ticket fue cerrado por el equipo de staff. El canal se eliminará en **5 segundos**.",
            color=COLORES["ban"],
            timestamp=datetime.utcnow(),
        )
        embed_cierre.add_field(name="👮 Cerrado por", value=interaction.user.mention,                    inline=True)
        embed_cierre.add_field(name="📋 Tipo",        value=info.get("tipo", "?") if info else "?",     inline=True)
        embed_cierre.add_field(name="🆔 Número",      value=f"`#{info.get('numero', '?')}`" if info else "?", inline=True)
        embed_cierre.add_field(name="📝 Motivo",      value=self.motivo.value,                          inline=False)
        embed_cierre.set_footer(text=ts())

        await interaction.response.send_message(embed=embed_cierre)

        if ch_id in tdata["tickets"]:
            del tdata["tickets"][ch_id]
            guardar_tickets(tdata)

        await asyncio.sleep(5)
        try:
            await interaction.channel.delete(reason=f"Ticket cerrado por {interaction.user}: {self.motivo.value}")
        except Exception:
            pass

# Vista con botones Reclamar + Cerrar (persistente)
class TicketActionView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="✋ Reclamar ticket", style=discord.ButtonStyle.success, custom_id="ticket_claim_btn")
    async def claim_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not es_staff(interaction.user):
            return await interaction.response.send_message("❌ Solo el staff puede reclamar tickets.", ephemeral=True)

        tdata = cargar_tickets()
        ch_id = str(interaction.channel_id)
        info  = tdata["tickets"].get(ch_id)

        if info:
            info["reclamado_por"] = str(interaction.user.id)
            guardar_tickets(tdata)

        embed = discord.Embed(
            title="✋ Ticket reclamado",
            description=f"{interaction.user.mention} tomó a cargo este ticket y lo atenderá a la brevedad.",
            color=COLORES["ok"],
            timestamp=datetime.utcnow(),
        )
        embed.set_author(name=str(interaction.user), icon_url=interaction.user.display_avatar.url)
        embed.set_footer(text=ts())
        await interaction.response.send_message(embed=embed)

    @discord.ui.button(label="🔒 Cerrar ticket", style=discord.ButtonStyle.danger, custom_id="ticket_close_btn")
    async def close_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not es_staff(interaction.user):
            return await interaction.response.send_message("❌ Solo el staff puede cerrar tickets.", ephemeral=True)
        await interaction.response.send_modal(CerrarTicketModal())

# ===============================
# TICKETS — SELECT MENÚ (PERSISTENTE)
# ===============================
class TicketSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(
                label="Soporte General",
                value="soporte_general",
                emoji=discord.PartialEmoji(name="member", id=1485682448300904668),
                description="Consultas y preguntas generales",
            ),
            discord.SelectOption(
                label="Soporte Técnico",
                value="soporte_tecnico",
                emoji=discord.PartialEmoji(name="Developer", id=1485682311373656326),
                description="Problemas técnicos o bugs",
            ),
            discord.SelectOption(
                label="Reclamar Beneficios",
                value="reclamar_beneficios",
                emoji=discord.PartialEmoji(name="Vip", id=1485682412179554355),
                description="Reclamá tus beneficios VIP u otros premios",
            ),
            discord.SelectOption(
                label="Solicitar Superiores",
                value="solicitar_superiores",
                emoji=discord.PartialEmoji(name="Owner", id=1485682488952098917),
                description="Contacta directamente con la administración",
            ),
        ]
        super().__init__(
            placeholder="📋  Seleccioná el tipo de ticket...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="ticket_panel_select",
        )

    async def callback(self, interaction: discord.Interaction):
        tipo_key  = self.values[0]
        tipo_info = TIPOS_TICKET[tipo_key]
        tipo_nombre, emoji_name, emoji_id, _ = tipo_info

        tdata = cargar_tickets()
        uid   = str(interaction.user.id)

        for ch_id, info in list(tdata["tickets"].items()):
            if info.get("user_id") == uid:
                canal_existente = interaction.guild.get_channel(int(ch_id))
                if canal_existente:
                    return await interaction.response.send_message(
                        f"❌ Ya tenés un ticket abierto: {canal_existente.mention}\n"
                        f"Cerralo antes de abrir uno nuevo.",
                        ephemeral=True,
                    )
                else:
                    del tdata["tickets"][ch_id]
                    guardar_tickets(tdata)
                    break

        tdata["counter"] += 1
        numero      = f"{tdata['counter']:03d}"
        nombre_canal = f"ticket-{numero}"

        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(
                view_channel=True, send_messages=True, read_message_history=True, attach_files=True
            ),
        }
        staff_role = interaction.guild.get_role(STAFF_ROLE_ID)
        if staff_role:
            overwrites[staff_role] = discord.PermissionOverwrite(
                view_channel=True, send_messages=True, read_message_history=True, manage_messages=True
            )

        categoria = interaction.guild.get_channel(1466491475436245220)
        try:
            canal_ticket = await interaction.guild.create_text_channel(
                name=nombre_canal,
                overwrites=overwrites,
                category=categoria,
                reason=f"Ticket #{numero} — {interaction.user} — {tipo_nombre}",
            )
        except discord.Forbidden:
            return await interaction.response.send_message(
                "❌ No tengo permisos para crear el canal del ticket.", ephemeral=True
            )

        tdata["tickets"][str(canal_ticket.id)] = {
            "user_id":  uid,
            "tipo":     tipo_nombre,
            "numero":   numero,
            "guild_id": str(interaction.guild.id),
            "fecha":    ts(),
        }
        guardar_tickets(tdata)

        icono_txt = f"<:{emoji_name}:{emoji_id}>"

        embed_bienvenida = discord.Embed(
            title=f"{icono_txt}  Ticket #{numero} — {tipo_nombre}",
            description=(
                f"¡Hola {interaction.user.mention}! Tu ticket fue creado exitosamente.\n\n"
                f"El equipo de staff te atenderá a la brevedad. Mientras tanto, "
                f"describí tu consulta o problema con el mayor detalle posible."
            ),
            color=discord.Color.from_str("#5865F2"),
            timestamp=datetime.utcnow(),
        )
        embed_bienvenida.set_thumbnail(url=interaction.user.display_avatar.url)
        embed_bienvenida.add_field(name="👤 Abierto por", value=f"{interaction.user.mention} (`{interaction.user}`)", inline=True)
        embed_bienvenida.add_field(name="📋 Categoría",   value=tipo_nombre,                                           inline=True)
        embed_bienvenida.add_field(name="🆔 Número",      value=f"`#{numero}`",                                        inline=True)
        embed_bienvenida.add_field(
            name="📌 Instrucciones",
            value=(
                "• Describí tu caso claramente.\n"
                "• Adjuntá capturas si es necesario.\n"
                "• Sé respetuoso con el staff.\n"
                "• Usá el botón de abajo para cerrar cuando termine."
            ),
            inline=False,
        )
        embed_bienvenida.set_footer(
            text=f"Ticket abierto el {ts()}  •  Solo el staff puede ver este canal.",
        )

        await canal_ticket.send(
            content=f"{interaction.user.mention} — <@&{STAFF_ROLE_ID}>",
            embed=embed_bienvenida,
            view=TicketActionView(),
        )

        await interaction.response.send_message(
            f"✅ Ticket creado correctamente: {canal_ticket.mention}",
            ephemeral=True,
        )

class TicketPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketSelect())

# ===============================
# READY
# ===============================
@bot.event
async def on_ready():
    bot.add_view(TicketPanelView())
    bot.add_view(TicketActionView())
    await tree.sync()
    print(f"✅ Bot listo como {bot.user} | Servidores: {len(bot.guilds)}")

bot.run(TOKEN)
