from domain.settings import CURRENT_VERSION
from infrastructure.config.config_migrator import ConfigMigrator


def _make_migration(from_v, to_v, call_log=None):
    def fn(data):
        if call_log is not None:
            call_log.append(from_v)
        data["version"] = to_v
        return data

    return fn


class TestNoMigrationNeeded:
    def test_returns_same_data_when_version_is_current(self):
        migrator = ConfigMigrator()
        migrator.migrations = {}
        data = {"version": CURRENT_VERSION, "key": "value"}

        result, was_migrated = migrator.migrate(data)

        assert result == data
        assert result is data
        assert was_migrated is False


class TestMigrationToV7:
    def test_adds_pusd_to_existing_stablecoins(self):
        migrator = ConfigMigrator()
        data = {
            "version": 6,
            "assets": {"crypto": {"stablecoins": ["USDC"]}},
        }

        result, was_migrated = migrator.migrate(data)

        assert was_migrated is True
        assert result["version"] == CURRENT_VERSION
        assert result["assets"]["crypto"]["stablecoins"] == ["USDC", "PUSD"]

    def test_adds_pusd_when_stablecoins_are_missing(self):
        migrator = ConfigMigrator()
        data = {"version": 6, "assets": {"crypto": {}}}

        result, _ = migrator.migrate(data)

        assert result["assets"]["crypto"]["stablecoins"] == ["PUSD"]

    def test_does_not_duplicate_existing_pusd(self):
        migrator = ConfigMigrator()
        data = {
            "version": 6,
            "assets": {"crypto": {"stablecoins": ["PUSD", "USDC"]}},
        }

        result, _ = migrator.migrate(data)

        assert result["assets"]["crypto"]["stablecoins"] == ["PUSD", "USDC"]


class TestMigrationToV8:
    def test_adds_quick_edit_mode_to_existing_config(self):
        migrator = ConfigMigrator()
        data = {
            "version": 7,
            "general": {"defaultCurrency": "EUR"},
        }

        result, was_migrated = migrator.migrate(data)

        assert was_migrated is True
        assert result["version"] == CURRENT_VERSION
        assert result["general"]["editMode"] == "QUICK"

    def test_preserves_existing_edit_mode(self):
        migrator = ConfigMigrator()
        data = {
            "version": 7,
            "general": {"editMode": "DRAFT"},
        }

        result, _ = migrator.migrate(data)

        assert result["general"]["editMode"] == "DRAFT"


class TestMigrationFromMissingVersion:
    def test_assumes_version_1_and_applies_all_migrations(self):
        migrator = ConfigMigrator()
        call_log = []
        migrator.migrations = {
            1: _make_migration(1, 2, call_log),
            2: _make_migration(2, 3, call_log),
            3: _make_migration(3, 4, call_log),
        }

        result, was_migrated = migrator.migrate({"key": "value"})

        assert was_migrated is True
        assert result["version"] == 4
        assert call_log == [1, 2, 3]
        assert result["key"] == "value"


class TestMigrationFromSpecificVersion:
    def test_migrates_from_v3_skipping_earlier_versions(self):
        migrator = ConfigMigrator()
        call_log = []
        migrator.migrations = {
            1: _make_migration(1, 2, call_log),
            2: _make_migration(2, 3, call_log),
            3: _make_migration(3, 4, call_log),
            4: _make_migration(4, 5, call_log),
        }

        result, was_migrated = migrator.migrate({"version": 3, "key": "value"})

        assert was_migrated is True
        assert result["version"] == 5
        assert call_log == [3, 4]
        assert result["key"] == "value"


class TestStopsMigratingWhenNoFunction:
    def test_stops_when_no_migration_exists_for_version(self):
        migrator = ConfigMigrator()
        migrator.migrations = {}

        result, was_migrated = migrator.migrate({"version": 99})

        assert result["version"] == 99
        assert was_migrated is False

    def test_stops_at_gap_in_migration_chain(self):
        migrator = ConfigMigrator()
        migrator.migrations = {1: _make_migration(1, 2)}

        result, was_migrated = migrator.migrate({"version": 1})

        assert result["version"] == 2
        assert was_migrated is True


class TestDeepCopy:
    def test_original_data_not_mutated_during_migration(self):
        migrator = ConfigMigrator()

        def mutating_migration(data):
            data["version"] = 2
            data["added"] = "new_value"
            data["nested"] = {"key": "value"}
            return data

        migrator.migrations = {1: mutating_migration}
        original = {"version": 1, "existing": "unchanged"}

        result, _ = migrator.migrate(original)

        assert original["version"] == 1
        assert "added" not in original
        assert "nested" not in original
        assert original["existing"] == "unchanged"
        assert result["version"] == 2
        assert result["added"] == "new_value"
