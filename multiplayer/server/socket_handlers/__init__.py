"""Socket.IO event handlers for the multiplayer server.

These handlers manage real-time WebSocket communication.
State mutations go through the API server; these handlers only:
1. Manage Socket.IO room membership
2. Relay Redis events to clients
3. Handle low-latency actions (chat, answer submission)
"""

from server.socket_handlers import lobby_handlers
from server.socket_handlers import game_handlers
from server.socket_handlers import chat_handlers

__all__ = ['lobby_handlers', 'game_handlers', 'chat_handlers']