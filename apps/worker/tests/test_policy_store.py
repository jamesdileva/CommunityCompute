"""Sprint 11: policy persistence + CLI pause/resume."""

import json

from worker.policy.schema import AvailabilityPolicy
from worker.policy.store import load_policy, policy_path, save_policy, set_paused


def test_missing_file_gives_defaults(tmp_path):
    assert load_policy(tmp_path / "none.json") == AvailabilityPolicy()


def test_round_trip(tmp_path):
    path = tmp_path / "policy.json"
    policy = AvailabilityPolicy(idle_only=True, max_cpu_percent=42.5,
                                battery_policy="plugged_only")
    save_policy(path, policy)
    assert load_policy(path) == policy


def test_corrupt_file_gives_defaults(tmp_path):
    path = tmp_path / "policy.json"
    path.write_text("{not json at all", encoding="utf-8")
    assert load_policy(path) == AvailabilityPolicy()


def test_invalid_fields_give_defaults(tmp_path):
    path = tmp_path / "policy.json"
    path.write_text(json.dumps({"max_cpu_percent": 500}), encoding="utf-8")
    assert load_policy(path) == AvailabilityPolicy()


def test_set_paused_toggles(tmp_path):
    path = tmp_path / "policy.json"
    assert set_paused(path, True).paused is True
    assert load_policy(path).paused is True
    assert set_paused(path, False).paused is False
    assert load_policy(path).paused is False


def test_policy_path_beside_id_file(tmp_path):
    assert policy_path(tmp_path / ".worker_id").name == "policy.json"
    assert policy_path(tmp_path / ".worker_id").parent == tmp_path
