"""轻量 schema 自愈：给已存在的表补上新增的列，避免线上旧库升级后报错。

仅处理「新增可空列」这一种情况，不做删列、改类型等危险操作。
"""

from sqlalchemy import inspect, text


def ensure_columns(app, db, log=print):
    with app.app_context():
        insp = inspect(db.engine)
        for table in db.metadata.sorted_tables:
            try:
                if not insp.has_table(table.name):
                    continue
            except Exception:
                continue
            existing = {c["name"] for c in insp.get_columns(table.name)}
            for col in table.columns:
                if col.name in existing:
                    continue
                try:
                    coltype = col.type.compile(db.engine.dialect)
                    db.session.execute(
                        text(f'ALTER TABLE {table.name} ADD COLUMN {col.name} {coltype}')
                    )
                    db.session.commit()
                    log(f"[schema] {table.name} 新增列 {col.name}")
                except Exception as exc:  # 列已存在或数据库不支持，跳过即可
                    db.session.rollback()
                    log(f"[schema] 跳过 {table.name}.{col.name}: {exc}")
