# Socket Handlers

Socket.IO event handlers for the multiplayer service.

---
## Files
- `lobby_handlers.py` — join/leave/ready lifecycle
- `game_handlers.py` — start, question flow, submit answers
- `chat_handlers.py` — lobby/game chat events

Handlers receive client events and broadcast updates to the lobby/game as needed.
