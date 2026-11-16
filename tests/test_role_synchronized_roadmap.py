"""
Comprehensive Tests for Role-Synchronized Career Roadmap & Weekly Planner Synchronization.
Covers Part 5.1 (Roadmap) and Part 5.2 (Synchronization) without asyncio/TestClient hangs.
"""

import os
import shutil
import tempfile
import unittest

from backend.auth import hash_password
from backend.career_launchpad import (
    get_role_roadmap_with_progress,
    sync_weekly_plan_with_roadmap,
    toggle_roadmap_topic_completion,
    update_weekly_task_and_rebalance,
)
from backend.career_roadmap_registry import (
    CURRICULUM_REGISTRY,
    audit_curriculum_coverage,
    get_verified_curriculum,
)
from backend.database import get_db, init_db, new_id, utc_now


class TestRoleSynchronizedCareerRoadmap(unittest.TestCase):
    _PW_HASH: str = ""
    temp_dir: str = ""
    user_a_id: str = ""
    user_b_id: str = ""

    @classmethod
    def setUpClass(cls) -> None:
        cls._PW_HASH = hash_password("RoadmapTest123!")
        cls.temp_dir = tempfile.mkdtemp(prefix="studyos_role_rm_")
        os.environ.pop("VERCEL", None)
        os.environ["MONGODB_URI"] = ""
        os.environ["BRAINOVA_DATA_DIR"] = cls.temp_dir
        os.environ["AETHER_DB_PATH"] = os.path.join(cls.temp_dir, "role_rm.db")
        init_db()

        cls.user_a_id = new_id("usr")
        cls.user_b_id = new_id("usr")
        now = utc_now()
        with get_db(commit=True) as conn:
            for uid, name in ((cls.user_a_id, "User Alpha"), (cls.user_b_id, "User Beta")):
                conn.execute(
                    """
                    INSERT INTO users (id, email, name, password_hash, role, target_role, bio, avatar_color, created_at, updated_at)
                    VALUES (?, ?, ?, ?, 'Learner', 'Full Stack Developer', '', '#d6b56d', ?, ?)
                    """,
                    (uid, f"{uid}@example.com", name, cls._PW_HASH, now, now),
                )

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def test_01_all_verified_curricula_have_valid_prerequisites(self) -> None:
        self.assertGreaterEqual(len(CURRICULUM_REGISTRY), 13)
        for role_key, entry in CURRICULUM_REGISTRY.items():
            audit = audit_curriculum_coverage(entry)
            self.assertTrue(
                audit["prerequisites_valid"],
                f"Broken prereqs in {role_key}: {audit['broken_prerequisite_refs']}",
            )
            self.assertGreater(audit["topic_count"], 0)

    def test_02_full_stack_and_quantum_curricula_are_distinct(self) -> None:
        fs = get_verified_curriculum("Full Stack Developer")
        qc = get_verified_curriculum("Quantum Computing Engineer")
        self.assertTrue(fs["verified"])
        self.assertTrue(qc["verified"])
        self.assertEqual(len(fs["categories"]), 43)
        self.assertEqual(len(qc["categories"]), 40)

        fs_ids = {t["topic_id"] for c in fs["categories"] for t in c["topics"]}
        qc_ids = {t["topic_id"] for c in qc["categories"] for t in c["topics"]}
        self.assertEqual(fs_ids & qc_ids, set())

        unverified = get_verified_curriculum("Underwater Basket Weaver")
        self.assertFalse(unverified["verified"])
        self.assertIn("not yet available", unverified["unavailable_reason"].lower())

    def test_03_topic_completion_persists_per_user_and_per_role(self) -> None:
        with get_db(commit=True) as conn:
            prof_a = {"target_career": "Full Stack Developer", "available_hours_per_week": 10}
            res1 = toggle_roadmap_topic_completion(
                conn, self.user_a_id, "Full Stack Developer", "fs_cs_01", True, prof_a
            )
            self.assertIsNotNone(res1)
            rm_fs = res1["roadmap"]
            self.assertEqual(rm_fs["completed_topics"], 1)
            self.assertEqual(rm_fs["categories"][0]["completed_count"], 1)

            # User B remains at 0 completed topics
            rm_b = get_role_roadmap_with_progress(conn, self.user_b_id, "Full Stack Developer")
            self.assertEqual(rm_b["completed_topics"], 0)

            # Switching User A to Quantum Computing starts at 0 completed
            rm_qc = get_role_roadmap_with_progress(conn, self.user_a_id, "Quantum Computing Engineer")
            self.assertEqual(rm_qc["completed_topics"], 0)

            # Completing a Quantum topic does not touch Full Stack
            toggle_roadmap_topic_completion(
                conn,
                self.user_a_id,
                "Quantum Computing Engineer",
                "qc_math_01",
                True,
                {"target_career": "Quantum Computing Engineer", "available_hours_per_week": 10},
            )
            rm_fs_restored = get_role_roadmap_with_progress(conn, self.user_a_id, "Full Stack Developer")
            self.assertEqual(rm_fs_restored["completed_topics"], 1)

            # Uncompleting reverses progress cleanly
            res_un = toggle_roadmap_topic_completion(
                conn, self.user_a_id, "Full Stack Developer", "fs_cs_01", False, prof_a
            )
            self.assertEqual(res_un["roadmap"]["completed_topics"], 0)

    def test_04_role_switch_and_completion_synchronize_weekly_planner(self) -> None:
        with get_db(commit=True) as conn:
            # Start with Full Stack Developer
            prof_fs = {"target_career": "Full Stack Developer", "available_hours_per_week": 8}
            tasks_fs = sync_weekly_plan_with_roadmap(conn, self.user_a_id, prof_fs)
            self.assertGreater(len(tasks_fs), 0)
            self.assertTrue(all(t["role_key"] == "full_stack_developer" for t in tasks_fs))
            total_planned = sum(t["planned_minutes"] for t in tasks_fs)
            self.assertLessEqual(total_planned, 8 * 60)

            # Manually reschedule first task -> sets is_manual=1
            manual = update_weekly_task_and_rebalance(
                conn, self.user_a_id, tasks_fs[0]["id"], day_of_week="Sat"
            )
            self.assertEqual(manual["is_manual"], 1)

            # Switch to Quantum Computing Engineer
            prof_qc = {"target_career": "Quantum Computing Engineer", "available_hours_per_week": 8}
            tasks_qc = sync_weekly_plan_with_roadmap(conn, self.user_a_id, prof_qc)
            non_manual_qc = [t for t in tasks_qc if not t.get("is_manual")]
            self.assertGreater(len(non_manual_qc), 0)
            self.assertTrue(all(t["role_key"] == "quantum_computing_engineer" for t in non_manual_qc))
            # Manual task from earlier was preserved
            self.assertTrue(any(t["id"] == tasks_fs[0]["id"] for t in tasks_qc))

            # Completing a scheduled Quantum topic removes/completes it and schedules next eligible topic
            first_qc_tid = non_manual_qc[0]["topic_id"]
            res = toggle_roadmap_topic_completion(
                conn, self.user_a_id, "Quantum Computing Engineer", first_qc_tid, True, prof_qc
            )
            pending_qc_tids = {
                t["topic_id"]
                for t in res["weekly_tasks"]
                if t.get("role_key") == "quantum_computing_engineer" and t.get("status") == "pending"
            }
            self.assertNotIn(first_qc_tid, pending_qc_tids)

    def test_05_settings_and_career_profile_single_source_of_truth_and_3_role_progress(self) -> None:
        from backend.main import CareerProfileUpdateRequest, ProfileUpdateRequest, update_career_profile, update_profile

        with get_db(commit=True) as conn:
            u_a = conn.execute("SELECT * FROM users WHERE id = ?", (self.user_a_id,)).fetchone()
            u_b = conn.execute("SELECT * FROM users WHERE id = ?", (self.user_b_id,)).fetchone()

        # 1. Updating Primary Career Role in Settings updates career_profiles & weekly tasks
        res_settings = update_profile(
            ProfileUpdateRequest(target_role="Backend Developer"),
            current_user=dict(u_a),
        )
        self.assertEqual(res_settings["user"]["target_role"], "Backend Developer")
        with get_db() as conn:
            cp_a = conn.execute("SELECT target_career FROM career_profiles WHERE user_id = ?", (self.user_a_id,)).fetchone()
            self.assertEqual(cp_a["target_career"], "Backend Developer")

        # 2. Updating Career Profile updates users.target_role & returns synced roadmap + weekly_tasks
        res_cp = update_career_profile(
            CareerProfileUpdateRequest(
                target_career="Full Stack Developer",
                target_job_role="Full Stack Engineer",
                target_company="",
                graduation_year=2026,
                current_skill_level="Intermediate",
                available_hours_per_week=10,
                target_deadline="",
            ),
            current_user=dict(u_a),
        )
        self.assertEqual(res_cp["career_roadmap"]["role_key"], "full_stack_developer")
        self.assertTrue(
            all(
                t["role_key"] == "full_stack_developer"
                for t in res_cp["weekly_tasks"]
                if not t.get("is_manual") and t.get("status") in ("pending", "rescheduled")
            )
        )
        with get_db() as conn:
            user_row = conn.execute("SELECT target_role FROM users WHERE id = ?", (self.user_a_id,)).fetchone()
            self.assertEqual(user_row["target_role"], "Full Stack Developer")

        # 3. 3-role progress preservation (Full Stack: 2, Backend: 2, Quantitative: 1) + User B isolated
        with get_db(commit=True) as conn:
            for tid in ("fs_cs_01", "fs_cs_02"):
                toggle_roadmap_topic_completion(conn, self.user_a_id, "Full Stack Developer", tid, True, {"target_career": "Full Stack Developer", "available_hours_per_week": 10})
            for tid in ("be_dsa", "be_oop"):
                toggle_roadmap_topic_completion(conn, self.user_a_id, "Backend Developer", tid, True, {"target_career": "Backend Developer", "available_hours_per_week": 10})
            toggle_roadmap_topic_completion(conn, self.user_a_id, "Quantitative Developer", "qd_la_calc", True, {"target_career": "Quantitative Developer", "available_hours_per_week": 10})

            self.assertEqual(get_role_roadmap_with_progress(conn, self.user_a_id, "Full Stack Developer")["completed_topics"], 2)
            self.assertEqual(get_role_roadmap_with_progress(conn, self.user_a_id, "Backend Developer")["completed_topics"], 2)
            self.assertEqual(get_role_roadmap_with_progress(conn, self.user_a_id, "Quantitative Developer")["completed_topics"], 1)
            self.assertEqual(get_role_roadmap_with_progress(conn, self.user_b_id, "Backend Developer")["completed_topics"], 0)
            self.assertEqual(dict(u_b)["target_role"], "Full Stack Developer")
