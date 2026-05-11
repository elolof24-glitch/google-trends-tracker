import os
import io
import discord
from discord.ext import commands
from serpapi import GoogleSearch
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

print("bot starting")

TOKEN = (os.getenv("DISCORD_BOT_TOKEN") or "").strip()
SERPAPI_KEY = (os.getenv("SERPAPI_KEY") or "").strip()
GOOGLE_TRENDS_CHANNEL_ID = 1503070666457350328

print("token exists:", bool(TOKEN))
print("serpapi key exists:", bool(SERPAPI_KEY))
print("google trends channel:", GOOGLE_TRENDS_CHANNEL_ID)

if not TOKEN:
    raise ValueError("DISCORD_BOT_TOKEN is missing")

if not SERPAPI_KEY:
    raise ValueError("SERPAPI_KEY is missing")

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="", intents=intents)

def parse_timeframe(raw: str):
    t = raw.lower().strip().replace(" ", "")
    if t in ["1w", "1week"]:
        return ("now 7-d", "1 Week")
    if t in ["1m", "1month"]:
        return ("today 1-m", "1 Month")
    if t in ["3m", "3months"]:
        return ("today 3-m", "3 Months")
    if t in ["6m", "6months"]:
        return ("today 6-m", "6 Months")
    if t in ["1y", "1year"]:
        return ("today 12-m", "1 Year")
    if t in ["all", "alltime", "all-time"]:
        return ("all", "All Time")
    return (None, None)

def extract_keyword_and_timeframe(message_text: str):
    raw = message_text.strip()
    if not raw.lower().startswith("google "):
        return (None, None)

    body = raw[7:].strip()
    patterns = [
        " 1w",
        " 1week",
        " 1m",
        " 1month",
        " 3m",
        " 3months",
        " 3 months",
        " 6m",
        " 6months",
        " 6 months",
        " 1y",
        " 1year",
        " 1 year",
        " all",
        " alltime",
        " all-time",
        " all time"
    ]

    lower_body = body.lower()
    for p in patterns:
        if lower_body.endswith(p):
            keyword = body[: -len(p)].strip()
            timeframe = body[-len(p):].strip()
            return (keyword, timeframe)

    return (None, None)

def fetch_trends_data(keyword: str, date_value: str):
    params = {
        "engine": "google_trends",
        "q": keyword,
        "data_type": "TIMESERIES",
        "date": date_value,
        "api_key": SERPAPI_KEY
    }

    search = GoogleSearch(params)
    results = search.get_dict()

    if "error" in results:
        raise Exception(results["error"])

    timeline_data = results.get("interest_over_time", {}).get("timeline_data", [])
    if not timeline_data:
        raise Exception("No timeline data returned from SerpApi")

    labels = []
    values = []

    for point in timeline_data:
        labels.append(point.get("date", ""))
        point_values = point.get("values", [])
        if point_values and isinstance(point_values, list):
            extracted_value = point_values[0].get("extracted_value", 0)
            values.append(int(extracted_value))
        else:
            values.append(0)

    return labels, values

def build_chart(keyword: str, label: str, labels, values):
    plt.style.use("dark_background")
    fig, ax = plt.subplots(figsize=(12, 5))

    x = range(len(values))
    ax.plot(x, values, color="#4285F4", linewidth=2.5, zorder=3)
    ax.fill_between(x, values, color="#4285F4", alpha=0.15, zorder=2)

    ax.set_title(f"Google Trends: {keyword}", fontsize=17, fontweight="bold", pad=14)
    ax.set_xlabel("Time", fontsize=10, labelpad=8)
    ax.set_ylabel("Interest (0–100)", fontsize=10, labelpad=8)
    ax.set_ylim(0, 105)
    ax.set_xlim(0, max(len(values) - 1, 1))

    ax.grid(True, axis="y", alpha=0.15, linestyle="--", zorder=1)
    ax.grid(False, axis="x")

    # Smart tick positioning: target ~8 evenly-spaced labels
    max_ticks = 8
    n = len(labels)
    if n > 1:
        step = max(1, (n - 1) // (max_ticks - 1))
        tick_positions = list(range(0, n, step))
        # Always include the last point
        if tick_positions[-1] != n - 1:
            tick_positions.append(n - 1)
        tick_labels = [labels[i] for i in tick_positions]
        ax.set_xticks(tick_positions)
        ax.set_xticklabels(tick_labels, rotation=35, ha="right", fontsize=8)
    elif n == 1:
        ax.set_xticks([0])
        ax.set_xticklabels(labels, fontsize=8)

    # Subtle spines
    for spine in ax.spines.values():
        spine.set_alpha(0.2)

    # Watermark-style timeframe label in top-right corner
    ax.text(
        0.99, 0.97, label,
        transform=ax.transAxes,
        fontsize=9, color="white", alpha=0.45,
        ha="right", va="top"
    )

    fig.tight_layout(pad=1.5)

    buffer = io.BytesIO()
    plt.savefig(buffer, format="png", dpi=150, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    buffer.seek(0)
    plt.close(fig)
    return buffer

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    if message.channel.id != GOOGLE_TRENDS_CHANNEL_ID:
        return

    if not message.content.lower().startswith("google "):
        await bot.process_commands(message)
        return

    keyword, timeframe_raw = extract_keyword_and_timeframe(message.content)

    if not keyword or not timeframe_raw:
        await message.channel.send(
            "Use: `google <keyword> <timeframe>`\n"
            "Timeframes: `1w` · `1month` · `3months` · `6months` · `1year` · `all time`\n"
            "Examples: `google bitcoin 1w`, `google solana 3 months`, `google ai all time`"
        )
        return

    date_value, label = parse_timeframe(timeframe_raw)
    if not date_value:
        await message.channel.send(
            "Invalid timeframe. Use `1w`, `1month`, `3months`, `6months`, `1year`, or `all time`."
        )
        return

    await message.channel.send(f"Fetching Google Trends for **{keyword}** ({label})...")

    try:
        labels, values = fetch_trends_data(keyword, date_value)

        if not values:
            await message.channel.send("No Google Trends data found for that keyword/timeframe.")
            return

        latest_value = int(values[-1])
        peak_value = int(max(values))

        chart_buffer = build_chart(keyword, label, labels, values)
        file = discord.File(chart_buffer, filename="google-trends.png")

        embed = discord.Embed(
            title=f"Google Trends: {keyword}",
            description=f"Timeframe: **{label}**",
            color=0x4285F4
        )
        embed.add_field(name="📈 Latest interest", value=f"**{latest_value}** / 100", inline=True)
        embed.add_field(name="🔝 Peak interest", value=f"**{peak_value}** / 100", inline=True)
        embed.set_footer(text="Values are relative interest scaled 0–100 · Powered by Google Trends")
        embed.set_image(url="attachment://google-trends.png")

        await message.channel.send(embed=embed, file=file)

    except Exception as e:
        err = str(e)
        print("Google Trends command failed:", err)
        short_err = err[:200] if len(err) > 200 else err
        await message.channel.send(
            f"⚠️ Could not fetch Google Trends data for **{keyword}**.\n"
            f"```{short_err}```"
        )

    await bot.process_commands(message)

bot.run(TOKEN)
