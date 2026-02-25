import random
import discord
from discord.ext import commands
from PIL import Image
import tempfile
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

# --- player database ---
DB_FILE = "player.db"

def get_db():
    return sqlite3.connect(DB_FILE, timeout=10)
    
def init_db():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS players (
        user_id TEXT PRIMARY KEY,
        total_draws INTEGER DEFAULT 0,
        last_draw TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS cards_owned (
        user_id TEXT,
        card_name TEXT,
        rarity TEXT,
        count INTEGER,
        PRIMARY KEY (user_id, card_name)
    )
    """)

    conn.commit()
    conn.close()

def add_card(user_id, rarity, name):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT count FROM cards_owned
        WHERE user_id=? AND card_name=?
    """, (user_id, name))

    row = cursor.fetchone()
    if row:
        cursor.execute("""
            UPDATE cards_owned
            SET count=count+1
            WHERE user_id=? AND card_name=?
        """, (user_id, name))
    else:
        cursor.execute("""
            INSERT INTO cards_owned (user_id, card_name, rarity, count)
            VALUES (?, ?, ?, 1)
        """, (user_id, name, rarity))

    conn.commit()
    conn.close()

def record_draw(user_id, amount=1):
    conn = get_db()
    cursor = conn.cursor()

    AEST = timezone(timedelta(hours=10))
    today = datetime.now(AEST).strftime("%Y-%m-%d")

    cursor.execute(
        "SELECT total_draws FROM players WHERE user_id=?",
        (user_id,)
    )
    row = cursor.fetchone()

    if row:
        cursor.execute("""
            UPDATE players
            SET total_draws = total_draws + ?,
                last_draw = ?
            WHERE user_id=?
        """, (amount, today, user_id))
    else:
        cursor.execute("""
            INSERT INTO players (user_id, total_draws, last_draw)
            VALUES (?, ?, ?)
        """, (user_id, amount, today))

    conn.commit()
    conn.close()

# --- pool ---
base_dir = Path(__file__).parent
with open(base_dir / "cards.json", encoding="utf-8") as f:
    card_data = json.load(f)
cards = card_data["cards"]

def draw_card():
    card = random.choice(cards)
    return card["rarity"], card["name"], base_dir / card["image"]

def prepare_image(image_path, max_size_mb=7):
    img = Image.open(image_path).convert("RGB")
    quality = 95
    temp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
    temp_path = temp.name
    temp.close()

    while True:
        img.save(temp_path, "JPEG", quality=quality)
        size_mb = os.path.getsize(temp_path) / (1024 * 1024)
        if size_mb <= max_size_mb or quality <= 30:
            break
        quality -= 10

    img.close()
    return temp_path

# --- bot commands ---
@bot.tree.command(name="mimihelp", description="使用說明")
async def mimihelp(interaction: discord.Interaction):
    help_text = """```
MimiGacha使用說明：

1.在文字頻道中輸入
 /draw: 抽一張卡
 /draw5: 抽五張卡
 /latest: 卡池內容一覽
 /mimihelp: MimiGacha使用說明
2.卡片種類為SSR、SR和R三種
3.機制僅使用隨機，無保底
4.圖片會直接顯示在訊息中，請耐心等待

p.s.可以提供自己的OC加入卡池
```"""
    await interaction.response.send_message(help_text)

@bot.tree.command(name="latest", description="卡池內容")
async def latest(interaction: discord.Interaction):
    latest_text = """```
卡池內卡片一覽：

SSR
新年祈願

SR
米力全開、萬米奔騰、米到成功

R
不開心惹、好開心鴨、超好笑、好啊、我不要哇
```"""
    await interaction.response.send_message(latest_text)

@bot.tree.command(name="draw", description="抽一張卡")
async def draw(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    rarity, name, img_path = draw_card()
    add_card(user_id, rarity, name)
    record_draw(user_id, 1)
    await interaction.response.send_message(
        f"{interaction.user.mention} 抽到了 {rarity} - {name}",
        file=discord.File(img_path)
    )

@bot.tree.command(name="draw5", description="五連抽卡")
async def draw5(interaction: discord.Interaction):
    await interaction.response.defer()
    user_id = str(interaction.user.id)
    drawn_cards = [draw_card() for _ in range(5)]
    text_list = [f"{rarity} - {name}" for rarity, name, _ in drawn_cards]

    for rarity, name, _ in drawn_cards:
        add_card(user_id, rarity, name)
    record_draw(user_id, 5)

    files = []
    for i, (_, _, img_path) in enumerate(drawn_cards, 1):
        safe_img = prepare_image(img_path)
        files.append(discord.File(safe_img, filename=f"{user_id}_{i}.jpg"))

    await interaction.followup.send(
        f"{interaction.user.mention} 五連抽結果：\n" + ", ".join(text_list),
        files=files
    )

    for f in files:
        try:
            os.remove(f.fp.name)
        except:
            pass

# --- on_ready ---
@bot.event
async def on_ready():
    init_db()
    if os.getenv("SYNC_COMMANDS") == "1":
        await bot.tree.sync()
    print(f"Logged in as {bot.user}")

bot.run(token)
