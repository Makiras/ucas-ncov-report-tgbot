from include import *
from peewee import SqliteDatabase
import argparse
import traceback
import sys
import datetime
import requests
from shutil import copyfile

from apscheduler.schedulers.background import BackgroundScheduler

from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, DispatcherHandlerStop
import telegram


def tguser_check(update, context):
    if BOT_DEBUG is True and update.message.from_user.id != TG_BOT_MASTER:
        update.message.reply_text("DEBUGGING, Try again later.")
        raise DispatcherHandlerStop()

    user, _ = TGUser.get_or_create(
        userid=update.message.from_user.id
    )
    now_username = update.message.from_user.username or update.message.from_user.first_name
    if user.username != now_username:
        user.username = now_username
        user.save()


def start_entry(update, context):
    """Send a message when the command /start is issued."""
    update.message.reply_text("Welcome, {}. try /help.\nSpecial Thanks to https://github.com/HenryzhaoH/bupt-ncov-report-tgbot and https://github.com/WANNA959/ucas-covid19 ".format(
        update.message.from_user.username or update.message.from_user.first_name or ''), disable_web_page_preview=True)
    help_entry(update, context)


def help_entry(update, context):
    """Send a message when the command /help is issued."""
    update.message.reply_markdown(
        HELP_MARKDOWN.strip(), disable_web_page_preview=True)


def list_entry(update, context, admin_all=False):
    first_message = update.message.reply_markdown(f"用户列表查询中 ...")
    if admin_all is True:
        users = UCASUser.select().where(
            UCASUser.status != UCASUserStatus.removed).prefetch(TGUser)
    else:
        # users = UCASUser.select().where(UCASUser.owner == update.message.from_user.id).order_by(UCASUser.id.asc())
        tguser = TGUser.get(
            userid=update.message.from_user.id
        )
        users = tguser.ucasusers.where(
            UCASUser.status != UCASUserStatus.removed)
    ret_msgs = []
    ret_msg = ''
    for i, user in enumerate(users):
        if i % 10 == 0 and i != 0:
            ret_msgs.append(ret_msg)
            ret_msg = ''
        id = i+1
        ret_msg += f'ID: `{id}`\n'
        if user.username is not None:
            # Password: `{user.password}`\n'
            ret_msg += f'Username: `{user.username}`\n'
        else:
            # UUKey: `{user.cookie_uukey}`\n'
            ret_msg += f'eai-sess: `{user.cookie_eaisess}`\n'
        if admin_all:
            ret_msg += f'Owner: `{user.owner.userid}` `{user.owner.username.replace("`","")}`\n'
        if user.status == UCASUserStatus.normal:
            ret_msg += f'自动签到: `启用`\n'
        else:
            ret_msg += f'自动签到: `暂停`\n'
        if user.latest_response_data is None:
            ret_msg += '从未尝试签到\n'
        else:
            ret_msg += f'最后签到时间: `{user.latest_response_time}`\n'
            ret_msg += f'最后签到返回: `{user.latest_response_data[:100]}`\n'

        if not admin_all:
            ret_msg += f'暂停 /pause\_{id}   恢复 /resume\_{id}\n签到 /checkin\_{id} 删除 /remove\_{id}\n'
        ret_msg += "\n"
    ret_msgs.append(ret_msg)

    if len(users) == 0:
        ret_msgs = ['用户列表为空']
    if len(users) >= 2 and not admin_all:
        ret_msgs[-1] += f'恢复全部 /resume  暂停全部 /pause\n签到全部 /checkin  删除全部 /remove\_all \n'
    logger.debug(ret_msgs)

    first_message.delete()
    for msg in ret_msgs:
        update.message.reply_markdown(msg)


def add_by_cookie_entry(update, context):
    if len(context.args) != 2:
        first_message = update.message.reply_markdown(
            f"例：/add\_by\_cookie `1cmgkrrcssge6edkkg3ucigj1m` `44f522350f5e843fbac58b726753eb36`")
        return
    eaisess = context.args[0]
    uukey = context.args[1]
    first_message = update.message.reply_markdown(f"Adding ...")

    tguser = TGUser.get(
        userid=update.message.from_user.id
    )

    ucasuser, _ = UCASUser.get_or_create(
        owner=tguser,
        cookie_eaisess=eaisess,
        cookie_uukey=uukey,
        status=UCASUserStatus.normal,
    )

    first_message.edit_text('添加成功！', parse_mode=telegram.ParseMode.MARKDOWN)
    list_entry(update, context)


def add_by_uid_entry(update, context):
    if len(context.args) != 2:
        first_message = update.message.reply_markdown(
            f"例：/add\_by\_uid `2010211000` `password123`")
        return
    username = context.args[0]
    password = context.args[1]
    first_message = update.message.reply_markdown(f"Adding ...")

    tguser = TGUser.get(
        userid=update.message.from_user.id
    )

    ucasuser, _ = UCASUser.get_or_create(
        owner=tguser,
        username=username,
        password=password,
        status=UCASUserStatus.normal,
    )

    first_message.edit_text('添加成功！', parse_mode=telegram.ParseMode.MARKDOWN)
    list_entry(update, context)


def checkin_entry(update, context):
    tguser = TGUser.get(
        userid=update.message.from_user.id
    )
    if len(context.args) > 0:
        targets = tguser.get_ucasusers_by_seqids(list(map(int, context.args)))
    else:
        targets = tguser.get_ucasusers()

    if len(targets) == 0:
        ret_msg = '用户列表为空'
        update.message.reply_markdown(ret_msg)
        return
    for ucasuser in targets:
        try:
            ret = ucasuser.ncov_checkin(force=True)[:100]
            ret_msg = f"用户：`{ucasuser.username or ucasuser.cookie_eaisess or '[None]'}`\n签到成功！\n服务器返回：`{ret}`"
        except requests.exceptions.Timeout as e:
            ret_msg = f"用户：`{ucasuser.username or ucasuser.cookie_eaisess or '[None]'}`\n签到失败，服务器错误！\n`{e}`"
        except Exception as e:
            ret_msg = f"用户：`{ucasuser.username or ucasuser.cookie_eaisess or '[None]'}`\n签到异常！\n服务器返回：`{e}`"
        update.message.reply_markdown(ret_msg)


def nowloc_entry(update, context):
    tguser = TGUser.get(
        userid=update.message.from_user.id
    )
    if len(context.args) != 1:
        ret_msg = "请携带位置参数编号，例如 `/nowloc 1`,\n"\
            "`/nowloc 1` : 雁栖湖\n"\
            "`/nowloc 2` : 玉泉路\n"\
            "`/nowloc 3` : 中关村\n"\
            "`/nowloc 4` : 奥运村\n"\
            "`/nowloc 5` : 京外"
        update.message.reply_markdown(ret_msg)
        return
    if len(context.args) == 1:
        if type(context.args[0]) == int:
            loc = context.args[0]
            targets = tguser.get_ucasusers()
        else:
            targets = tguser.get_ucasusers_by_seqids(
                list(map(int, context.args[0].split(' ')[0])))
            loc = context.args[0].split(' ')[-1]

    if len(targets) == 0:
        ret_msg = '用户列表为空'
        update.message.reply_markdown(ret_msg)
        return
    for ucasuser in targets:
        ucasuser.now_location = int(loc)
        ucasuser.save()
        ret_msg = f"用户：`{ucasuser.username or ucasuser.cookie_eaisess or '[None]'}`\n位置设置成功！\n当前位置：`{ucasuser.now_location}`"
        update.message.reply_markdown(ret_msg)


def haspcr_entry(update, context):
    tguser = TGUser.get(
        userid=update.message.from_user.id
    )
    if len(context.args) > 0:
        targets = tguser.get_ucasusers_by_seqids(list(map(int, context.args)))
    else:
        targets = tguser.get_ucasusers()

    if len(targets) == 0:
        ret_msg = '用户列表为空'
        update.message.reply_markdown(ret_msg)
        return
    for ucasuser in targets:
        ucasuser.has_pcr = 1
        ucasuser.save()
        ret_msg = f"用户：`{ucasuser.username or ucasuser.cookie_eaisess or '[None]'}`\n今日核酸设置成功！"
        update.message.reply_markdown(ret_msg)


def pause_entry(update, context):
    tguser = TGUser.get(
        userid=update.message.from_user.id
    )
    if len(context.args) > 0:
        targets = tguser.get_ucasusers_by_seqids(list(map(int, context.args)))
    else:
        targets = tguser.get_ucasusers()

    for ucasuser in targets:
        ucasuser.status = UCASUserStatus.stopped
        ucasuser.save()
        ret_msg = f"用户：`{ucasuser.username or ucasuser.cookie_eaisess or '[None]'}`\n已暂停自动签到。"
        update.message.reply_markdown(ret_msg)


def resume_entry(update, context):
    tguser = TGUser.get(
        userid=update.message.from_user.id
    )
    if len(context.args) > 0:
        targets = tguser.get_ucasusers_by_seqids(list(map(int, context.args)))
    else:
        targets = tguser.get_ucasusers()

    for ucasuser in targets:
        ucasuser.status = UCASUserStatus.normal
        ucasuser.save()
        ret_msg = f"用户：`{ucasuser.username or ucasuser.cookie_eaisess or '[None]'}`\n已启用自动签到。"
        update.message.reply_markdown(ret_msg)


def remove_entry(update, context):
    assert len(context.args) > 0, "错误的命令，请用 /help 查看使用帮助。"

    tguser = TGUser.get(
        userid=update.message.from_user.id
    )
    if context.args[0].lower() != 'all':
        targets = tguser.get_ucasusers_by_seqids(list(map(int, context.args)))
    else:
        targets = tguser.get_ucasusers()

    for ucasuser in targets:
        ucasuser.status = UCASUserStatus.removed
        ucasuser.save()
        ret_msg = f"用户：`{ucasuser.username or ucasuser.cookie_eaisess or '[None]'}`\n已删除。"
        update.message.reply_markdown(ret_msg)

    list_entry(update, context)


def error_callback(update, context):
    """Log Errors caused by Updates."""
    logger.warning('Update "%s" caused error "%s: %s"', update,
                   context.error.__class__.__name__, context.error)
    update.message.reply_text("{}: {}".format(
        context.error.__class__.__name__, context.error))
    traceback.print_exc()


def tg_debug_logging(update, context):
    log_str = 'User %s `%d`: "%s"' % (
        update.message.from_user.username, update.message.from_user.id, update.message.text)
    logger.info(log_str)

    # Skip forwarding when command call.
    if update.message.text is not None and update.message.text.startswith('/'):
        return
    # Skip master message
    if update.message.from_user.id == TG_BOT_MASTER:
        return

    updater.bot.send_message(
        chat_id=TG_BOT_MASTER, text="[LOG] " + log_str, parse_mode=telegram.ParseMode.MARKDOWN)
    # Forward non-text message, like stickers.
    if update.message.text is None:
        updater.bot.forward_message(
            TG_BOT_MASTER, update.message.chat_id, update.message.message_id)


def checkinall_entry(update, context):
    assert update.message.from_user.id == TG_BOT_MASTER
    if len(context.args) > 0:
        if context.args[0] == 'retry':
            checkin_all_retry()
    else:
        checkin_all()


def pauseall_entry(update, context):
    assert update.message.from_user.id == TG_BOT_MASTER
    pause_all()


def listall_entry(update, context):
    assert update.message.from_user.id == TG_BOT_MASTER
    list_entry(update, context, admin_all=True)


def status_entry(update, context):
    assert update.message.from_user.id == TG_BOT_MASTER
    cron_data = "\n".join(["name: %s, trigger: %s, handler: %s, next: %s" % (
        job.name, job.trigger, job.func, job.next_run_time) for job in scheduler.get_jobs()])
    update.message.reply_text("Cronjob: " + cron_data)
    update.message.reply_text("System time: " + str(datetime.datetime.now()))


def send_message_entry(update, context):
    assert update.message.from_user.id == TG_BOT_MASTER
    updater.bot.send_message(chat_id=context.args[0], text=' '.join(
        update.message.text.split(' ')[2:]))


def broadcast_entry(update, context):
    assert update.message.from_user.id == TG_BOT_MASTER
    active_userids = set()
    for user in UCASUser.select().where(
        (UCASUser.status == UCASUserStatus.normal)
    ).prefetch(TGUser):
        active_userids.add(user.owner.userid)
    for userid in active_userids:
        try:
            updater.bot.send_message(chat_id=userid, text=' '.join(
                update.message.text.split(' ')[1:]))
        except Exception as e:
            logger.warning(str(e))


def text_command_entry(update, context):
    req_args = update.message.text.strip(f'@{updater.bot.username}').split('_')
    command = req_args[0][1:]
    context.args = list(filter(lambda i: i != '', req_args[1:]))
    getattr(sys.modules[__name__], "%s_entry" % command)(update, context)


def backup_db():
    logger.info("backup started!")
    copyfile('./my_app.db', './backup/my_app.{}.db'.format(
        str(datetime.datetime.now()).replace(":", "").replace(" ", "_")))
    logger.info("backup finished!")


def checkin_all_retry():
    logger.info("checkin_all_retry started!")
    for user in UCASUser.select().where(
        (UCASUser.status == UCASUserStatus.normal)
        & (UCASUser.latest_response_time < datetime.datetime.combine(datetime.date.today(), datetime.datetime.min.time()))
    ).prefetch(TGUser):
        ret_msg = ''
        try:
            ret = user.ncov_checkin()[:100]
            ret_msg = f"用户：`{user.username or user.cookie_eaisess or '[None]'}`\n重试签到成功！\n服务器返回：`{ret}`\n{display_time_formatted()}"
        except requests.exceptions.Timeout as e:
            ret_msg = f"用户：`{user.username or user.cookie_eaisess or '[None]'}`\n重试签到失败，服务器错误，请尝试手动签到！\nhttps://app.ucas.ac.cn/ncov/wap/default/index\n`{e}`\n{display_time_formatted()}"
            traceback.print_exc()
        except Exception as e:
            ret_msg = f"用户：`{user.username or user.cookie_eaisess or '[None]'}`\n重试签到异常！\n服务器返回：`{e}`\n{display_time_formatted()}"
            traceback.print_exc()
        logger.info(ret_msg)
        try:
            updater.bot.send_message(
                chat_id=user.owner.userid, text=ret_msg, parse_mode=telegram.ParseMode.MARKDOWN)
        except Exception as e:
            logger.warning(str(e))
    logger.info("checkin_all_retry finished!")


def checkin_all():
    try:
        backup_db()
    except:
        pass
    logger.info("checkin_all started!")
    for user in UCASUser.select().where(UCASUser.status == UCASUserStatus.normal).prefetch(TGUser):
        ret_msg = ''
        try:
            ret = user.ncov_checkin()[:100]
            ret_msg = f"用户：`{user.username or user.cookie_eaisess or '[None]'}`\n自动签到成功！\n服务器返回：`{ret}`\n{display_time_formatted()}"
        except requests.exceptions.Timeout as e:
            ret_msg = f"用户：`{user.username or user.cookie_eaisess or '[None]'}`\n自动签到失败，服务器错误，将重试！\n`{e}`\n{display_time_formatted()}"
            traceback.print_exc()
        except Exception as e:
            ret_msg = f"用户：`{user.username or user.cookie_eaisess or '[None]'}`\n自动签到异常！\n服务器返回：`{e}`\n{display_time_formatted()}"
            traceback.print_exc()
        logger.info(ret_msg)
        try:
            updater.bot.send_message(
                chat_id=user.owner.userid, text=ret_msg, parse_mode=telegram.ParseMode.MARKDOWN)
        except Exception as e:
            logger.warning(str(e))
    logger.info("checkin_all finished!")


def pause_all():
    logger.info("pause_all started!")
    user: UCASUser
    for user in UCASUser.select().where(UCASUser.status == UCASUserStatus.normal).prefetch(TGUser):
        ret_msg = ''
        try:
            user.pause()
            ret_msg = f"用户：`{user.username or user.cookie_eaisess or '[None]'}`\n系统管理已暂停签到！\n国科大系统更新，暂停服务1-2天，后续请手动开启更新。\n{display_time_formatted()}"
        except Exception as e:
            ret_msg = f"用户：`{user.username or user.cookie_eaisess or '[None]'}`\n暂停签到异常！\n服务器返回：`{e}`\n{display_time_formatted()}"
            traceback.print_exc()
        logger.info(ret_msg)
        try:
            updater.bot.send_message(
                chat_id=user.owner.userid, text=ret_msg, parse_mode=telegram.ParseMode.MARKDOWN)
        except Exception as e:
            logger.warning(str(e))
    logger.info("pause_all finished!")


def main():
    global updater, scheduler
    parser = argparse.ArgumentParser(description='UCAS 2019-nCoV Report Bot')
    parser.add_argument('--initdb', default=False, action='store_true')
    args = parser.parse_args()

    database = SqliteDatabase(config.SQLITE_DB_FILE_PATH)
    database_proxy.initialize(database)

    if args.initdb:
        db_init()
        exit(0)

    updater = Updater(
        TG_BOT_TOKEN, request_kwargs=TG_BOT_PROXY, use_context=True)
    # Get the dispatcher to register handlers
    dp = updater.dispatcher

    # on different commands - answer in Telegram
    dp.add_handler(MessageHandler(Filters.all, tg_debug_logging), -10)
    dp.add_handler(MessageHandler(Filters.all, tguser_check), -1)
    dp.add_handler(CommandHandler("start", start_entry))
    dp.add_handler(CommandHandler("help", help_entry))
    dp.add_handler(CommandHandler("list", list_entry))
    dp.add_handler(CommandHandler("add_by_uid", add_by_uid_entry))
    dp.add_handler(CommandHandler("add_by_cookie", add_by_cookie_entry))
    dp.add_handler(CommandHandler("checkin", checkin_entry))
    dp.add_handler(CommandHandler("nowloc", nowloc_entry))
    dp.add_handler(CommandHandler("haspcr", haspcr_entry))
    dp.add_handler(CommandHandler("pause", pause_entry))
    dp.add_handler(CommandHandler("resume", resume_entry))
    dp.add_handler(CommandHandler("remove", remove_entry))
    dp.add_handler(MessageHandler(Filters.regex(
        r'^/(remove|resume|pause|checkin|nowloc|haspcr)_.*$'), text_command_entry))
    dp.add_handler(CommandHandler("checkinall", checkinall_entry))
    dp.add_handler(CommandHandler("pauseall", pauseall_entry))
    dp.add_handler(CommandHandler("listall", listall_entry))
    dp.add_handler(CommandHandler("status", status_entry))
    dp.add_handler(CommandHandler("sendmsg", send_message_entry))
    dp.add_handler(CommandHandler("broadcast", broadcast_entry))
    #dp.add_handler(MessageHandler(Filters.command, no_such_command),10)

    # on noncommand i.e message - echo the message on Telegram
    #dp.add_handler(MessageHandler(Filters.text, echo))

    # log all errors
    dp.add_error_handler(error_callback)

    # Start the Bot
    updater.start_polling()

    # Run the bot until you press Ctrl-C or the process receives SIGINT,
    # SIGTERM or SIGABRT. This should be used most of the time, since
    # start_polling() is non-blocking and will stop the bot gracefully.

    scheduler.add_job(
        func=checkin_all,
        id='checkin_all',
        trigger="cron",
        hour=CHECKIN_ALL_CRON_HOUR,
        minute=CHECKIN_ALL_CRON_MINUTE,
        max_instances=1,
        replace_existing=False,
        misfire_grace_time=10,
    )
    scheduler.add_job(
        func=checkin_all_retry,
        id='checkin_all_retry',
        trigger="cron",
        hour=CHECKIN_ALL_CRON_RETRY_HOUR,
        minute=CHECKIN_ALL_CRON_RETRY_MINUTE,
        max_instances=1,
        replace_existing=False,
        misfire_grace_time=10,
    )

    scheduler.start()
    logger.info(["name: %s, trigger: %s, handler: %s, next: %s" % (
        job.name, job.trigger, job.func, job.next_run_time) for job in scheduler.get_jobs()])

    updater.idle()


if __name__ == "__main__":
    logging.basicConfig(
        handlers=[
            logging.handlers.TimedRotatingFileHandler(
                "log/main", when='midnight', backupCount=30, encoding='utf-8',
                atTime=datetime.time(hour=0, minute=0)
            ),
            logging.StreamHandler(sys.stdout)
        ],
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.DEBUG if config.BOT_DEBUG else logging.INFO,
    )
    logger = logging.getLogger(__name__)

    scheduler = BackgroundScheduler(timezone=CRON_TIMEZONE)

    main()
