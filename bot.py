import datetime
import discord
from discord.ext import commands
from discord.ext.commands import has_permissions, CheckFailure
from collections import defaultdict
import sqlite3
import os
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("TOKEN")

intents = discord.Intents.all()

bot = commands.Bot(command_prefix="nan!", intents=intents, help_command=None)

conn = sqlite3.connect("settings.db")
c = conn.cursor()

c.execute("""
CREATE TABLE IF NOT EXISTS server_settings (
    guild_id INTEGER PRIMARY KEY,
    log_channel_id INTEGER,
    action_on_bots BOOLEAN DEFAULT 1
)
""")

c.execute("""
CREATE TABLE IF NOT EXISTS rules (
    guild_id INTEGER,
    name TEXT,
    triggers TEXT,
    amount INTEGER,
    time INTEGER,
    punishment TEXT,
    PRIMARY KEY (guild_id, name)
)
""")
conn.commit()

def get_server_settings(guild_id):
    c.execute("SELECT log_channel_id, action_on_bots FROM server_settings WHERE guild_id = ?", (guild_id,))
    result = c.fetchone()
    return {"log_channel_id": result[0], "action_on_bots": bool(result[1])} if result else None

def set_server_setting(guild_id, key, value):
    current_settings = get_server_settings(guild_id)
    if current_settings:
        c.execute(f"UPDATE server_settings SET {key} = ? WHERE guild_id = ?", (value, guild_id))
    else:
        c.execute(f"INSERT INTO server_settings (guild_id, {key}) VALUES (?, ?)", (guild_id, value))
    conn.commit()

def get_rules(guild_id):
    c.execute("SELECT name, triggers, amount, time, punishment FROM rules WHERE guild_id = ?", (guild_id,))
    return {row[0]: {"triggers": row[1].split(";"), "amount": row[2], "time": row[3], "punishment": row[4]} for row in c.fetchall()}

def add_rule(guild_id, name, triggers, amount, time, punishment):
    c.execute("INSERT INTO rules (guild_id, name, triggers, amount, time, punishment) VALUES (?, ?, ?, ?, ?, ?)",
              (guild_id, name, ";".join(triggers), amount, time, punishment))
    conn.commit()

def remove_rule(guild_id, name):
    if name == "all":
        c.execute("DELETE FROM rules WHERE guild_id = ?", (guild_id,))
    else:
        c.execute("DELETE FROM rules WHERE guild_id = ? AND name = ?", (guild_id, name))
    conn.commit()

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

@bot.command()
@has_permissions(administrator=True)
async def setlogchannel(ctx, channel: discord.TextChannel):
    set_server_setting(ctx.guild.id, "log_channel_id", channel.id)
    await ctx.send(f"Log channel set to {channel.mention}")

@bot.command()
@has_permissions(administrator=True)
async def addrule(ctx, name: str, triggers: str, amount: int, time: int, punishment: str):
    if name in get_rules(ctx.guild.id):
        await ctx.send("Rule name already exists.")
        return
    add_rule(ctx.guild.id, name, triggers.split(";"), amount, time, punishment)
    await ctx.send(f"Rule {name} added.")

@bot.command()
@has_permissions(administrator=True)
async def removerule(ctx, name: str):
    if name not in get_rules(ctx.guild.id) and name != "all":
        await ctx.send("Rule not found.")
        return
    remove_rule(ctx.guild.id, name)
    await ctx.send(f"Rule {name} removed." if name != "all" else "All rules removed.")

@bot.command()
@has_permissions(administrator=True)
async def togglebots(ctx, value: str):
    if value.lower() in ["true", "false"]:
        set_server_setting(ctx.guild.id, "action_on_bots", int(value.lower() == "true"))
        await ctx.send(f"Take action on bots set to {value.lower() == 'true'}.")
    else:
        await ctx.send("Invalid value. Use 'true' or 'false'.")
        
@bot.event
async def on_member_update(before, after):
    if before.timed_out_until != after.timed_out_until and after.timed_out_until is not None:
        async for entry in after.guild.audit_logs(limit=1, action=discord.AuditLogAction.member_update):
            if entry.target == after:
                await handle_action(after.guild, entry.user, "mute")

@bot.command()
async def help(ctx):
    embed = discord.Embed(title="Nates' Anti Nuke Bot - Help", color=0x006c8e)
    embed.add_field(name="`nan!setlogchannel <#channel>`", value="Set the log channel.", inline=False)
    embed.add_field(name="`nan!addrule <name> <trigger> <amount> <time> <punishment>`", 
                    value="Add a rule. Available triggers: `kick`, `mute`, `ban`.", inline=False)
    embed.add_field(name="`nan!removerule <name|all>`", value="Remove a rule by name or remove all rules.", inline=False)
    embed.add_field(name="`nan!togglebots <true|false>`", value="Enable/disable taking action on bots.", inline=False)
    embed.set_footer(text="Requires administrator privileges.")
    await ctx.send(embed=embed)

@setlogchannel.error
@addrule.error
@removerule.error
@togglebots.error
async def admin_only_error(ctx, error):
    if isinstance(error, CheckFailure):
        await ctx.send("You need to be an administrator to use this command.")

@bot.event
async def on_member_ban(guild, user):
    await handle_action(guild, user, "ban")

@bot.event
async def on_member_remove(member):
    if member.guild.get_member(member.id) is None:
        await handle_action(member.guild, member, "kick")

async def handle_action(guild, user, action):
    settings = get_server_settings(guild.id)
    if not settings or (not settings["action_on_bots"] and user.bot):
        return

    rules = get_rules(guild.id)
    for rule_name, rule in rules.items():
        if action in rule["triggers"]:
            now = discord.utils.utcnow()
            rule.setdefault("violations", defaultdict(list))
            rule["violations"][user.id].append(now)
            rule["violations"][user.id] = [t for t in rule["violations"][user.id] if (now - t).total_seconds() < rule["time"]]
            if len(rule["violations"][user.id]) >= rule["amount"]:
                await apply_punishment(guild, user, rule["punishment"])
                rule["violations"][user.id].clear()
                if settings["log_channel_id"]:
                    log_channel = guild.get_channel(settings["log_channel_id"])
                    if log_channel:
                        await log_channel.send(f"Rule {rule_name} triggered for {user.mention}.")

async def apply_punishment(guild, user, punishment):
    if punishment == "ban":
        await guild.ban(user, reason="Triggered rule")
    elif punishment == "kick":
        await guild.kick(user, reason="Triggered rule")
    elif punishment == "mute":
        member = guild.get_member(user.id)
        await member.timeout(datetime.timedelta(hours=1), reason="Triggered rule")
        
@bot.command(name='adminlist')
async def admin_list(ctx):
    admin_users = []

    for member in ctx.guild.members:
        if member.guild_permissions.administrator:
            admin_users.append(member.name)

    if admin_users:
        await ctx.send(f'Users with Admin permissions: {", ".join(admin_users)}')
    else:
        await ctx.send('No users with Admin permissions found.')

bot.run(TOKEN)
