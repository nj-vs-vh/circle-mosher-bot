import asyncio
import enum
import logging
import os
import time
from pathlib import Path

from telebot import AsyncTeleBot
from telebot import types as tg
from telebot.runner import BotRunner
from telebot_components.form.handler import (
    FormExitContext,
    FormHandler,
    FormHandlerConfig,
)
from telebot_components.menu import (
    Menu,
    MenuConfig,
    MenuHandler,
    MenuItem,
    TerminatorContext,
)
from telebot_components.redis_utils.emulation import PersistentRedisEmulation

from forms import SingleVideoNoteFieldResult, single_video_note_form
from processings import VideoProcessingContext, average, datamosh_basic, median

SCRIPT_DIR = Path(__file__).parent


class Processing(enum.StrEnum):
    AVG = enum.auto()
    MEDIAN = enum.auto()
    DATAMOSH_BASIC = enum.auto()


main_menu = Menu(
    text="choose processing type",
    menu_items=[
        MenuItem(label="< average frame >", terminator=Processing.AVG),
        MenuItem(label="median frame", terminator=Processing.MEDIAN),
        MenuItem(label="datamosh (basic)", terminator=Processing.DATAMOSH_BASIC),
    ],
    config=MenuConfig(
        back_label=None,
        lock_after_termination=False,
    ),
)


async def main() -> None:
    bot_prefix = "media-proc-bot"
    bot = AsyncTeleBot(os.environ["TOKEN"])
    redis = PersistentRedisEmulation(dirname=(SCRIPT_DIR / ".storage"))  # type: ignore

    menu_handler = MenuHandler(
        name="main-menu",
        bot_prefix=bot_prefix,
        menu_tree=main_menu,
        redis=redis,
    )
    single_video_note_form_handler = FormHandler[SingleVideoNoteFieldResult](
        redis=redis,
        bot_prefix=bot_prefix,
        name="single-video-note",
        form=single_video_note_form,
        config=FormHandlerConfig(
            form_starting_template="ok!",
            can_skip_field_template="{} - skip field.",
            cant_skip_field_msg="this field is mandatory!",
            echo_filled_field=False,
            retry_field_msg="fix pls!",
            unsupported_cmd_error_template="command not supported, supported are: {}",
            cancelling_because_of_error_template="error :( ({})",
        ),
    )

    @bot.message_handler()
    async def start(m: tg.Message):
        await menu_handler.start_menu(bot, user=m.from_user)

    async def choose_processing(context: TerminatorContext):
        processing = Processing(context.terminator)
        match processing:
            case Processing.AVG | Processing.MEDIAN | Processing.DATAMOSH_BASIC:
                await single_video_note_form_handler.start(
                    bot=bot,
                    user=context.user,
                    initial_form_result={"processing": processing},  # type: ignore
                )

    async def single_video_note_processing(
        context: FormExitContext[SingleVideoNoteFieldResult],
    ):
        processing = Processing(context.result["processing"])  # type: ignore
        logging.info(f"Running processing on a single video note: {processing}")
        video_note = context.result["video_note"]
        logging.info(f"Downloading video: {video_note.file_id}")
        start = time.time()
        try:
            file_obj = await bot.get_file(file_id=video_note.file_id)
            file_body = await bot.download_file(file_path=file_obj.file_path)
            logging.info(f"Saved in {time.time() - start:.3f} sec")
        except Exception as e:
            await bot.send_message(
                context.last_update.from_user.id,
                "error downloading your video\n\n" + str(e),
            )
        video_processsing_ctx = VideoProcessingContext(
            video=file_body,
            bot=context.bot,
            user=context.last_update.from_user,
        )
        try:
            match processing:
                case Processing.AVG:
                    await average(video_processsing_ctx)
                case Processing.MEDIAN:
                    await median(video_processsing_ctx)
                case Processing.DATAMOSH_BASIC:
                    await datamosh_basic(video_processsing_ctx)
        except Exception as e:
            await bot.send_message(
                context.last_update.from_user.id,
                "error processing video\n\n" + str(e),
            )

    menu_handler.setup(bot, on_terminal_menu_option_selected=choose_processing)
    single_video_note_form_handler.setup(
        bot,
        on_form_completed=single_video_note_processing,
    )

    await BotRunner(
        bot_prefix=bot_prefix,
        bot=bot,
    ).run_polling()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
