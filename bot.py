
import os
import io
import discord
from discord.ext import commands
from pytrends.request import TrendReq
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

TOKEN = os.getenv("DISCORD_BOT_TOKEN")

if not TOKEN:
    raise ValueError("DISCORD_BOT_TOKEN is missing")

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="", intents=intents)

def parse_timeframe(text: str):
    t = text.lower().strip().replace(" ", "")
    if t in ["1w", "1week"]:
        return "now 7-d", "1 Week"
    if t in ["1m", "1month"]:
        return "today 1-m", "1 Month"
    if t in ["3m", "3months"]:
        return "today 3-m", "3 Months"
    if t in ["6m", "6months"]:
        return "today 6-m", "6 Months"
    if t in ["1y", "1year"]:
        return "today 12-m", "1 Year"
    return None, None

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    content = message.content.strip()
    if not content.lower().startswith("google "):
        return

    parts = content.split()
    if len(parts) < 3:
        await message.channel.send("Usage: `google <keyword> <1w|1month|3months|6months|1year>`")
        return

    timeframe_raw = parts[-1]
    keyword = " ".join(parts[1:-1])

    timeframe, label = parse_timeframe(timeframe_raw)
    if not timeframe:
        await message.channel.send("Invalid timeframe. Use: `1w`, `1month`, `3months`, `6months`, or `1year`.")
        return

    await message.channel.send(f"Fetching Google Trends for **{keyword}** ({label})...")

    try:
        pytrends = TrendReq(hl="en-US", tz=0)
        pytrends.build_payload([keyword], timeframe=timeframe)
        df = pytrends.interest_over_time()

        if df.empty or keyword not in df.columns:
            await message.channel.send("No Google Trends data found for that keyword/timeframe.")
            return

        series = df[keyword]

        plt.figure(figsize=(10, 5))
        plt.plot(series.index, series.values, linewidth=2)
        plt.title(f"Google Trends: {keyword} ({label})")
        plt.xlabel("Date")
        plt.ylabel("Interest")
        plt.grid(True, alpha=0.3)
        plt.tight_layout()

        buffer = io.BytesIO()
        plt.savefig(buffer, format="png")
        buffer.seek(0)
        plt.close()

        file = discord.File(buffer, filename="trend.png")
        embed = discord.Embed(
            title=f"Google Trends for {keyword}",
            description=f"Timeframe: {label}",
            color=discord.Color.blue()
        )
        embed.set_image(url="attachment://trend.png")

        await message.channel.send(embed=embed, file=file)

    except Exception as e:
        await message.channel.send(f"Error fetching trends: `{str(e)}`")

bot.run(TOKEN)
