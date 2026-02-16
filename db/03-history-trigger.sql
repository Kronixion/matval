-- Migration: add trigger for historical price/availability tracking.
-- Run this on existing databases that were created before the trigger
-- was added to schema.sql.

CREATE OR REPLACE FUNCTION record_store_product_history()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO product_availability_history (
        store_product_id,
        availability_status_id,
        price,
        unit_price
    ) VALUES (
        OLD.store_product_id,
        OLD.availability_status_id,
        OLD.price,
        OLD.unit_price
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_store_product_history
    AFTER UPDATE ON store_products
    FOR EACH ROW
    WHEN (
        OLD.price IS DISTINCT FROM NEW.price
        OR OLD.unit_price IS DISTINCT FROM NEW.unit_price
        OR OLD.availability_status_id IS DISTINCT FROM NEW.availability_status_id
    )
    EXECUTE FUNCTION record_store_product_history();
