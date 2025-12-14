# Socket Handlers

This directory contains the event handlers for the Multiplayer WebSocket server.

## What are Socket Handlers?

In a standard web API, you have "Routes" that respond to requests. In a WebSocket server (using Socket.IO), we have "Event Handlers". These functions listen for specific messages (events) sent by the frontend and react to them in real-time.

## How it works

The handlers are organized by feature:

- **`lobby_handlers.py`**: Manages the pre-game waiting room.
  - `join_lobby`: A player enters the lobby.
  - `leave_lobby`: A player disconnects or quits.
  - `player_ready`: A player signals they are ready to start.

- **`game_handlers.py`**: Manages the active game flow.
  - `submit_answer`: A player sends their answer to a question.
  - `next_question`: The host requests the next question.

- **`chat_handlers.py`**: Manages the in-game chat.
  - `send_message`: A player sends a chat message to the group.

## Real-time Communication

Unlike HTTP requests which are one-way (Client asks -> Server answers), WebSockets allow two-way communication.
- The client emits an event (e.g., "I answered B").
- The handler processes it.
- The server can then "broadcast" an update to *all* players in the game (e.g., "Player 1 answered!").
