import discord
from discord.ext import commands
from discord import Member
from discord.ext.commands import has_permissions, MissingPermissions
from discord.utils import get
from config import settings
from mysqlconfig import host, user, password, db_name
from message import messages
import random
from asyncio import sleep
import sqlite3 as sq
from datetime import timedelta, datetime
import mysql.connector
from dislash import InteractionClient, Option, OptionType
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger


intents = discord.Intents.all() #получам права
bot = commands.Bot(command_prefix = settings['prefix'], intents = intents) #прогружаем префикс
slash = InteractionClient(bot)




con = mysql.connector.connect(
    host=host,
    user=user,
    password=password,
    database=db_name
)
cur = con.cursor()

async def getuserid(discordId):
    if await getclient(discordId) == False:
        return(0)
    cur.execute(f"SELECT id FROM user WHERE discordId = {discordId}")
    record = cur.fetchall()
    return(record[0][0])


async def defsetmoney(discordId, money):
    cur.execute(f"UPDATE user SET money = {money} WHERE discordId = {discordId}")
    con.commit()


async def createchannel(owner, reaction, category, recipient = 0, money = 0,):
    guild = bot.get_guild(settings['guild'])
    discorowner = guild.get_member(owner)
    cur.execute(f"INSERT INTO tickets(ownerId, type, money, recipient) VALUES({owner.id}, '{category}', {money}, {recipient})")
    con.commit()
    cur.execute("SELECT ticketId FROM tickets ORDER BY ticketId DESC LIMIT 1")
    record = cur.fetchall()
    ticketcategori = bot.get_channel(settings['ticketcategori'])
    bitcategori = bot.get_channel(settings['bitcategori'])
    if category == "bid":
        channel = await guild.create_text_channel(f"bid-{record[0][0]}", category = bitcategori)
        await channel.set_permissions(owner, read_messages=True)
        color = discord.Colour.from_rgb(0, 102, 102)
        embed = discord.Embed(
            title = "Тиккет",
            description = f"{owner.mention} вы создали запрос. Укажите ник игрока и описание ситуации.",
            colour = color
        )

        await channel.send(embed=embed)
        return(channel)

    msg = "Если вы видете это. Вы что-то сломали"
    if category == "reg":
        msg = "Это начало регистрации! Ожидайте пока Вам ответит сотрудник банка"
    if category == "alm":
        msg = "Вы хотите пополнить ваш IBM счет - алмазами? Дождитесь ответа тех. поддержки"
    if category == "pkr":
        msg = "Вы хотите получить кредит? Дождитесь ответа тех. поддержки"
    if category == "hbk":
        msg = "Вам нужна помощь по банку? Можете задать Ваш вопрос в этом чате. Свободный сотрудник тех.поддержки ответит как только освободиться!"
    if category == "hsl":
        msg = "Вам нужна помощь по IMB SALE? Можете задать Ваш вопрос в этом чате. Свободный сотрудник тех.поддержки ответит как только освободиться!"
    if category == "nks":
        msg = "Вам нужна помощь по накопительному счету? Можете задать Ваш вопрос в этом чате. Свободный сотрудник тех.поддержки ответит как только освободиться!"
    channel = await guild.create_text_channel(f"{category}-{record[0][0]}", category = ticketcategori)
    await channel.set_permissions(owner, read_messages=True)

    color = discord.Colour.from_rgb(0, 102, 102)
    embed = discord.Embed(
        title = "Тиккет",
        description = f"{owner.mention} {msg}",
        colour = color
    )

    await channel.send(embed=embed)
    return(channel)


async def deletechannel(channel, invterval, delta):
    async def lol():
        await channel.delete()
    date_now = datetime.now()
    scheduler = AsyncIOScheduler()
    if invterval == 0:
        await channel.delete()
        return
    if delta == "s":
        time = date_now + timedelta(seconds=invterval)
        scheduler.add_job(lol, trigger='cron', second=time.second)
    if delta == "m":
        time = date_now + timedelta(minutes=invterval)
        scheduler.add_job(lol, trigger='cron', minute=time.minute, second=time.second)
    else:
        await channel.delete()
        return
    scheduler.start()
      

async def getclient(memberId):
    cur.execute(f"SELECT status FROM user WHERE discordId = {memberId}")
    record = cur.fetchall()
    if len(record) == 0:
        return(False)
    if record[0][0] == 'ban':
        return(False)
    return(True)


async def checkclient(memberId):
    cur.execute(f"SELECT status FROM user WHERE discordId = {memberId}")
    record = cur.fetchall()
    if len(record) == 0:
        return(False)
    if record[0][0] == 'ban':
        return(False)
    return(True)  


async def getrole(memberId, permmision):
    cur.execute(f"SELECT status FROM user WHERE discordId = {memberId}")
    record = cur.fetchall()
    if len(record) == 0:
        return(False)
    if record[0][0] in permmision:
        return(True)
    return(False)


async def reply(ctx, redgreen, head, text):
    if text in messages:
        text = messages[text]

    if redgreen:
        color = discord.Colour.from_rgb(51, 153, 102)
    else:
        color = discord.Colour.from_rgb(255, 102, 102)
    embed = discord.Embed(
        title = head,
        description = text,
        colour = color
    )
    await ctx.reply(embed=embed)
    return


async def setcard(opponent, card):
    cardlist = ["Обычная", "Универсальная", "Золотая", "Платиновая"]
    for i in cardlist:
        if settings[i] == card:
            card = i

    cardlist = ["Обычная", "Универсальная", "Золотая", "Платиновая"]
    guild = bot.get_guild(settings['guild'])
    user = guild.get_member(opponent)


    if card not in cardlist:
         return(False)

    if await checkclient(opponent):
        cur.execute(f"SELECT card FROM user WHERE discordId = {opponent}")
        record = cur.fetchall()

        oldrole = discord.utils.get(guild.roles, id = settings[record[0][0]])
        await user.remove_roles(oldrole)

    try:
        cur.execute(f"UPDATE user SET card = '{card}' WHERE discordId = {opponent}")
        con.commit()
    except:
        pass

    role = discord.utils.get(guild.roles, id = settings[card])
    await user.add_roles(role)

    await user.send(f"Вы получили карту, её статус ``{card}``")
    await user.send(f"Подробности по карте, вы можете узнать в канале: *ИНФОРМАЦИЯ*")

    return(True)


async def moneylog(sender, getter, text, money):
    guild = bot.get_guild(settings['guild'])
    channel = guild.get_channel(settings['moneylogch'])
    text = messages[text]
    text = f"{sender}, {text} ``{money} alm`` {getter}"
    color = discord.Colour.from_rgb(51, 153, 102)
    embed = discord.Embed(
        title = "Транзакция",
        description = text,
        colour = color
    )
    await channel.send(embed=embed)


async def depositdb():
    print("depositdb start",datetime.now())
    cur.execute("SELECT id, card, money, deposit_Box, deposit_money, discordId FROM user WHERE deposit_box != 0")
    record = cur.fetchall()
    if len(record) == 0:
        return

    cardlist = {
        'Обычная': 0, 
        'Универсальная': 5, 
        'Золотая': 5, 
        'Платиновая': 7
        }

    for i in record:
        id = i[0]
        card = i[1]
        money = i[2]
        depositBox= i[3]
        depositMoney = i[4]
        discordId = i[5]

        percent = cardlist[card]
        percentmoney = round(money/100*percent)
        newDepositMoney = depositMoney+percentmoney

        if newDepositMoney >= 1728*depositBox:
            user = bot.get_user(discordId)
            await user.send("У вас заполнились ячейки. Купите новые!")
            return


        cur.execute(f"UPDATE user SET deposit_money = {newDepositMoney} WHERE id = {id}")
        con.commit()


async def getseller(memberId):
    memberId = await getuserid(memberId)
    cur.execute(f"SELECT id FROM shops WHERE owner = {memberId}")
    record = cur.fetchall()
    if len(record) == 0:
        return(0)
    return(record[0][0])

@bot.remove_command('help') #удаляем команду help


@slash.slash_command( #обход
    description = '[owner] react', 
    options = [
        Option("type", description = "type", type=OptionType.STRING, required=True)
    ])   
async def react(ctx, type: str):
    print("Старт")
    member = ctx.author
    role = await getrole(member.id, {"owner"})
    if role == False:
        await ctx.send(f"У вас недостаточно прав для рассмотрения запроса")
        return
    if type == "reg":
        message = settings['eregmsg']
        reactionList = ["✅"]
    elif type == "tp":
        message = settings['emhelpmsg']
        reactionList = ["💶", "💳", "🏦" , "🛍️", "🛸"]
    else:
        return
    message = await ctx.channel.fetch_message(message)
    for i in reactionList:
        await message.add_reaction(i)
    


@slash.slash_command( #обход
    description = '[owner] выдать роль', 
    options = [
        Option("opponent", description = "пользователь", type=OptionType.USER, required=True),
        Option("role", description = "роль", type=OptionType.STRING, required=True)
    ])   
async def role(ctx, opponent: discord.Member, role: str):
    member = ctx.author.id
    checkrole = await getrole(member, {"owner"})
    if checkrole == False:
        await reply(ctx, False, "Выдача роли", "notowner")
        return
    cur.execute(f"SELECT status FROM user WHERE discordId = {opponent.id}")
    opRecord = cur.fetchall()
    if len(opRecord) == 0:
        await reply(ctx, False, "Выдача роли", f"{opponent.mention} не является клиентом банка")
        return
    rolelist = ["admin", "tp", "user", "ban"]
    if role not in rolelist:
        await reply(ctx, False, "Выдача роли", f"Вы указали неверную роль. Укажите роль из списка: {rolelist}")
        return
    cur.execute(f"UPDATE user SET status = '{role}' WHERE discordId = {opponent.id}")
    await reply(ctx, True, "Выдача роли", f"Вы установили роль ``{role}`` для {opponent.mention}")
    con.commit()

@slash.slash_command(
    description = '[A] установить карту', 
    options = [
        Option("opponent", description = "пользователь", type=OptionType.USER, required=True),
        Option("card", description = "роль", type=OptionType.ROLE, required=True)
    ])   
async def card(ctx, opponent: discord.Member, card: discord.Role):
    member = ctx.author
    role = await getrole(member.id, {"admin", "owner"})
    if role == False:
        await reply(ctx, False, "Установка карты", "notrights")
        return

    if await setcard(opponent.id, card) == False:
        await reply(ctx, False, "Установка карты", "notcard")
        return
    await reply(ctx, True, "Установка карты", "successfully")


@slash.slash_command(
    description = 'отправить деньги', 
    options = [
        Option("opponent", description = "пользователь", type=OptionType.USER, required=True),
        Option("money", description = "кол-во alm", type=OptionType.INTEGER, required=True),
    ])    
async def givemoney(ctx, opponent: discord.Member, money: int): # Создаём функцию и передаём аргумент ctx.
    member = ctx.author
    if opponent == member:
        await reply(ctx, False, "Отправить алмазы", "error")
        return

    if await checkclient(member.id) == False:
        await reply(ctx, False, "Отправить алмазы", "notclient")
        return

    cur.execute(f"SELECT money FROM user WHERE discordId = {member.id}")
    record = cur.fetchall()
    if record[0][0] <= money:
        await reply(ctx, False, "Отправить алмазы", "notmoney")
        return
    if 0 >= money:
        await reply(ctx, False, "Отправить алмазы", "error")
        return
    cur.execute(f"SELECT money FROM user WHERE discordId = {opponent.id}")
    opRecord = cur.fetchall()
    if len(opRecord) == 0:
        await reply(ctx, False, "Отправить алмазы", f"{opponent.mention} не является клиентом банка")
        return
    await defsetmoney(opponent.id, opRecord[0][0] + money) #начисляем деньги
    await defsetmoney(member.id, record[0][0] - money) #снимаем деньги
    await reply(ctx, True, "Отправить алмазы", f"Вы перевели {opponent.mention} - ``{money} алм.``")
    await moneylog(member, opponent, 'sendmoney',money)


@slash.slash_command(
    description = '[A] Отправить деньги', 
    options = [
        Option("opponent", description = "ник на сервере", type=OptionType.STRING, required=True),
        Option("money", description = "кол-во alm", type=OptionType.INTEGER, required=True),
    ])    
async def sgivemoney(ctx, opponent, money: int): # Создаём функцию и передаём аргумент ctx.
    guild = bot.get_guild(927978558528323676)
    opponent = discord.utils.get(guild.members, name = opponent)
    member = ctx.author

    if opponent == member:
        await reply(ctx, False, "Скрытый перевод", "error")
        return
    role = await getrole(member.id, {"admin", "owner"})
    if role == False:
        await reply(ctx, False, "Скрытый перевод", "notrights")
        return

    cur.execute(f"SELECT money FROM user WHERE discordId = {member.id}")
    record = cur.fetchall()
    if len(record) == 0:
        await reply(ctx, False, "Скрытый перевод", "notclient")
        return
    if record[0][0] <= money:
        await reply(ctx, False, "Скрытый перевод", "notmoney")
        return
    if 0 >= money:
        await reply(ctx, False, "Скрытый перевод", "error")
        return
    cur.execute(f"SELECT money FROM user WHERE discordId = {opponent.id}")
    opRecord = cur.fetchall()
    if len(opRecord) == 0:
        await reply(ctx, False, f"{opponent.mention} не является клиентом банка")
        return
    await defsetmoney(opponent.id, opRecord[0][0] + money) #начисляем деньги
    await defsetmoney(member.id, record[0][0] - money) #снимаем деньги
    await reply(ctx, True, f"Вы перевели {opponent.mention} - ``{money} алм.``") #добавить проверку на кол-во и сделать склонение
    await moneylog(member, opponent, 'sendmoney',money)


@slash.slash_command(
    description = '[owner] установить деньги', 
    options = [
        Option("opponent", description = "пользователь", type=OptionType.USER, required=True),
        Option("money", description = "кол-во alm", type=OptionType.INTEGER, required=True),
    ])   
async def setmoney(ctx, opponent: discord.Member, money: int):
    member = ctx.author
    cur.execute(f"SELECT money FROM user WHERE discordId = {opponent.id}")
    opRecord = cur.fetchall()
    if len(opRecord) == 0:
        await reply(ctx, False, "Установка денег", f"{opponent.mention} не является клиентом банка")
        return
    role = await getrole(member.id, {"owner"})
    if role == False:
        await reply(ctx, False, "Установка денег", "notowner")
        return
    await reply(ctx, True, "Установка денег", "successfully")
    await defsetmoney(opponent.id, money)
    await moneylog(member, opponent, 'setmoney',money)


@slash.slash_command(
    description = '[A] добавить деньги', 
    options = [
        Option("opponent", description = "пользователь", type=OptionType.USER, required=True),
        Option("money", description = "кол-во alm", type=OptionType.INTEGER, required=True),
    ])   
async def addmoney(ctx, opponent: discord.Member, money: int):
    member = ctx.author
    cur.execute(f"SELECT money FROM user WHERE discordId = {opponent.id}")
    opRecord = cur.fetchall()
    if len(opRecord) == 0:
        await reply(ctx, False, "Добавить денег", f"{opponent.mention} не является клиентом банка")
        return
    opponentMoney = opRecord[0][0]
    newMoney = opponentMoney + money
    cur.execute(f"SELECT status FROM user WHERE discordId = {member.id}")
    record = cur.fetchall()
    role = record[0][0]
    if role == "tp":
        channel = await createchannel(member, "", "bid", opponent.id, money)
        await member.send(f"Был создан запрос ``{channel}`` на изменение счета пользователя ``{opponent}``")
        embed = discord.Embed(
            title = "Создано автоматически",
            description = f"{member.mention} хочет пополнить счет пользователя ``{opponent}`` в размере ``{money} alm``",
            colour = discord.Colour.from_rgb(0, 102, 102)
        )

        await channel.send(embed=embed)
        return
    role = await getrole(member.id, {"admin", "owner"})
    if role == False:
        await reply(ctx, False, "Добавить денег", "notrights")
        return

    await defsetmoney(opponent.id, newMoney)
    await reply(ctx, True, "Добавить денег", f"Вы дали ``{money} alm`` для ``{opponent}``, теперь его счет составляет ``{newMoney} alm``")
    await moneylog(member, opponent, 'addmoney',money)


@slash.slash_command(
    description = '[A] убрать деньги', 
    options = [
        Option("opponent", description = "пользователь", type=OptionType.USER, required=True),
        Option("money", description = "кол-во alm", type=OptionType.INTEGER, required=True),
    ])   
async def removemoney(ctx, opponent: discord.Member, money: int):
    member = ctx.author
    cur.execute(f"SELECT money FROM user WHERE discordId = {opponent.id}")
    opRecord = cur.fetchall()
    if len(opRecord) == 0:
        await reply(ctx, False, "Забрать денеги", f"{opponent.mention} не является клиентом банка")
        return
    opponentMoney = opRecord[0][0]
    newMoney = opponentMoney - money

    cur.execute(f"SELECT status FROM user WHERE discordId = {member.id}")
    record = cur.fetchall()
    role = record[0][0]
    rolelist = ["admin", "owner"]
    if role == "tp":
        await member.send(f"Был создан запрос на изменение счета пользователя {opponent}")
        channel = await createchannel(member, "", "bid", opponent.id, money*-1)
        await channel.send(f"--*Создано автоматически*--\n{member.mention} хочет снять деньги с пользователя ``{opponent}`` в размере ``{money} alm``")
        return

    role = await getrole(member.id, {"admin", "owner"})
    if role == False:
        await reply(ctx, False, "Забрать денеги", "notrights")
        return

    await defsetmoney(opponent.id, newMoney)
    await reply(ctx, True, "Забрать денеги", f"Вы забрали ``{money} alm`` у ``{opponent}``, теперь его счет составляет ``{newMoney} alm``")
    await moneylog(member, opponent, 'removemoney',money)


@slash.slash_command(
    description = 'Посмотреть профиль', 
    options = [
        Option("opponent", description = "пользователь (необязательно)", type=OptionType.USER, required=False)
    ])    
async def info(ctx):
    member = ctx.author
    if await getclient(member.id) == False:
        await reply(ctx, False, "Информация", "notrights")
        return
    cur.execute(f"SELECT id, minecraftNick, money, deposit_Box, deposit_basicMoney, deposit_Money, FROM user WHERE discordId = {member.id}")
    record = cur.fetchall()
    memberid = record[0][0]
    minecraftnick = record[0][1]
    money = record[0][2]
    depositbox = record[0][3]
    depositmoney = record[0][4]+record[0][5]

    embed = discord.Embed(colour=discord.Colour.from_rgb(204, 255, 0),title = f"Профиль {member}", description = f"ID: {memberid} | Майнкрафт ник: {minecraftnick}")
    embed.set_footer(text=f"{datetime.now()}")
    embed.set_thumbnail(url=member.avatar_url)
    embed.add_field(name="Алмазы:", value=f"{money}")
    embed.add_field(name="Ячейки накопительного счета:", value=f"{depositbox}")
    embed.add_field(name="Деньги на накопительном счету", value=f"{depositmoney}")
    await ctx.reply(embed=embed)


@slash.slash_command(
    description = '[A] просмотр профиля', 
    options = [
        Option("opponent", description = "пользователь", type=OptionType.USER, required=True)
    ])   
async def ainfo(ctx, opponent: discord.Member):
    member = ctx.author
    role = await getrole(member.id, {"tp", "admin", "owner"})
    if role == False:
        await ctx.reply(f"У вас недостаточно прав для рассмотрения запроса")
        return

    if await checkclient(opponent.id) == False:
        await reply(ctx, False, "AINFO", "error")
        return

    cur.execute(f"SELECT id, minecraftNick, money, deposit_Box, deposit_basicMoney, deposit_Money, dateRegister, card, status FROM user WHERE discordId = {opponent.id}")
    record = cur.fetchall()
    memberid = record[0][0]
    minecraftnick = record[0][1]
    money = record[0][2]
    depositbox = record[0][3]
    depositmoney = record[0][4]+record[0][5]
    dateRegister = record[0][6]
    card = record[0][7]
    role = record[0][8]

    now = datetime.now()
    now = now.strftime("%m/%d/%Y, %H:%M:%S")
    embed = discord.Embed(colour=discord.Colour.from_rgb(204, 255, 0),title = f"Профиль {opponent}", description = f"ID: {memberid} | Майнкрафт ник: {minecraftnick}")
    embed.set_footer(text=f"{now} - ainfo запрос {member}")
    embed.set_thumbnail(url=opponent.avatar_url)
    embed.add_field(name="Алмазы:", value=f"{money}")
    embed.add_field(name="Ячейки накопительного счета:", value=f"{depositbox}")
    embed.add_field(name="Деньги на накопительном счету:", value=f"{depositmoney}")
    embed.add_field(name="Карта:", value=f"{card}")
    embed.add_field(name="Роль:", value=f"{role}")
    embed.add_field(name="Дата регистрации:", value=f"{dateRegister}")
    await ctx.reply(embed=embed)


@slash.slash_command(
    description = 'Купить ячейку накопительного счета', 
    )   
async def deposit_buy(ctx):
    member = ctx.author
    if await checkclient(member.id) == False:
        await reply(ctx, False, "Покупка ячейки", "notclient")
        return
    cur.execute(f"SELECT money, deposit_Box FROM user WHERE discordId = {member.id}")
    record = cur.fetchall()
    usermoney = record[0][0]
    depositbox = record[0][1]
    if usermoney < 45:
        await reply(ctx, False, "Покупка ячейки", "notmoney")
        return
    cur.execute(f"UPDATE user SET deposit_Box = {depositbox} + 1 WHERE discordId = {member.id}")
    cur.execute(f"UPDATE user SET money = {usermoney} - 45 WHERE discordId = {member.id}")
    con.commit()
    await reply(ctx, True, "Покупка ячейки", "depositbuy")


@slash.slash_command(
    description = 'Собрать деньги с накопительного счета', 
    )   
async def deposit_collect(ctx):
    member = ctx.author
    if await checkclient(member.id) == False:
        await reply(ctx, False, "Ячейка", "notclient")
        return

    cur.execute(f"SELECT deposit_Money, money FROM user WHERE discordId = {member.id}")
    record = cur.fetchall()
    depositmoney = record[0][0]
    usermoney = record[0][1]
    if depositmoney <= 0:
        await reply(ctx, False, "Ячейка", "depositnotmoney")
        return
    cur.execute(f"UPDATE user SET deposit_Money = 0 WHERE discordId = {member.id}")
    cur.execute(f"UPDATE user SET money = {usermoney} + {depositmoney} WHERE discordId = {member.id}")
    con.commit()
    await reply(ctx, True, "Ячейка", "depositcollect")


@slash.slash_command(
    description = '[A] зарегистрировать клиента', 
    options = [
        Option("opponent", description = "пользователь", type=OptionType.USER, required=True),
        Option("minecraftnick", description = "майнкрафт ник", type=OptionType.STRING, required=True),
        Option("card", description = "карта", type=OptionType.ROLE, required=True),
        Option("depositbox", description = "количество ячеек", type=OptionType.INTEGER, required=True),
        Option("money", description = "кол-во alm", type=OptionType.INTEGER, required=True),
    ])   
async def reg(ctx, opponent: discord.Member, minecraftnick: str, card: discord.Role, depositbox: int, money: int):
    member = ctx.author
    guild = bot.get_guild(settings['guild'])
    clientrole = settings['clientrole']
    channelName = str(ctx.channel)
    channelName = channelName.rpartition("-")
    name = channelName[0]
    id = channelName[2]

    role = await getrole(member.id, {"tp", "admin", "owner"})
    if role == False:
        await reply(ctx, False, "Регистрация", "notrights")
        return

    if name != "reg":
        await reply(ctx, False, "Регистрация", "notregch")
        return

    cur.execute(f"SELECT modClosedId FROM tickets WHERE ticketId = '{id}'")
    record = cur.fetchall()
    if record[0][0] != None:
        await reply(ctx, False, "Регистрация", "ticketclose")
        return

    if await setcard(opponent.id, card) == False:
        await reply(ctx, False, "Регистрация", "notcard")
        return

    if await checkclient(opponent.id):
        cur.execute(f"UPDATE tickets SET modClosedId = {member.id} WHERE ticketId = '{id}'")
        con.commit()
        await reply(ctx, False, "Регистрация", "regclose2")
        await reply(ctx, False, "Регистрация", "regclose")
        await reply(ctx, False, "Регистрация", "close2m")
        return

    card = str(guild.get_role(card))
    cur.execute(f"UPDATE tickets SET modClosedId = {member.id} WHERE ticketId = '{id}'")
    cur.execute(f"INSERT INTO user(discordId, minecraftNick, card, deposit_Box, money, dateRegister, status ) VALUES({opponent.id}, '{minecraftnick}', '{card}', {depositbox}, {money}, '{datetime.now().date()}', 'user')")
    con.commit()
    await setcard(opponent.id, card)
    await reply(ctx, True, "Регистрация", "regclose")
    await reply(ctx, True, "Регистрация", "close2m")
    user = guild.get_member(member.id)
    clientrole = guild.get_role(clientrole)
    await user.add_roles(clientrole)
    await deletechannel(ctx.channel, 2, "m")


@slash.slash_command(
    description = '[A] открыть запрос', 
    )   
async def bid(ctx):
    member = ctx.author

    role = await getrole(member.id, {"tp", "admin", "owner"})
    if role == False:
        await reply(ctx, False, "Открытие запроса", "notrights")
        return
    await reply(ctx, True, "Открытие запроса", "successfully")
    await createchannel(member, "", "bid")


@slash.slash_command(
    description = '[A] одобрить запрос', 
    )   
async def accept(ctx):
    member = ctx.author
    channelName = str(ctx.channel)
    channelName = channelName.rpartition("-")
    name = channelName[0]
    id = channelName[2]

    role = await getrole(member.id, {"admin", "owner"})
    if role == False:
        await reply(ctx, False, "Запрос", "notrights")
        return

    cur.execute(f"SELECT money, recipient FROM tickets WHERE ticketId = '{id}'")
    record = cur.fetchall()
    if len(record) != 0:
        if record[0][0] != 0:
            cur.execute(f"SELECT discordId, money FROM user WHERE discordId = {record[0][1]}")
            usermoney = cur.fetchall()
            await defsetmoney(usermoney[0][0], usermoney[0][1]+record[0][0])
            getter = bot.get_user(usermoney[0][0])
            await moneylog(member, getter, "acceptmoney", record[0][0])

    cur.execute(f"UPDATE tickets SET type = 'bid-accept' WHERE ticketId = '{id}'")
    con.commit()
    await reply(ctx, True, "Запрос", f"Заявка была принята {member.mention}")
    await reply(ctx, True, "Запрос", "close15")
    await deletechannel(ctx.channel, 15, "s")


@slash.slash_command(
    description = '[A] отклонить запрос', 
    )   
async def deny(ctx):
    member = ctx.author
    channelName = str(ctx.channel)
    channelName = channelName.rpartition("-")
    name = channelName[0]
    id = channelName[2]

    role = await getrole(member.id, {"admin", "owner"})
    if role == False:
        await reply(ctx, False, "Запрос", "notrights")
        return

    cur.execute(f"UPDATE tickets SET type = 'bid-deny' WHERE ticketId = '{id}'")
    con.commit()
    await reply(ctx, False, "Запрос", f"Заявка была отклонена {member.mention}")
    await reply(ctx, False, "Запрос", "close15")
    await deletechannel(ctx.channel, 15, "s")


@slash.slash_command(
    description = '[A] закрыть тиккет', 
    )   
async def close(ctx):
    member = ctx.author
    channelName = str(ctx.channel)
    channelName = channelName.rpartition("-")

    role = await getrole(member.id, {"tp","admin", "owner"})
    if role == False:
        await reply(ctx, False, "Тиккет", "notrights")
        return

    cur.execute(f"SELECT type FROM tickets WHERE ticketId = {channelName[2]}")
    record = cur.fetchall()
    if len(record) == 0:
        await reply(ctx, False, "Тиккет", "error")
        return
    ticktype = record[0][0]

    cur.execute(f"UPDATE tickets SET modClosedId = {member.id} WHERE ticketId = '{channelName[2]}'")
    con.commit()

    await reply(ctx, True, "Тиккет", "successfully")
    await deletechannel(ctx.channel, 0, "m")


@slash.slash_command(
    description = '[owner] написать от именни бота', 
    options = [
        Option("message", description = "тут текст который отправит бот", type=OptionType.STRING, required=True)
    ])   
async def say(ctx, message):
    member = ctx.author
    print(type(ctx.author))
    role = await getrole(member.id, {"owner"})
    if role == False:
        await reply(ctx, False, "say", "notrights")
        return
    channel = bot.get_channel(ctx.channel.id)
    await ctx.channel.send(message)


#shop command

# @slash.slash_command(
#     description = '[owner] зарегистрировать магазин', 
#     options = [
#         Option("opponent", description = "Владелец магазина", type=OptionType.USER, required=True),
#         Option("shopname", description = "Название магазина", type=OptionType.STRING, required=True)
#     ])   
# async def shopreg(ctx, opponent, shopname):
#     role = await getrole(member.id, {"admin", "owner"})
#     if role == False:
#         await reply(ctx, False, "Регистрация магазина", "notrights")
#         return
#     print(await getseller(opponent.id))
#     if await getseller(opponent.id) != 0:
#         await reply(ctx, False, 'Регистрация магазина', 'EROR')
#         return
#     ownerid = await getuserid(opponent.id)
#     cur.execute(f"INSERT INTO shops(owner, name, dateRegister) VALUES({ownerid}, '{shopname}','{datetime.now().date()}')")
#     con.commit()
#     await reply(ctx, True, 'Регистрация магазина', 'successfully')


# @slash.slash_command(
#     description = '[owner] просмотр магазина', 
#     options = [
#         Option("shopname", description = "Название магазина", type=OptionType.STRING, required=True)
#     ])   
# async def shop(ctx, shopname):
#     if await getclient(member.id) == False:
#         await reply(ctx, False, "Просмотр магазина", "notrights")
#         return
#     cur.execute(f"SELECT id, owner, dateRegister, rating FROM shops WHERE name = '{shopname}'")
#     record = cur.fetchall()
#     if len(record) == 0:
#         await reply(ctx, False, "Просмотр магазина", "Магазин - не найден")
#         return
#     await reply(ctx, True, "Просмотр магазина", f"{record[0][0:]}")


# @slash.slash_command(
#     description = '[seller] добавить товар в магазин', 
#     options = [
#         Option("product", description = "Название товара", type=OptionType.STRING, required=True),
#         Option("price", description = "Цена товара", type=OptionType.INTEGER, required=True),
#         Option("ammout", description = "Кол-во товара (пример: 12 или 6ст или 1 шалкер)", type=OptionType.STRING, required=True),
#         Option("discription", description = "Описание товара", type=OptionType.STRING, required=True)
#     ])   
# async def addtoshop(ctx, shopname):
#     return

#events
@bot.event
async def on_raw_reaction_add(reaction):
    member = reaction.member
    memberObj = bot.get_user(member.id)
    channel = bot.get_channel(reaction.channel_id)
    message = await channel.fetch_message(reaction.message_id)
    user = bot.get_user(reaction.user_id)
    if reaction.message_id == settings['eregmsg']: #проверка для канала регистрации
        await message.remove_reaction(reaction.emoji, user)
        cur.execute(f"SELECT discordId FROM user WHERE discordId = {member.id}")
        Record = cur.fetchall()
        if len(Record) != 0:
            return
        cur.execute(f"SELECT ticketId FROM tickets WHERE ownerId = {member.id} AND type = 'reg'")
        twoRecord = cur.fetchall()
        if len(twoRecord) != 0:
            await memberObj.send(f"Вы уже создавали запрос на регистрацию #reg-{twoRecord[0][0]} если вы этого не делали - отправьте это сообщение любому администратору или обратитесь в тех.поддержку")
            return
        await createchannel(member, reaction, "reg")
    if reaction.message_id == settings['emhelpmsg']: #проверка для канала тех-поддержка
            await message.remove_reaction(reaction.emoji, user)
            emoji = str(reaction.emoji)
            if emoji == "💶": #пополнение счета
                await createchannel(member, reaction, "alm")
                return
            elif emoji == "💳": #получение кредита
                await createchannel(member, reaction, "pkr")
                return
            elif emoji == "🏦": #помощь по банку
                await createchannel(member, reaction, "hbk")
                return
            elif emoji == "🛍️": #помощь по IMB SALE
                await createchannel(member, reaction, "hsl")
                return
            elif emoji == "💰": #снять деньги с накопительного счета
                await createchannel(member, reaction, "nks")
                return
            elif emoji == "<a:2365peepocookie:919878291442266112>": #Почему IBM group - не перамида? 
                await reaction.member.send("Мы ТОЧНО не пирамида, мы уже это доказали администраторам SH")
                return
            else:
                await reaction.member.send("Данная категория - в разработке")
                return


@bot.event
async def on_message(message):
    text_message = message.content.lower()
    text_message = text_message.rpartition(" ")
    if "скам" in text_message:
        await message.channel.send(f"{message.author.mention} сам ты скам!")
        await message.author.send(f"{message.author.mention} Вы были забанены на сервере!")


@bot.event
async def on_ready():
    print (f"{datetime.now()} Bot ready")
    scheduler = AsyncIOScheduler(timezone="Europe/Moscow")
    scheduler.add_job(depositdb, trigger='cron', day_of_week = 'sun', hour = 0, minute = 1 )
    scheduler.start()


print (f"{datetime.now()} BOT START")
bot.run(settings['token']) #берем токен из конфига и стартуем