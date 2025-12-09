"""Repository for managing multiplayer game sessions."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from bson import ObjectId

from common.repositories.base_repository import BaseRepository
from common.repositories.questions_repository import QuestionsRepository
from common.repositories.quiz_repository import QuizRepository
from common.utils.ai.service import AIQuestionService


class GameSessionRepository(BaseRepository):
    """Persistence layer for the `multiplayer_game_sessions` collection."""

    def __init__(
        self, 
        db_controller, 
        questions_repository: QuestionsRepository,
        quiz_repository: QuizRepository,
        ai_service: Optional[AIQuestionService] = None
    ) -> None:
        super().__init__(db_controller, "multiplayer_game_sessions")
        self.questions_repository = questions_repository
        self.quiz_repository = quiz_repository
        self.ai_service = ai_service or AIQuestionService()

    def create_game_session(self, lobby_id: str, lobby_code: str, questions: List[Dict[str, Any]]) -> Dict[str, Any]:
        now = datetime.now()
        session_doc = {
            "lobby_id": lobby_id,
            "lobby_code": lobby_code,
            "questions": questions,
            "current_question_index": -1,  # Not started yet
            "question_start_time": None,
            "player_answers": {},  # {user_id: [answers]}
            "created_at": now,
            "updated_at": now
        }
        
        self.collection.insert_one(session_doc)
        session_doc["_id"] = str(session_doc["_id"])
        return session_doc

    def get_game_session_by_lobby(self, lobby_code: str) -> Optional[Dict[str, Any]]:
        session = self.collection.find_one({"lobby_code": lobby_code})
        if session:
            session["_id"] = str(session["_id"])
        return session

    def record_player_answer(
        self, 
        lobby_code: str, 
        user_id: str, 
        question_index: int, 
        answer: str, 
        time_taken: float, 
        is_correct: bool, 
        points: int
    ) -> bool:
        answer_record = {
            "question_index": question_index,
            "answer": answer,
            "time_taken": time_taken,
            "is_correct": is_correct,
            "points": points,
            "timestamp": datetime.now()
        }
        
        # Initialize list if not exists, then push
        # Using $push with upsert logic for the user key
        key = f"player_answers.{user_id}"
        
        result = self.collection.update_one(
            {"lobby_code": lobby_code},
            {
                "$push": {key: answer_record},
                "$set": {"updated_at": datetime.now()}
            }
        )
        return result.modified_count > 0

    def advance_question(self, lobby_code: str) -> int:
        """Increment current_question_index and return new index."""
        result = self.collection.find_one_and_update(
            {"lobby_code": lobby_code},
            {
                "$inc": {"current_question_index": 1},
                "$set": {
                    "question_start_time": datetime.now(),
                    "updated_at": datetime.now()
                }
            },
            return_document=True
        )
        if result:
            return result["current_question_index"]
        return -1

    def get_current_question(self, lobby_code: str) -> Optional[Dict[str, Any]]:
        session = self.get_game_session_by_lobby(lobby_code)
        if not session:
            return None
            
        idx = session["current_question_index"]
        if 0 <= idx < len(session["questions"]):
            return session["questions"][idx]
        return None

    def get_player_total_score(self, lobby_code: str, user_id: str) -> int:
        session = self.get_game_session_by_lobby(lobby_code)
        if not session:
            return 0
            
        answers = session.get("player_answers", {}).get(user_id, [])
        return sum(a["points"] for a in answers)

    def get_all_player_scores(self, lobby_code: str) -> Dict[str, int]:
        session = self.get_game_session_by_lobby(lobby_code)
        if not session:
            return {}
            
        scores = {}
        for user_id, answers in session.get("player_answers", {}).items():
            scores[user_id] = sum(a["points"] for a in answers)
        return scores

    def is_game_complete(self, lobby_code: str) -> bool:
        session = self.get_game_session_by_lobby(lobby_code)
        if not session:
            return True
            
        return session["current_question_index"] >= len(session["questions"])

    def fetch_questions_for_game(self, categories: List[str], difficulty: int, count: int) -> List[Dict[str, Any]]:
        """Generate multiple-choice questions for multiplayer game using AI.
        
        All questions are generated fresh for each game to ensure variety and prevent memorization.
        Uses the new generate_multiplayer_question method for structured JSON responses.
        """
        questions = []
        questions_per_category = count // len(categories) if categories else count
        remainder = count % len(categories) if categories else 0
        
        for i, category in enumerate(categories):
            needed = questions_per_category + (1 if i < remainder else 0)
            
            # Generate questions using AI with structured output
            for _ in range(needed):
                try:
                    # Get random keyword for variety
                    keyword = self.quiz_repository.get_random_keyword(category)
                    if not keyword:
                        keyword = "general"
                    
                    # Generate structured multiple-choice question
                    question_data = self.ai_service.generate_multiplayer_question(
                        category=category,
                        subcategory="General",  # Could be enhanced to fetch real subcategory
                        keyword=keyword,
                        difficulty=difficulty,
                        style_modifier=None  # Random style could be added here
                    )
                    
                    # Format for game session storage
                    questions.append({
                        "question_text": question_data["question"],
                        "options": question_data["options"],
                        "correct_answer": question_data["correct_answer"],
                        "category": category,
                        "difficulty": difficulty,
                        "keyword": keyword
                    })
                    
                except Exception as e:
                    # Use proper logging instead of print
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.error(
                        "question_generation_failed category=%s keyword=%s difficulty=%d error=%s",
                        category, keyword, difficulty, str(e)
                    )
                    # Fail fast - don't return partial results
                    raise ValueError(
                        f"Failed to generate question for {category}/{keyword}: {str(e)}"
                    ) from e
        
        # All questions generated successfully
        return questions

    def fetch_questions_from_list(self, question_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Generate questions from a structured question list.
        
        Each entry in question_list should have:
        - category: Category name
        - subject: Subject/subcategory name
        - difficulty: Difficulty level (1-3)
        - count: Number of questions to generate
        
        Args:
            question_list: List of question set configurations
            
        Returns:
            List of generated question dictionaries
        """
        import logging
        logger = logging.getLogger(__name__)
        
        all_questions = []
        
        for question_set in question_list:
            category = question_set.get('category')
            subject = question_set.get('subject', 'General')
            difficulty = question_set.get('difficulty', 2)
            count = question_set.get('count', 1)
            
            logger.info("generating_questions category=%s subject=%s difficulty=%d count=%d",
                       category, subject, difficulty, count)
            
            # Generate questions for this set
            for _ in range(count):
                try:
                    # Get random keyword for variety
                    keyword = self.quiz_repository.get_random_keyword(category)
                    if not keyword:
                        keyword = "general"
                    
                    # Generate structured multiple-choice question with proper subcategory
                    question_data = self.ai_service.generate_multiplayer_question(
                        category=category,
                        subcategory=subject,  # Use the subject as subcategory
                        keyword=keyword,
                        difficulty=difficulty,
                        style_modifier=None
                    )
                    
                    # Format for game session storage
                    all_questions.append({
                        "question_text": question_data["question"],
                        "options": question_data["options"],
                        "correct_answer": question_data["correct_answer"],
                        "category": category,
                        "subject": subject,
                        "difficulty": difficulty,
                        "keyword": keyword
                    })
                    
                except Exception as e:
                    # Fail fast - don't create partial/broken game
                    logger.error(
                        "question_generation_failed category=%s subject=%s difficulty=%d "
                        "generated=%d/%d error=%s",
                        category, subject, difficulty, len(all_questions), 
                        sum(qs.get('count', 1) for qs in question_list), str(e)
                    )
                    raise ValueError(
                        f"Failed to generate question for {category}/{subject}: {str(e)}"
                    ) from e
        
        # Validate we generated all expected questions
        total_expected = sum(qs.get('count', 1) for qs in question_list)
        if len(all_questions) != total_expected:
            raise ValueError(
                f"Generated {len(all_questions)} questions but expected {total_expected}"
            )
        
        logger.info("questions_generated total=%d", len(all_questions))
        return all_questions
