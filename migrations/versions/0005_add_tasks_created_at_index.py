from collections.abc import Sequence

from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index("ix_tasks_project_id_created_at", "tasks", ["project_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_tasks_project_id_created_at", table_name="tasks")
