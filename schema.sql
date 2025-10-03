-- Esquema para dominio de aviones

-- Tipo enum para el estado de los aviones
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'estado_avion_enum') THEN
        CREATE TYPE estado_avion_enum AS ENUM ('disponible', 'mantenimiento', 'fuera_de_servicio');
    END IF;
END $$;

-- Tabla principal de aviones
CREATE TABLE IF NOT EXISTS public.aviones (
    id serial4 PRIMARY KEY,
    modelo varchar(255) NOT NULL,
    capacidad int4 NOT NULL CHECK (capacidad > 0),
    aerolinea varchar(255) NOT NULL,
    estado estado_avion_enum NOT NULL DEFAULT 'disponible',
    fecha_fabricacion timestamptz NULL
);

-- Índices útiles
CREATE INDEX IF NOT EXISTS idx_aviones_estado ON public.aviones USING btree (estado);
CREATE INDEX IF NOT EXISTS idx_aviones_aerolinea ON public.aviones USING btree (aerolinea);
CREATE INDEX IF NOT EXISTS idx_aviones_fecha_fabricacion ON public.aviones USING btree (fecha_fabricacion);