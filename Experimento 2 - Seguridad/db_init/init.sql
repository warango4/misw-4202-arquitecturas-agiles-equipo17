CREATE TABLE IF NOT EXISTS usuarios (
    id SERIAL PRIMARY KEY,
    client_id VARCHAR(100) UNIQUE NOT NULL,
    client_secret VARCHAR(255) NOT NULL,
    nombre VARCHAR(200)
);

CREATE TABLE IF NOT EXISTS permisos (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(100) UNIQUE NOT NULL,
    descripcion VARCHAR(255)
);

CREATE TABLE IF NOT EXISTS usuario_permisos (
    id SERIAL PRIMARY KEY,
    usuario_id INTEGER NOT NULL REFERENCES usuarios(id),
    permiso_id INTEGER NOT NULL REFERENCES permisos(id)
);

CREATE TABLE IF NOT EXISTS reservas (
    id SERIAL PRIMARY KEY,
    usuario_id INTEGER NOT NULL REFERENCES usuarios(id),
    checkin VARCHAR(20) NOT NULL,
    checkout VARCHAR(20) NOT NULL,
    destino VARCHAR(200) NOT NULL,
    valor_pagado VARCHAR(50) NOT NULL,
    fecha_registro TIMESTAMP DEFAULT NOW()
);

INSERT INTO usuarios (client_id, client_secret, nombre)
VALUES ('admin', 'admin', 'Administrador')
ON CONFLICT (client_id) DO NOTHING;

INSERT INTO usuarios (client_id, client_secret, nombre)
VALUES ('test', 'test', 'Test User')
ON CONFLICT (client_id) DO NOTHING;

INSERT INTO permisos (nombre, descripcion)
VALUES
    ('reserva', 'Acceso al endpoint /reserva'),
    ('historico', 'Acceso al endpoint /historico')
ON CONFLICT (nombre) DO NOTHING;

INSERT INTO usuario_permisos (usuario_id, permiso_id)
SELECT u.id, p.id
FROM usuarios u, permisos p
WHERE u.client_id = 'admin'
  AND p.nombre IN ('reserva', 'historico')
  AND NOT EXISTS (
      SELECT 1 FROM usuario_permisos up
      WHERE up.usuario_id = u.id AND up.permiso_id = p.id
  );

INSERT INTO usuario_permisos (usuario_id, permiso_id)
SELECT u.id, p.id
FROM usuarios u, permisos p
WHERE u.client_id = 'test'
  AND p.nombre IN ('reserva')
  AND NOT EXISTS (
      SELECT 1 FROM usuario_permisos up
      WHERE up.usuario_id = u.id AND up.permiso_id = p.id
  );

INSERT INTO reservas (usuario_id, checkin, checkout, destino, valor_pagado)
SELECT u.id, '2024-03-01', '2024-03-07', 'Cartagena', '1500000'
FROM usuarios u WHERE u.client_id = 'admin';

INSERT INTO reservas (usuario_id, checkin, checkout, destino, valor_pagado)
SELECT u.id, '2024-06-15', '2024-06-20', 'Medellín', '900000'
FROM usuarios u WHERE u.client_id = 'admin';