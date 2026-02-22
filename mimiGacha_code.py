import random
import discord
from discord.ext import commands
from PIL import Image
import json
from datetime import datetime, timezone, timedelta
import os
from pathlib import Path
import sqlite3

token = os.getenv('token')

# bot settings
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

DB_FILE = "player.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS players (
            user_id TEXT PRIMARY KEY,
            date TEXT,
            draw_count INTEGER
        )
    """)

    conn.commit()
    conn.close()

# pool
base_dir = Path(__file__).parent
pool_dir = base_dir / "pool"
cards = [
    ("SSR", "XXX", pool_dir / "SSR.png"),
    ("SR", "YYY", pool_dir / "SR.png"),
    ("R", "ZZZ", pool_dir / "R.png"),
    ("R", "ZZZ", pool_dir / "R2.png"),
    ("R", "ZZZ", pool_dir / "R3.png")
]

def can_draw(user_id, draw_count=1):

    AEST = timezone(timedelta(hours=10))
    today = datetime.now(AEST).strftime("%Y-%m-%d")

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute(
        "SELECT date, draw_count FROM players WHERE user_id=?",
        (user_id,)
    )
    row = cursor.fetchone()

    if row is None:
        cursor.execute(
            "INSERT INTO players VALUES (?, ?, ?)",
            (user_id, today, draw_count)
        )
        conn.commit()
        conn.close()
        return True, draw_count

    saved_date, count = row

    if saved_date != today:
        count = 0

    if count + draw_count > 22:
        conn.close()
        return False, count

    count += draw_count

    cursor.execute(
        "UPDATE players SET date=?, draw_count=? WHERE user_id=?",
        (today, count, user_id)
    )

    conn.commit()
    conn.close()

    return True, count

# combine image
def combine_images(image_paths, user_id, target_height=300):
    resized_images = []

    for p in image_paths:
        img = Image.open(p).convert("RGBA")
        w, h = img.size
        new_width = int(w * (target_height / h))
        img = img.resize(
            (new_width, target_height),
            Image.Resampling.LANCZOS
        )
        resized_images.append(img)

    total_width = sum(img.size[0] for img in resized_images)
    combined = Image.new("RGBA", (total_width, target_height))

    x_offset = 0
    for img in resized_images:
        combined.paste(img, (x_offset, 0))
        x_offset += img.size[0]

    filename = f"result_{user_id}_{random.randint(1000,9999)}.png"
    combined.save(filename)

    for img in resized_images:
        img.close()

    return filename

# /draw
@bot.tree.command(name="draw", description="抽一張卡")
async def draw(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    allowed, count = can_draw(user_id)
    if not allowed:
        await interaction.response.send_message(
            f"{interaction.user.mention} 今天已經抽滿 22 次囉！"
        )
        return

    rarity, name, img_path = random.choice(cards)
    await interaction.response.send_message(
        f"{interaction.user.mention} 抽到了 {rarity} - {name} (今天已抽 {count}/22)",
        file=discord.File(img_path)
    )

# /draw5
@bot.tree.command(name="draw5", description="五連抽卡")
async def draw5(interaction: discord.Interaction):
    await interaction.response.defer()
    user_id = str(interaction.user.id)
    allowed, count = can_draw(user_id, draw_count=5)
    if not allowed:
        await interaction.response.send_message(
            f"{interaction.user.mention} 五連抽會超過今天 22 抽上限！目前已抽 {count}/22"
        )
        return

    drawn_cards = [random.choice(cards) for _ in range(5)]
    text_list = [f"{rarity} - {name}" for rarity, name, _ in drawn_cards]
    image_paths = [img_path for _, _, img_path in drawn_cards]
    result_path = combine_images(image_paths, user_id)

    await interaction.followup.send(
        f"{interaction.user.mention} 五連抽結果 (今天已抽 {count}/22)：\n" + ", ".join(text_list),
        file=discord.File(result_path)
    )

# run bot
@bot.event
async def on_ready():
    init_db()
    await bot.tree.sync()
    print(f"Logged in as {bot.user}")


bot.run(token)





