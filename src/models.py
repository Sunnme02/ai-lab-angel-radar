"""SQLAlchemy 数据模型(对应规格第6节的 9 张表)。所有表带 created_at/updated_at。"""
import datetime as dt

from sqlalchemy import (Boolean, Column, DateTime, Float, ForeignKey, Integer,
                        String, Text, UniqueConstraint)
from sqlalchemy.orm import declarative_base

Base = declarative_base()


def _now():
    return dt.datetime.utcnow()


class TimestampMixin:
    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now, onupdate=_now)


class Lab(Base, TimestampMixin):
    __tablename__ = "labs"
    id = Column(Integer, primary_key=True)
    school = Column(String)
    lab_name = Column(String)
    pi_name = Column(String, index=True)
    pi_name_cn = Column(String)
    homepage_url = Column(String)
    keywords = Column(Text)          # 逗号分隔
    source_url = Column(String)
    __table_args__ = (UniqueConstraint("school", "pi_name", name="uq_lab_school_pi"),)


class Paper(Base, TimestampMixin):
    __tablename__ = "papers"
    id = Column(Integer, primary_key=True)
    title = Column(Text)
    norm_title = Column(String, index=True)   # 规范化标题做去重主键
    year = Column(Integer)
    venue = Column(String)
    abstract = Column(Text)
    url = Column(String)
    pdf_url = Column(String)
    source = Column(String)                   # openalex / s2 / dblp / openreview
    citation_count = Column(Integer, default=0)
    keywords_matched = Column(Text)
    lab_id = Column(Integer, ForeignKey("labs.id"), index=True)
    __table_args__ = (UniqueConstraint("norm_title", "lab_id", name="uq_paper_title_lab"),)


class Person(Base, TimestampMixin):
    __tablename__ = "people"
    id = Column(Integer, primary_key=True)
    name = Column(String, index=True)
    raw_name = Column(String)
    normalized_name = Column(String, index=True)
    name_cn = Column(String)
    role = Column(String, default="Unknown")  # PI/PhD/Master/Undergraduate/Researcher/Unknown
    affiliation = Column(String)
    homepage_url = Column(String)
    github_url = Column(String)
    google_scholar_url = Column(String)
    semantic_scholar_author_id = Column(String)
    openalex_author_id = Column(String, index=True)
    is_student_candidate = Column(Boolean, default=False)
    is_pi = Column(Boolean, default=False)


class Authorship(Base, TimestampMixin):
    __tablename__ = "authorships"
    id = Column(Integer, primary_key=True)
    paper_id = Column(Integer, ForeignKey("papers.id"), index=True)
    person_id = Column(Integer, ForeignKey("people.id"), index=True)
    author_order = Column(Integer)
    is_first_author = Column(Boolean, default=False)
    is_corresponding_author = Column(Boolean, default=False)
    affiliation_at_publication = Column(String)
    __table_args__ = (UniqueConstraint("paper_id", "person_id", name="uq_authorship"),)


class Repo(Base, TimestampMixin):
    __tablename__ = "repos"
    id = Column(Integer, primary_key=True)
    repo_name = Column(String)
    owner = Column(String)
    url = Column(String, unique=True)
    description = Column(Text)
    readme_text = Column(Text)
    stars = Column(Integer, default=0)
    forks = Column(Integer, default=0)
    watchers = Column(Integer, default=0)
    open_issues = Column(Integer, default=0)
    last_commit_at = Column(DateTime)
    created_at_github = Column(DateTime)
    topics = Column(Text)
    language = Column(String)
    matched_keywords = Column(Text)


class PersonRepoLink(Base, TimestampMixin):
    __tablename__ = "person_repo_links"
    id = Column(Integer, primary_key=True)
    person_id = Column(Integer, ForeignKey("people.id"), index=True)
    repo_id = Column(Integer, ForeignKey("repos.id"), index=True)
    link_type = Column(String)   # owner/contributor/mentioned_in_readme/homepage_link/fuzzy_match
    confidence = Column(Float, default=0.0)
    __table_args__ = (UniqueConstraint("person_id", "repo_id", name="uq_person_repo"),)


class Company(Base, TimestampMixin):
    __tablename__ = "companies"
    id = Column(Integer, primary_key=True)
    company_name = Column(String)
    company_name_cn = Column(String)
    website = Column(String)
    description = Column(Text)
    source_url = Column(String)


class Relationship(Base, TimestampMixin):
    __tablename__ = "relationships"
    id = Column(Integer, primary_key=True)
    source_type = Column(String)
    source_id = Column(Integer)
    target_type = Column(String)
    target_id = Column(Integer)
    relation_type = Column(String, index=True)
    confidence = Column(Float, default=1.0)
    evidence_text = Column(Text)
    evidence_url = Column(String)
    __table_args__ = (UniqueConstraint("source_type", "source_id", "target_type",
                                       "target_id", "relation_type", name="uq_rel"),)


class Score(Base, TimestampMixin):
    __tablename__ = "scores"
    id = Column(Integer, primary_key=True)
    entity_type = Column(String, index=True)   # lab/person/repo/paper
    entity_id = Column(Integer, index=True)
    score_name = Column(String)
    score_value = Column(Float)
    score_detail_json = Column(Text)
    __table_args__ = (UniqueConstraint("entity_type", "entity_id", "score_name",
                                       name="uq_score"),)
