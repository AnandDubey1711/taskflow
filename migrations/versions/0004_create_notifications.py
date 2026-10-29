from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OVERDUE_CANDIDATE_CONDITION = "status <> 'done' AND overdue_notified_at IS NULL"


def upgrade() -> None:
    op.add_column("tasks", sa.Column("overdue_notified_at", sa.DateTime(timezone=True)))
    op.create_index(
        "ix_tasks_overdue_candidates",
        "tasks",
        ["due_date"],
        postgresql_where=sa.text(OVERDUE_CANDIDATE_CONDITION),
        sqlite_where=sa.text(OVERDUE_CANDIDATE_CONDITION),
    )
    op.create_table(
        "notifications",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "task_id",
            sa.Uuid(),
            sa.ForeignKey("tasks.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column(
            "type",
            sa.Enum(
                "task_assigned",
                "task_reassigned",
                "task_unassigned",
                "task_status_changed",
                "task_overdue",
                name="notification_type",
                native_enum=False,
                length=30,
            ),
            nullable=False,
        ),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("event_id", "user_id", name="uq_notifications_event_id_user_id"),
    )
    op.create_index(
        "ix_notifications_user_id_created_at", "notifications", ["user_id", "created_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_notifications_user_id_created_at", table_name="notifications")
    op.drop_table("notifications")
    op.drop_index("ix_tasks_overdue_candidates", table_name="tasks")
    op.drop_column("tasks", "overdue_notified_at")
