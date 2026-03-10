from sqlalchemy import create_engine, Column, String, Integer, ForeignKey, DateTime, Text
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from datetime import datetime

Base = declarative_base()


class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, autoincrement=True)
    client_id = Column(String(100), unique=True, nullable=False)
    client_secret = Column(String(255), nullable=False)
    nombre = Column(String(200), nullable=True)

    permisos = relationship("UsuarioPermiso", back_populates="usuario")
    reservas = relationship("Reserva", back_populates="usuario")


class Permiso(Base):
    __tablename__ = "permisos"

    id = Column(Integer, primary_key=True, autoincrement=True)
    nombre = Column(String(100), unique=True, nullable=False)
    descripcion = Column(String(255), nullable=True)

    usuarios = relationship("UsuarioPermiso", back_populates="permiso")


class UsuarioPermiso(Base):
    __tablename__ = "usuario_permisos"

    id = Column(Integer, primary_key=True, autoincrement=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    permiso_id = Column(Integer, ForeignKey("permisos.id"), nullable=False)

    usuario = relationship("Usuario", back_populates="permisos")
    permiso = relationship("Permiso", back_populates="usuarios")


class Reserva(Base):
    __tablename__ = "reservas"

    id = Column(Integer, primary_key=True, autoincrement=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    checkin = Column(String(20), nullable=False)
    checkout = Column(String(20), nullable=False)
    destino = Column(String(200), nullable=False)
    valor_pagado = Column(String(50), nullable=False)
    fecha_registro = Column(DateTime, default=datetime.utcnow)

    usuario = relationship("Usuario", back_populates="reservas")


def get_engine(database_url):
    return create_engine(database_url)


def get_session_factory(engine):
    return sessionmaker(bind=engine)


def init_db(engine):
    Base.metadata.create_all(engine)