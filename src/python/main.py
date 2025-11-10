"""Quiz app REST API."""
from flask import Flask, request, jsonify
from config import Config
from validation import validate_difficulty, validate_required_fields
from quiz_utils import get_categories, get_subjects, get_random_keyword
from ai_utils import generate_question, evaluate_answer

app = Flask(__name__)

# Error message template
def error_response(message, code=400):
    """Return error response."""
    return jsonify({'error': message}), code


# Health checl route
@app.route('/api/health')
def health():
    """Health check."""
    return jsonify({'status': 'ok'})


# Returns all categories
@app.route('/api/categories')
def api_categories():
    """Get all categories."""
    return jsonify({'categories': get_categories()})


@app.route('/api/subjects')
def api_subjects():
    """Get subjects for category."""
    category = request.args.get('category')
    if not category:
        return error_response('category parameter required')
    return jsonify({'subjects': get_subjects(category)})


@app.route('/api/question/generate', methods=['POST'])
def api_generate_question():
    """Generate a question."""
    data = request.get_json()
    
    try:
        validate_required_fields(data, ['category', 'subject', 'difficulty'])
        difficulty = validate_difficulty(data['difficulty'])
    except ValueError as e:
        return error_response(str(e))
    
    keyword = get_random_keyword(data['category'], data['subject'])
    if not keyword:
        return error_response('No keywords found', 404)
    
    question = generate_question(data['category'], keyword, difficulty)
    
    return jsonify({
        'question': question,
        'keyword': keyword,
        'category': data['category'],
        'subject': data['subject'],
        'difficulty': difficulty
    })


@app.route('/api/answer/evaluate', methods=['POST'])
def api_evaluate_answer():
    """Evaluate an answer."""
    data = request.get_json()
    
    try:
        validate_required_fields(data, ['question', 'answer', 'difficulty'])
        difficulty = validate_difficulty(data['difficulty'])
    except ValueError as e:
        return error_response(str(e))
    
    feedback = evaluate_answer(data['question'], data['answer'], difficulty)
    return jsonify({'feedback': feedback})


if __name__ == "__main__":
    app.run(debug=Config.DEBUG, host=Config.HOST, port=Config.PORT)