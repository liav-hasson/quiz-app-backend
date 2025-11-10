"""Quiz app Flask REST API.

Simple REST API for quiz app. Designed to be stateless and serve a React frontend.
In production, run under a WSGI server (gunicorn/uwsgi).
"""

import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from quiz_utils import get_categories, get_subjects, get_random_keyword
from ai_utils import generate_question, evaluate_answer

app = Flask(__name__)
CORS(app)  # Enable CORS for React frontend


@app.route('/api/health', methods=['GET'])
def health():
    """Health check endpoint."""
    return jsonify({'status': 'ok'})


@app.route('/api/categories', methods=['GET'])
def api_categories():
    """Get all available categories."""
    categories = get_categories()
    return jsonify({'categories': categories})


@app.route('/api/subjects', methods=['GET'])
def api_subjects():
    """Get subjects for a specific category."""
    category = request.args.get('category')
    if not category:
        return jsonify({'error': 'category parameter required'}), 400
    
    subjects = get_subjects(category)
    return jsonify({'subjects': subjects})


@app.route('/api/question/generate', methods=['POST'])
def api_generate_question():
    """Generate a question based on category, subject, and difficulty."""
    data = request.get_json()
    
    category = data.get('category')
    subject = data.get('subject')
    difficulty = data.get('difficulty')
    
    if not all([category, subject, difficulty]):
        return jsonify({
            'error': 'category, subject, and difficulty are required'
        }), 400
    
    try:
        difficulty = int(difficulty)
        if difficulty not in [1, 2, 3]:
            raise ValueError()
    except (ValueError, TypeError):
        return jsonify({'error': 'difficulty must be 1, 2, or 3'}), 400
    
    keyword = get_random_keyword(category, subject)
    if not keyword:
        return jsonify({'error': 'No keywords found for this category/subject'}), 404
    
    question = generate_question(category, keyword, difficulty)
    
    return jsonify({
        'question': question,
        'keyword': keyword,
        'category': category,
        'subject': subject,
        'difficulty': difficulty
    })


@app.route('/api/answer/evaluate', methods=['POST'])
def api_evaluate_answer():
    """Evaluate an answer to a question."""
    data = request.get_json()
    
    question = data.get('question')
    answer = data.get('answer')
    difficulty = data.get('difficulty')
    
    if not all([question, answer, difficulty]):
        return jsonify({
            'error': 'question, answer, and difficulty are required'
        }), 400
    
    try:
        difficulty = int(difficulty)
        if difficulty not in [1, 2, 3]:
            raise ValueError()
    except (ValueError, TypeError):
        return jsonify({'error': 'difficulty must be 1, 2, or 3'}), 400
    
    feedback = evaluate_answer(question, answer, difficulty)
    
    return jsonify({'feedback': feedback})


if __name__ == "__main__":
    debug_env = os.environ.get("FLASK_DEBUG", "false").lower()
    debug = debug_env in ("1", "true", "yes")
    host = os.environ.get("FLASK_HOST", "0.0.0.0")
    
    try:
        port = int(os.environ.get("FLASK_PORT", 5000))
    except (TypeError, ValueError):
        port = 5000
    
    app.run(debug=debug, host=host, port=port)