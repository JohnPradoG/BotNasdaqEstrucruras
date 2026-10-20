-- 002: duración de la salida a 2 R (necesaria para simular una sola posición a la vez)
ALTER TABLE outcomes ADD COLUMN dur_2r_min INTEGER;
