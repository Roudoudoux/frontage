import datetime

# from server.extensions import db
from uuid import uuid4
from db.base import Base
from sqlalchemy import Column, Integer, String, DateTime, Boolean
from sqlalchemy.dialects import postgresql

def cln_str(s):
    if s:
        return s.replace(
            "'",
            "").replace(
            '\\',
            '').replace(
            '%',
            '').replace(
                ';',
            '')
    return ''

class MeshConfiguration(Base):
    __tablename__ = 'meshconfiguration'

    uniqid = Column(String(36), primary_key=True)
    rows = Column(Integer)
    cols = Column(Integer)

    def __init__(self):
        self.uniqid = str(uuid4())
        self.rows = 4
        self.cols = 19

    def __repr__(self):
        return '<meshconfiguration %r (%r) (%r)>' % (
            self.uniqid, self.rows, self.cols)

    def getRows(self):
        return self.rows
        
    def getCols(self):
        return self.cols

    def setRows(self, newRows):
        self.rows = newRows

    def setCols(self, newCols):
        self.cols = newCols

class Cell():
    def __init__(self, x, y, macAddress):
        self.x = x
        self.y = y
        self.macAddress = macAddress

class CellTable(Base):
    __tablename__ = 'celltable'

    uniqid = Column(String(36), primary_key=True)
    #table = Column(postgresql.ARRAY(Cell, dimensions=1), nullable=True)

    def __init__(self):
        self.uniqid = str(uuid4())
        self.table = []

    def __repr__(self):
        return '<celtable %r (%r)>' % (
            self.uniqid, len(self.table))

    #def addTailTable(self, cell):
    #    table.append(cell)

    #def removeTailTable(self):
    #    table.pop()

class FappModel(Base):
    __tablename__ = 'fapp'

    uniqid = Column(String(36), primary_key=True)
    name = Column(String(36), unique=True)
    is_scheduled = Column(Boolean)
    default_params = Column(String(4096))
    position = Column(Integer)

    def __init__(self, app_name, is_scheduled=False):
        self.uniqid = str(uuid4())
        self.position = 0
        self.name = app_name
        self.is_scheduled = is_scheduled
        self.default_params = '{}'

    def __repr__(self):
        return '<Fapp %r (%r) (%r) (%r)>' % (
            self.uniqid, self.is_scheduled, self.position, self.default_params)


class ConfigModel(Base):
    __tablename__ = 'configmodel'

    uniqid = Column(String(36), primary_key=True)

    forced_sunrise = Column(String(36))
    offset_sunrise = Column(Integer)

    forced_sunset = Column(String(36))
    offset_sunset = Column(Integer)
    state = Column(String(36))
    expires_delay = Column(Integer)
    default_app_lifetime = Column(Integer)

    admin_login = Column(String(36))
    admin_hash = Column(String(512))

    def __init__(self):
        self.uniqid = str(uuid4())
        self.forced_sunset = ""
        self.offset_sunset = 0
        self.state = 'scheduled'

        self.forced_sunrise = ""
        self.offset_sunrise = 0
        self.default_app_lifetime = 15 * 60

        self.expires_delay = 90

    def __repr__(self):
        return '<ConfigModel %r (%r) (%r)>' % (
            self.uniqid, self.expires_delay, self.forced_sunset)
