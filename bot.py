import discord
from discord.ext import commands
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
async def setlogchannel(ctx, channel: discord.TextChannel):
    if not ctx.author.guild_permissions.administrator:
        embed = discord.Embed(
            title="Error!",
            description="You must be an administrator to run this command.",
            color=discord.Color.red()
        )
        await ctx.reply(embed=embed, mention_author=False)
        return

    set_server_setting(ctx.guild.id, "log_channel_id", channel.id)
    await ctx.reply(f"Log channel set to {channel.mention}", mention_author=False)

@bot.command()
async def addrule(ctx, name: str, triggers: str, amount: int, time: int, punishment: str):
    if not ctx.author.guild_permissions.administrator:
        embed = discord.Embed(
            title="Error!",
            description="You must be an administrator to run this command.",
            color=discord.Color.red()
        )
        await ctx.reply(embed=embed, mention_author=False)
        return

    if name in get_rules(ctx.guild.id):
        await ctx.reply("Rule name already exists.", mention_author=False)
        return
    add_rule(ctx.guild.id, name, triggers.split(";"), amount, time, punishment)
    await ctx.reply(f"Rule {name} added.", mention_author=False)

@bot.command()
async def removerule(ctx, name: str):
    if not ctx.author.guild_permissions.administrator:
        embed = discord.Embed(
            title="Error!",
            description="You must be an administrator to run this command.",
            color=discord.Color.red()
        )
        await ctx.reply(embed=embed, mention_author=False)
        return

    if name not in get_rules(ctx.guild.id) and name != "all":
        await ctx.reply("Rule not found.", mention_author=False)
        return
    remove_rule(ctx.guild.id, name)
    await ctx.reply(f"Rule {name} removed." if name != "all" else "All rules removed.", mention_author=False)

@bot.command()
async def togglebots(ctx, value: str):
    if not ctx.author.guild_permissions.administrator:
        embed = discord.Embed(
            title="Error!",
            description="You must be an administrator to run this command.",
            color=discord.Color.red()
        )
        await ctx.reply(embed=embed, mention_author=False)
        return

    if value.lower() in ["true", "false"]:
        set_server_setting(ctx.guild.id, "action_on_bots", int(value.lower() == "true"))
        await ctx.reply(f"Take action on bots set to {value.lower() == 'true'}.", mention_author=False)
    else:
        await ctx.reply("Invalid value. Use 'true' or 'false'.", mention_author=False)

@bot.command()
async def listrules(ctx):
    if not ctx.author.guild_permissions.administrator:
        embed = discord.embed(
            title="error!",
            description="you must be an administrator to run this command.",
            color=discord.color.red()
        )
        await ctx.reply(embed=embed, mention_author=False)
        return

    rules = get_rules(ctx.guild.id)
    if not rules:
        await ctx.reply("No rules have been set.", mention_author=False)
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
    await ctx.reply(embed=embed, mention_author=False)

@bot.command(name='listadmins')
async def admin_list(ctx, show_bots: str = "false"):
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
    await ctx.reply(embed=embed, mention_author=False)

@bot.command()
async def setstaffrole(ctx, role: discord.Role):
    if not ctx.author.guild_permissions.administrator:
        embed = discord.Embed(
            title="Error!",
            description="You must be an administrator to run this command.",
            color=discord.Color.red()
    )
        await ctx.reply(embed=embed, mention_author=False)
        return

    set_server_setting(ctx.guild.id, "staff_role_id", role.id)
    await ctx.reply("Staff role set succesfully.", mention_author=False)

@bot.command()
async def liststaff(ctx):
    settings = get_server_settings(ctx.guild.id)
    staff_role_id = settings.get("staff_role_id") if settings else None
    if not staff_role_id:
        await ctx.reply("No staff role has been set.", mention_author=False)
        return

    staff_role = ctx.guild.get_role(staff_role_id)
    if not staff_role:
        await ctx.reply("Staff role not found. Please set it again.", mention_author=False)
        return

    staff_members = [member.name for member in staff_role.members]

    embed = discord.Embed(title=f"Members with the {staff_role.name} role", color=0x006c8e)
    if staff_members:
        embed.description = ", ".join(staff_members)
    else:
        embed.description = "No members with this role."
    await ctx.reply(embed=embed, mention_author=False)

@bot.command()
async def help(ctx):
    embed = discord.Embed(title="Nate's Anti Nuke Bot - Help", color=0x006c8e)
    
    embed.add_field(
        name="**`nan!setlogchannel <#channel>`**",
        value="Set the channel where logs for actions will be sent.",
        inline=False
    )
    
    embed.add_field(
        name="**`nan!addrule <name> <triggers> <amount> <time> <punishment>`**",
        value=(
            "Add a rule to monitor actions on the server.\n"
            "**Parameters:**\n"
            "- **name**: A unique name for the rule.\n"
            "- **triggers**: Semicolon-separated triggers (e.g., `kick;mute;ban`).\n"
            "- **amount**: Number of actions to trigger the rule.\n"
            "- **time**: Time frame (in seconds) for tracking actions.\n"
            "- **punishment**: Action to apply (`ban`, `kick`, or `mute`)."
        ),
        inline=False
    )
    
    embed.add_field(
        name="**`nan!removerule <name|all>`**",
        value="Remove a specific rule by name or all rules (`all`).",
        inline=False
    )
    
    embed.add_field(
        name="**`nan!togglebots <true|false>`**",
        value="Enable or disable actions on bots (`true` or `false`).",
        inline=False
    )
    
    embed.add_field(
        name="**`nan!listrules`**",
        value="List all active rules for the server in a formatted embed.",
        inline=False
    )
    
    embed.add_field(
        name="**`nan!listadmins [true|false]`**",
        value=(
            "List all server administrators.\n"
            "- **true**: Include bots in the list.\n"
            "- **false** (default): Exclude bots."
        ),
        inline=False
    )
    
    embed.add_field(
        name="**`nan!setstaffrole <@role>`**",
        value="Assign a role to be used as staff for listing purposes.",
        inline=False
    )
    
    embed.add_field(
        name="**`nan!liststaff`**",
        value="List all members with the staff role in a formatted embed.",
        inline=False
    )
    
    embed.set_footer(text="All commands requiring setup or moderation access need administrator privileges.")
    await ctx.reply(embed=embed, mention_author=False)

@bot.command()
async def massrole(ctx, role: discord.Role):
    if not ctx.author.guild_permissions.administrator:
        embed = discord.Embed(
            title="Error!",
            description="You must be an administrator to run this command.",
            color=discord.Color.red()
        )
        await ctx.reply(embed=embed, mention_author=False)
        return
    if not ctx.guild.me.guild_permissions.manage_roles:
        await ctx.reply("I don't have the `Manage Roles` permission.", mention_author=False)
        return

    for member in ctx.guild.members:
        try:
            await member.add_roles(role)
            print(f"Added {role.name} to {member.name}")
        except Exception as e:
            print(f"Failed to add {role.name} to {member.name}: {e}")

    await ctx.reply(f"Mass role assignment complete. {role.name} assigned to all members.", mention_author=False)

bot.run(TOKEN)
