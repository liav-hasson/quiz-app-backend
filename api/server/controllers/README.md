# Controllers

This directory contains the "Controllers" for our API. In the Model-View-Controller (MVC) pattern, controllers are the brains of the operation.

## What do Controllers do?

Controllers sit between the API Routes (which handle the HTTP stuff like URLs and methods) and the Data Layer (Repositories).

When a request comes in:
1. **Route**: The route function receives the request (e.g., `GET /api/quiz`).
2. **Controller**: The route calls a function in a controller (e.g., `QuizController.generate_quiz`).
3. **Logic**: The controller does the heavy lifting:
   - It validates the input.
   - It calls the AI service to generate questions.
   - It saves the new quiz to the database using a Repository.
4. **Response**: The controller returns the data back to the route, which sends it to the user as JSON.

## Why separate Routes and Controllers?

Separating them keeps the code organized.
- **Routes** care about HTTP (status codes, headers, URLs).
- **Controllers** care about Business Logic (rules of the game, data processing).

This makes it easier to read and maintain the code as the application grows.
