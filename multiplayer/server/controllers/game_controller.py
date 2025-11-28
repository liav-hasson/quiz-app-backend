from typing import Dict, Any, List
from server.models.repositories.game_session_repository import GameSessionRepository
from server.models.repositories.lobby_repository import LobbyRepository
from server.models.repositories.multiplayer_xp_repository import MultiplayerXPRepository

class GameController:
    def __init__(
        self, 
        game_session_repository: GameSessionRepository,
        lobby_repository: LobbyRepository,
        multiplayer_xp_repository: MultiplayerXPRepository
    ):
        self.game_session_repository = game_session_repository
        self.lobby_repository = lobby_repository
        self.multiplayer_xp_repository = multiplayer_xp_repository

    def start_game(self, lobby_code: str) -> Dict[str, Any]:
        lobby = self.lobby_repository.get_lobby_by_code(lobby_code)
        if not lobby:
            raise ValueError("Lobby not found")
            
        # Fetch questions
        questions = self.game_session_repository.fetch_questions_for_game(
            lobby["categories"], 
            lobby["difficulty"], 
            count=5 # Default or from config
        )
        
        # Create session
        session = self.game_session_repository.create_game_session(
            lobby["_id"], lobby_code, questions
        )
        
        self.lobby_repository.update_lobby_status(lobby_code, "in_progress")
        return session

    def get_current_question(self, lobby_code: str) -> Dict[str, Any]:
        question = self.game_session_repository.get_current_question(lobby_code)
        if not question:
            return None
            
        # Return without correct answer
        session = self.game_session_repository.get_game_session_by_lobby(lobby_code)
        return {
            "question_text": question["question_text"],
            "options": question["options"],
            "category": question["category"],
            "index": session["current_question_index"],
            "total": len(session["questions"])
        }

    def get_question_results(self, lobby_code: str) -> Dict[str, Any]:
        """Get results for the current question (correct answer and scores)."""
        question = self.game_session_repository.get_current_question(lobby_code)
        scores = self.game_session_repository.get_all_player_scores(lobby_code)
        
        # Get answers for current question
        session = self.game_session_repository.get_game_session_by_lobby(lobby_code)
        current_index = session["current_question_index"]
        
        player_answers = {}
        for uid, answers in session.get("player_answers", {}).items():
            # Find answer for current index
            ans = next((a for a in answers if a["question_index"] == current_index), None)
            if ans:
                player_answers[uid] = ans["answer"]
        
        return {
            "correct_answer": question["correct_answer"],
            "player_scores": scores,
            "player_answers": player_answers
        }

    def submit_answer(self, lobby_code: str, user_id: str, answer: str, time_taken: float) -> Dict[str, Any]:
        session = self.game_session_repository.get_game_session_by_lobby(lobby_code)
        if not session:
            raise ValueError("Game session not found")
            
        current_question = self.game_session_repository.get_current_question(lobby_code)
        if not current_question:
            raise ValueError("No active question")
            
        # Check if already answered
        existing_answers = session.get("player_answers", {}).get(user_id, [])
        if any(a["question_index"] == session["current_question_index"] for a in existing_answers):
            raise ValueError("Already answered this question")

        is_correct = (answer == current_question["correct_answer"])
        
        # Calculate score
        lobby = self.lobby_repository.get_lobby_by_code(lobby_code)
        points = self.calculate_score(is_correct, time_taken, lobby["question_timer"])
        
        self.game_session_repository.record_player_answer(
            lobby_code, 
            user_id, 
            session["current_question_index"], 
            answer, 
            time_taken, 
            is_correct, 
            points
        )
        
        # Update total score in lobby for realtime display
        total_score = self.game_session_repository.get_player_total_score(lobby_code, user_id)
        self.lobby_repository.update_player_score(lobby_code, user_id, total_score)
        
        return {
            "is_correct": is_correct,
            "points_earned": points
        }

    def calculate_score(self, is_correct: bool, time_taken: float, timer_duration: int) -> int:
        if not is_correct:
            return 0
        
        base_points = 1000
        time_ratio = min(time_taken / timer_duration, 1.0)
        time_multiplier = 1 - (time_ratio * 0.5)
        
        points = int(base_points * time_multiplier)
        return max(points, 500)

    def advance_to_next_question(self, lobby_code: str) -> bool:
        new_index = self.game_session_repository.advance_question(lobby_code)
        session = self.game_session_repository.get_game_session_by_lobby(lobby_code)
        return new_index < len(session["questions"])

    def record_auto_fail(self, lobby_code: str, user_id: str, question_index: int):
        self.game_session_repository.record_player_answer(
            lobby_code, user_id, question_index, "", 0, False, 0
        )

    def finalize_game(self, lobby_code: str) -> Dict[str, Any]:
        game_session = self.game_session_repository.get_game_session_by_lobby(lobby_code)
        lobby = self.lobby_repository.get_lobby_by_code(lobby_code)
        
        player_scores = self.game_session_repository.get_all_player_scores(lobby_code)
        
        ranked_players = sorted(
            player_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        difficulty_multipliers = {1: 1.0, 2: 1.5, 3: 2.0}
        difficulty_multiplier = difficulty_multipliers.get(lobby['difficulty'], 1.0)
        
        xp_awarded = {}
        question_count = len(game_session['questions'])
        
        rankings = []
        for rank, (user_id, score) in enumerate(ranked_players, start=1):
            xp = int(score * difficulty_multiplier)
            if rank == 1:
                xp = int(xp * 1.2)
            
            self.multiplayer_xp_repository.award_game_xp(
                user_id=user_id,
                final_score=score,
                difficulty_multiplier=difficulty_multiplier,
                question_count=question_count
            )
            
            xp_awarded[user_id] = xp
            
            player = next((p for p in lobby['players'] if p['user_id'] == user_id), None)
            if player:
                rankings.append({
                    'rank': rank,
                    'user_id': user_id,
                    'username': player['username'],
                    'score': score,
                    'xp_earned': xp
                })
        
        self.lobby_repository.update_lobby_status(lobby_code, "completed")
        
        return {
            'rankings': rankings,
            'xp_awarded': xp_awarded
        }
