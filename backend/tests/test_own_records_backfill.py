"""Amendment 60 (Section 63): which existing records get an owner from the migration -- and which do not.

The migration only assigns an owner where the data itself says who a record belongs to (the enquiry trail); it
guesses nothing. This runs the migration's own backfill function on synthetic records shaped like old data."""

import importlib.util
import uuid
from datetime import date, timedelta
from pathlib import Path

from app.core.security import hash_password
from app.models.client import Client, ClientType
from app.models.opportunity import Opportunity, OpportunityStage
from app.models.project import Project
from app.models.user import User, UserRole
from tests.test_quotations_admin import _create_client_record, _create_project

MIGRATION = Path(__file__).resolve().parents[1] / "alembic" / "versions" / "a3f9c27d5e14_add_record_owners.py"


def _backfill(db_session):
    spec = importlib.util.spec_from_file_location("owners_migration", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.backfill(db_session.connection())
    db_session.commit()
    db_session.expire_all()


def _sales(db_session, email):
    user = User(name=email.split("@")[0], email=email, hashed_password=hash_password("TestPass!1"), role=UserRole.SALES)
    db_session.add(user)
    db_session.commit()
    return user


def test_records_get_an_owner_only_where_the_enquiry_trail_says_who(client, director_user, db_session):
    from tests.test_attachments import _director_headers

    headers = _director_headers(client, director_user)
    ravi, sona = _sales(db_session, "ravi@bf.test"), _sales(db_session, "sona@bf.test")

    # a client won through Ravi's enquiry, and its project started from that enquiry
    won_client = Client(name="Won School", type=ClientType.SCHOOL)
    db_session.add(won_client)
    db_session.flush()
    enquiry = Opportunity(
        lead_name="Won lead", client_id=won_client.id, stage=OpportunityStage.WON, next_follow_up_date=None,
        created_by_id=ravi.id, owner_id=None,
    )
    db_session.add(enquiry)
    db_session.commit()
    project_id = _create_project(client, headers, str(won_client.id))
    project = db_session.get(Project, uuid.UUID(project_id))
    project.opportunity_id = enquiry.id

    # a second client with two enquiries: the EARLIER one's owner wins
    two = Client(name="Two Enquiries School", type=ClientType.SCHOOL)
    db_session.add(two)
    db_session.flush()
    later = Opportunity(lead_name="later", client_id=two.id, stage=OpportunityStage.NEW, next_follow_up_date=date.today() + timedelta(days=1), created_by_id=sona.id)
    db_session.add(later)
    db_session.commit()
    earlier = Opportunity(lead_name="earlier", client_id=two.id, stage=OpportunityStage.NEW, next_follow_up_date=date.today() + timedelta(days=1), created_by_id=ravi.id)
    earlier.created_at = later.created_at - timedelta(days=5)
    db_session.add(earlier)
    db_session.commit()

    # a client and a project with no enquiry trail at all: nobody can say whose they are
    lone_client_id = _create_client_record(client, headers, "Lone School")
    lone_project_id = _create_project(client, headers, lone_client_id)
    for row in db_session.query(Client).all():
        row.owner_id = None
    for row in db_session.query(Project).all():
        row.owner_id = None
    for row in db_session.query(Opportunity).all():
        row.owner_id = None
    db_session.commit()

    _backfill(db_session)

    assert db_session.get(Opportunity, enquiry.id).owner_id == ravi.id  # an enquiry belongs to whoever created it
    assert db_session.get(Client, won_client.id).owner_id == ravi.id
    assert db_session.get(Project, project.id).owner_id == ravi.id  # the enquiry that started it
    assert db_session.get(Client, two.id).owner_id == ravi.id  # the earliest enquiry's owner, not the later one's
    # nothing guessed: no trail -> unassigned
    lone_client = db_session.query(Client).filter(Client.name == "Lone School").one()
    assert lone_client.owner_id is None
    assert str(db_session.query(Project).filter(Project.client_id == lone_client.id).one().owner_id) == "None"


def test_running_the_backfill_again_changes_nothing(client, director_user, db_session):
    ravi = _sales(db_session, "ravi2@bf.test")
    enquiry = Opportunity(lead_name="x", stage=OpportunityStage.NEW, next_follow_up_date=date.today() + timedelta(days=1), created_by_id=ravi.id)
    db_session.add(enquiry)
    db_session.commit()
    _backfill(db_session)
    first = db_session.get(Opportunity, enquiry.id).owner_id
    enquiry.owner_id = None
    db_session.commit()
    sona = _sales(db_session, "sona2@bf.test")
    db_session.get(Opportunity, enquiry.id).owner_id = sona.id  # reassigned by a person since
    db_session.commit()
    _backfill(db_session)
    assert first == ravi.id and db_session.get(Opportunity, enquiry.id).owner_id == sona.id  # never overwritten
