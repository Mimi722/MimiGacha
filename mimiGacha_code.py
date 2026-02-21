import random
import discord
from discord.ext import commands
from PIL import Image
import json
from datetime import datetime
import os

token = os.getenv('token')
bot.run(token)

# bot settings
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# pool
cards = [
    ("SSR", "XXX", r"C:\Users\jhua0\Desktop\MimiGacha\pool\SSR.png"),
    ("SR", "YYY", r"C:\Users\jhua0\Desktop\MimiGacha\pool\SR.png"),
    ("R", "ZZZ", r"C:\Users\jhua0\Desktop\MimiGacha\pool\R.png"),
    ("R", "ZZZ", r"C:\Users\jhua0\Desktop\MimiGacha\pool\R2.png"),
    ("R", "ZZZ", r"C:\Users\jhua0\Desktop\MimiGacha\pool\R3.png")
]

# record card count / day
DATA_FILE = "player_data.json"


def load_data():
    try:
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)


def can_draw(user_id, draw_count=1):
    data = load_data()
    today = datetime.now().strftime("%Y-%m-%d")

    if user_id not in data:
        data[user_id] = {"date": today, "count": 0}

    if data[user_id]["date"] != today:
        data[user_id]["date"] = today
        data[user_id]["count"] = 0

    if data[user_id]["count"] + draw_count > 22:
        return False, data[user_id]["count"]

    data[user_id]["count"] += draw_count
    save_data(data)
    return True, data[user_id]["count"]

# combine image
def combine_images(image_paths, target_height=300):

    resized_images = []
    for p in image_paths:
        img = Image.open(p)
        w, h = img.size
        new_width = int(w * (target_height / h))
        img = img.resize((new_width, target_height), Image.Resampling.LANCZOS)
        resized_images.append(img)

    total_width = sum(img.size[0] for img in resized_images)
    combined = Image.new("RGBA", (total_width, target_height))

    x_offset = 0
    for img in resized_images:
        combined.paste(img, (x_offset, 0))
        x_offset += img.size[0]

    combined.save("result.png")
    return "result.png"

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

# /draw10
@bot.tree.command(name="draw5", description="五連抽卡")
async def draw5(interaction: discord.Interaction):
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
    result_path = combine_images(image_paths)

    await interaction.response.send_message(
        f"{interaction.user.mention} 五連抽結果 (今天已抽 {count}/22)：\n" + ", ".join(text_list),
        file=discord.File(result_path)
    )

# run bot
@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"Logged in as {bot.user}")


bot.run(token)
