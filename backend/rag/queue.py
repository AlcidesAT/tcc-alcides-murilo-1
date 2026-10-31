"""
Fila de geração das respostas.

O modelo escreve poucas respostas por minuto, então, com muita gente perguntando,
quem espera não pode ocupar as threads do servidor: com elas todas presas, nem a
página abre. Aqui a espera acontece no laço assíncrono, sem thread, e só
`slots` respostas são pedidas ao modelo por vez, em ordem de chegada.

Todos os métodos rodam no laço de eventos do servidor (um único processo), por
isso não há locks.
"""

import asyncio
import time
from collections import deque
from typing import Deque, Dict, Optional


class Ticket:
    """Lugar de uma pergunta na fila. `turn` é ligado quando chega a vez dela."""

    def __init__(self) -> None:
        self.turn = asyncio.Event()


class GenerationQueue:
    def __init__(self, slots: int) -> None:
        self._slots = slots
        self._active = 0
        self._waiting: Deque[Ticket] = deque()
        self._pace: Optional[float] = None  # segundos entre respostas (média móvel)
        self._last_done: Optional[float] = None

    def join(self) -> Ticket:
        ticket = Ticket()
        if self._active < self._slots and not self._waiting:
            self._active += 1
            ticket.turn.set()
        else:
            self._waiting.append(ticket)
        return ticket

    def leave(self, ticket: Ticket, completed: bool = False) -> None:
        """Libera a vaga ou o lugar na fila (inclusive de quem desistiu)."""
        if not ticket.turn.is_set():
            self._waiting.remove(ticket)
            return
        self._active -= 1
        if self._waiting:
            self._active += 1
            self._waiting.popleft().turn.set()
        if completed:
            self._note_completion()

    async def wait(self, ticket: Ticket, timeout: float) -> None:
        """Espera a vez por até `timeout` segundos."""
        try:
            await asyncio.wait_for(ticket.turn.wait(), timeout)
        except asyncio.TimeoutError:
            pass

    def status(self, ticket: Ticket) -> Dict:
        """Posição na fila e estimativa de espera (None até haver medição)."""
        position = self._waiting.index(ticket) + 1
        eta = round(position * self._pace) if self._pace else None
        return {"position": position, "eta_seconds": eta}

    def _note_completion(self) -> None:
        now = time.monotonic()
        if self._last_done is not None:
            gap = now - self._last_done
            self._pace = gap if self._pace is None else 0.7 * self._pace + 0.3 * gap
        # Com o servidor ocioso, o próximo intervalo não mediria o ritmo do modelo.
        self._last_done = now if self._active else None
