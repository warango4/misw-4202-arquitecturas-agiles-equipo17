"""
Modelos SQLAlchemy para el servicio de reservas.
Refleja únicamente las tablas necesarias para persistir reservas.
"""
from sqlalchemy import Column, Integer, String, ForeignKey, TIMESTAMP, text
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True)
    client_id = Column(String(100), unique=True, nullable=False)
    client_secret = Column(String(255), nullable=False)
    nombre = Column(String(200))

    reservas = relationship("Reserva", back_populates="usuario")


class Reserva(Base):
    __tablename__ = "reservas"

    id = Column(Integer, primary_key=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    checkin = Column(String(20), nullable=False)
    checkout = Column(String(20), nullable=False)
    destino = Column(String(200), nullable=False)
    valor_pagado = Column(String(50), nullable=False)
    fecha_registro = Column(TIMESTAMP, server_default=text("NOW()"))

    usuario = relationship("Usuario", back_populates="reservas")
