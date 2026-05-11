import os
import io
import discord
from discord.ext import commands
from serpapi import GoogleSearch
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

TOKEN = (os.getenv("DISCORD_BOT_TOKEN") or "").strip()
SERPAPI_KEY = (os.getenv("SERPAPI_KEY") or "").strip()
ALLOWED_CHANNEL_ID = 1503070666457350328

if not TOKEN:
    raise ValueError("Missing DISCORD_BOT_TOKEN")

if not SERPAPI_KEY:
    raise ValueError("Missing SERPAPI_KEY")

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="", intents=intents)

def parse_timeframe(text: str):
    value = text.lower().strip()
    mapping = {
        "1w": ("now 7-d", "1 Week"),
        "1week": ("now 7-d", "1 Week"),
        "1m": ("today 1-m", "1 Month"),
        "1month": ("today 1-m", "1 Month"),
        "3m": ("today 3-m", "3 Months"),
        "3month": ("today 3-m", "3 Months"),
        "3months": ("today 3-m", "3 Months"),
        "6m": ("today 6-m", "6 Months"),
        "6month": ("today 6-m", "6 Months"),
        "6months": ("today 6-m", "6 Months"),
        "1y": ("today 12-m", "1 Year"),
        "1year": ("today 12-m", "1 Year"),
        "all": ("all", "All Time"),
        "alltime": ("all", "All Time"),
        "all time": ("all", "All Time"),
    }
    return mapping.get(value, (None, None))

def extract_keyword_and_timeframe(message_text: str):
    raw = message_text.strip()
    if not raw.lower().startswith("google "):
        return None, None

    body = raw[7:].strip()
    parts = body.split()

    if len(parts) < 2:
        return None, None

    candidates = []

    if len(parts) >= 2:
        candidates.append(" ".join(parts[-2:]).lower())
    candidates.append(parts[-1].lower())

    normalized = {
        "1 week": "1week",
        "1 month": "1month",
        "3 months": "3months",
        "6 months": "6months",
        "1 year": "1year",
        "all time": "all time",
    }

    for candidate in candidates:
        tf = normalized.get(candidate, candidate.replace(" ", ""))
        date_value, label = parse_timeframe(tf)
        if date_value:
            keyword_part_len = 2 if candidate in normalized and candidate == "all time" else (
                2 if candidate in ["1 week", "1 month", "3 months", "6 months", "1 year"] else 1
            )
            keyword = " ".join(parts[:-keyword_part_len]).strip()
            if keyword:
                return keyword, tf

    return None, None

def fetch_trends(keyword: str, date_value: str):
    params = {
        "engine": "google_trends",
        "q": keyword,
        "data_type": "TIMESERIES",
        "date": date_value,
        "geo": "SE",
        "hl": "en",
        "api_key": SERPAPI_KEY,
    }

    search = GoogleSearch(params)
    results = search.get_dict()

    if results.get("error"):
        raise Exception(results["error"])

    timeline = results.get("interest_over_time", {}).get("timeline_data", [])
    if not timeline:
        raise Exception("No timeline data returned")

    labels = []
    values = []

    for point in timeline:
        labels.append(point.get("date", ""))
        point_values = point.get("values", [])
        if point_values and isinstance(point_values, list):
            values.append(int(point_values[0].get("extracted_value", 0)))
        else:
            values.append(0)

    return labels, values

def make_chart(keyword: str, timeframe_label: str, labels, values):
    plt.style.use("default")

    fig, ax = plt.subplots(figsize=(12, 5), facecolor="white")
    ax.set_facecolor("white")

    x = list(range(len(values)))

    ax.plot(x, values, color="#4285F4", linewidth=2.5)
    ax.fill_between(x, values, 0, color="#4285F4", alpha=0.08)

    ax.set_title(f"{keyword} ({timeframe_label})", fontsize=16, color="#202124", pad=14)
    ax.set_ylabel("Interest", fontsize=10, color="#5f6368")
    ax.set_ylim(0, 100)

    ax.grid(axis="y", color="#e8eaed", linewidth=1)
    ax.grid(axis="x", visible=False)

    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#dadce0")
    ax.spines["bottom"].set_color("#dadce0")

    ax.tick_params(axis="x", colors="#5f6368", labelsize=9, rotation=0)
    ax.tick_params(axis="y", colors="#5f6368", labelsize=9)

    max_ticks = 8
    if len(labels) > 1:
        step = max(1, len(labels) // max_ticks)
        tick_positions = list(range(0, len(labels), step))
        if tick_positions[-1] != len(labels) - 1:
            tick_positions.append(len(labels) - 1)
        tick_labels = [labels[i] for i in tick_positions]
        ax.set_xticks(tick_positions)
        ax.set_xticklabels(tick_labels)

    fig.tight_layout()

    buffer = io.BytesIO()
    plt.savefig(buffer, format="png", dpi=160, bbox_inches="tight", facecolor="white")
    buffer.seek(0)
    plt.close(fig)
    return buffer

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} ({bot.user.id})")

@bot.listen()
async def on_message(message):
    if message.author.bot:
        return

    if message.channel.id != ALLOWED_CHANNEL_ID:
        return

    if not message.content.lower().startswith("google "):
        return

    keyword, timeframe_raw = extract_keyword_and_timeframe(message.content)
    if not keyword or not timeframe_raw:
        await message.channel.send(
            "Use: `google <keyword> <1w|1month|3months|6months|1year|all time>`\n"
            "Examples: `google bitcoin 1w`, `google solana 3 months`, `google ethereum 1 year`, `google bitcoin all time`"
        )
        return

    date_value, timeframe_label = parse_timeframe(timeframe_raw)
    if not date_value:
        await message.channel.send("Invalid timeframe.")
        return

    try:
        await message.channel.send(f"Fetching Google Trends for **{keyword}** ({timeframe_label})...")

        labels, values = fetch_trends(keyword, date_value)
        chart_buffer = make_chart(keyword, timeframe_label, labels, values)

        latest_value = values[-1] if values else 0
        peak_value = max(values) if values else 0

        file = discord.File(chart_buffer, filename="google-trends.png")

        embed = discord.Embed(
            title=f"Google Trends: {keyword}",
            description=f"Timeframe: **{timeframe_label}**",
            color=discord.Color.blue()
        )
        embed.add_field(name="Latest interest", value=str(latest_value), inline=True)
        embed.add_field(name="Peak interest", value=str(peak_value), inline=True)
        embed.set_footer(text="Google Trends values are relative interest from 0 to 100.")
        embed.set_image(url="attachment://google-trends.png")

        await message.channel.send(file=file, embed=embed)

    except Exception as e:
        print("Trend fetch error:", repr(e))
        await message.channel.send(f"Failed to fetch Google Trends data: `{str(e)[:180]}`")

bot.run(TOKEN)
