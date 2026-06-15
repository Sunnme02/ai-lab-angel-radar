"""数据库:初始化 SQLite、建表、upsert(去重)、简单查询。"""
import json

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from .models import Base, Score
from .utils.logging import get_logger

log = get_logger()


class DB:
    def __init__(self, path: str):
        self.engine = create_engine(f"sqlite:///{path}", future=True)
        Base.metadata.create_all(self.engine)
        log.info(f"SQLite 就绪: {path}")

    def session(self) -> Session:
        return Session(self.engine, future=True)

    # ---- 通用 upsert：按唯一键查，存在则更新非空字段，否则插入 ----
    def upsert(self, sess, model, match: dict, values: dict):
        """match=唯一定位字段；values=要写入的字段。返回对象。"""
        stmt = select(model)
        for k, v in match.items():
            stmt = stmt.where(getattr(model, k) == v)
        obj = sess.execute(stmt).scalars().first()
        if obj:
            for k, v in values.items():
                if v is not None and v != "":
                    setattr(obj, k, v)
        else:
            obj = model(**{**match, **values})
            sess.add(obj)
        sess.flush()
        return obj

    def save_score(self, sess, entity_type, entity_id, score_name, value, detail: dict):
        self.upsert(sess, Score,
                    {"entity_type": entity_type, "entity_id": entity_id,
                     "score_name": score_name},
                    {"score_value": value,
                     "score_detail_json": json.dumps(detail, ensure_ascii=False)})
