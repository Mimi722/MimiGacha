import random
import discord
from discord.ext import commands
from PIL import Image
import json
from datetime import datetime, timezone, timedelta
import os
from pathlib import Path
import sqlite3
from collections import defaultdict

token = os.getenv('token')

# bot settings
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# database
DB_FILE = "player.db"
def get_db():
    return sqlite3.connect(DB_FILE, timeout=10)
    
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
    conn = sqlite3.connect(DB_FILE)
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
            INSERT INTO cards_owned
            VALUES (?, ?, ?, 1)
        """, (user_id, name, rarity))

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

# daily limit
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

# /mimihelp
@bot.tree.command(name="mimihelp", description="使用說明")
async def mimihelp(interaction: discord.Interaction):
    help_text = """```
    
    MimiGacha使用說明：
    1.在文字頻道中輸入
     /draw: 抽一張卡
     /draw5: 抽五張卡
     /latest: 卡池內容一覽
     /help: MimiGacha使用說明
    2.每日上限22抽，隔天重置
    3.卡片種類為SSR、SR和R三種，因目前卡片數量較少所以機制僅使用隨機，無保底
    4.圖片會直接顯示在訊息中，請耐心等待

    p.s.可以提供自己的OC加入卡池
    ```"""
    await interaction.response.send_message(help_text)

# /latest
@bot.tree.command(name="latest", description="卡池內容")
async def latest(interaction: discord.Interaction):
    latest_text = """```

    卡池內卡片一覽：
    SSR：新年祈願
    SR：米力全開、米到成功、萬米奔騰
    R：隨機表情符號
    ```"""
    await interaction.response.send_message(latest_text)

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
    add_card(user_id, rarity, name)
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
        await interaction.followup.send(
            f"{interaction.user.mention} 五連抽會超過今天 22 抽上限！目前已抽 {count}/22"
        )
        return

    drawn_cards = [random.choice(cards) for _ in range(5)]
    text_list = [f"{rarity} - {name}" for rarity, name, _ in drawn_cards]
    for rarity, name, _ in drawn_cards:
        add_card(user_id, rarity, name)

    files = []
    for i, (_, _, img_path) in enumerate(drawn_cards, 1):
        files.append(discord.File(img_path, filename=f"{user_id}_{i}.png"))

    await interaction.followup.send(
        f"{interaction.user.mention} 五連抽結果 (今天已抽 {count}/22)：\n" + ", ".join(text_list),
        files=files
    )

# /collection
@bot.tree.command(name="collection", description="查看你的收藏")
async def collection(interaction: discord.Interaction):

    user_id = str(interaction.user.id)

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT rarity, card_name, count
        FROM cards_owned
        WHERE user_id=?
        ORDER BY
        CASE rarity
            WHEN 'SSR' THEN 3
            WHEN 'SR' THEN 2
            WHEN 'R' THEN 1
        END DESC
    """, (user_id,))

    rows = cursor.fetchall()
    conn.close()

    if not rows:
        await interaction.response.send_message(
            "你還沒有抽到任何卡片！"
        )
        return

    groups = defaultdict(list)

    for rarity, name, count in rows:
        groups[rarity].append(f"{name} x{count}")
    
    text = "**你的收藏：**\n"
    
    for rarity in ["SSR", "SR", "R"]:
        if rarity in groups:
            text += f"\n**{rarity}**\n"
            text += "\n".join(groups[rarity])
            text += "\n"
            
    await interaction.response.send_message(text)

# run bot
@bot.event
async def on_ready():
    init_db()
    await bot.tree.sync()
    print(f"Logged in as {bot.user}")


bot.run(token)


