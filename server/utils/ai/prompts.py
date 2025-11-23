"""Prompt templates used for OpenAI interactions."""

QUESTION_PROMPTS = {
    1: (
        "You are a DevOps interviewer, create an easy technical question.\n\n"
        "Topic: {subcategory} in {category}.\n"
        "Focus keyword: {keyword}\n"
        "Question style: {style_modifier}\n\n"
        "Create a SHORT, CLEAR question that:\n"
        "- Is appropriate for beginner DevOps student.\n"
        "- Can be answered in 2-3 sentences.\n\n"
        "Generate only the question, no additional text."
    ),
    2: (
        "You are a DevOps interviewer, create a medium technical question.\n\n"
        "Topic: {subcategory} in {category}\n"
        "Focus keyword: {keyword}\n"
        "Question style: {style_modifier}\n\n"
        "Create a SHORT, PRACTICAL question that:\n"
        "- Is appropriate for entry-level DevOps engineers.\n"
        "- Can be answered in 3-4 sentences.\n\n"
        "Generate only the question, no additional text."
    ),
    3: (
        "You are a DevOps interviewer, create an hard level technical question.\n\n"
        "Topic: {subcategory} in {category}\n"
        "Focus keyword: {keyword}\n"
        "Question style: {style_modifier}\n\n"
        "Create a SHORT, CHALLENGING question that:\n"
        "- Is appropriate for senior DevOps engineers.\n"
        "- Can be answered in 3-4 sentences.\n\n"
        "Generate only the question, no additional text."
    ),
}


EVAL_PROMPT = (
    "You are a friendly DevOps teacher.\n"
    "I will give you a question and the student's answer for review. Ignore casing and punctuation in evaluation.\n"
    "Question difficulty: {difficulty_label}.\n"
    'Q: "{question}"\n'
    'A: "{answer}"\n\n'
    "Tasks: \n"
    "1. Review the student's answer based on the question, and expected difficulty. Expect a short response, no more than 5 sentences.\n"
    "2. Give short, constructive feedback on the user's answer quality, note only on significant mistakes.\n"
    "3. Scoring: 10 = fully correct; 8–9 = mostly correct; 6–7 = partly correct; 4–5 = major gaps; 0–3 = mostly wrong.\n"
    'Return the following in Json format: {{ "score": "/10", "feedback": "" }}'
)