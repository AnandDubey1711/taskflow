from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tasks",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "project_id",
            sa.Uuid(),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "todo",
                "in_progress",
                "done",
                name="task_status",
                native_enum=False,
                length=20,
            ),
            nullable=False,
        ),
        sa.Column(
            "assignee_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("due_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("creator_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "number", name="uq_tasks_project_id_number"),
    )
    op.create_index("ix_tasks_project_id_status", "tasks", ["project_id", "status"])
    op.create_index("ix_tasks_project_id_assignee_id", "tasks", ["project_id", "assignee_id"])
    op.create_index("ix_tasks_project_id_due_date", "tasks", ["project_id", "due_date"])


def downgrade() -> None:
    op.drop_index("ix_tasks_project_id_due_date", table_name="tasks")
    op.drop_index("ix_tasks_project_id_assignee_id", table_name="tasks")
    op.drop_index("ix_tasks_project_id_status", table_name="tasks")
    op.drop_table("tasks")
