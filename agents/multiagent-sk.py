# === Agent 1: Sentiment Skill ===
class SentimentSkill:
    def run(self, text: str) -> str:
        if "excellent" in text.lower():
            return "positive"
        elif "poor" in text.lower():
            return "negative"
        else:
            return "neutral"

# === Agent 2: Feedback Skill ===
class FeedbackSkill:
    def run(self, text: str, sentiment: str) -> str:
        if sentiment == "positive":
            return "Your resume reflects strong qualities. Keep it up!"
        elif sentiment == "negative":
            return "Consider revising your resume to better highlight your strengths."
        else:
            return "Your resume is balanced. You could enhance it with more achievements."

# === Orchestrator ===
class ResumeOrchestrator:
    def __init__(self):
        self.sentiment_skill = SentimentSkill()
        self.feedback_skill = FeedbackSkill()

    def run(self, text: str) -> dict:
        sentiment = self.sentiment_skill.run(text)
        feedback = self.feedback_skill.run(text, sentiment)
        return {
            "sentiment": sentiment,
            "feedback": feedback
        }

# === Example Usage ===
if __name__ == "__main__":
    resume_text = "John is an excellent team player with strong leadership skills."
    orchestrator = ResumeOrchestrator()
    result = orchestrator.run(resume_text)
    print("Sentiment:", result["sentiment"])
    print("Feedback:", result["feedback"])