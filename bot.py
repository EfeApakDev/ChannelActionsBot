# @ChannelActionsBot
# (c) @xditya.

import contextlib
import re
import logging

from aioredis import Redis
from decouple import config
from telethon import TelegramClient, events, Button, types, functions, errors

logging.basicConfig(
    level=logging.INFO, format="[%(levelname)s] %(asctime)s - %(message)s"
)
log = logging.getLogger("ChannelActions")
log.info("\n\nStarting...\n")


try:
    bot_token = config("BOT_TOKEN")
    REDIS_URI = config("REDIS_URI")
    REDIS_PASSWORD = config("REDIS_PASSWORD")
    AUTH = [int(i) for i in config("OWNERS").split(" ")]
except Exception as e:
    log.exception(e)
    exit(1)

# connecting the client
try:
    bot = TelegramClient(None, 6, "eb06d4abfb49dc3eeb1aeb98ae0f581e").start(
        bot_token=bot_token
    )
except Exception as e:
    log.exception(e)
    exit(1)

REDIS_URI = REDIS_URI.split(":")
db = Redis(
    host=REDIS_URI[0],
    port=REDIS_URI[1],
    password=REDIS_PASSWORD,
    decode_responses=True,
)

# users to db
def str_to_list(text):  # Returns List
    return text.split(" ")


def list_to_str(list):  # Returns String  # sourcery skip: avoid-builtin-shadow
    str = "".join(f"{x} " for x in list)
    return str.strip()


async def is_added(var, id):  # Take int or str with numbers only , Returns Boolean
    if not str(id).isdigit():
        return False
    users = await get_all(var)
    return str(id) in users


async def add_to_db(var, id):  # Take int or str with numbers only , Returns Boolean
    # sourcery skip: avoid-builtin-shadow
    id = str(id)
    if not id.isdigit():
        return False
    try:
        users = await get_all(var)
        users.append(id)
        await db.set(var, list_to_str(users))
        return True
    except Exception as e:
        return False


async def get_all(var):  # Returns List
    users = await db.get(var)
    return [""] if users is None or users == "" else str_to_list(users)


async def get_me():
    me = await bot.get_me()
    myname = me.username
    return f"@{myname}"


bot_username = bot.loop.run_until_complete(get_me())
start_msg = """Merhaba {user}!

**Ben Kanal İstek Onay Botuyum, esas olarak yeni istekleri onaylamaya odaklanan bir botum [yönetici onayı davet bağlantıları](https://t.me/telegram/153).**

**__Bunları Yapabilirim __**:
- __Yeni katılma isteklerini otomatik olarak onaylamak.__
- __Yeni Katılma İsteklerini Otomatik Reddet.__

`Beni nasıl kullanacağınızı öğrenmek için aşağıdaki butona tıklayın!`"""
start_buttons = [
    [Button.inline("beni nasıl kullanabilirsin❓", data="helper")],
    [Button.url("İLETİŞİM ", "https://t.me/sosyox")],
]


@bot.on(events.NewMessage(incoming=True, pattern=f"^/start({bot_username})?$"))
async def starters(event):
    from_ = await bot.get_entity(event.sender_id)
    await event.reply(
        start_msg.format(user=from_.first_name),
        buttons=start_buttons,
        link_preview=False,
    )
    if not (await is_added("BOTUSERS", event.sender_id)):
        await add_to_db("BOTUSERS", event.sender_id)


@bot.on(events.CallbackQuery(data="start"))
async def start_in(event):
    from_ = await bot.get_entity(event.sender_id)
    with contextlib.suppress(errors.rpcerrorlist.MessageNotModifiedError):
        await event.edit(
            start_msg.format(user=from_.first_name),
            buttons=start_buttons,
            link_preview=False,
        )


@bot.on(events.CallbackQuery(data="helper"))
async def helper(event):
    await event.edit(
        '**Kullanım talimatları.**\n\n"YÖNETİCİ OLARAK " izniyle yönetici olarak beni kanalınıza ekleyin ve beni ayarlamak için o sohbetten bana bir mesaj iletin!\n\n@Sosyox.',
        buttons=Button.inline("ANA MENÜ 📭", data="start"),
    )


@bot.on(events.NewMessage(incoming=True, func=lambda e: e.is_private and e.fwd_from))
async def settings_selctor(event):  # sourcery skip: avoid-builtin-shadow
    id = event.fwd_from.from_id
    if not isinstance(id, types.PeerChannel):
        await event.reply("Bu bir kanaldan değil gibi görünüyor!")
        return
    try:
        chat = await bot.get_entity(id)
        if chat.admin_rights is None:
            await event.reply("Bu kanalda admin değilim gibi görünüyor!")
            return
    except ValueError:
        await event.reply("Anlaşılan beni kanalına eklememişsin!")
        return

    # check if the guy trying to change settings is an admin

    try:
        who_u = (
            await bot(
                functions.channels.GetParticipantRequest(
                    channel=chat.id,
                    participant=event.sender_id,
                )
            )
        ).participant
    except errors.rpcerrorlist.UserNotParticipantError:
        await event.reply(
            "Bu eylemi gerçekleştirmek için kanalda veya yönetici değilsiniz."
        )
        return
    if not (
        isinstance(
            who_u, (types.ChannelParticipantCreator, types.ChannelParticipantAdmin)
        )
    ):
        await event.reply(
            "Bu kanalın yöneticisi değilsiniz ve ayarlarını değiştiremezsiniz!"
        )
        return

    added_chats = await db.get("CHAT_SETTINGS") or "{}"
    added_chats = eval(added_chats)
    welcome_msg = eval(await db.get("WELCOME_MSG") or "{}")
    is_modded = bool(welcome_msg.get(chat.id))
    setting = added_chats.get(str(chat.id)) or "Auto-Approve"
    await event.reply(
        "**Ayarlar  {title}**\n\n__Yeni katılma isteklerinde ne yapacağınızı seçin:__\n**Şimdiki ayar ** - __{set}__\n\n__Karşılama mesajınızı ayarlayın:__\nŞu anda değiştirilmiş: {is_modded}".format(
            title=chat.title, set=setting, is_modded=is_modded
        ),
        buttons=[
            [Button.inline("Otomatik Onay ", data=f"set_ap_{chat.id}")],
            [Button.inline("Otomatik onaylama ", data=f"set_disap_{chat.id}")],
            [Button.inline("Karşılama mesajı ayarla ", data=f"mod_{chat.id}")],
        ],
    )


@bot.on(events.CallbackQuery(data=re.compile("set_(.*)")))
async def settings(event):
    args = event.pattern_match.group(1).decode("utf-8")
    setting, chat = args.split("_")
    added_chats = await db.get("CHAT_SETTINGS") or "{}"
    added_chats = eval(added_chats)
    if setting == "ap":
        op = "Otomatik Onay"
        added_chats.update({chat: op})
    elif setting == "disap":
        op = "Otomatik Onaylama"
        added_chats.update({chat: op})
    await db.set("CHAT_SETTINGS", str(added_chats))
    await event.edit(
        f"Ayarlar güncellendi! Kanal id 👉 `{chat}`  {op}d!"
    )


@bot.on(events.CallbackQuery(data=re.compile("mod_(.*)")))
async def mod_welcome(event):
    args = int(event.pattern_match.group(1).decode("utf-8"))
    welcome_msg = eval(await db.get("WELCOME_MSG") or "{}")
    await event.delete()
    async with bot.conversation(event.sender_id) as conv:
        await conv.send_message(
            "Kanalınıza kabul edildiğinde bir kullanıcıya gönderilmesini istediğiniz yeni karşılama mesajını gönderin.\nKullanılabilir biçimlendirmeler :\n- {name} - Kullanıcı adı. \n- {chat} - Sohbet başlığı .",
            buttons=Button.force_reply(),
        )
        msg = await conv.get_reply()
        if not msg.text:
            await event.reply("Yalnızca bir metin mesajı ayarlayabilirsiniz!")
            return
        msg = msg.text
        welcome_msg.update({args: msg})
        await db.set("WELCOME_MSG", str(welcome_msg))
        chat = await bot.get_entity(args)
        await conv.send_message(
            f"üyeler için hoş geldiniz mesajı {chat.title} Başarıyla Ayarlandı !"
        )


@bot.on(events.Raw(types.UpdateBotChatInviteRequester))
async def approver(event):
    chat = event.peer.channel_id
    chat_settings = await db.get("CHAT_SETTINGS") or "{}"
    chat_settings = eval(chat_settings)
    welcome_msg = eval(await db.get("WELCOME_MSG") or "{}")
    chat_welcome = (
        welcome_msg.get(chat)
        or "Merhaba {name},  katılma isteğiniz başarılı {chat}   {dn}"
    )
    chat_welcome += "\n /start yazarak daha fazlasını öğrenebilirsiniz ."  # \n\n__** Developer 🇹🇷 @SancakBegi**__"
    who = await bot.get_entity(event.user_id)
    chat_ = await bot.get_entity(chat)
    dn = "approved!"
    appr = True
    if chat_settings.get(str(chat)) == "Otomatik onayla ":
        appr = True
        dn = "approved!"
    elif chat_settings.get(str(chat)) == "Otomatik Onaylama":
        appr = False
        dn = "disapproved :("
    with contextlib.suppress(
        errors.rpcerrorlist.UserIsBlockedError, errors.rpcerrorlist.PeerIdInvalidError
    ):
        await bot.send_message(
            event.user_id,
            chat_welcome.format(name=who.first_name, chat=chat_.title, dn=dn),
            buttons=Button.url("İletişim", url="https://t.me/sosyox"),
        )
    with contextlib.suppress(errors.rpcerrorlist.UserAlreadyParticipantError):
        await bot(
            functions.messages.HideChatJoinRequestRequest(
                approved=appr, peer=chat, user_id=event.user_id
            )
        )


@bot.on(events.NewMessage(incoming=True, from_users=AUTH, pattern="^/panel$"))
async def auth_(event):
    xx = await event.reply("Calculating...")
    t = await db.get("CHAT_SETTINGS") or "{}"
    t = eval(t)
    await xx.edit(
        "**Sosyox Istek Onaylayıcı Bot İstatistikleri**\n\nKullanıcılar : {}\nGruplar eklendi  (değiştirilmiş ayarlarla): {}".format(
            len(await get_all("BOTUSERS")), len(t.keys())
        )
    )


@bot.on(events.NewMessage(incoming=True, from_users=AUTH, pattern="^/broadcast$"))
async def broad(e):
    if not e.reply_to_msg_id:
        return await e.reply(
            "lütfen bize  `/broadcast` yayınlamak istediğiniz mesaja cevap olarak."
        )
    msg = await e.get_reply_message()
    xx = await e.reply("In progress...")
    users = await get_all("BOTUSERS")
    done = error = 0
    for i in users:
        try:
            await bot.send_message(
                int(i),
                msg.text,
                file=msg.media,
                buttons=msg.buttons,
                link_preview=False,
            )
            done += 1
        except Exception:
            error += 1
    await xx.edit("Yayın tamamlandı .\nbaşarı : {}\nArızalı : {}".format(done, error))


log.info("bot başlatıldı - %s", bot_username)
log.info("\n@Sosyox 🇹🇷\n\n - @SancakBegi.")

bot.run_until_disconnected()
