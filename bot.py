import discord
from discord.ext import commands
from discord import Member
from discord.ext.commands import has_permissions, MissingPermissions
from discord.utils import get
from dislash import *
from config import settings, cardList, shop_card_price
from mysqlconfig import host, user, password, db_name
from message import messages
from asyncio import sleep
from datetime import timedelta, datetime
import mysql.connector
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

intents = discord.Intents.all()  # получам права
bot = commands.Bot(command_prefix=settings['prefix'], intents=intents)  # прогружаем префикс
slash = InteractionClient(bot)

con = mysql.connector.connect(
    host=host,
    user=user,
    password=password,
    database=db_name
)


class IClient:
    def __init__(self, ClientId):
        cur = con.cursor()
        cur.execute(f"""
            SELECT id, discordId, minecraftNick, money, deposit_box, deposit_money, 
            dateRegister, card, status, reklama, verification, clan, salesman 
            FROM user 
            WHERE id = {ClientId} or discordId = {ClientId}
        """)
        record = cur.fetchone()
        cur.close()
        if record is None:
            self.check = False
            return
        self.check = True
        self.id = record[0]
        self.discord_id = record[1]
        self.nick = record[2]
        self.money = record[3]
        self.deposit_box = record[4]
        self.deposit_money = record[5]
        self.register_date = record[6]
        self.card = record[7]
        self.status = record[8]
        self.reklama = record[9]
        self.verification = record[10]
        self.clan = record[11]
        self.salesman = record[12]

    def setmoney(self, money):
        cur = con.cursor()
        cur.execute(f"UPDATE user SET money = {money} WHERE discordId = {self.discord_id}")
        con.commit()
        cur.close()

    def deposit_add(self):
        cur = con.cursor()
        cur.execute(f"UPDATE user SET deposit_box = deposit_box+1 WHERE discordId = {self.discord_id}")
        con.commit()
        cur.close()

    def deposit_collect(self):
        cur = con.cursor()
        cur.execute(f"UPDATE user SET deposit_money = 0 WHERE discordId = {self.discord_id}")
        con.commit()
        cur.close()

    def setrole(self, role):
        cur = con.cursor()
        cur.execute(f"UPDATE user SET status = '{role}' WHERE discordId = {self.discord_id}")
        con.commit()
        cur.close()

    async def setcard(self, cardId):
        guild = bot.get_guild(settings['guild'])
        role_new = discord.utils.get(guild.roles, id=cardId)
        role_old = discord.utils.get(guild.roles, id=cardList[self.card])
        try:
            check = cardList[role_new.name]
            users = guild.get_member(self.discord_id)
        except:
            return False
        await users.remove_roles(role_old)
        await users.add_roles(role_new)
        cur = con.cursor()
        cur.execute(f"UPDATE user SET card = '{role_new.name}' WHERE discordId = {self.discord_id}")
        con.commit()
        cur.close()
        return True


class IShop:
    def __init__(self, ShopID, owner=-1):
        if owner != -1:
            owner = IClient(owner)
            owner = owner.id
        cur = con.cursor()
        cur.execute(f"SELECT id, owner, managers, name, dateRegister, rating FROM shops WHERE id = {ShopID} OR owner = {owner}")
        record = cur.fetchone()
        cur.close()
        if record is None:
            self.check = False
            return
        self.check = True
        self.id = record[0]
        self.owner_id = record[1]
        sale_man = IClient(self.owner_id)
        guild = bot.get_guild(settings['guild'])
        self.owner_name = sale_man.nick
        self.owner_discord = guild.get_member(sale_man.discord_id)
        self.managers = record[2]
        self.name = record[3]
        self.dateRegister = record[4]
        self.rating = record[5]
        cur = con.cursor()
        cur.execute(f"SELECT id FROM itemstore WHERE shop = {self.id}")
        items = cur.fetchall()
        cur.close()
        self.item = len(items)

    def register(self, name, owner_id):
        if self.check:
            return False
        cur = con.cursor()
        cur.execute(f"UPDATE user SET salesman = True WHERE id = {owner_id}")
        cur.execute(f"INSERT INTO shops(owner, name, dateRegister) VALUES({owner_id}, '{name}','{datetime.now().date()}')")
        con.commit()
        cur.close()

    def add_item(self, product, price, amount, description):
        cur = con.cursor()
        cur.execute(f"INSERT INTO itemstore(shop, name, price, amount, description) VALUES({self.id}, '{product}', {price}, {amount}, '{description}')")
        con.commit()
        cur.close()
        return


class IChannel:
    def __init__(self, ticketId: int):
        cur = con.cursor()
        cur.execute(
            f"SELECT ticketId, ownerId, type, modClosedId, money, recipient FROM tickets WHERE ticketId = {ticketId}")
        record = cur.fetchone()
        cur.close()
        if record is None:
            self.check = False
            return
        self.check = True
        self.id = record[0]
        self.ownerId = record[1]
        self.type = record[2]
        self.ModClosedId = record[3]
        self.money = record[4]
        self.recipient = record[5]

    async def close(self, clouser, status=True):
        if self.type != 'bid':
            if self.money != 0 and status:
                client = IClient(self.recipient)
                client.setmoney(client.money + self.money)
                self.type = "bid-accept"
            else:
                self.type = "bid-deny"
        cur = con.cursor()
        cur.execute(f"UPDATE tickets SET type = '{self.type}', modClosedId = {clouser} WHERE ticketId = {self.id}")
        con.commit()
        cur.close()

    async def create(type, ownerId, money=0, recipient=0):
        guild = bot.get_guild(settings['guild'])
        owner = guild.get_member(ownerId)
        ticketcategori = bot.get_channel(settings['ticketcategori'])
        bitcategori = bot.get_channel(settings['bitcategori'])

        cur = con.cursor()
        cur.execute(
            f"INSERT INTO tickets(ownerId, type, money, recipient) VALUES({ownerId}, '{type}', {money}, {recipient})")
        con.commit()
        cur.execute("SELECT ticketId FROM tickets ORDER BY ticketId DESC LIMIT 1")
        record = cur.fetchone()
        cur.close()
        if type == 'bid':
            mychannel = await guild.create_text_channel(f"bid-{record[0]}", category=bitcategori)
            await mychannel.set_permissions(owner, read_messages=True)
            color = discord.Colour.from_rgb(0, 102, 102)
            embed = discord.Embed(
                title="Тиккет",
                description=f"{owner.mention} вы создали запрос. Укажите ник игрока и описание ситуации.",
                colour=color
            )
            await mychannel.send(embed=embed)
            return (mychannel)

        msg = "Если вы видете это. Вы что-то сломали"
        if type == "reg":
            msg = "Это начало регистрации! Ожидайте пока Вам ответит сотрудник банка"
        if type == "alm":
            msg = "Вы хотите пополнить ваш IBM счет - алмазами? Дождитесь ответа тех. поддержки"
        if type == "pkr":
            msg = "Вы хотите получить кредит? Дождитесь ответа тех. поддержки"
        if type == "hbk":
            msg = "Вам нужна помощь по банку? Можете задать Ваш вопрос в этом чате. Свободный сотрудник тех.поддержки ответит как только освободиться!"
        if type == "hsl":
            msg = "Вам нужна помощь по IMB SALE? Можете задать Ваш вопрос в этом чате. Свободный сотрудник тех.поддержки ответит как только освободиться!"
        if type == "nks":
            msg = "Вам нужна помощь по накопительному счету? Можете задать Ваш вопрос в этом чате. Свободный сотрудник тех.поддержки ответит как только освободиться!"
        chn = await guild.create_text_channel(f"{type}-{record[0]}", category=ticketcategori)
        await chn.set_permissions(owner, read_messages=True)

        color = discord.Colour.from_rgb(0, 102, 102)
        embed = discord.Embed(
            title="Тиккет",
            description=f"{owner.mention} {msg}",
            colour=color
        )

        await chn.send(embed=embed)
        return chn

    async def delete(self, channel, interval, delta):
        async def lol():
            await channel.delete()

        if not self.check:
            return False
        date_now = datetime.now()
        scheduler = AsyncIOScheduler()
        if interval == 0:
            await channel.delete()
        if delta == "s":
            time = date_now + timedelta(seconds=interval)
            scheduler.add_job(lol, trigger='cron', second=time.second)
        if delta == "m":
            time = date_now + timedelta(minutes=interval)
            scheduler.add_job(lol, trigger='cron', minute=time.minute, second=time.second)
        else:
            await channel.delete()
        return True


class IItem:
    def __init__(self, ItemId: int):
        cur = con.cursor()
        cur.execute(f"SELECT id, shop, name, description, price, amount FROM itemstore WHERE id = {ItemId}")
        record = cur.fetchone()
        cur.close()
        if record is None:
            self.check = False
            return
        self.check = True
        self.id = record[0]
        self.shop = IShop(record[1])
        self.name = record[2]
        self.description = record[3]
        self.price = record[4]
        self.amount = record[5]


async def searh_item(item_name):
    cur = con.cursor()
    cur.execute(f"SELECT id, shop, name, description, price, amount FROM itemstore WHERE name LIKE '%{item_name}%'")
    record = cur.fetchall()
    cur.close()
    return record


async def reply(ctx, redgreen, head, text):
    if text in messages:
        text = messages[text]

    if redgreen:
        color = discord.Colour.from_rgb(51, 153, 102)
    else:
        color = discord.Colour.from_rgb(255, 102, 102)
    embed = discord.Embed(
        title=head,
        description=text,
        colour=color
    )
    await ctx.reply(embed=embed)
    return


async def moneylog(sender, getter, text, money):
    guild = bot.get_guild(settings['guild'])
    channel = guild.get_channel(settings['moneylogch'])
    text = messages[text]
    text = f"{sender}, {text} ``{money} alm`` {getter}"
    color = discord.Colour.from_rgb(51, 153, 102)
    embed = discord.Embed(
        title="Транзакция",
        description=text,
        colour=color
    )
    await channel.send(embed=embed)


async def depositdb():
    print("depositdb start", datetime.now())
    cur = con.cursor()
    cur.execute("SELECT id, card, money, deposit_Box, deposit_money, discordId FROM user WHERE deposit_box != 0")
    record = cur.fetchall()
    cur.close()
    if len(record) == 0:
        return

    cardlist = {
        'Обычная': 0,
        'Универсальная': 5 / 4,
        'Золотая': 5 / 4,
        'Платиновая': 7 / 4
    }

    for i in record:
        id = i[0]
        card = i[1]
        money = i[2]
        depositBox = i[3]
        depositMoney = i[4]
        discordId = i[5]

        percent = cardlist[card]
        percentmoney = round(money / 100 * percent)
        newDepositMoney = depositMoney + percentmoney

        if newDepositMoney >= 1728 * depositBox:
            user = bot.get_user(discordId)
            await user.send("У вас заполнились ячейки. Купите новые!")
            return
        cur = con.cursor()
        cur.execute(f"UPDATE user SET deposit_money = {newDepositMoney} WHERE id = {id}")
        con.commit()
        cur.close()


@bot.remove_command('help')  # удаляем команду help

@slash.slash_command(  # обход
    description='[owner] react',
    options=[
        Option("type", description="type", type=OptionType.STRING, required=True)
    ])
async def react(ctx, types: str):
    client = IClient(ctx.author.id)
    if client.role != 'owner':
        await ctx.send(f"У вас недостаточно прав для рассмотрения запроса")
        return
    if types == "reg":
        message = settings['eregmsg']
        reaction_list = ["✅"]
    elif types == "tp":
        message = settings['emhelpmsg']
        reaction_list = ["💶", "💳", "🏦", "🛍️", "🛸"]
    else:
        return
    message = await ctx.channel.fetch_message(message)
    for i in reaction_list:
        await message.add_reaction(i)


@slash.slash_command(  # обход
    description='[owner] выдать роль',
    options=[
        Option("opponent", description="пользователь", type=OptionType.USER, required=True),
        Option("role", description="роль", type=OptionType.STRING, required=True)
    ])
async def role(ctx, opponent: discord.Member, role: str):
    member = ctx.author
    client = IClient(member.id)
    client_op = IClient(opponent.id)
    rolelist = ['owner', "admin", "tp", "user", "ban"]
    if client.status != 'owner':
        await reply(ctx, False, "Выдача роли", "notowner")
        return
    if not client_op.check:
        await reply(ctx, False, "Выдача роли", f"{opponent.mention} не является клиентом банка")
        return
    if role not in rolelist:
        await reply(ctx, False, "Выдача роли", f"Вы указали неверную роль. Укажите роль из списка: {rolelist}")
        return
    await reply(ctx, True, "Выдача роли", f"Вы установили роль ``{role}`` для {opponent.mention}")
    client_op.setrole(role)


@slash.slash_command(
    description='[A] установить карту',
    options=[
        Option("opponent", description="пользователь", type=OptionType.USER, required=True),
        Option("card", description="роль", type=OptionType.ROLE, required=True)
    ])
async def card(ctx, opponent: discord.Member, card: discord.Role):
    member = ctx.author
    client = IClient(member.id)
    client_op = IClient(opponent.id)
    if client.status not in ('admin', 'owner'):
        await reply(ctx, False, "Установка карты", "notrights")
        return
    check = await client_op.setcard(card)
    if not check:
        await reply(ctx, False, "Установка карты", "notcard")
        return
    await reply(ctx, True, "Установка карты", "successfully")


@slash.slash_command(
    description='отправить деньги',
    options=[
        Option("opponent", description="пользователь", type=OptionType.USER, required=True),
        Option("money", description="кол-во alm", type=OptionType.INTEGER, required=True),
    ])
async def givemoney(ctx, opponent: discord.Member, money: int):  # Создаём функцию и передаём аргумент ctx.
    member = ctx.author
    client = IClient(member.id)
    client_op = IClient(opponent.id)
    if opponent == member:
        await reply(ctx, False, "Отправить алмазы", "error")
        return

    if not client.check or not client_op.check:
        await reply(ctx, False, "Отправить алмазы", "notclient")
        return

    if client.money < money or money <= 0:
        await reply(ctx, False, "Отправить алмазы", "notmoney")
        return
    client.setmoney(client.money - money)
    client_op.setmoney(client_op.money + money)
    await reply(ctx, True, "Отправить алмазы", f"Вы перевели {opponent.mention} - ``{money} алм.``")
    await moneylog(member, opponent, 'sendmoney', money)


@slash.slash_command(
    description='[A] Отправить деньги',
    options=[
        Option("opponent", description="ник на сервере", type=OptionType.STRING, required=True),
        Option("money", description="кол-во alm", type=OptionType.INTEGER, required=True),
    ])
async def sgivemoney(ctx, opponent, money: int):  # Создаём функцию и передаём аргумент ctx.
    guild = bot.get_guild(settings['guild'])
    opponent = discord.utils.get(guild.members, name=opponent)
    member = ctx.author
    client = IClient(member.id)
    client_op = IClient(opponent.id)
    if opponent == member:
        await reply(ctx, False, "Скрытый перевод", "error")
        return

    if not client.check or not client_op.check:
        await reply(ctx, False, "Скрытый перевод", "notclient")
        return

    if client.money < money or money <= 0:
        await reply(ctx, False, "Скрытый перевод", "notmoney")
        return
    client.setmoney(client.money - money)
    client_op.setmoney(client_op.money + money)
    await reply(ctx, True, "Скрытый перевод", f"Вы перевели {opponent.mention} - ``{money} алм.``")
    await moneylog(member, opponent, 'sendmoney', money)


@slash.slash_command(
    description='[owner] установить деньги',
    options=[
        Option("opponent", description="пользователь", type=OptionType.USER, required=True),
        Option("money", description="кол-во alm", type=OptionType.INTEGER, required=True),
    ])
async def setmoney(ctx, opponent: discord.Member, money: int):
    member = ctx.author
    client = IClient(member.id)
    client_op = IClient(opponent.id)
    if not client.check or not client_op.check:
        await reply(ctx, False, "Скрытый перевод", "notclient")
        return
    if client.status != 'owner':
        await reply(ctx, False, "Установка денег", "notowner")
        return
    client_op.setmoney(money)
    await reply(ctx, True, "Установка денег", "successfully")
    await moneylog(member, opponent, 'setmoney', money)


@slash.slash_command(
    description='[A] добавить деньги',
    options=[
        Option("opponent", description="пользователь", type=OptionType.USER, required=True),
        Option("money", description="кол-во alm", type=OptionType.INTEGER, required=True),
    ])
async def addmoney(ctx, opponent: discord.Member, money: int):
    member = ctx.author
    client = IClient(member.id)
    client_op = IClient(opponent.id)

    if not client.check or not client_op.check:
        await reply(ctx, False, "Добавить денег", "notclient")
        return
    if client.status == 'tp':
        channel = await IChannel.create('bid', member.id, money, opponent.id)
        await member.send(f"Был создан запрос ``{channel}`` на изменение счета пользователя ``{opponent}``")
        embed = discord.Embed(
            title="Создано автоматически",
            description=f"{member.mention} хочет пополнить счет пользователя ``{opponent}`` в размере ``{money} alm``",
            colour=discord.Colour.from_rgb(0, 102, 102)
        )
        await channel.send(embed=embed)
        return
    if client.status not in ('admin', 'owner'):
        await reply(ctx, False, "Добавить денег", "notclient")
        return

    client_op.setmoney(client_op.money + money)
    await reply(ctx, True, "Добавить денег",
                f"Вы дали ``{money} alm`` для ``{opponent}``, теперь его счет составляет ``{client_op.money} alm``")
    await moneylog(member, opponent, 'addmoney', money)


@slash.slash_command(
    description='[A] убрать деньги',
    options=[
        Option("opponent", description="пользователь", type=OptionType.USER, required=True),
        Option("money", description="кол-во alm", type=OptionType.INTEGER, required=True),
    ])
async def removemoney(ctx, opponent: discord.Member, money: int):
    member = ctx.author
    client = IClient(member.id)
    client_op = IClient(opponent.id)

    if not client.check or not client_op.check:
        await reply(ctx, False, "Забрать денеги", "notclient")
        return
    if client.status == 'tp':
        channel = await IChannel.create('bid', member.id, money * -1, opponent.id)
        await member.send(f"Был создан запрос ``{channel}`` на изменение счета пользователя ``{opponent}``")
        embed = discord.Embed(
            title="Создано автоматически",
            description=f"{member.mention} хочет снять деньги с пользователя ``{opponent}`` в размере ``{money} alm``",
            colour=discord.Colour.from_rgb(0, 102, 102)
        )
        await channel.send(embed=embed)
        return
    if client.status not in ('admin', 'owner'):
        await reply(ctx, False, "Забрать денеги", "notclient")
        return

    client_op.setmoney(client_op.money - money)
    await reply(ctx, True, "Забрать денеги",
                f"Вы забрали ``{money} alm`` у ``{opponent}``, теперь его счет составляет ``{client_op.money} alm``")
    await moneylog(member, opponent, 'removemoney', money)


@slash.slash_command(description='Посмотреть профиль')
async def info(ctx):
    member = ctx.author
    client = IClient(member.id)
    if not client.check:
        await reply(ctx, False, "Информация", "notrights")
        return
    embed = discord.Embed(colour=discord.Colour.from_rgb(204, 255, 0), title=f"Профиль {member}",
                          description=f"ID: {client.id} | Майнкрафт ник: {client.nick}")
    embed.set_footer(text=f"{datetime.now()}")
    embed.set_thumbnail(url=member.avatar_url)
    embed.add_field(name="Алмазы:", value=f"{client.money}")
    embed.add_field(name="Ячейки накопительного счета:", value=f"{client.deposit_box}")
    embed.add_field(name="Деньги на накопительном счету", value=f"{client.deposit_money}")
    await ctx.reply(embed=embed)


@slash.slash_command(
    description='[A] просмотр профиля',
    options=[
        Option("opponent", description="пользователь", type=OptionType.USER, required=True)
    ])
async def ainfo(ctx, opponent: discord.Member):
    member = ctx.author
    client = IClient(member.id)
    client_op = IClient(opponent.id)

    if not client_op.check or not client.check:
        await reply(ctx, False, "AINFO", "error")
        return

    if client.status not in {"tp", "admin", "owner"}:
        await ctx.reply(f"У вас недостаточно прав")
        return

    now = datetime.now()
    now = now.strftime("%m/%d/%Y, %H:%M:%S")
    embed = discord.Embed(colour=discord.Colour.from_rgb(204, 255, 0), title=f"Профиль {opponent}",
                          description=f"ID: {client_op.id} | Майнкрафт ник: {client_op.nick}")
    embed.set_footer(text=f"{now} - ainfo запрос {member}")
    embed.set_thumbnail(url=opponent.avatar_url)
    embed.add_field(name="Алмазы:", value=f"{client_op.money}")
    embed.add_field(name="Ячейки накопительного счета:", value=f"{client_op.deposit_box}")
    embed.add_field(name="Деньги на накопительном счету:", value=f"{client_op.deposit_money}")
    embed.add_field(name="Карта:", value=f"{client_op.card}")
    embed.add_field(name="Роль:", value=f"{client_op.status}")
    embed.add_field(name="Дата регистрации:", value=f"{client_op.register_date}")
    await ctx.reply(embed=embed)


@slash.slash_command(
    description='Купить ячейку накопительного счета',
)
async def deposit_buy(ctx):
    member = ctx.author
    client = IClient(member.id)
    if not client.check:
        await reply(ctx, False, "Покупка ячейки", "notclient")
        return
    usermoney = client.money
    depositbox = client.deposit_box
    card = client.card

    if card == 'Универсальная':
        price = 45
    elif card == 'Золотая':
        price = 90
    else:
        price = 288
    print(usermoney)
    print(price)
    if usermoney < price:
        await reply(ctx, False, "Покупка ячейки", "notmoney")
        return

    client.setmoney(usermoney - price)
    client.deposit_add()
    await reply(ctx, True, "Покупка ячейки", "depositbuy")


@slash.slash_command(
    description='Собрать деньги с накопительного счета',
)
async def deposit_collect(ctx):
    member = ctx.author
    client = IClient(member.id)
    if not client.check:
        await reply(ctx, False, "Ячейка", "notclient")
        return
    if client.deposit_money <= 0:
        await reply(ctx, False, "Ячейка", "depositnotmoney")
        return
    client.setmoney(client.money + client.deposit_money)
    client.deposit_collect()
    await reply(ctx, True, "Ячейка", "depositcollect")


@slash.slash_command(
    description='[A] зарегистрировать клиента',
    options=[
        Option("opponent", description="пользователь", type=OptionType.USER, required=True),
        Option("minecraftnick", description="майнкрафт ник", type=OptionType.STRING, required=True),
        Option("card", description="карта", type=OptionType.ROLE, required=True),
        Option("depositbox", description="количество ячеек", type=OptionType.INTEGER, required=True),
        Option("money", description="кол-во alm", type=OptionType.INTEGER, required=True),
    ])
async def reg(ctx, opponent: discord.Member, minecraftnick: str, card: discord.Role, depositbox: int, money: int):
    member = ctx.author
    guild = bot.get_guild(settings['guild'])
    client = IClient(member.id)
    client_op = IClient(opponent.id)
    channel_name = str(ctx.channel)
    channel_name = channel_name.rpartition("-")
    channel = IChannel(channel_name[2])
    if channel.type != "reg":
        await reply(ctx, False, "Регистрация", "notregch")
        return
    if channel.ownerId != opponent.id:
        await reply(ctx, False, 'Регистрация', 'reg_not_owner')
        return
    if client.status not in ('tp', 'admin', 'owner'):
        await reply(ctx, False, 'Регистрация', 'notrights')
    if client_op.check:
        await reply(ctx, False, 'Регистрация', 'regclose2')
        return

    cur = con.cursor()
    cur.execute(
        f"INSERT INTO user(discordId, minecraftNick, card, deposit_Box, money, dateRegister, status) VALUES({opponent.id}, '{minecraftnick}', 'Обычная', {depositbox}, {money}, '{datetime.now().date()}', 'user')")
    con.commit()
    cur.close()

    client_op = IClient(opponent.id)
    await reply(ctx, True, "Регистрация", "regclose")
    try:
        await client_op.setcard(int(card))
        await reply(ctx, True, 'Регистрация', 'regsetcard')
    except:
        await reply(ctx,False, 'Регистрация', 'regnotcard')
    await reply(ctx, True, "Регистрация", "close2m")
    await channel.delete(ctx.channel, 2, 'm')
    role = settings['clientrole']
    role = guild.get_role(role)
    await opponent.add_roles(role)


@slash.slash_command(
    description='[owner] офлайн регистрация',
    options=[
        Option("opponent", description="пользователь", type=OptionType.USER, required=True),
        Option("minecraftnick", description="майнкрафт ник", type=OptionType.STRING, required=True),
    ])
async def offline_reg(ctx, opponent: discord.Member, minecraftnick: str):
    member = ctx.author
    client = IClient(member.id)
    client_op = IClient(opponent.id)

    if client.status != 'owner':
        await reply(ctx, False, "Регистрация", "notowner")
        return
    if client_op.check:
        await reply(ctx, False, "Регистрация", "regclose2")
        return
    cur = con.cursor()
    cur.execute(
        f"INSERT INTO user(discordId, minecraftNick, card, deposit_Box, money, dateRegister, status) VALUES({opponent.id}, '{minecraftnick}', 'Обычная', 0, 0, '{datetime.now().date()}', 'user')")
    con.commit()
    cur.close()
    await reply(ctx, True, "Регистрация", "reg_offline")



@slash.slash_command(
    description='[A] открыть запрос',
)
async def bid(ctx):
    member = ctx.author
    client = IClient(member.id)
    if client.status not in ('tp', 'admin', 'owner'):
        await reply(ctx, False, "Открытие запроса", "notrights")
        return
    await reply(ctx, True, "Открытие запроса", "successfully")
    await IChannel.create('bid', member.id)


@slash.slash_command(
    description='[A] одобрить запрос',
)
async def accept(ctx):
    channelName = str(ctx.channel)
    channelName = channelName.rpartition("-")

    ch = IChannel(channelName[2])
    await ch.close(ctx.author.id, True)
    await ch.delete(ctx.channel, 15, "s")


@slash.slash_command(
    description='[A] отклонить запрос',
)
async def deny(ctx):
    channelName = str(ctx.channel)
    channelName = channelName.rpartition("-")

    ch = IChannel(channelName[2])
    await ch.close(ctx.author.id, False)
    await ch.delete(ctx.channel, 15, "s")


@slash.slash_command(
    description='[A] закрыть тиккет',
)
async def close(ctx):
    channelName = str(ctx.channel)
    channelName = channelName.rpartition("-")
    if channelName[2] != 'bid':
        await reply(ctx, True, 'Close', 'eror')
    ch = IChannel(channelName[2])
    await ch.close(ctx.author.id)
    await ch.delete(ctx.channel, 15, "s")


@slash.slash_command(
    description='[owner] написать от именни бота',
    options=[
        Option("message", description="тут текст который отправит бот", type=OptionType.STRING, required=True)
    ])
async def say(ctx, message):
    member = ctx.author
    client = IClient(member.id)
    if client.status != 'owner':
        await reply(ctx, False, "say", "notrights")
        return
    await ctx.channel.send(message)


# shop command

# @slash.slash_command(
#     description = 'Купить магазин',
#     options = [
#         Option("shop_name", description = "Название магазина", type=OptionType.STRING, required=True)
#     ])
# async def shop_by(ctx, shop_name):
#     member = ctx.author
#     client = IClient(member.id)
#     shop = IShop(-1)
#
#     if client.salesman:
#         await reply(ctx, False,'Покупка лавки', 'shop_there')
#         return
#
#     if not client.check:
#         await reply(ctx, False, 'Покупка лавки', 'notclient')
#
#     shop_price = shop_card_price[client.card]
#     if client.money < shop_price:
#         await reply(ctx, False, 'Покупка лавки', 'notmoney')
#         return
#
#     await moneylog(member,'IBM SALE', 'shop_by', shop_price )
#     await reply(ctx, True, 'Покупка лавки', 'shop_register')
#     client.setmoney(client.money - shop_price)
#     shop.register(shop_name, client.id)
#
#
# @slash.slash_command(
#     description = 'Посмотреть свой или чужой магазин',
#     options = [
#         Option("shop_id", description = "ID магазина (необязательно)", type=OptionType.STRING, required=False)
#     ])
# async def shop(ctx, shop_id=-1):
#     member = ctx.author
#     client = IClient(member.id)
#     if shop_id == -1:
#         if client.salesman:
#             shop = IShop(-1, client.id)
#         else:
#             await reply(ctx, False, 'Просмотр магазин', 'shop_nothing')
#             return
#     else:
#         shop = IShop(shop_id)
#         if not shop.check:
#             await reply(ctx, False, 'Просмотр магазин', 'shop_not')
#             return
#
#     embed = discord.Embed(colour=discord.Colour.from_rgb(204, 255, 0), title=f'Магазин: "{shop.name}"',
#                           description=f"ID: {shop.id} | Владелец: {shop.owner_discord} / {shop.owner_name}")
#     embed.set_footer(text=f"{datetime.now()}")
#     embed.set_thumbnail(url=shop.owner_discord.avatar_url)
#     embed.add_field(name="Рейтинг:", value=f"{shop.rating}")
#     embed.add_field(name="Товаров:", value=f"{shop.item}")
#     embed.add_field(name="Дата регистрации:", value=f"{shop.dateRegister}")
#     await ctx.reply(embed=embed)
#
#
# @slash.slash_command(
#     description = '[seller] добавить товар в магазин',
#     options = [
#         Option("product", description = "Название товара", type=OptionType.STRING, required=True),
#         Option("price", description = "Цена товара", type=OptionType.INTEGER, required=True),
#         Option("amount", description = "Кол-во товара (штучно)", type=OptionType.INTEGER, required=True),
#         Option("description", description = "Описание товара", type=OptionType.STRING, required=True)
#     ])
# async def shop_add_item(ctx, product, price, amount, description):
#     member = ctx.author
#     client = IClient(member.id)
#
#     if not client.check:
#         await reply(ctx, False, 'Покупка лавки', 'notclient')
#     if price <= 0 or amount <= 0:
#         await reply(ctx, False, 'Добавить товар в магазин', 'shop_error1')
#         return
#     if not client.salesman:
#         await reply(ctx, False, 'Добавить товар в магазин', 'shop_nothing')
#         return
#
#     shop = IShop(-1, member.id)
#     shop.add_item(product, price, amount, description)
#     await reply(ctx, True, 'Добавить товар в магазин', 'item_add')
#
#
# @slash.slash_command(
#     description = 'Найти товар в IBM SALE',
#     options = [
#         Option("product", description = "Название товара", type=OptionType.STRING, required=True),
#     ])
# async def search(ctx, product):
#     items = await searh_item(product) #id, shop, name, description, price, amount
#     member = ctx.author
#     client = IClient(member.id)
#
#     if not client.check:
#         await reply(ctx, False, 'Покупка лавки', 'notclient')
#     if len(items) == 0:
#         await reply(ctx, False, 'IBM SEARCH', 'items_not_found')
#         return
#
#     embed = discord.Embed(colour=discord.Colour.from_rgb(204, 255, 0), title='IBM SEARCH', description=f"Поиск по предмету: {product}")
#     embed.set_footer(text=f"Найдено товаров: {len(items)}")
#     options = []
#     for i in items:
#         item_id = i[0]
#         shop = IShop(i[1])
#         item_name = i[2]
#         item_description = i[3]
#         item_price = i[4]
#         item_amount = i[5]
#         embed.add_field(name=f"ID: {item_id} | Название: {item_name}\n{shop.name}", value=f"Цена: {item_price}\nКоличество: {item_amount}\nОписание: {item_description}")
#         options.append(SelectOption(f"Купить товар с ID {item_id}", f"{item_id}"),)
#     await ctx.reply(
#         embed=embed,
#         components=[
#             SelectMenu(
#                 custom_id="test",
#                 placeholder="Выберите товар",
#                 options=options
#             )
#         ]
#     )
#
#
# @slash.slash_command(
#     description = 'Купить товар в IBM SALE',
#     options = [
#         Option("product_id", description = "id товара", type=OptionType.INTEGER, required=True),
#     ])
# async def buy(ctx, product_id):
#     member = ctx.author
#     client = IClient(member.id)
#
#     if not client.check:
#         await reply(ctx, False, 'Покупка лавки', 'notclient')
#     item = IItem(product_id)
#     if not item.check:
#         await reply(ctx, False, 'Покупка товара', 'item_not_found')
#
#     row = ActionRow(
#         Button(
#             style=ButtonStyle.green,
#             label="Да",
#             custom_id="test_button"
#         ),
#         Button(
#             style=ButtonStyle.red,
#             label="Нет",
#             custom_id="test_button2"
#         )
#     )
#     embed = discord.Embed(colour=discord.Colour.from_rgb(0, 0, 0), title='IBM SALE', description=f"Товар: {item.name}")
#     embed.add_field(name=f"ID: {item.id}\nМагазин: {item.shop.name}", value=f"Цена: {item.price}\nКоличество: {item.amount}\nОписание: {item.description}")
#     await ctx.reply('Вы точно хотите купить этот товар?', embed=embed, components=[row])


# events
@bot.event
async def on_raw_reaction_add(reaction):
    member = reaction.member
    memberObj = bot.get_user(member.id)
    channel = bot.get_channel(reaction.channel_id)
    message = await channel.fetch_message(reaction.message_id)
    user = bot.get_user(reaction.user_id)
    if reaction.message_id == settings['eregmsg']:  # проверка для канала регистрации
        await message.remove_reaction(reaction.emoji, user)
        client = IClient(member.id)
        if client.check:
            return
        cur = con.cursor()
        cur.execute(f"SELECT ticketId FROM tickets WHERE ownerId = {member.id} AND type = 'reg'")
        record = cur.fetchall()
        cur.close()
        if len(record) != 0:
            await memberObj.send(
                f"Вы уже создавали запрос на регистрацию #reg-{record[0][0]} если вы этого не делали - отправьте это сообщение любому администратору или обратитесь в тех.поддержку")
            return
        await IChannel.create('reg', member.id)
        return
    if reaction.message_id == settings['emhelpmsg']:  # проверка для канала тех-поддержка
        await message.remove_reaction(reaction.emoji, user)
        emoji = str(reaction.emoji)
        if emoji == "💶":  # пополнение счета
            await IChannel.create('alm', member.id)
            return
        elif emoji == "💳":  # получение кредита
            await IChannel.create('pkr', member.id)
            return
        elif emoji == "🏦":  # помощь по банку
            await IChannel.create('hbk', member.id)
            return
        elif emoji == "🛍️":  # помощь по IMB SALE
            await IChannel.create('hsl', member.id)
            return
        elif emoji == "💰":  # снять деньги с накопительного счета
            await IChannel.create('nks', member.id)
            return
        elif emoji == "<a:2365peepocookie:919878291442266112>":  # Почему IBM group - не перамида?
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
    print(f"{datetime.now()} Bot ready")
    scheduler = AsyncIOScheduler(timezone="Europe/Moscow")
    scheduler.add_job(depositdb, trigger='cron', day_of_week='sun', hour=0, minute=1)
    scheduler.start()


print(f"{datetime.now()} BOT START")
bot.run(settings['token'])  # берем токен из конфига и стартуем
