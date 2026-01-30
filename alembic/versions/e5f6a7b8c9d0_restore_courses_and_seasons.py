"""restore courses and seasons

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2025-01-24

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text

revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    # 1. Create courses table
    if not inspect(conn).has_table("courses"):
        op.create_table(
            "courses",
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("code", sa.String(255), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
            sa.Column("created_by", sa.BigInteger(), nullable=False),
            sa.Column("updated_by", sa.BigInteger(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP")),
            sa.Column("deleted_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
            sa.ForeignKeyConstraint(["updated_by"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("code"),
        )
        op.create_index("ix_courses_id", "courses", ["id"])

        # Seed standard courses (only if empty)
        r = conn.execute(text("SELECT COUNT(*) FROM courses")).scalar()
        if r == 0:
            conn.execute(text("""
                INSERT INTO courses (name, code, description, is_active, created_by, updated_by)
                VALUES
                ('Accounting Technician Level I', 'AT-I', 'Foundation level covering fundamental accounting principles.', 1, 1, 1),
                ('Accounting Technician Level II', 'AT-II', 'Intermediate level focusing on financial reporting and cost accounting.', 1, 1, 1),
                ('Foundation Level (Knowledge and Skills Level)', 'CPA-FND', 'Introduction to professional accounting and business environment.', 1, 1, 1),
                ('Intermediate Level', 'CPA-INT', 'Covers financial management, auditing, and taxation principles.', 1, 1, 1),
                ('Final Level', 'CPA-FNL', 'Advanced professional competency in accounting, taxation, and business law.', 1, 1, 1)
            """))

    # 2. Add course_id to subjects (nullable)
    if inspect(conn).has_table("subjects"):
        cols = [c["name"] for c in inspect(conn).get_columns("subjects")]
        if "course_id" not in cols:
            op.add_column("subjects", sa.Column("course_id", sa.BigInteger(), nullable=True))
            op.create_foreign_key("fk_subjects_course_id", "subjects", "courses", ["course_id"], ["id"], ondelete="CASCADE")
            # Default existing subjects to CPA-FND (id=3)
            conn.execute(text("UPDATE subjects SET course_id = 3 WHERE course_id IS NULL"))

    # 3. Create seasons table
    if not inspect(conn).has_table("seasons"):
        op.create_table(
            "seasons",
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("code", sa.String(255), nullable=False),
            sa.Column("start_date", sa.Date(), nullable=False),
            sa.Column("end_date", sa.Date(), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
            sa.Column("created_by", sa.BigInteger(), nullable=False),
            sa.Column("updated_by", sa.BigInteger(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP")),
            sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
            sa.ForeignKeyConstraint(["updated_by"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("code"),
        )
        op.create_index("ix_seasons_id", "seasons", ["id"])

    # 4. Create season_subjects table
    if not inspect(conn).has_table("season_subjects"):
        op.create_table(
            "season_subjects",
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("season_id", sa.BigInteger(), nullable=False),
            sa.Column("subject_id", sa.BigInteger(), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
            sa.Column("created_by", sa.BigInteger(), nullable=False),
            sa.Column("updated_by", sa.BigInteger(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP")),
            sa.ForeignKeyConstraint(["season_id"], ["seasons.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["subject_id"], ["subjects.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
            sa.ForeignKeyConstraint(["updated_by"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("season_id", "subject_id", name="season_subject_unique"),
        )
        op.create_index("ix_season_subjects_id", "season_subjects", ["id"])


def downgrade() -> None:
    conn = op.get_bind()
    if inspect(conn).has_table("season_subjects"):
        op.drop_table("season_subjects")
    if inspect(conn).has_table("seasons"):
        op.drop_table("seasons")
    if inspect(conn).has_table("subjects"):
        cols = [c["name"] for c in inspect(conn).get_columns("subjects")]
        if "course_id" in cols:
            op.drop_constraint("fk_subjects_course_id", "subjects", type_="foreignkey")
            op.drop_column("subjects", "course_id")
    if inspect(conn).has_table("courses"):
        op.drop_table("courses")
