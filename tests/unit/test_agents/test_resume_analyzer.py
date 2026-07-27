import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../functions')))

from agents.resume_analyzer import ResumeAnalyzerAgent

def mock_chat_json(system, user, task_type):
    return {
        "uid": "123",
        "name": "John Doe",
        "current_role": "Software Engineer",
        "experience_level": 5,
        "skill_graph": {
            "skills": ["Python", "FastAPI"]
        }
    }

def test_resume_analyzer(monkeypatch):
    import llm.client
    monkeypatch.setattr(llm.client.llm, "chat_json", mock_chat_json)
    
    agent = ResumeAnalyzerAgent()
    # Passing a mock txt file
    profile = agent.analyze(b"John Doe\nPython Dev", "resume.txt")
    
    assert profile is not None
    assert profile["name"] == "John Doe"
    assert "Python" in profile["skill_graph"]["skills"]
