import os

from sqlalchemy import create_engine, Column, Integer, String, ForeignKey
from sqlalchemy.orm import backref, relationship, sessionmaker
from sqlalchemy.ext.declarative import declarative_base


engine = create_engine(f"sqlite:///{os.getcwd()}/data")
Base = declarative_base()


class Page(Base):
    __tablename__ = 'pages'
    id = Column(Integer, primary_key=True)
    url = Column(String, nullable=False, unique=True)
    recursion_depth = Column(Integer, default=1)
    from_page_id = Column(Integer, ForeignKey('pages.id'))
    links = relationship("Page", backref=backref(
        'from_page', remote_side=[id]
    ))

    def __repr__(self):
        return f"<Page(id={self.id}, url={self.url}," \
            f" recursion_depth={self.recursion_depth}, from_page_id = {self.from_page_id})>"


Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
db_session = Session()
