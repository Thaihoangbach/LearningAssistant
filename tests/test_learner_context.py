import os
import sys
import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.services.learner_context import build_learner_context
from app.models import Base, LearningProfile, MasteryScore, Topic


class LearnerContextTestCase(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=self.engine)
        self.db = sessionmaker(bind=self.engine)()

    def tearDown(self):
        self.db.close()

    def _seed_topic_score(self, user_id, name, score):
        topic = Topic(user_id=user_id, name=name)
        self.db.add(topic)
        self.db.commit()
        self.db.add(MasteryScore(user_id=user_id, topic_id=topic.id, score=score))
        self.db.commit()
        return topic


def no_recall(*args, **kwargs):
    return []


class TestLevelResolution(LearnerContextTestCase):
    def test_explicit_level_wins(self):
        self.db.add(LearningProfile(user_id="u1", preferred_level="advanced"))
        self.db.commit()
        ctx = build_learner_context(self.db, "u1", requested_level="beginner", recall_fn=no_recall)
        self.assertEqual(ctx.effective_level, "beginner")

    def test_explicit_level_is_persisted_as_new_preference(self):
        build_learner_context(self.db, "u1", requested_level="advanced", recall_fn=no_recall)
        profile = self.db.query(LearningProfile).filter(LearningProfile.user_id == "u1").first()
        self.assertEqual(profile.preferred_level, "advanced")

    def test_falls_back_to_stored_preference(self):
        self.db.add(LearningProfile(user_id="u1", preferred_level="advanced"))
        self.db.commit()
        ctx = build_learner_context(self.db, "u1", recall_fn=no_recall)
        self.assertEqual(ctx.effective_level, "advanced")

    def test_infers_beginner_from_low_mastery_when_never_declared(self):
        self._seed_topic_score("u1", "Backpropagation", 0.1)
        ctx = build_learner_context(self.db, "u1", recall_fn=no_recall)
        self.assertEqual(ctx.effective_level, "beginner")

    def test_returns_none_when_nothing_known(self):
        ctx = build_learner_context(self.db, "u1", recall_fn=no_recall)
        self.assertIsNone(ctx.effective_level)

    def test_absent_level_does_not_overwrite_stored_preference(self):
        self.db.add(LearningProfile(user_id="u1", preferred_level="advanced"))
        self.db.commit()
        build_learner_context(self.db, "u1", recall_fn=no_recall)
        profile = self.db.query(LearningProfile).filter(LearningProfile.user_id == "u1").first()
        self.assertEqual(profile.preferred_level, "advanced")


class TestGoalAndWeakTopics(LearnerContextTestCase):
    def test_returns_stored_learning_goal(self):
        self.db.add(LearningProfile(user_id="u1", learning_goal="Ôn thi cuối kỳ"))
        self.db.commit()
        ctx = build_learner_context(self.db, "u1", recall_fn=no_recall)
        self.assertEqual(ctx.learning_goal, "Ôn thi cuối kỳ")

    def test_weak_topics_lists_only_low_scores(self):
        self._seed_topic_score("u1", "Backpropagation", 0.2)
        self._seed_topic_score("u1", "Decision Tree", 0.9)
        ctx = build_learner_context(self.db, "u1", recall_fn=no_recall)
        self.assertEqual(ctx.weak_topics, ["Backpropagation"])

    def test_weak_topics_empty_when_no_data(self):
        ctx = build_learner_context(self.db, "u1", recall_fn=no_recall)
        self.assertEqual(ctx.weak_topics, [])


class TestRecall(LearnerContextTestCase):
    def test_recall_is_skipped_without_query(self):
        calls = []

        def spy_recall(*args, **kwargs):
            calls.append(kwargs)
            return []

        build_learner_context(self.db, "u1", recall_fn=spy_recall)
        self.assertEqual(calls, [])

    def test_recalled_contents_are_returned_as_plain_strings(self):
        class FakeEvent:
            content = "Lần trước bạn sai câu về learning rate"

        ctx = build_learner_context(
            self.db, "u1", query="gradient descent", recall_fn=lambda *a, **k: [FakeEvent()]
        )
        self.assertEqual(ctx.recalled_events, ["Lần trước bạn sai câu về learning rate"])


if __name__ == "__main__":
    unittest.main()
