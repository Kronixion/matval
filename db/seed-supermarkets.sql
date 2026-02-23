--- Supermarket seeder script. (Maybe I should take them from a json and have a python script that does that)
--- Additional supermarkets that have a developed scraper should be added here.

INSERT INTO supermarkets (name)
    ('coop')
    ('hemkop')
    ('ica')
    ('mathem')
    ('willys')
ON CONFLICT (name) DO NOTHING