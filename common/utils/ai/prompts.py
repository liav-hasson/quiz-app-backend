"""Prompt templates used for OpenAI interactions."""

QUESTION_PROMPTS = {
    1: (
        "You are a DevOps interviewer, create an very easy technical question.\n\n"
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
    "I will give you a question and the student's answer for review.\n"
    "Question difficulty: {difficulty_label}.\n"
    'Q: "{question}"\n'
    'A: "{answer}"\n\n'
    "Tasks: \n"
    "1. Review the student's answer based on the question, and expected difficulty. Expect a short response, no more than 100 words. Ignore casing and punctuation in evaluation.\n"
    "2. Give short feedback on the user's answer quality, note only on significant mistakes. no more than 50 words.\n"
    "3. Scoring: 10 = fully correct; 8–9 = mostly correct; 6–7 = partly correct; 4–5 = major gaps; 0–3 = mostly wrong.\n\n"
    'Output format: {{"score": "X/10", "feedback": "your feedback here"}}\n'
    "Do NOT wrap the JSON in ```json or ``` markers."
)

PERFECT_ANSWER_PROMPT = (
    "You are an expert DevOps engineer providing a perfect model answer to a technical question.\n\n"
    'Question: "{question}"\n\n'
    "Provide a concise, comprehensive, and technically accurate answer that would score 10/10. "
    "Your answer should:\n"
    "- Be clear and well-structured\n"
    "- Include all key concepts and details\n"
    "- Use proper technical terminology\n"
    "- Be 3-5 sentences (approximately 50-100 words)\n"
    "- Serve as a reference for what a perfect answer looks like\n\n"
    "Return ONLY the answer text, no additional formatting or preamble."
    "Do NOT wrap the JSON in ```json or ``` markers."
)

# Multiplayer mode - Multiple choice questions with structured JSON output
MULTIPLAYER_QUESTION_PROMPTS = {
    1: (
        "You are a DevOps quiz teacher creating multiple-choice questions for a multiplayer quiz game.\n\n"
        "Category: {category}\n"
        "Subject: {subcategory}\n"
        "Focus keyword: {keyword}\n"
        "Focus style: basic definition or general understanding\n"
        "Difficulty: VERY EASY (appropriate for a student just starting out)\n\n"
        "Create a multiple-choice question that:\n"
        "- The question MUST be under 20 words and contain the focus keyword\n"
        "- Each answer option MUST be under 10 words\n"
        "- Has exactly 4 answer options\n"
        "- Has ONE clearly correct answer\n"
        "- Has 3 plausible but incorrect distractors\n"
        "\n"
        "CRITICAL INSTRUCTIONS:\n"
        "- Put the CORRECT answer as the FIRST option in the array\n"
        "- Put 3 incorrect answers as the remaining options\n"
        "- The correct_answer field should always be \"A\"\n"
        "- Do NOT include letter prefixes (A., B., C., D.) in the options text\n\n"
        "Return ONLY valid JSON in this exact format:\n"
        '{{"question": "...", "options": ["Correct answer text without prefix", "Wrong option without prefix", "Wrong option without prefix", "Wrong option without prefix"], "correct_answer": "A"}}\n\n'
        "Do NOT include any markdown, code blocks, or extra text. Output must be pure JSON."
    ),
    2: (
        "You are a DevOps quiz master creating multiple-choice questions for a multiplayer quiz game.\n\n"
        "Category: {category}\n"
        "Subject: {subcategory}\n"
        "Focus keyword: {keyword}\n"
        "Focus style: concept knowledge, comparison or purpose\n"
        "Difficulty: EASY (appropriate for an entry-level DevOps student)\n\n"
        "Create a multiple-choice question that:\n"
        "- The question MUST be under 25 words and contain the focus keyword\n"
        "- Each answer option MUST be under 15 words\n"
        "- Has exactly 4 answer options\n"
        "- Has ONE clearly correct answer\n"
        "- Has 3 plausible but incorrect distractors\n"
        "\n"
        "CRITICAL INSTRUCTIONS:\n"
        "- Put the CORRECT answer as the FIRST option in the array\n"
        "- Put 3 incorrect answers as the remaining options\n"
        "- The correct_answer field should always be \"A\"\n"
        "- Do NOT include letter prefixes (A., B., C., D.) in the options text\n\n"
        "Return ONLY valid JSON in this exact format:\n"
        '{{"question": "...", "options": ["Correct answer text without prefix", "Wrong option without prefix", "Wrong option without prefix", "Wrong option without prefix"], "correct_answer": "A"}}\n\n'
        "Do NOT include any markdown, code blocks, or extra text. Output must be pure JSON."
    ),
    3: (
        "You are a DevOps quiz master creating multiple-choice questions for a multiplayer quiz game.\n\n"
        "Category: {category}\n"
        "Subject: {subcategory}\n"
        "Focus keyword: {keyword}\n"
        "Focus style: challange concept knowledge and purpose\n"
        "Difficulty: MEDIUM (appropriate for a junior DevOps engineer)\n\n"
        "Create a multiple-choice question that:\n"
        "- The question MUST be under 25 words and contain the focus keyword\n"
        "- Each answer option MUST be under 15 words\n"
        "- Has exactly 4 answer options\n"
        "- Has ONE clearly correct answer\n"
        "- Has 3 distractors that test understanding\n"
        "\n"
        "CRITICAL INSTRUCTIONS:\n"
        "- Put the CORRECT answer as the FIRST option in the array\n"
        "- Put 3 incorrect answers as the remaining options\n"
        "- The correct_answer field should always be \"A\"\n"
        "- We will shuffle the options randomly after generation\n"
        "- Do NOT include letter prefixes (A., B., C., D.) in the options text\n\n"
        "Return ONLY valid JSON in this exact format:\n"
        '{{"question": "...", "options": ["Correct answer text without prefix", "Wrong option without prefix", "Wrong option without prefix", "Wrong option without prefix"], "correct_answer": "A"}}\n\n'
        "Do NOT include any markdown, code blocks, or extra text. Output must be pure JSON."
    ),
}


DEEP_DIVE_PROMPT = (
    "You are an expert DevOps technical writer creating a concise educational article.\n\n"
    "Topic: {keyword} (within {subcategory} / {category})\n\n"
    "Write a focused ~500-word article in Markdown format that:\n"
    "- Starts with a level-2 heading (## Title) that includes the keyword\n"
    "- Has 3-4 sections using level-3 headings (### Section)\n"
    "- Explains what it is, why it matters, and how to use it\n"
    "- Includes at least one practical code block or configuration example where relevant\n"
    "- Uses bullet points for key takeaways\n"
    "- Is written for intermediate DevOps practitioners\n"
    "- Ends with a short 'Key Takeaways' bullet list\n\n"
    "Constraints:\n"
    "- Stay between 400-600 words\n"
    "- Use proper Markdown formatting (headers, code fences with language tags, bold for emphasis)\n"
    "- Be technically accurate and practical\n"
    "- Do NOT include preamble like 'Here is an article...' — start directly with the ## heading\n"
)