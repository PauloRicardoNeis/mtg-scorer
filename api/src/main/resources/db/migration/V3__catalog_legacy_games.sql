-- Preserve the legacy digital game availability present in default-cards.
ALTER TABLE catalog.catalog_printing DROP CONSTRAINT catalog_printing_games_check;
ALTER TABLE catalog.catalog_printing ADD CONSTRAINT catalog_printing_games_check
 CHECK (games <@ ARRAY['paper','arena','mtgo','astral','sega']);
