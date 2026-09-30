"""add client 360: contacts, sites, source tracking, duplicate dismissal (P2, 2026-09-30)

Revision ID: c1a4f7b92d63
Revises: a52ee7f4a768
Create Date: 2026-09-30 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c1a4f7b92d63'
down_revision: Union[str, None] = 'a52ee7f4a768'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'client_contacts',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('client_id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('designation', sa.String(length=200), nullable=True),
        sa.Column('phone', sa.String(length=20), nullable=True),
        sa.Column('email', sa.String(length=255), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_by_id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id'], ),
        sa.ForeignKeyConstraint(['created_by_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_client_contacts_client_id'), 'client_contacts', ['client_id'], unique=False)

    op.create_table(
        'client_sites',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('client_id', sa.UUID(), nullable=False),
        sa.Column('label', sa.String(length=200), nullable=False),
        sa.Column('city', sa.String(length=100), nullable=False),
        sa.Column('site_address', sa.String(length=500), nullable=True),
        sa.Column('site_state_code', sa.String(length=10), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_client_sites_client_id'), 'client_sites', ['client_id'], unique=False)

    op.create_table(
        'dismissed_duplicate_pairs',
        sa.Column('client_id_a', sa.UUID(), nullable=False),
        sa.Column('client_id_b', sa.UUID(), nullable=False),
        sa.Column('dismissed_by_id', sa.UUID(), nullable=False),
        sa.Column('dismissed_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['client_id_a'], ['clients.id'], ),
        sa.ForeignKeyConstraint(['client_id_b'], ['clients.id'], ),
        sa.ForeignKeyConstraint(['dismissed_by_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('client_id_a', 'client_id_b'),
        sa.CheckConstraint('client_id_a <> client_id_b', name='ck_dismissed_duplicate_pairs_not_self'),
        sa.CheckConstraint('client_id_a < client_id_b', name='ck_dismissed_duplicate_pairs_normalised_order'),
    )

    op.add_column('clients', sa.Column('source', sa.String(length=20), nullable=True))
    op.add_column('opportunities', sa.Column('source', sa.String(length=20), nullable=True))

    # projects.site_id references client_sites, which must exist first (above).
    op.add_column('projects', sa.Column('site_id', sa.UUID(), nullable=True))
    op.create_foreign_key(
        'fk_projects_site_id_client_sites', 'projects', 'client_sites', ['site_id'], ['id'],
    )


def downgrade() -> None:
    # P2 contract Section 8: rollback is refused, not silently applied, if there is any real data
    # to lose -- two independent checks, either one failing is enough to stop. "New tables empty"
    # must not be read as "safe to drop": a populated column on an existing table is real data
    # even when every new table has zero rows.
    bind = op.get_bind()

    table_counts = {
        table: bind.execute(sa.text(f"SELECT COUNT(*) FROM {table}")).scalar()
        for table in ('client_contacts', 'client_sites', 'dismissed_duplicate_pairs')
    }
    column_counts = {
        'clients.source': bind.execute(sa.text("SELECT COUNT(*) FROM clients WHERE source IS NOT NULL")).scalar(),
        'opportunities.source': bind.execute(sa.text("SELECT COUNT(*) FROM opportunities WHERE source IS NOT NULL")).scalar(),
        'projects.site_id': bind.execute(sa.text("SELECT COUNT(*) FROM projects WHERE site_id IS NOT NULL")).scalar(),
    }
    populated = {f"table:{k}" for k, v in table_counts.items() if v} | {f"column:{k}" for k, v in column_counts.items() if v}
    if populated:
        raise RuntimeError(
            "Refusing to roll back P2 (Client 360): real data would be lost. "
            f"Non-empty: {sorted(populated)}. Row/non-null counts: tables={table_counts}, columns={column_counts}. "
            "This migration does not drop data silently -- resolve or explicitly accept the loss before retrying."
        )

    op.drop_constraint('fk_projects_site_id_client_sites', 'projects', type_='foreignkey')
    op.drop_column('projects', 'site_id')
    op.drop_column('opportunities', 'source')
    op.drop_column('clients', 'source')
    op.drop_table('dismissed_duplicate_pairs')
    op.drop_index(op.f('ix_client_sites_client_id'), table_name='client_sites')
    op.drop_table('client_sites')
    op.drop_index(op.f('ix_client_contacts_client_id'), table_name='client_contacts')
    op.drop_table('client_contacts')
