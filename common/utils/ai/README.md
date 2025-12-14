# AI Utilities

This directory contains the logic for integrating with OpenAI's API. We use AI to generate dynamic quiz questions and to evaluate user answers.

## How it works

We don't just send a simple string to ChatGPT. We use a structured approach to ensure the AI gives us exactly what we need for the app to work.

### Question Generation (`generator.py`)

When a user requests a quiz on a specific topic:
1. We construct a prompt that tells the AI to act as a "Quiz Master".
2. We specify the difficulty, topic, and the exact JSON format we need for the output.
3. We parse the JSON response to create `Question` objects that our frontend can display.

### Answer Evaluation (`evaluator.py`)

When a user answers a question:
1. We send the question, the correct answer (hidden from user), and the user's answer to the AI.
2. The AI determines if the user's answer is correct, even if it's phrased differently than the official answer.
3. It provides a score (0-100) and a brief explanation of why it was right or wrong.

## Configuration

The AI settings (like which model to use, temperature/creativity) are controlled via environment variables defined in `common/utils/config.py`.
