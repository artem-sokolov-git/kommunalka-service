"""The bot on aiogram: long polling as a task of the app, access by user id, handlers."""

import asyncio
import contextlib
from collections.abc import Callable

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import BufferedInputFile, Message

from kommunalka.application.unit_of_work import UnitOfWork
from kommunalka.infrastructure.config import Settings
from kommunalka.presentation.telegram import texts
from kommunalka.presentation.telegram.commands import UsageError, parse_bill_args
from kommunalka.presentation.telegram.handlers import send_bill


def create_router(uow_factory: Callable[[], UnitOfWork], allowed_user_ids: list[int]) -> Router:
    """Handlers of the bot; messages from users outside `allowed_user_ids` are not handled."""
    router = Router(name="bill")
    router.message.filter(F.from_user.id.in_(allowed_user_ids))

    @router.message(Command("bill"))
    async def bill(message: Message, command: CommandObject) -> None:
        try:
            parsed = parse_bill_args(command.args)
        except UsageError:
            await message.answer(texts.USAGE)
            return
        # Queries and PDF drawing are synchronous: keep them off the event loop.
        reply = await asyncio.to_thread(send_bill, parsed, uow_factory())
        if reply.document is None or reply.file_name is None:
            await message.answer(reply.text)
        else:
            await message.answer_document(
                BufferedInputFile(reply.document, reply.file_name), caption=reply.text
            )

    return router


class BillBot:
    def __init__(
        self, token: str, uow_factory: Callable[[], UnitOfWork], allowed_user_ids: list[int]
    ):
        self._bot = Bot(token)
        self._dispatcher = Dispatcher()
        self._dispatcher.include_router(create_router(uow_factory, allowed_user_ids))
        self._task: asyncio.Task[None] | None = None

    def start(self) -> None:
        # Polling retries network errors itself; the signals belong to the server.
        self._task = asyncio.create_task(
            self._dispatcher.start_polling(self._bot, handle_signals=False)
        )

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task


def create_bot(settings: Settings, uow_factory: Callable[[], UnitOfWork]) -> BillBot | None:
    """The bot, or None unless both the token and allowed users are set."""
    if not settings.bot_token or not settings.allowed_users_tg_ids:
        return None
    return BillBot(settings.bot_token, uow_factory, settings.allowed_users_tg_ids)
