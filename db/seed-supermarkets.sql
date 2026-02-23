--- These are the first 5 seeded supermarkets.
--- Additional supermarkets that have a developed scraper should be added here.

INSERT INTO supermarkets (name)
    ('coop')
    ('hemkop')
    ('ica')
    ('mathem')
    ('willys')
ON CONFLICT (name) DO NOTHING