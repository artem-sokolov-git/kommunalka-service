from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Any

import pytest
from aiogram import Bot, Dispatcher
from aiogram.client.session.base import BaseSession
from aiogram.methods import SendDocument, SendMessage, TelegramMethod
from aiogram.types import Chat, InputFile, Message, Update, User
from sqlalchemy import Engine

from kommunalka.infrastructure.config import Settings
from kommunalka.infrastructure.db.unit_of_work import SqlUnitOfWork
from kommunalka.presentation.telegram import create_bot
from kommunalka.presentation.telegram.bot import create_router

pytestmark = pytest.mark.anyio


class RecordingSession(BaseSession):
    """Takes the place of the network: remembers what the bot would send."""

    def __init__(self) -> None:
        super().__init__()
        self.sent: list[TelegramMethod[Any]] = []

    async def close(self) -> None: ...

    async def make_request(self, bot: Bot, method: TelegramMethod[Any], timeout: Any = None) -> Any:
        self.sent.append(method)

    async def stream_content(self, *args: Any, **kwargs: Any) -> AsyncGenerator[bytes]:
        yield b""


@pytest.fixture
def session() -> RecordingSession:
    return RecordingSession()


@pytest.fixture
def feed(session: RecordingSession, engine: Engine) -> Any:
    dispatcher = Dispatcher()
    dispatcher.include_router(create_router(lambda: SqlUnitOfWork(engine), [42, 43]))
    bot = Bot("1:test", session=session)

    async def feed(user_id: int, text: str) -> None:
        message = Message(
            message_id=1,
            date=datetime.now(UTC),
            chat=Chat(id=user_id, type="private"),
            from_user=User(id=user_id, is_bot=False, first_name="Test"),
            text=text,
        )
        await dispatcher.feed_update(bot, Update(update_id=1, message=message))

    return feed


@pytest.mark.usefixtures("household")
async def test_sends_the_pdf_to_an_allowed_user(feed: Any, session: RecordingSession) -> None:
    await feed(42, "/bill 2026-09")

    [method] = session.sent
    assert isinstance(method, SendDocument)
    assert method.chat_id == 42
    assert isinstance(method.document, InputFile)
    assert method.document.filename == "bill-2026-09.pdf"
    assert method.caption == "Счёт за сентябрь 2026 · Дом <b>"


async def test_ignores_other_users_and_other_texts(feed: Any, session: RecordingSession) -> None:
    await feed(7, "/bill 2026-09")
    await feed(42, "привет")

    assert session.sent == []


async def test_wrong_month_shows_the_format(feed: Any, session: RecordingSession) -> None:
    await feed(42, "/bill 2026-13")

    [method] = session.sent
    assert isinstance(method, SendMessage)
    assert method.text.startswith("Формат: /bill")


def test_bot_is_created_only_with_a_token_and_allowed_users(engine: Engine) -> None:
    def uow_factory() -> SqlUnitOfWork:
        return SqlUnitOfWork(engine)

    token, users = "123:abc", [42]
    assert create_bot(Settings(_env_file=None), uow_factory) is None
    assert create_bot(Settings(_env_file=None, bot_token=token), uow_factory) is None
    assert create_bot(Settings(_env_file=None, allowed_users_tg_ids=users), uow_factory) is None
    both = Settings(_env_file=None, bot_token=token, allowed_users_tg_ids=users)
    assert create_bot(both, uow_factory)
