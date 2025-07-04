import nextcord
from nextcord.ext import commands
from nextcord import Interaction
import sqlite3
from datetime import datetime, timedelta
import random
import openpyxl
import os
from dotenv import load_dotenv
import asyncio

intents = nextcord.Intents.default()
intents.message_content = True
intents.members = True

load_dotenv()
Token = os.getenv("Token")

bot = commands.Bot(command_prefix="!", intents=intents)

DB_FILE = "data.db"


# --- DB 초기화 함수 ---
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id TEXT PRIMARY KEY,
        name TEXT,
        follower INTEGER DEFAULT 0,
        following INTEGER DEFAULT 0,
        like INTEGER DEFAULT 0,
        hate INTEGER DEFAULT 0,
        balance INTEGER DEFAULT 0,
        last_post_time TEXT,
        last_feed_time TEXT,
        last_event_time TEXT,
        last_checkin_time TEXT
    )
    """)
    conn.commit()
    conn.close()


# --- 유저 존재 확인 ---
def user_exists(user_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT 1 FROM users WHERE user_id = ?", (user_id,))
    exists = c.fetchone() is not None
    conn.close()
    return exists


# --- 유저 추가 (가입) ---
def add_user(user_id, name):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id, name) VALUES (?, ?)", (user_id, name))
    conn.commit()
    conn.close()


# --- 쿨타임 체크 함수 ---
def is_on_cooldown(last_time_str, cooldown_minutes):
    if last_time_str is None:
        return False, 0
    try:
        last_time = datetime.strptime(last_time_str, "%Y-%m-%d %H:%M:%S")
        now = datetime.now()
        remaining = (last_time + timedelta(minutes=cooldown_minutes)) - now
        if remaining.total_seconds() > 0:
            return True, int(remaining.total_seconds())
        else:
            return False, 0
    except Exception:
        return False, 0
    


# --- 가입 명령어 ---
@bot.slash_command(name="가입", description="디스타그램에 가입합니다.")
async def 가입(interaction: Interaction):
    user_id = str(interaction.user.id)
    name = interaction.user.name

    if user_exists(user_id):
        await interaction.response.send_message("이미 가입되어 있습니다!", ephemeral=True)
        return

    add_user(user_id, name)
    await interaction.response.send_message(f"환영합니다, {name}님! 디스타그램에 가입 완료되었습니다.", ephemeral=True)


# --- 탈퇴 명령어 ---
@bot.slash_command(name="탈퇴", description="디스타그램에서 탈퇴합니다.")
async def 탈퇴(interaction: Interaction):
    user_id = str(interaction.user.id)

    if not user_exists(user_id):
        await interaction.response.send_message("가입되어 있지 않습니다.", ephemeral=True)
        return

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

    await interaction.response.send_message("탈퇴가 완료되었습니다. 다시 만날 날을 기다릴게요!", ephemeral=True)



@bot.slash_command(name="타임아웃", description="선택한 유저를 타임아웃합니다.", default_member_permissions=nextcord.Permissions(administrator=True))
async def timeout_user(ctx: nextcord.Interaction,
                       멤버: nextcord.Member=nextcord.SlashOption(description="멤버를 입력하세요."),
                       시간: int=nextcord.SlashOption(description="시간을 입력하세요. (분 단위)")):
    
    await ctx.response.defer()  # 응답 지연

     # ✅ 관리자 또는 서버 소유자인지 확인
    if ctx.user.guild_permissions.administrator or ctx.guild.owner_id == ctx.user.id:
        try:
            duration = timedelta(minutes=시간)  #  타임아웃 시간 설정
            await 멤버.timeout(duration, reason="타임아웃 명령어 사용")
            await ctx.followup.send(f"✅ {멤버.mention}님이 {시간}분간 타임아웃 되었습니다.")
        except Exception as e:
            await ctx.followup.send(f"❌ 타임아웃 중 오류가 발생했습니다: {e}")
    else:
        await ctx.followup.send("❌ 관리자 또는 서버 소유자만 사용할 수 있는 명령어입니다!", ephemeral=True)



@bot.slash_command(name="추방", description="유저를 추방함", default_member_permissions=nextcord.Permissions(administrator=True))
async def kick(ctx: nextcord.Interaction, 
               멤버: nextcord.Member = nextcord.SlashOption(description="추방할 멤버를 골라주세요.", required=True),
               사유: str = nextcord.SlashOption(description="사유를 적어주세요", required=False)):
    await ctx.response.defer()

    if ctx.user.guild_permissions.administrator or ctx.guild.owner_id == ctx.user.id:   # 관리자_아이디에 적힌 유저만 사용 가능
    
        if ctx.user.guild_permissions.kick_members:
            await 멤버.kick(reason=사유) # 추방코드
            await ctx.followup.send(f'✅ 추방성공 \n**사유** : {사유}')
        else:
            # 봇이 멤버를 추방할 권한이 없을 떄
            await ctx.followup.send(f"❌구성원을 추방할 권한이 없습니다.", ephemeral=True)
    else:
        # 관리자가 아닌 사람이 이 명령어를 입력하였을 때
        await ctx.followup.send(f"❌이 명령어를 사용할 권한이 없습니다.", ephemeral=True) 



@bot.slash_command(name="서버차단", description="유저를 영구차단함", default_member_permissions=nextcord.Permissions(administrator=True))
async def ban(ctx: nextcord.Interaction, 
              멤버: nextcord.Member = nextcord.SlashOption(description="서버에서 차단할 멤버를 골라주세요.", required=True),
              사유: str = nextcord.SlashOption(description="사유를 적어주세요", required=False)):
    
    await ctx.response.defer()
    
    if ctx.user.guild_permissions.administrator or ctx.guild.owner_id == ctx.user.id:  # 관리자_아이디에 적힌 유저만 사용 가능
        if ctx.user.guild_permissions.ban_members:
            await 멤버.ban(reason=사유)  # 차단코드
            await ctx.followup.send(f'✅ 차단성공 \n**사유** : {사유}')
        else:
            # 봇이 멤버를 차단할 권한이 없을 떄
            await ctx.followup.send(f"❌구성원을 차단할 수 있는 권한이 없습니다.", ephemeral=True)
    else:
        # 관리자가 아닌 사람이 이 명령어를 입력하였을 때
        await ctx.followup.send(f"❌이 명령어를 사용할 권한이 없습니다.", ephemeral=True)



@bot.slash_command(name="메시지삭제", description="입력한 개수만큼 메시지를 삭제합니다.", default_member_permissions=nextcord.Permissions(administrator=True))
async def delete_messages(
    ctx: nextcord.Interaction,
    개수: int = nextcord.SlashOption(description="삭제할 메시지 개수를 입력하세요.", min_value=1, max_value=100)
):
    await ctx.response.defer()  # 응답 지연 방지

    if not ctx.guild.me.guild_permissions.manage_messages:
        return await ctx.followup.send("❌ 봇에게 '메시지 관리' 권한이 없습니다. 서버 설정을 확인하세요.")

    if ctx.user.guild_permissions.administrator or ctx.guild.owner_id == ctx.user.id:
        try:
            deleted = await ctx.channel.purge(limit=개수)
            await ctx.followup.send(f"✅ 최근 {len(deleted)}개의 메시지를 삭제했습니다.", ephemeral=True)
        except nextcord.Forbidden:
            await ctx.followup.send("❌ 메시지 삭제 권한이 부족합니다.")
        except Exception as e:
            await ctx.followup.send(f"❌ 메시지 삭제 중 오류가 발생했습니다.: {e}")
    else:
        await ctx.followup.send("❌ 관리자만 사용할 수 있는 명령어입니다.", ephemeral=True)



# --- 잔액 조회 ---
@bot.slash_command(name="잔액", description="잔액을 알려줍니다.")
async def 잔액(interaction: Interaction):
    user_id = str(interaction.user.id)
    if not user_exists(user_id):
        await interaction.response.send_message("가입을 해주세요.", ephemeral=True)
        return

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    balance = c.fetchone()[0]
    conn.close()

    embed = nextcord.Embed(
        title=f"{interaction.user.name}",
        description="돈 잔액",
        color=nextcord.Color(0xF3F781)
    )
    embed.add_field(name="현재 잔액", value=f"{balance}", inline=False)
    await interaction.response.send_message(embed=embed)



@bot.slash_command(name="출석", description="출석하고 보상을 받아가세요! (하루 1회)")
async def 출석(interaction: Interaction):
    await interaction.response.defer(ephemeral=True)  # thinking 방지

    user_id = str(interaction.user.id)
    name = interaction.user.name

    if not user_exists(user_id):
        await interaction.followup.send("❗가입하지 않은 사용자입니다. 먼저 가입해주세요.")
        return

    now = datetime.now()
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    c.execute("SELECT balance, last_checkin_time FROM users WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    balance = result[0] or 0
    last_checkin_time = result[1]

    already_checked_in = False
    if last_checkin_time:
        try:
            last_time = datetime.strptime(last_checkin_time, "%Y-%m-%d %H:%M:%S")
            if last_time.date() == now.date():
                already_checked_in = True
        except Exception:
            pass  # 잘못된 값이면 무시

    if already_checked_in:
        await interaction.followup.send("📅 이미 오늘 출석하셨습니다!")
        conn.close()
        return

    reward = 100
    balance += reward

    c.execute("UPDATE users SET balance = ?, last_checkin_time = ? WHERE user_id = ?",
              (balance, now.strftime("%Y-%m-%d %H:%M:%S"), user_id))
    conn.commit()
    conn.close()

    embed = nextcord.Embed(title="✅ 출석 완료!", color=0x76FF7A)
    embed.add_field(name="출석자", value=name, inline=True)
    embed.add_field(name="받은 보상", value=f"{reward}원", inline=True)
    embed.add_field(name="현재 잔액", value=f"{balance}원", inline=False)

    await interaction.followup.send(embed=embed)




@bot.slash_command(name="잔액랭킹", description="상위 5명의 잔액 랭킹을 확인합니다.")
async def 잔액랭킹(interaction: Interaction):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    c.execute("SELECT name, balance FROM users ORDER BY balance DESC LIMIT 5")
    top_users = c.fetchall()
    conn.close()

    embed = nextcord.Embed(title="💰 잔액 랭킹 TOP 5", color=0xFFD700)

    for idx, (name, balance) in enumerate(top_users, start=1):
        embed.add_field(
            name=f"{idx}위 - {name}",
            value=f"잔액: {balance:,}원",
            inline=False
        )

    await interaction.response.send_message(embed=embed)



# --- 잔액 변경 (관리자만) ---
@bot.slash_command(name="잔액변경", description="유저의 잔액을 변경할 수 있습니다.", default_member_permissions=nextcord.Permissions(administrator=True))
async def 잔액변경(
    interaction: Interaction,
    유저: nextcord.Member = nextcord.SlashOption(description="유저를 선택하세요."),
    사유: str = nextcord.SlashOption(description="변경 사유를 입력하세요."),
    변경할금액: int = nextcord.SlashOption(description="변경할 금액을 입력하세요.")
):
    if not (interaction.user.guild_permissions.administrator or interaction.guild.owner_id == interaction.user.id):
        await interaction.response.send_message("관리자만 사용할 수 있는 명령어입니다.", ephemeral=True)
        return

    user_id = str(유저.id)
    if not user_exists(user_id):
        await interaction.response.send_message("❌ 가입이 되어있지 않거나 존재하지 않는 유저입니다.", ephemeral=True)
        return

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    current_balance = c.fetchone()[0] or 0
    new_balance = current_balance + 변경할금액
    c.execute("UPDATE users SET balance = ? WHERE user_id = ?", (new_balance, user_id))
    conn.commit()
    conn.close()

    embed = nextcord.Embed(
        title=f"{interaction.user.name}님의 요청",
        description=f"{유저.mention}님의 잔액 변경 완료!",
        color=nextcord.Color(0xF3F781)
    )
    embed.add_field(name="변경한 금액", value=f"{변경할금액}원", inline=False)
    embed.add_field(name="현재 잔액", value=f"{new_balance}원", inline=False)
    embed.add_field(name="사유", value=사유, inline=False)
    await interaction.response.send_message(embed=embed)


# --- 게시물 올리기 (쿨타임 15초) ---
@bot.slash_command(name="게시물올리기", description="디스타그램에 게시물을 올립니다.")
async def 게시물올리기(interaction: Interaction):
    user_id = str(interaction.user.id)
    if not user_exists(user_id):
        await interaction.response.send_message("❗가입하지 않은 사용자입니다.", ephemeral=True)
        return

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT follower, like, hate, last_post_time FROM users WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    follower, like, hate, last_post_time = result if result else (0, 0, 0, None)

    success = [
        "멋진 오운완 사진", "감성 카페에서 찍은 한 컷", "그냥 외모가 원인",
        "해시태그 전략이 제대로 먹혔다", "스토리 공유 이벤트 덕분에 떡상"
    ]
    fail = [
        "감성글 썼다가 감성팔이로 오해받음", "무심코 한 말이 트리거", "과한 보정",
        "정치 얘기 살짝 해버림", "짜증나는 광고같이 보임"
    ]
    neutral = [
        "이상하게 이 사진은 다들 무시함", "알고리즘이 나를 버림", "업로드 시간 실패",
        "너무 자주 올렸더니 피로감 온 듯", "감성 폭발했는데 나만 느낌"
    ]

    result_choice = random.choice(["good", "bad", "neutral"])

    if result_choice == "good":
        origin = random.choice(success)
        follower += 10
        like += 30
        msg = f"📈 알고리즘을 탔습니다!\n(원인: {origin})\n+10 Follower / +30 Like"
    elif result_choice == "bad":
        origin = random.choice(fail)
        follower -= 10
        hate += 30
        msg = f"📉 논란의 여지가 있는 사진이네요...\n(원인: {origin})\n-10 Follower / +30 Hate"
    else:
        origin = random.choice(neutral)
        msg = f"😐 이목을 끌지 못했어요..\n(원인: {origin})\n+0 Follower / +0 Like"

    c.execute("""
        UPDATE users SET follower = ?, like = ?, hate = ?, last_post_time = ?
        WHERE user_id = ?
    """, (follower, like, hate, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), user_id))

    conn.commit()
    conn.close()

    embed = nextcord.Embed(title="📸 게시물 업로드", description=msg, color=0xff76c3)
    await interaction.response.send_message(embed=embed)


# --- 내피드 확인 (쿨타임 10초) ---
@bot.slash_command(name="내피드", description="자신의 디스타그램 피드를 확인합니다.")
async def 내피드(interaction: Interaction):
    await interaction.response.defer()  # 응답 지연 방지
    user_id = str(interaction.user.id)

    if not user_exists(user_id):
        await interaction.followup.send("❗가입하지 않은 사용자입니다.", ephemeral=True)
        return

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT name, follower, following, like, hate, last_feed_time FROM users WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    conn.close()

    if result is None:
        await interaction.followup.send("❗가입된 유저 정보가 없습니다.", ephemeral=True)
        return

    name, follower, following, like, hate, last_feed_time = result

    # 칭호 설정
    if follower >= 10000:
        title = "🎤 연예인"
    elif follower >= 5000:
        title = "🌟 인플루언서"
    elif follower >= 1000:
        title = "🔥 라이징스타"
    elif hate >= 10000:
        title = "💀 혐오유발자"
    elif hate >= 5000:
        title = "🦇 다크나이트"
    elif hate >= 1000:
        title = "💢 불행전달자"
    else:
        title = "👤 일반인"

    embed = nextcord.Embed(title="📱 내 디스타그램 피드", color=0xbf74fd)
    embed.add_field(name="이름", value=name, inline=False)
    embed.add_field(name="📈 팔로워", value=str(follower), inline=True)
    embed.add_field(name="📉 팔로잉", value=str(following), inline=True)
    embed.add_field(name="❤️ 좋아요", value=str(like), inline=True)
    embed.add_field(name="💔 싫어요", value=str(hate), inline=True)
    embed.add_field(name="🏷️ 칭호", value=title, inline=False)

    await interaction.followup.send(embed=embed)



# --- 랜덤 이벤트 발생 (쿨타임 15분) ---
@bot.slash_command(name="이벤트", description="랜덤 이벤트가 발생합니다(쿨타임 : 5분)")
async def 이벤트(interaction: Interaction):
    user_id = str(interaction.user.id)
    if not user_exists(user_id):
        await interaction.response.send_message("❗가입하지 않은 사용자입니다.", ephemeral=True)
        return

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT follower, following, like, hate, last_event_time FROM users WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    follower, following, like, hate, last_event_time = result

    on_cd, secs_left = is_on_cooldown(last_event_time, 5)
    if on_cd:
        mins = secs_left // 60
        secs = secs_left % 60
        await interaction.response.send_message(f"⏳ 쿨타임입니다. {mins}분 {secs}초 후에 다시 시도해주세요.", ephemeral=True)
        conn.close()
        return

    events = [
        ("📺 방송에 출연했어요!", 1000, 0, 1000, 0, 0.1),
        ("💸 팔로워 구매에 홀렸어요...", 200, 0, 0, 100, 5),
        ("🔓 해킹을 당했어요 (팔로잉)", -50, 200, 100, 0, 5),
        ("📈 릴스가 떡상했어요!", 100, 0, 500, 0, 10),
        ("❌ 해킹을 당했어요 (계정)", -follower, -following, -like, -hate, 0.1),
        ("🏢 기획사에 들어갔어요!", 500, 0, 500, 0, 0.4),
        ("🧹 팔로잉을 정리했어요!", 0, -100, 0, 50, 0.4),
        ("🗯️ 혐오발언을 했어요...", -200, 0, 0, 500, 4.5),
        ("❤️ 기부 사진을 올렸어요!", 200, 0, 1000, 0, 4.5),
        ("📶 소소한 오름", 1, 0, 1, 0, 45),
        ("💤 아무 일도 없었어요", 0, 0, 0, 0, 45),
    ]

    weights = [e[5] for e in events]
    selected = random.choices(events, weights=weights, k=1)[0]
    name, f_change, fg_change, l_change, h_change, _ = selected

    if name == "❌ 해킹을 당했어요 (계정)":
        follower, following, like, hate = 0, 0, 0, 0
    else:
        follower += f_change
        following += fg_change
        like += l_change
        hate += h_change

    c.execute("""
        UPDATE users SET follower = ?, following = ?, like = ?, hate = ?, last_event_time = ?
        WHERE user_id = ?
    """, (follower, following, like, hate, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), user_id))

    conn.commit()
    conn.close()

    embed = nextcord.Embed(title="🎲 이벤트 발생!", description=name, color=0xffdf7c)
    if name == "💤 아무 일도 없었어요":
        embed.add_field(name="🥱", value="정말 아무 일도 없었어요...", inline=False)
    else:
        embed.add_field(name="📊 변화량", value=(
            f"📈 팔로워: {f_change:+}\n"
            f"📉 팔로잉: {fg_change:+}\n"
            f"❤️ 좋아요: {l_change:+}\n"
            f"💔 싫어요: {h_change:+}"
        ), inline=False)

    await interaction.response.send_message(embed=embed)


@bot.slash_command(name="익명", description="익명으로 메시지를 보냅니다.")
async def 익명(interaction: nextcord.Interaction, *, 내용: str):
    # 익명 메시지 전송 (박스 스타일)
    await interaction.channel.send(f"🗣️ **익명 메시지:**\n```{내용}```")

    # 로그 채널 가져오기
    log_channel = bot.get_channel(1383790330926858341)  # 숫자형 ID
    if log_channel:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        nickname = interaction.user.nick if interaction.user.nick else interaction.user.name
        user_id = interaction.user.id

        # 임베드 만들기
        embed = nextcord.Embed(title="🗒️ 익명 메시지 로그", color=0x888888)
        embed.add_field(name="보낸 시각", value=f"`{now}`", inline=False)
        embed.add_field(name="닉네임", value=f"`{nickname}`", inline=True)
        embed.add_field(name="유저 ID", value=f"`{user_id}`", inline=True)
        embed.add_field(name="내용", value=f"```{내용}```", inline=False)
        embed.set_footer(text="익명 시스템 로그")

        await log_channel.send(embed=embed)

    # 사용자에게 응답 (자신만 보기)
    await interaction.response.send_message("✅ 익명 메시지가 전송되었습니다.", ephemeral=True)


# --- 닉네임 변경 명령어 ---
@bot.command(name="닉네임변경")
async def 닉네임변경(ctx, *, 새_닉네임: str):
    if not ctx.guild.me.guild_permissions.manage_nicknames:
        await ctx.send("❌ 봇에게 '닉네임 변경' 권한이 없습니다. 서버 설정을 확인하세요.")
        return

    try:
        await ctx.author.edit(nick=새_닉네임)
        await ctx.send(f"✅ {ctx.author.mention}님의 닉네임이 `{새_닉네임}`(으)로 변경되었습니다.")
    except nextcord.Forbidden:
        await ctx.send("❌ 닉네임 변경 권한이 부족합니다.")
    except Exception as e:
        await ctx.send(f"❌ 닉네임 변경 중 오류가 발생했습니다: {e}")


@bot.command(name="수빈")
async def 수빈(ctx):
    await ctx.send("서버 내 최강 미녀")

@bot.command(name="인천나얼")
async def 인천나얼(ctx):
    await ctx.send("서버 내 핵심인재")

@bot.command(name="레인")
async def 레인(ctx):
    await ctx.send("레인공쥬등장")

@bot.command(name="봄")
async def 봄(ctx):
    await ctx.send('봄이는 수비니를 조아해')

@bot.command(name="어서오세요")
async def 어서오세요(ctx):
    ran = random.randint(0, 3)
    if ran == 0:
        r = "반가워요"
    elif ran == 1:
        r = "환영해요"
    elif ran == 2:
        r = "음챗해요"
    else:
        r = "게임해요"
    await ctx.channel.send(r)


@bot.event
async def on_ready():
    print(f'We have logged in as {bot.user}')
    print("등록된 명령어 목록:", [cmd.name for cmd in bot.commands])


init_db()
bot.run(Token)
