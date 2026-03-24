"""Smoke tests — verify that the package imports cleanly."""


def test_import_top_level() -> None:
    import pmod

    assert pmod.__version__ == "0.1.0"


def test_import_config() -> None:
    from pmod.config import Settings

    settings = Settings()
    assert settings.database_url.startswith("sqlite")


def test_import_submodules() -> None:
    import pmod.auth
    import pmod.broker
    import pmod.data
    import pmod.research
    import pmod.optimizer
    import pmod.preferences
    import pmod.scheduler
    import pmod.dashboard

    # If we get here without ImportError, the skeleton is wired correctly
    assert True


def test_dashboard_creates() -> None:
    from pmod.dashboard.app import create_app

    app = create_app()
    assert "PrintMoneyOrDie" in app.title
