"""Shared pytest fixtures."""

from datetime import datetime
import pytest

from pmod.data.models import ExternalAccount, get_session


@pytest.fixture
def test_external_account(request):
    """Create a test external account with test isolation."""
    # Use test name to make account names unique
    test_name = request.node.name
    acct_name = f"Test-{test_name}-{datetime.now().timestamp()}"

    with get_session() as session:
        acct = ExternalAccount(
            name=acct_name,
            account_type="401k",
            last_imported_at=datetime.now(),
        )
        session.add(acct)
        session.commit()
        acct_id = acct.id

    yield acct_id

    # Cleanup (delete all positions first, then account)
    with get_session() as session:
        from pmod.data.models import ExternalPosition
        session.query(ExternalPosition).filter_by(account_id=acct_id).delete()
        acct = session.query(ExternalAccount).filter_by(id=acct_id).first()
        if acct:
            session.delete(acct)
        session.commit()
