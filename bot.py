import datetime
import discord
from discord.ext import commands
import sqlite3
import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TOKEN")
OWNER = 1306137346583826452

intents = discord.Intents.all()

bot = commands.Bot(command_prefix="nan!", intents=intents, help_command=None)

conn = sqlite3.connect("settings.db")
c = conn.cursor()

c.execute("""
CREATE TABLE IF NOT EXISTS server_settings (
    guild_id INTEGER PRIMARY KEY,
    log_channel_id INTEGER,
    action_on_bots BOOLEAN DEFAULT 1,
    staff_role_id INTEGER
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

c.execute("""
CREATE TABLE IF NOT EXISTS managers (
    guild_id INTEGER,
    user_id INTEGER,
    PRIMARY KEY (guild_id, user_id)
)
""")

conn.commit()

def get_server_settings(guild_id):
    c.execute("SELECT log_channel_id, action_on_bots, staff_role_id FROM server_settings WHERE guild_id = ?", (guild_id,))
    result = c.fetchone()
    return {"log_channel_id": result[0], "action_on_bots": bool(result[1]), "staff_role_id": result[2]} if result else None

def set_server_setting(guild_id, key, value):
    current_settings = get_server_settings(guild_id)
    if current_settings:
        c.execute(f"UPDATE server_settings SET {key} = ? WHERE guild_id = ?", (value, guild_id))
    else:
        c.execute(f"INSERT INTO server_settings (guild_id, {key}) VALUES (?, ?)", (guild_id, value))
    conn.commit()

def is_manager(ctx):
    if ctx.author.id == OWNER or ctx.guild.owner_id == ctx.author.id:
        return True
    c.execute("SELECT 1 FROM managers WHERE guild_id = ? AND user_id = ?", (ctx.guild.id, ctx.author.id))
    return c.fetchone() is not None

def add_manager(guild_id, user_id):
    c.execute("INSERT OR IGNORE INTO managers (guild_id, user_id) VALUES (?, ?)", (guild_id, user_id))
    conn.commit()

def remove_manager(guild_id, user_id):
    c.execute("DELETE FROM managers WHERE guild_id = ? AND user_id = ?", (guild_id, user_id))
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
async def addmanager(ctx, member: discord.Member):
    if ctx.author.id == OWNER or ctx.guild.owner_id == ctx.author.id:
        add_manager(ctx.guild.id, member.id)
        await ctx.send(f"{member.mention} has been added as a manager.")
    else:
        await ctx.send("You do not have permission to add managers.")

@bot.command()
async def removemanager(ctx, member: discord.Member):
    if ctx.author.id == OWNER or ctx.guild.owner_id == ctx.author.id:
        remove_manager(ctx.guild.id, member.id)
        await ctx.send(f"{member.mention} has been removed as a manager.")
    else:
        await ctx.send("You do not have permission to remove managers.")

@bot.command()
async def listmanagers(ctx):
    c.execute("SELECT user_id FROM managers WHERE guild_id = ?", (ctx.guild.id,))
    manager_ids = [row[0] for row in c.fetchall()]
    managers = [ctx.guild.get_member(manager_id) for manager_id in manager_ids]
    managers = [member.mention for member in managers if member]

    embed = discord.Embed(title="Managers", color=0x006c8e)
    if managers:
        embed.description = ", ".join(managers)
    else:
        embed.description = "No managers set."
    await ctx.send(embed=embed)

@bot.command()
@commands.check(is_manager)
async def addrule(ctx, name: str, triggers: str, amount: int, time: int, punishment: str):
    if name in get_rules(ctx.guild.id):
        await ctx.send("Rule name already exists.")
        return
    add_rule(ctx.guild.id, name, triggers.split(";"), amount, time, punishment)
    await ctx.send(f"Rule {name} added.")

@bot.command()
@commands.check(is_manager)
async def removerule(ctx, name: str):
    if name not in get_rules(ctx.guild.id) and name != "all":
        await ctx.send("Rule not found.")
        return
    remove_rule(ctx.guild.id, name)
    await ctx.send(f"Rule {name} removed." if name != "all" else "All rules removed.")

@bot.command()
async def listrules(ctx):
    rules = get_rules(ctx.guild.id)
    if not rules:
        await ctx.send("No rules have been set.")
        return

    embed = discord.Embed(title="Rules for this server", color=0x006c8e)
    for name, details in rules.items():
        embed.add_field(
            name=name,
            value=f"**Triggers**: {', '.join(details['triggers'])}\n"
                  f"**Amount**: {details['amount']}\n"
                  f"**Time**: {details['time']} seconds\n"
                  f"**Punishment**: {details['punishment']}",
            inline=False
        )
    await ctx.send(embed=embed)

@bot.command()
async def clearrules(ctx):
    if is_manager(ctx):
        remove_rule(ctx.guild.id, "all")
        await ctx.send("All rules have been cleared.")
    else:
        await ctx.send("You do not have permission to clear rules.")

@bot.command()
@commands.check(is_manager)
async def setlogchannel(ctx, channel: discord.TextChannel):
    set_server_setting(ctx.guild.id, "log_channel_id", channel.id)
    await ctx.send(f"Log channel set to {channel.mention}")

@bot.command()
@commands.check(is_manager)
async def togglebots(ctx, value: str):
    if value.lower() in ["true", "false"]:
        set_server_setting(ctx.guild.id, "action_on_bots", int(value.lower() == "true"))
        await ctx.send(f"Take action on bots set to {value.lower() == 'true'}.")
    else:
        await ctx.send("Invalid value. Use 'true' or 'false'.")

@bot.command()
async def listadmins(ctx, show_bots: str = "false"):
    show_bots = show_bots.lower() == "true"
    admin_users = []

    for member in ctx.guild.members:
        if member.guild_permissions.administrator and (show_bots or not member.bot):
            admin_users.append(member.name)

    embed = discord.Embed(title="Administrators", color=0x006c8e)
    if admin_users:
        embed.description = ", ".join(admin_users)
    else:
        embed.description = "No administrators found."
    await ctx.send(embed=embed)

@bot.command()
@commands.check(is_manager)
async def setstaffrole(ctx, role: discord.Role):
    set_server_setting(ctx.guild.id, "staff_role_id", role.id)
    await ctx.send(f"Staff role set to {role.mention}")

@bot.command()
async def listrole(ctx):
    settings = get_server_settings(ctx.guild.id)
    staff_role_id = settings.get("staff_role_id") if settings else None
    if not staff_role_id:
        await ctx.send("No staff role has been set.")
        return

    staff_role = ctx.guild.get_role(staff_role_id)
    if not staff_role:
        await ctx.send("Staff role not found. Please set it again.")
        return

    staff_members = [member.mention for member in staff_role.members]

    embed = discord.Embed(title=f"Members with the {staff_role.name} role", color=0x006c8e)
    if staff_members:
        embed.description = ", ".join(staff_members)
    else:
        embed.description = "No members with this role."
    await ctx.send(embed=embed)

@bot.command()
async def help(ctx):
    embed = discord.Embed(title="Nates' Anti Nuke Bot - Help", color=0x006c8e)
    
    embed.add_field(
        name="**`nan!setlogchannel <#channel>`**",
        value="Set the channel where logs for actions will be sent.",
        inline=False
    )
    
    embed.add_field(
        name="**`nan!addrule <name> <triggers> <amount> <time> <punishment>`**",
        value="Add a rule. Use `;` to separate multiple triggers.",
        inline=False
    )

    embed.add_field(
        name="**`nan!listrules`**",
        value="List all rules for the server.",
        inline=False
    )

    embed.add_field(
        name="**`nan!removerule <name>`**",
        value="Remove a rule. Use 'all' to remove all rules.",
        inline=False
    )

    embed.add_field(
        name="**`nan!setstaffrole <role>`**",
        value="Set the staff role for your server.",
        inline=False
    )

    embed.add_field(
        name="**`nan!listadmins`**",
        value="List all administrators in the server.",
        inline=False
    )

    embed.add_field(
        name="**`nan!listrole`**",
        value="List members with the staff role.",
        inline=False
    )

    embed.add_field(
        name="**`nan!togglebots <true/false>`**",
        value="Toggle action on bots in your server.",
        inline=False
    )

    embed.add_field(
        name="**`nan!clearrules`**",
        value="Clear all rules in the server.",
        inline=False
    )

    embed.add_field(
        name="**`nan!listmanagers`**",
        value="List all managers for this server.",
        inline=False
    )

    embed.add_field(
        name="**`nan!addmanager <@member>`**",
        value="Add a manager to your server.",
        inline=False
    )

    embed.add_field(
        name="**`nan!removemanager <@member>`**",
        value="Remove a manager from your server.",
        inline=False
    )

    await ctx.send(embed=embed)

bot.run(TOKEN)

