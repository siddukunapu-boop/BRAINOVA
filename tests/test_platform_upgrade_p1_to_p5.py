"""
Comprehensive Regression & Verification Suite for StudyOS Premium Upgrade (Priorities 2-5).
"""

import os
import shutil
import tempfile
import unittest
from unittest.mock import patch
from fastapi import HTTPException
from starlette.requests import Request

from backend.auth import create_access_token, get_current_user, hash_password
from backend.career_launchpad import (
    compute_career_readiness_intelligence,
    compute_skill_gap_and_readiness,
    generate_adaptive_weekly_plan,
    record_spaced_repetition_attempt,
    simulate_readiness_projection,
    update_weekly_task_and_rebalance,
)
from backend.database import get_db, init_db, new_id, utc_now
from backend.main import app, tech_pulse_cron_ingest, tech_pulse_diagnostics
from backend.music_service import list_music_library_for_user
from backend.roadmap_curriculum import (
    NON_TECHNICAL_ROLES,
    TECHNICAL_ROLES,
    build_comprehensive_role_curriculum,
    get_supported_roles_catalog,
    validate_roadmap_curriculum,
)


class TestStudyOSPremiumUpgrade(unittest.TestCase):
    _PW_HASH: str = ""
    temp_dir: str = ""
    user_id: str = ""
    admin_id: str = ""

    @classmethod
    def setUpClass(cls) -> None:
        cls._PW_HASH = hash_password("UpgradePass123!")
        cls.temp_dir = tempfile.mkdtemp(prefix="studyos_upgrade_test_")
        os.environ.pop("VERCEL", None)
        os.environ["MONGODB_URI"] = ""
        os.environ["BRAINOVA_DATA_DIR"] = cls.temp_dir
        os.environ["AETHER_DB_PATH"] = os.path.join(cls.temp_dir, "upgrade_test.db")
        init_db()

        cls.user_id = new_id("usr")
        cls.admin_id = new_id("usr")
        now = utc_now()
        with get_db(commit=True) as conn:
            conn.execute(
                """
                INSERT INTO users (id, email, name, password_hash, role, target_role, bio, avatar_color, created_at, updated_at)
                VALUES (?, ?, 'Student User', ?, 'Learner', 'Full Stack Developer', '', '#d6b56d', ?, ?)
                """,
                (cls.user_id, f"{cls.user_id}@example.com", cls._PW_HASH, now, now),
            )
            conn.execute(
                """
                INSERT INTO users (id, email, name, password_hash, role, target_role, bio, avatar_color, created_at, updated_at)
                VALUES (?, ?, 'Admin User', ?, 'admin', 'Software Architect', '', '#d6b56d', ?, ?)
                """,
                (cls.admin_id, f"{cls.admin_id}@example.com", cls._PW_HASH, now, now),
            )

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def test_01_roadmap_role_catalog_and_upsc_curriculum(self) -> None:
        catalog = get_supported_roles_catalog()
        self.assertGreaterEqual(len(TECHNICAL_ROLES), 30)
        self.assertGreaterEqual(len(NON_TECHNICAL_ROLES), 14)
        self.assertGreaterEqual(catalog["total_roles"], 44)

        ias = build_comprehensive_role_curriculum("IAS / Civil Services", "Intermediate", 20)
        self.assertGreaterEqual(len(ias["phases"]), 5)
        all_titles = " ".join(
            t["title"] for p in ias["phases"] for t in p["topics"]
        )
        self.assertIn("UPSC CSE", all_titles)
        self.assertIn("CSAT", all_titles)
        self.assertIn("Mains", all_titles)

        quality = validate_roadmap_curriculum(ias)
        self.assertTrue(quality["english_only_verified"])
        self.assertEqual(quality["duplicate_resource_warnings"], [])
        self.assertGreater(quality["coverage_percentage"], 70)
        self.assertLessEqual(quality["coverage_percentage"], 96)

    def test_02_quantitative_developer_curriculum_distinct_from_upsc(self) -> None:
        quant = build_comprehensive_role_curriculum("Quantitative Developer", "Advanced", 15)
        quant_text = " ".join(t["title"] for p in quant["phases"] for t in p["topics"])
        self.assertIn("Stochastic", quant_text)
        self.assertIn("Market Microstructure", quant_text)
        self.assertNotIn("UPSC", quant_text)

    def test_03_career_readiness_intelligence_and_simulator(self) -> None:
        latest = {
            "category_scores_json": '{"programming": 82, "dsa": 45, "dbms": 60}',
            "project_evidence_json": '{"deployed_projects": 1, "has_github_portfolio": true, "has_automated_tests": false}',
        }
        gap = compute_skill_gap_and_readiness(
            target_career="Software Engineer",
            latest_assessment=latest,
            roadmap_stats={"overall_progress_percent": 40},
            quiz_stats={"attempts_count": 3, "average_percentage": 75.0},
        )
        intel = compute_career_readiness_intelligence(
            target_career="Software Engineer",
            gap_analysis=gap,
            latest_assessment=latest,
            quiz_stats={"attempts_count": 3, "average_percentage": 75.0},
            roadmap_stats={"overall_progress_percent": 40},
        )
        self.assertGreaterEqual(len(intel["competency_dimensions"]), 3)
        self.assertGreaterEqual(len(intel["top_next_actions"]), 1)

        sim = simulate_readiness_projection(
            target_career="Software Engineer",
            latest_assessment=latest,
            boosts={"dsa": 30},
            roadmap_stats={"overall_progress_percent": 40},
            quiz_stats={"attempts_count": 3, "average_percentage": 75.0},
        )
        self.assertTrue(sim["is_projection"])
        self.assertGreater(sim["projected_indicator"], sim["baseline_indicator"])

    def test_04_adaptive_weekly_planner_and_spaced_repetition_integration(self) -> None:
        with get_db(commit=True) as conn:
            profile = {"available_hours_per_week": 10}
            gap = {"priority_areas": [{"category": "dsa", "label": "DSA", "gap": 35}]}
            tasks = generate_adaptive_weekly_plan(conn, self.user_id, profile, gap, preserve_existing=False)
            self.assertGreaterEqual(len(tasks), 3)

            # Marking a task missed automatically reschedules it to next day
            updated = update_weekly_task_and_rebalance(
                conn, self.user_id, tasks[0]["id"], status="missed"
            )
            self.assertIsNotNone(updated)
            self.assertEqual(updated["status"], "rescheduled")
            self.assertEqual(updated["priority"], "critical")

            # Weak spaced repetition (<60%) resets interval to 1 and injects revision task
            weak_rev = record_spaced_repetition_attempt(
                conn,
                self.user_id,
                topic_key="dynamic_programming",
                topic_title="Dynamic Programming",
                skill_category="dsa",
                score_percent=45.0,
            )
            self.assertEqual(weak_rev["interval_days"], 1)
            injected = conn.execute(
                "SELECT * FROM career_weekly_tasks WHERE user_id = ? AND source_type = 'spaced_repetition'",
                (self.user_id,),
            ).fetchall()
            self.assertGreaterEqual(len(injected), 1)

            # Strong spaced repetition (>=80%) expands interval
            strong_rev = record_spaced_repetition_attempt(
                conn,
                self.user_id,
                topic_key="dynamic_programming",
                topic_title="Dynamic Programming",
                skill_category="dsa",
                score_percent=90.0,
            )
            self.assertGreaterEqual(strong_rev["interval_days"], 3)

    def test_05_music_library_has_no_builtin_songs(self) -> None:
        with get_db() as conn:
            lib = list_music_library_for_user(conn, self.user_id)
        self.assertEqual(lib["builtin_tracks"], [])
        self.assertEqual(len(lib["categories"]), 1)
        self.assertEqual(lib["categories"][0]["id"], "uploaded")

    def test_06_tech_pulse_diagnostics_admin_only_and_cron_secret(self) -> None:
        def _make_request(path: str, auth_header: str = "") -> Request:
            headers = []
            if auth_header:
                headers.append((b"authorization", auth_header.encode("utf-8")))
            return Request(
                {
                    "type": "http",
                    "method": "GET",
                    "path": path,
                    "headers": headers,
                    "query_string": b"",
                }
            )

        learner_token = create_access_token(self.user_id, f"{self.user_id}@example.com")
        admin_token = create_access_token(self.admin_id, f"{self.admin_id}@example.com")

        prev_secret = os.environ.get("CRON_SECRET")
        prev_disable_sched = os.environ.get("BRAINOVA_DISABLE_SCHEDULER")
        os.environ["BRAINOVA_DISABLE_SCHEDULER"] = "1"
        os.environ["CRON_SECRET"] = "test-cron-secret"

        try:
            with patch(
                "backend.main.run_ingestion_cycle",
                return_value={
                    "status": "completed",
                    "sources_checked": 1,
                    "discovered_count": 0,
                    "published_count": 0,
                },
            ) as mock_ingest:
                # 1. Unauthenticated request without Bearer token is rejected (401)
                with self.assertRaises(HTTPException) as unauth_ctx:
                    get_current_user(_make_request("/api/tech-pulse/diagnostics"), authorization=None)
                self.assertEqual(unauth_ctx.exception.status_code, 401)

                # 2. Ordinary learner is rejected (403)
                learner_user = get_current_user(
                    _make_request("/api/tech-pulse/diagnostics", f"Bearer {learner_token}"),
                    authorization=f"Bearer {learner_token}",
                )
                with self.assertRaises(HTTPException) as forbidden_ctx:
                    tech_pulse_diagnostics(current_user=learner_user)
                self.assertEqual(forbidden_ctx.exception.status_code, 403)

                # 3. Admin user is allowed (200-equivalent dict with sources & recent_runs)
                admin_user = get_current_user(
                    _make_request("/api/tech-pulse/diagnostics", f"Bearer {admin_token}"),
                    authorization=f"Bearer {admin_token}",
                )
                diag = tech_pulse_diagnostics(current_user=admin_user)
                self.assertIn("sources", diag)
                self.assertIn("recent_runs", diag)

                # 4. Missing or wrong CRON_SECRET is rejected (401)
                with self.assertRaises(HTTPException) as cron_missing_ctx:
                    tech_pulse_cron_ingest(_make_request("/api/cron/tech-pulse"))
                self.assertEqual(cron_missing_ctx.exception.status_code, 401)

                with self.assertRaises(HTTPException) as cron_wrong_ctx:
                    tech_pulse_cron_ingest(
                        _make_request("/api/cron/tech-pulse", "Bearer wrong-secret")
                    )
                self.assertEqual(cron_wrong_ctx.exception.status_code, 401)

                # 5. Valid CRON_SECRET invokes ingestion safely
                res = tech_pulse_cron_ingest(
                    _make_request("/api/cron/tech-pulse", "Bearer test-cron-secret")
                )
                self.assertTrue(res.get("ok"))
                mock_ingest.assert_called_once()
        finally:
            if prev_secret is None:
                os.environ.pop("CRON_SECRET", None)
            else:
                os.environ["CRON_SECRET"] = prev_secret
            if prev_disable_sched is None:
                os.environ.pop("BRAINOVA_DISABLE_SCHEDULER", None)
            else:
                os.environ["BRAINOVA_DISABLE_SCHEDULER"] = prev_disable_sched
