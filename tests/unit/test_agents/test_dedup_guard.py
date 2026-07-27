import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../functions')))

from cache.dedup_guard import DedupGuard
from db.models import Job

class MockRedis:
    def __init__(self):
        self.data = {}
        self.sets = {}
        
    def get(self, key):
        return self.data.get(key)
        
    def set(self, key, val, ex=None):
        self.data[key] = val
        return True
        
    def incr(self, key):
        val = int(self.data.get(key, 0)) + 1
        self.data[key] = str(val)
        return val
        
    def sismember(self, key, member):
        return member in self.sets.get(key, set())
        
    def sadd(self, key, *members):
        if key not in self.sets:
            self.sets[key] = set()
        for m in members:
            self.sets[key].add(m)
        return len(members)
        
    def expire(self, key, seconds):
        return True

def test_dedup_guard_spam(monkeypatch):
    import cache.dedup_guard
    mock_redis = MockRedis()
    monkeypatch.setattr(sys.modules["cache.dedup_guard"], "redis_client", mock_redis)
    
    guard = DedupGuard()
    guard.spam_threshold = 2
    
    jobs = [
        Job(title="Software Engineer", company="Google", location="Bangalore", portal="naukri", url="1"),
        Job(title="Software Engineer", company="Google", location="Bangalore", portal="linkedin", url="2"),
        Job(title="Software Engineer", company="Google", location="Bangalore", portal="indeed", url="3")
    ]
    
    passed, dropped = guard.filter_jobs("user1", jobs)
    
    assert len(passed) == 2
    assert dropped == 1
    
def test_dedup_guard_seen(monkeypatch):
    import cache.dedup_guard
    mock_redis = MockRedis()
    monkeypatch.setattr(sys.modules["cache.dedup_guard"], "redis_client", mock_redis)
    
    guard = DedupGuard()
    
    jobs1 = [Job(title="Dev", company="Meta", location="Pune", portal="naukri", job_id="meta123", url="x")]
    
    passed1, dropped1 = guard.filter_jobs("user1", jobs1)
    assert len(passed1) == 1
    assert dropped1 == 0
    
    # Try filtering the exact same job for the same user
    passed2, dropped2 = guard.filter_jobs("user1", jobs1)
    assert len(passed2) == 0
    assert dropped2 == 1
