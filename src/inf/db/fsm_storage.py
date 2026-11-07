import json
from typing import Any, Dict, Optional
from aiogram.fsm.state import State
from aiogram.fsm.storage.base import BaseStorage, StorageKey, StateType
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
from src.inf.db.models import FsmStateModel


class PostgresFSMStorage(BaseStorage):
    """Зберігання станів FSM у PostgreSQL, щоб анкети не злітали при перезапуску бота."""

    def __init__(self, session_pool: async_sessionmaker[AsyncSession]):
        self._session_pool = session_pool

    @staticmethod
    def _build_key(key: StorageKey) -> str:
        return f"{key.bot_id}:{key.chat_id}:{key.user_id}:{key.destiny}"

    async def set_state(self, key: StorageKey, state: StateType = None) -> None:
        raw_key = self._build_key(key)
        state_str = state.state if isinstance(state, State) else state
        async with self._session_pool() as session:
            record = await session.get(FsmStateModel, raw_key)
            if record:
                record.state = state_str
            else:
                session.add(FsmStateModel(key=raw_key, state=state_str, data="{}"))
            await session.commit()

    async def get_state(self, key: StorageKey) -> Optional[str]:
        raw_key = self._build_key(key)
        async with self._session_pool() as session:
            record = await session.get(FsmStateModel, raw_key)
            return record.state if record else None

    async def set_data(self, key: StorageKey, data: Dict[str, Any]) -> None:
        raw_key = self._build_key(key)
        data_json = json.dumps(data, ensure_ascii=False)
        async with self._session_pool() as session:
            record = await session.get(FsmStateModel, raw_key)
            if record:
                record.data = data_json
            else:
                session.add(FsmStateModel(key=raw_key, state=None, data=data_json))
            await session.commit()

    async def get_data(self, key: StorageKey) -> Dict[str, Any]:
        raw_key = self._build_key(key)
        async with self._session_pool() as session:
            record = await session.get(FsmStateModel, raw_key)
            if not record or not record.data:
                return {}
            try:
                return json.loads(record.data)
            except json.JSONDecodeError:
                return {}

    async def close(self) -> None:
        pass
